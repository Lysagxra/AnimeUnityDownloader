"""Module to download anime episodes from a given AnimeUnity URL.

It extracts the anime ID, formats the anime name, retrieves episode IDs and
URLs, and downloads episodes concurrently.

Usage:
    - Run the script with the URL of the anime page as a command-line argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the anime name where each episode will be downloaded.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from argparse import Namespace
from pathlib import Path

import requests
from rich.live import Live

from helpers.config import prepare_headers
from helpers.crawler.crawler import Crawler
from helpers.crawler.crawler_utils import extract_download_link
from helpers.download_utils import (
    get_episode_filename,
    run_in_parallel,
    save_file_with_progress,
)
from helpers.general_utils import (
    clear_terminal,
    create_download_directory,
    fetch_page,
    fetch_page_httpx,
)
from helpers.progress_utils import create_progress_bar, create_progress_table

HEADERS = prepare_headers()


def download_episode(
    download_link: str,
    download_path: str,
    task_info: tuple,
    retries: int = 4,
) -> None:
    """Download an episode from the download link and provides progress updates."""
    for attempt in range(retries):
        try:
            response = requests.get(
                download_link, stream=True, headers=HEADERS, timeout=10,
            )
            response.raise_for_status()

        except requests.RequestException:
            if attempt < retries - 1:
                delay = 10 * (attempt + 1) + random.uniform(1, 2)  # noqa: S311
                time.sleep(delay)

        else:
            filename = get_episode_filename(download_link)
            final_path = Path(download_path) / filename
            save_file_with_progress(response, final_path, task_info)
            break


def process_video_url(video_url: str, download_path: str, task_info: tuple) -> None:
    """Process an embed URL to extract episode download links."""
    soup = fetch_page(video_url)
    script_items = soup.find_all("script")
    download_link = extract_download_link(script_items, video_url)
    download_episode(download_link, download_path, task_info)


def download_anime(anime_name: str, video_urls: list[str], download_path: str) -> None:
    """Download episodes of a specified anime from provided video URLs."""
    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    with Live(progress_table, refresh_per_second=10):
        run_in_parallel(process_video_url, video_urls, job_progress, download_path)


async def process_anime_download(
    url: str,
    start_episode: int | None = None,
    end_episode: int | None = None,
) -> None:
    """Process the download of an anime from the specified URL."""
    soup = fetch_page_httpx(url)
    crawler = Crawler(url=url, start_episode=start_episode, end_episode=end_episode)
    video_urls = await crawler.collect_video_urls()

    try:
        anime_name = crawler.extract_anime_name(soup)
        download_path = create_download_directory(anime_name)
        download_anime(anime_name, video_urls, download_path)

    except ValueError as val_err:
        message = f"Value error: {val_err}"
        logging.exception(message)


def parse_arguments() -> Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download anime episodes from a given URL.",
    )
    parser.add_argument("url", help="The URL of the Anime series to download.")
    parser.add_argument(
        "--start", type=int, default=None, help="The starting episode number.",
    )
    parser.add_argument(
        "--end", type=int, default=None, help="The ending episode number.",
    )
    return parser.parse_args()


async def main() -> None:
    """Execute the script to download anime episodes from a given AnimeUnity URL."""
    clear_terminal()
    args = parse_arguments()
    await process_anime_download(
        args.url, start_episode=args.start, end_episode=args.end,
    )


if __name__ == "__main__":
    asyncio.run(main())
