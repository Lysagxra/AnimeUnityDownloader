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
from asyncio import Semaphore
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import requests

from helpers.config import (
    BASE_HEADERS,
    DOWNLOAD_LINK_PATTERN,
    HTTP_STATUS_FORBIDDEN,
    prepare_headers,
)
from helpers.general_utils import prepare_cloudscraper_session

if TYPE_CHECKING:
    from bs4 import Tag
    from requests import Response


class MockResponse:
    """Wrapper around a `requests.Response` object that mimics its interface."""

    def __init__(self, response: Response) -> None:
        """Initialize a MockResponse with the given `requests.Response` object."""
        self.status_code = response.status_code
        self.text = response.text
        self.content = response.content
        self.headers = response.headers
        self._response = response

    def json(self) -> dict:
        """Return the JSON-decoded content of the response."""
        return self._response.json()

    def raise_for_status(self) -> None:
        """Raise an HTTPError if the HTTP request returned an unsuccessful status."""
        self._response.raise_for_status()


def validate_url(url: str) -> str:
    """Validate a URL by ensuring it does not have a trailing slash."""
    if url.endswith("/"):
        return url.rstrip("/")
    return url


def extract_host_domain(url: str) -> str:
    """Extract the host/domain name from a given URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc


def extract_name_from_title_tag(title_tag: Tag) -> str:
    """Extract the anime name from the title tag."""
    title_text = title_tag.string

    # Extract anime name from AnimeUnity title format
    if "AnimeUnity ~" in title_text:
        return title_text.split("AnimeUnity ~")[1].split("Streaming")[0].strip()

    # Fallback: Just use the title with cleanup
    return title_text.replace("AnimeUnity", "").replace("~", "").strip()


def validate_episode_range(
    start_episode: int | None,
    end_episode: int | None,
    num_episodes: int,
) -> None:
    """Validate the episode range to ensure it is within acceptable bounds."""

    def log_and_exit(message: str) -> None:
        logging.error(message)
        sys.exit(1)

    if start_episode and (start_episode < 1 or start_episode > num_episodes):
        log_and_exit(f"Start episode must be between 1 and {num_episodes}.")

    if start_episode and end_episode:
        if start_episode > end_episode:
            log_and_exit("Start episode cannot be greater than end episode.")

        if end_episode > num_episodes:
            log_and_exit(f"End episode must be between 1 and {num_episodes}.")


def episode_in_range(num: str, start: int | None, end: int | None) -> bool:
    """Check if episode number is within the specified range.

    The range is intended to be inclusive. If the episode number cannot be compared as
    a float, it is included by default. This assumes that the range is primarily used to
    exclude episodes, so the fallback behavior is to include everything unless
    explicitly excluded.
    """
    try:
        n = float(num)

    except ValueError:
        return True

    return (n >= start if start is not None else True) and (
        n <= end if end is not None else True
    )


async def fetch_with_cloudscraper(
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 15,
) -> dict | None:
    """Fetch data using cloudscraper as a fallback for Cloudflare protection."""
    scraper = prepare_cloudscraper_session()

    # Use provided headers or get new ones
    if headers is None:
        headers = prepare_headers()
        headers.update(BASE_HEADERS)

    try:
        # Make the request (cloudscraper is synchronous, so we need to handle this)
        response = scraper.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()

    except requests.exceptions.RequestException as req_err:
        log_message = f"Cloudscraper request to {url} failed: {req_err}"
        logging.exception(log_message)
        return None

    # Return a mock response object similar to httpx response
    return MockResponse(response)


async def fetch_with_retries(
    url: str,
    semaphore: Semaphore,
    headers: dict | None = None,
    params: dict | None = None,
    retries: int = 4,
) -> dict | None:
    """Fetch data from a URL with retries on failure."""

    async def retry_or_fallback(
        attempt: int,
        min_delay: float = 0.0,
        max_delay: float = 2.0,
    ) -> dict | None:
        if attempt < retries - 1:
            delay = 2 ** attempt + random.uniform(min_delay, max_delay)  # noqa: S311
            await asyncio.sleep(delay)

        return await fetch_with_cloudscraper(url, headers, params)

    # Use better headers if none provided
    if headers is None:
        headers = prepare_headers()
        headers.update(BASE_HEADERS)

    # First try with httpx
    async with semaphore, httpx.AsyncClient(
        headers=headers,
        timeout=15,
        follow_redirects=True,
        verify=False,  # noqa: S501
    ) as client:
        for attempt in range(retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

            except httpx.HTTPStatusError as https_err:
                if https_err.response.status_code == HTTP_STATUS_FORBIDDEN:
                    await retry_or_fallback(attempt, min_delay=1.0, max_delay=3.0)

                elif attempt < retries - 1:
                    delay = 2 ** attempt + random.uniform(0, 2)  # noqa: S311
                    await asyncio.sleep(delay)

            except httpx.RequestError:
                await retry_or_fallback(attempt)

            return response

    return None


def extract_download_link(script_items: list, video_url: str) -> str | None:
    """Extract the download URL from a list of script items."""
    for item in script_items:
        match = re.search(DOWNLOAD_LINK_PATTERN, item.text)
        if match:
            return match.group(1)

    # Return None if no download link is found
    message = f"Error extracting the download link for {video_url}"
    logging.error(message)
    return None
