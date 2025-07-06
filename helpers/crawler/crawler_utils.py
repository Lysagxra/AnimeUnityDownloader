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
from urllib.parse import urlparse

import httpx

from helpers.config import DOWNLOAD_LINK_PATTERN, prepare_headers

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


async def fetch_with_retries(
    url: str,
    semaphore: Semaphore,
    headers: dict | None = None,
    params: dict | None = None,
    retries: int = 4,
) -> dict | None:
    """Fetch data from a URL with retries on failure."""
    async with semaphore, httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()

            except httpx.HTTPStatusError:
                if attempt < retries - 1:
                    delay = 2**attempt + random.uniform(1, 2)  # noqa: S311
                    await asyncio.sleep(delay)

            except httpx.RequestError as req_err:
                message = f"Request failed for {url}: {req_err}"
                logging.exception(message)
                return None

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
