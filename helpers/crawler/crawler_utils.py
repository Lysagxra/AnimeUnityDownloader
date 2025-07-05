"""Crawler module of the project.

Module that provides functions to retrieve, extract, and process anime episode video
URLs from a web page.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import sys
import time
from asyncio import Semaphore
from urllib.parse import urlparse

import httpx
import cloudscraper

from helpers.config import prepare_headers

HEADERS = prepare_headers()


def validate_url(url: str) -> str:
    """Validate a URL by ensuring it does not have a trailing slash."""
    if url.endswith("/"):
        return url.rstrip("/")
    return url


def extract_host_domain(url: str) -> str:
    """Extract the host/domain name from a given URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc


def validate_episode_range(
    start_episode: int | None,
    end_episode: int | None,
    num_episodes: int,
) -> tuple:
    """Validate the episode range to ensure it is within acceptable bounds."""

    def log_and_exit(message: str) -> None:
        logging.error(message)
        sys.exit(1)

    if start_episode:
        if start_episode < 1 or start_episode > num_episodes:
            log_and_exit(f"Start episode must be between 1 and {num_episodes}.")

    if start_episode and end_episode:
        if start_episode > end_episode:
            log_and_exit("Start episode cannot be greater than end episode.")
        if end_episode > num_episodes:
            log_and_exit(f"End episode must be between 1 and {num_episodes}.")

    return start_episode, end_episode


async def fetch_with_cloudscraper(url: str, headers: dict = None, params: dict = None, timeout: int = 15) -> dict | None:
    """Fetch data using cloudscraper as a fallback for Cloudflare protection."""
    try:
        # Create a cloudscraper session
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'darwin',  # macOS
                'desktop': True
            }
        )
        
        # Disable SSL verification
        scraper.verify = False
        
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Use provided headers or get new ones
        if headers is None:
            from helpers.config import prepare_headers
            headers = prepare_headers()
            headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'max-age=0',
            })
        
        # Make the request (cloudscraper is synchronous, so we need to handle this)
        response = scraper.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        
        logging.info(f"Successfully fetched {url} using cloudscraper")
        
        # Create a mock response object similar to httpx response
        class MockResponse:
            def __init__(self, response):
                self.status_code = response.status_code
                self.text = response.text
                self.content = response.content
                self.headers = response.headers
                self._response = response
                
            def json(self):
                return self._response.json()
                
            def raise_for_status(self):
                self._response.raise_for_status()
        
        return MockResponse(response)
        
    except Exception as e:
        logging.error(f"Cloudscraper failed for {url}: {e}")
        # Check if it's a geo-blocking related error and show popup
        if "403" in str(e) or "SSL" in str(e) or "certificate" in str(e).lower() or "Cannot set verify_mode" in str(e):
            # Import the popup function
            try:
                from helpers.general_utils import show_vpn_popup
                show_vpn_popup()
            except ImportError:
                print("\n⚠️  Connect from Italy with a VPN to access AnimeUnity")
        return None


async def fetch_with_retries(
    url: str,
    semaphore: Semaphore,
    headers: dict | None = None,
    params: dict | None = None,
    retries: int = 4,
) -> dict | None:
    """Fetch data from a URL with retries on failure."""
    async with semaphore:
        # Use better headers if none provided
        if headers is None:
            headers = prepare_headers()
            headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'max-age=0',
            })
        
        # First try with httpx
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True, verify=False) as client:
            for attempt in range(retries):
                try:
                    # Add random delay to avoid bot detection
                    if attempt > 0:  # Don't delay on first attempt
                        delay = 0.5 + random.uniform(0, 1.5)
                        await asyncio.sleep(delay)
                    
                    response = await client.get(
                        url,
                        params=params,
                    )
                    response.raise_for_status()
                    return response

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        logging.warning(f"403 error with httpx for {url} - attempt {attempt + 1}")
                        if attempt < retries - 1:
                            delay = 2 ** attempt + random.uniform(1, 3)  # Longer delay for 403
                            await asyncio.sleep(delay)
                        else:
                            # All httpx attempts failed with 403, try cloudscraper
                            logging.warning(f"All httpx attempts failed for {url}, trying cloudscraper")
                            return await fetch_with_cloudscraper(url, headers, params)
                    else:
                        if attempt < retries - 1:
                            delay = 2 ** attempt + random.uniform(0, 2)
                            await asyncio.sleep(delay)

                except httpx.RequestError as req_err:
                    logging.warning(f"Request error for {url}: {req_err}")
                    if attempt < retries - 1:
                        delay = 2 ** attempt + random.uniform(0, 2)
                        await asyncio.sleep(delay)
                    else:
                        # Try cloudscraper as last resort
                        logging.warning(f"All httpx attempts failed for {url}, trying cloudscraper")
                        return await fetch_with_cloudscraper(url, headers, params)

        return None


def extract_download_link(script_items: list, video_url: str) -> str | None:
    """Extract the download URL from a list of script items."""
    pattern = r"window\.downloadUrl\s*=\s*'(https?:\/\/[^\s']+)'"

    for item in script_items:
        match = re.search(pattern, item.text)
        if match:
            return match.group(1)

    # Return None if no download link is found
    message = f"Error extracting the download link for {video_url}"
    logging.error(message)
    return None
