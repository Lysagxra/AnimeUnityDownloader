"""
Module to download anime episodes from a given AnimeUnity URL (async optimized).

It extracts the anime ID, formats the anime name, retrieves episode IDs and
URLs, and downloads episodes concurrently using aiohttp.

Usage:
    - Run the script with the URL of the anime page as a command-line argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the anime name where each episode will be downloaded.
"""

from __future__ import annotations

import asyncio
import random
import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

import aiohttp
from rich.live import Live

from helpers.config import prepare_headers
from helpers.crawler.crawler import Crawler
from helpers.crawler.crawler_utils import extract_download_link
from helpers.download_utils import get_episode_filename
from helpers.general_utils import clear_terminal, create_download_directory, fetch_page_httpx
from helpers.progress_utils import create_progress_bar, create_progress_table

# Limit how many files are downloaded at once
MAX_CONCURRENT_DOWNLOADS = 5


async def download_episode_async(
    session: aiohttp.ClientSession,
    download_link: str,
    download_path: str,
    task_info: tuple,
    retries: int = 4,
) -> None:
    """Download an episode from the link asynchronously with retries."""
    filename = get_episode_filename(download_link)
    final_path = Path(download_path) / filename

    for attempt in range(retries):
        try:
            async with session.get(download_link) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get("Content-Length", 0))
                task_id = task_info[0].add_task(filename, total=total_size)

                with open(final_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        f.write(chunk)
                        task_info[0].update(task_id, advance=len(chunk))
            break
        except Exception as e:
            logging.warning(f"Download failed for {download_link}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(10 * (attempt + 1) + random.uniform(0, 2))
            else:
                logging.error(f"Giving up on {download_link} after {retries} attempts.")


async def process_video_url_async(
    session: aiohttp.ClientSession,
    video_url: str,
    download_path: str,
    task_info: tuple,
) -> None:
    """Fetch embed page, extract real download link, and download the episode."""
    soup = await fetch_page_httpx(video_url)
    script_items = soup.find_all("script")
    download_link = extract_download_link(script_items, video_url)
    await download_episode_async(session, download_link, download_path, task_info)


async def download_anime_async(
    anime_name: str,
    video_urls: list[str],
    download_path: str,
) -> None:
    """Download episodes concurrently with progress bars."""
    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    headers = prepare_headers()

    async with aiohttp.ClientSession(headers=headers) as session:
        async def sem_task(url):
            async with semaphore:
                await process_video_url_async(session, url, download_path, (job_progress,))

        with Live(progress_table, refresh_per_second=10):
            await asyncio.gather(*(sem_task(url) for url in video_urls))


async def process_anime_download(
    url: str,
    start_episode: int | None = None,
    end_episode: int | None = None,
    custom_path: str | None = None,
) -> None:
    """Process the download of an anime from the specified URL."""
    soup = await fetch_page_httpx(url)
    crawler = Crawler(url=url, start_episode=start_episode, end_episode=end_episode)
    video_urls = await crawler.collect_video_urls()

    try:
        anime_name = crawler.extract_anime_name(soup, url)
        download_path = create_download_directory(anime_name, custom_path=custom_path)
        await download_anime_async(anime_name, video_urls, download_path)
    except ValueError as val_err:
        logging.exception(f"Value error: {val_err}")


def add_custom_path_argument(parser: ArgumentParser) -> None:
    """Add the --custom-path argument to the provided argument parser."""
    parser.add_argument(
        "--custom-path",
        type=str,
        default=None,
        help="The directory where the downloaded content will be saved.",
    )


def parse_arguments() -> Namespace:
    """Parse command-line arguments."""
    parser = ArgumentParser(description="Download anime episodes from a given URL.")
    parser.add_argument("url", help="The URL of the Anime series to download.")
    add_custom_path_argument(parser)
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="The starting episode number.",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="The ending episode number.",
    )
    return parser.parse_args()


async def main() -> None:
    """Execute the script to download anime episodes from a given AnimeUnity URL."""
    clear_terminal()
    args = parse_arguments()
    await process_anime_download(
        args.url,
        start_episode=args.start,
        end_episode=args.end,
        custom_path=args.custom_path,
    )


if __name__ == "__main__":
    asyncio.run(main())
