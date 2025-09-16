"""Utility functions for file input and output operations.

This module includes methods to read the contents of a file and to write content to a
file, with optional support for clearing the file.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

from .config import DOWNLOAD_FOLDER


def read_file(filename: str) -> list[str]:
    """Read the contents of a file and returns a list of its lines."""
    with Path(filename).open("r", encoding="utf-8") as file:
        return file.read().splitlines()


def write_file(filename: str, content: str = "") -> None:
    """Write content to a specified file.

    If content is not provided, the file is cleared.
    """
    with Path(filename).open("w", encoding="utf-8") as file:
        file.write(content)

def sanitize_directory_name(directory_name: str) -> str:
    """Sanitize a given directory name.

    Replace invalid characters with underscores. Handles the invalid characters specific
    to Windows, macOS, and Linux.
    """
    invalid_chars_dict = {
        "nt": r'[\\/:*?"<>|]',  # Windows
        "posix": r"[/:]",       # macOS and Linux
    }
    invalid_chars = invalid_chars_dict.get(os.name)
    return re.sub(invalid_chars, "_", directory_name)


def create_download_directory(
    directory_name: str, custom_path: str | None = None,
) -> str:
    """Create a directory for downloads if it doesn't exist."""
    sanitized_directory_name = sanitize_directory_name(directory_name)
    download_path = (
        Path(custom_path) / DOWNLOAD_FOLDER / sanitized_directory_name
        if custom_path is not None
        else Path(DOWNLOAD_FOLDER) / sanitized_directory_name
    )

    try:
        Path(download_path).mkdir(parents=True, exist_ok=True)

    except OSError as os_err:
        message = f"Error creating directory: {os_err}"
        logging.exception(message)
        sys.exit(1)

    return download_path
