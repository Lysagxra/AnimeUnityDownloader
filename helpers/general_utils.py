"""Utilities for fetching web pages, managing directories, and clearing the terminal.

This module includes functions to handle common tasks such as sending HTTP requests,
parsing HTML, creating download directories, and  clearing the terminal, making it
reusable across projects.
"""

import gzip
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import brotli
import cloudscraper
import httpx
import requests
import urllib3
from brotli import error as BrotliError  # noqa: N812
from bs4 import BeautifulSoup
from cloudscraper import CloudScraper

from .config import (
    DEFAULT_HEADERS,
    DOWNLOAD_FOLDER,
    ENCODING_HEADERS,
    HTTP_STATUS_FORBIDDEN,
    MIN_CONTENT_LENGTH,
    prepare_headers,
)

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def add_random_delay(min_delay: float = 0.5, max_delay: float = 2.0) -> None:
    """Add a random delay to avoid being detected as a bot."""
    delay = random.uniform(min_delay, max_delay)  # noqa: S311
    time.sleep(delay)


def prepare_cloudscraper_session() -> CloudScraper:
    """Create a cloudscraper session to mimic a Firefox browser on macOS."""
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "firefox",
            "platform": "darwin",  # macOS
            "desktop": True,
        },
    )

    # Disable SSL verification
    scraper.verify = False
    return scraper


def fetch_page_cloudflare(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch HTML content from a Cloudflare-protected webpage using cloudscraper."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Create a cloudscraper session with SSL verification disabled
    scraper = prepare_cloudscraper_session()

    # Get headers and update them
    headers = prepare_headers()
    headers.update(ENCODING_HEADERS)

    try:
        # Make the request using cloudscraper
        response = scraper.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

    except requests.RequestException as req_err:
        if (
            hasattr(req_err, "response")
            and req_err.response is not None
            and req_err.response.status_code == HTTP_STATUS_FORBIDDEN
        ):
            logging.exception("Cloudflare protection still blocking access")

        else:
            log_message = f"Request failed: {req_err}"
            logging.exception(log_message)

        # Re-raise the exception so calling code can handle it
        raise

    # Parse and return the HTML
    return BeautifulSoup(response.text, "html.parser")


def decompress_response(response: requests.Response) -> str:
    """Decompress the content of an HTTP response.

    Fall back to response.text if decompression fails.
    """
    encoding = response.headers.get("content-encoding", "").lower()

    try:
        if "br" in encoding:
            return brotli.decompress(response.content).decode("utf-8")

        if "gzip" in encoding:
            return gzip.decompress(response.content).decode("utf-8")

    except (BrotliError, OSError, UnicodeDecodeError) as decompress_err:
        log_message = (
            f"Decompression failed: {decompress_err}... using original response text"
        )
        logging.exception(log_message)

    return response.text


def fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Create a new session per worker
    session = requests.Session()
    session.verify = False

    # Add additional headers to look more like a real browser
    headers = prepare_headers()
    headers.update(DEFAULT_HEADERS)

    try:
        # First attempt: normal request
        response = session.get(url, headers=headers, timeout=timeout, stream=False)
        response.raise_for_status()

        # Handle text content
        text_content = response.text

        # If we get binary/compressed content that wasn't auto-decompressed, try manual
        # decompression
        if len(text_content) < MIN_CONTENT_LENGTH or not any(
            tag in text_content.lower() for tag in ["<html", "<head", "<title"]
        ):
            text_content = decompress_response(response)

        return BeautifulSoup(text_content, "html.parser")

    except requests.RequestException as req_err:
        if (
            hasattr(req_err, "response")
            and req_err.response is not None
            and req_err.response.status_code == HTTP_STATUS_FORBIDDEN
        ):
            # Fallback to cloudscraper for Cloudflare protection
            try:
                return fetch_page_cloudflare(url, timeout)

            except requests.exceptions.RequestException as cf_err:
                log_message = f"Cloudscraper fallback failed for {url}: {cf_err}"
                logging.exception(log_message)
                sys.exit(1)

        message = f"Error fetching page {url}: {req_err}"
        logging.warning(message)
        sys.exit(1)


def fetch_page_httpx(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content using HTTPX with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Add additional headers to look more like a real browser
    headers = prepare_headers()
    headers.update(ENCODING_HEADERS)

    try:
        # First try with regular httpx
        with httpx.Client(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            verify=False,  # noqa: S501
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            # Get the properly decoded text content
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Try different parsing
            if not soup.find("html") and not soup.find("head"):
                logging.warning("Response doesn't appear to be valid HTML")
                soup = BeautifulSoup(html_content, "lxml")

            return soup

    except httpx.HTTPStatusError as https_err:
        if https_err.response.status_code == HTTP_STATUS_FORBIDDEN:
            # Fallback to cloudscraper for Cloudflare protection
            return fetch_page_cloudflare(url, timeout)

        raise


def sanitize_directory_name(directory_name: str) -> str:
    """Sanitize a given directory name.

    Replace invalid characters with underscores. Handles the invalid characters specific
    to Windows, macOS, and Linux.
    """
    invalid_chars_dict = {
        "nt": r'[\\/:*?"<>|]',  # Windows
        "posix": r"[/:]",  # macOS and Linux
    }
    invalid_chars = invalid_chars_dict.get(os.name)
    return re.sub(invalid_chars, "_", directory_name)


def create_download_directory(directory_name: str) -> str:
    """Create a directory for downloads if it doesn't exist."""
    download_path = Path(DOWNLOAD_FOLDER) / sanitize_directory_name(directory_name)

    try:
        Path(download_path).mkdir(parents=True, exist_ok=True)

    except OSError as os_err:
        message = f"Error creating directory: {os_err}"
        logging.exception(message)
        sys.exit(1)

    return download_path


def clear_terminal() -> None:
    """Clear the terminal screen based on the operating system."""
    commands = {
        "nt": "cls",  # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        os.system(command)  # noqa: S605
