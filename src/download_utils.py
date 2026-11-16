"""Utilities for handling file downloads with progress tracking."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from .config import (
    DOWNLOAD_WORKERS,
    LARGE_FILE_CHUNK_SIZE,
    TASK_COLOR,
    THRESHOLDS,
)

if TYPE_CHECKING:
    from requests import Response
    from rich.progress import Progress


def remove_special_characters(input_string: str) -> str:
    """Remove special characters from the input string."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "", input_string)


def get_episode_filename(
    download_link: str,
    response: Response | None = None,
) -> str | None:
    """Extract a sanitized .mp4 filename from response headers or URL."""
    if response is not None:
        disposition = response.headers.get("Content-Disposition", "")
        match = re.search(
            r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
            disposition,
            re.IGNORECASE,
        )
        if match:
            cleaned = remove_special_characters(unquote(match.group(1).strip()))
            if cleaned.lower().endswith(".mp4"):
                return cleaned

        final_path_name = unquote(response.url.split("?")[0].rstrip("/").split("/")[-1])
        cleaned_url_name = remove_special_characters(final_path_name)
        if cleaned_url_name.lower().endswith(".mp4"):
            return cleaned_url_name

    if download_link and "=" in download_link:
        filename = unquote(download_link.split("=")[-1])
        cleaned = remove_special_characters(filename)
        if cleaned.lower().endswith(".mp4"):
            return cleaned

    return None


def get_chunk_size(file_size: int) -> int:
    """Determine the optimal chunk size based on the file size."""
    for threshold, chunk_size in THRESHOLDS:
        if file_size < threshold:
            return chunk_size

    return LARGE_FILE_CHUNK_SIZE


def save_file_with_progress(
    response: Response,
    final_path: str,
    task_info: tuple,
) -> None:
    """Save a file to the specified path while tracking and updating progress."""
    job_progress, task, overall_task = task_info
    file_size = int(response.headers.get("Content-Length", -1))
    chunk_size = get_chunk_size(file_size)
    total_downloaded = 0

    with Path(final_path).open("wb") as file:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                file.write(chunk)
                total_downloaded += len(chunk)
                if file_size > 0:
                    progress_percentage = (total_downloaded / file_size) * 100
                    job_progress.update(task, completed=progress_percentage)

    job_progress.update(task, completed=100, visible=False)
    job_progress.advance(overall_task)


def manage_running_tasks(futures: dict, job_progress: Progress) -> None:
    """Manage the status of running tasks and update their progress."""
    while futures:
        for future in list(futures.keys()):
            if future.running():
                task = futures.pop(future)
                job_progress.update(task, visible=True)


def run_in_parallel(
    func: callable, items: list, job_progress: Progress, *args: tuple,
) -> None:
    """Execute a function in parallel for a list of items, updating progress."""
    num_items = len(items)
    futures = {}
    all_futures = []

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        overall_task = job_progress.add_task(
            f"[{TASK_COLOR}]Progress", total=num_items, visible=True,
        )
        for indx, item in enumerate(items):
            task = job_progress.add_task(
                f"[{TASK_COLOR}]Episode {indx + 1}/{num_items}",
                total=100,
                visible=False,
            )
            task_info = (job_progress, task, overall_task)
            future = executor.submit(func, item, *args, task_info)
            futures[future] = task
            all_futures.append(future)
            manage_running_tasks(futures, job_progress)

    for future in all_futures:
        exc = future.exception()
        if exc is not None:
            logging.error("Download worker failed: %s", exc, exc_info=exc)
