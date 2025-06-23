"""Utilities for fetching web pages, managing directories, and clearing the terminal.

This module includes functions to handle common tasks such as sending HTTP requests,
parsing HTML, creating download directories, and  clearing the terminal, making it
reusable across projects.
"""

import logging
import os
import re
import sys
from pathlib import Path

import httpx
import requests
from bs4 import BeautifulSoup

from .config import DOWNLOAD_FOLDER


def fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage."""
    # Create a new session per worker
    session = requests.Session()

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    except requests.RequestException as req_err:
        message = f"Error fetching page {url}: {req_err}"
        logging.exception(message)
        sys.exit(1)


def fetch_page_httpx(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage using HTTPX."""
    response = httpx.get(url=url, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


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
        "nt": "cls",       # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        os.system(command)  # noqa: S605
