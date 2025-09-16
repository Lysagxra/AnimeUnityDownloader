"""Package provides utility modules and functions to support the main application.

These utilities include functions for downloading, file management, URL handling,
progress tracking, and more.

Modules:
    - config: Constants and settings used across the project.
    - download_utils: Functions for handling downloads.
    - file_utils: Utilities for managing file operations.
    - general_utils: Miscellaneous utility functions.
    - progress_utils: Tools for progress tracking and reporting.

This package is designed to be reusable and modular, allowing its components
to be easily imported and used across different parts of the application.
"""

# src/__init__.py

__all__ = [
    "config",
    "download_utils",
    "file_utils",
    "general_utils",
    "progress_utils",
]
