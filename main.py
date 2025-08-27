"""Main module of the project.

This module provides functionality to read URLs from a file, process
them for downloading Anime content, and write results back to the file.

Usage:
    To use this module, ensure that 'URLs.txt' is present in the same
    directory as this script. Execute the script to read URLs, download
    content, and clear the URL list upon completion.
"""

import asyncio

from anime_downloader import process_anime_download
from helpers.config import URLS_FILE
from helpers.file_utils import read_file, write_file
from helpers.general_utils import clear_terminal


async def process_urls(urls: list[str]) -> None:
    """Validate and downloads items for a list of URLs."""
    for url in urls:
        await process_anime_download(url)


async def main() -> None:
    """Run the script.

    Reads URLs from a file, processes them, and clears the file at the end.
    """
    clear_terminal()
    urls = read_file(URLS_FILE)
    await process_urls(urls)
    write_file(URLS_FILE)


if __name__ == "__main__":
    asyncio.run(main())
