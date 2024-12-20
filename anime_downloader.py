"""
This script downloads anime episodes from a given AnimeUnity URL.

It extracts the anime ID, formats the anime name, retrieves episode IDs and
URLs, and downloads episodes concurrently.

Usage:
    - Run the script with the URL of the anime page as a command-line argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the anime name where each episode will be downloaded.
"""

import os
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from rich.live import Live

from helpers.progress_utils import create_progress_bar, create_progress_table
from helpers.general_utils import (
    fetch_page, create_download_directory, clear_terminal
)
from helpers.download_utils import (
    get_episode_filename, save_file_with_progress, run_in_parallel
)
from helpers.anime_utils import (
    extract_anime_name, get_episode_ids, generate_episode_urls
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) "
        "Gecko/20100101 Firefox/117.0"
    ),
    "Connection": "keep-alive"
}

def get_embed_url(episode_url, tag, attribute):
    """
    Retrieves the embed URL from the given episode URL by parsing the specified
    HTML tag and attribute.

    Args:
        episode_url (str): The URL of the episode page to fetch.
        tag (str): The HTML tag to search for within the page.
        attribute (str): The attribute of the tag that contains the embed URL.

    Returns:
        str: The retrieved embed URL if found.

    Raises:
        requests.RequestException: If an error occurs while making the HTTP 
                                   request.
        AttributeError: If the specified tag is not found in the HTML page.
        KeyError: If the specified attribute is not found in the tag.
    """
    try:
        soup = fetch_page(episode_url)

        element = soup.find(tag)
        if element is None:
            raise AttributeError(f"Tag '{tag}' not found")

        embed_url = element.get(attribute)
        if embed_url is None:
            raise KeyError(f"Attribute '{attribute}' not found in tag '{tag}'")

        return embed_url

    except requests.RequestException as req_err:
        return print(f"HTTP request error: {req_err}")

def get_embed_urls(episode_urls):
    """
    Retrieves embed URLs from a list of episode URLs by making concurrent HTTP
    requests.

    Args:
        episode_urls (list of str): A list of episode URLs to extract the embed
                                    URLs from.

    Returns:
        list of str: A list of embed URLs extracted from the provided episode
                     URLs.

    Raises:
        requests.RequestException: If an error occurs while making any HTTP
                                   request.
    """
    embed_urls = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                get_embed_url, episode_url, 'video-player', 'embed_url'
            ): episode_url for episode_url in episode_urls
        }

        for future in as_completed(futures):
            embed_url = future.result()
            if embed_url:
                embed_urls.append(embed_url)

    return embed_urls

def download_episode(download_link, download_path, task_info, retries=3):
    """
    Downloads an episode from the specified link and provides real-time
    progress updates.

    Args:
        download_link (str): The URL from which to download the episode.
        download_path (str): The directory path where the episode file will
                             be saved.
        task_info (tuple): A tuple containing progress tracking information:
            - job_progress: The progress bar object.
            - task: The specific task being tracked.
            - overall_task: The overall progress task being updated.
        retries (int, optional): The number of retry attempts in case of a
                                 download failure. Defaults to 3 retries.

    Raises:
        requests.RequestException: If there is an error with the HTTP request,
                                   such as connectivity issues or invalid URLs.
    """
    for attempt in range(retries):
        try:
            response = requests.get(
                download_link, stream=True, headers=HEADERS, timeout=10
            )
            response.raise_for_status()

            filename = get_episode_filename(download_link)
            final_path = os.path.join(download_path, filename)
            save_file_with_progress(response, final_path, task_info)
            break

        except requests.RequestException as req_err:
            print(
                f"HTTP request failed: {req_err}\n"
                f"Retrying in a moment... ({attempt + 1}/{retries})"
            )
            time.sleep(30)

def process_embed_url(embed_url, download_path, task_info):
    """
    Processes an embed URL to extract episode download links and initiate their
    download.

    Args:
        embed_url (str): The embed URL to process.
        download_path (str): The path to save the downloaded episodes.
        task_info (tuple): A tuple containing progress tracking information.
    """
    def extract_download_link(text, match="window.downloadUrl = "):
        """
        Extracts a download link from a JavaScript text by searching for a
        specific match pattern.

        Args:
            text (str): The text to search for the download URL.
            match (str, optional): The pattern to search for in the text.
                                   Defaults to `window.downloadUrl = `.

        Returns:
            str: The extracted download URL if the pattern is found;
                 otherwise, `None`.

        Raises:
            IndexError: If the expected format of the text does not match the
                        pattern or the URL cannot be extracted.
        """
        if match in text:
            try:
                return text.split("'")[-2]

            except IndexError as indx_err:
                raise IndexError(
                    f"Error extracting the download link for {embed_url}"
                ) from indx_err

        return None

    soup = fetch_page(embed_url)
    script_items = soup.find_all('script')
    texts = [item.text for item in script_items]

    for text in texts:
        download_link = extract_download_link(text)
        if download_link:
            download_episode(download_link, download_path, task_info)

def download_anime(anime_name, video_urls, download_path):
    """
    Concurrently downloads episodes of a specified anime from provided video
    URLs and tracks the download progress in real-time.

    Args:
        anime_name (str): The name of the anime being downloaded.
        video_urls (list): A list of URLs corresponding to each episode to be
                           downloaded.
        download_path (str): The local directory path where the downloaded
                             episodes will be saved.
    """
    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    with Live(progress_table, refresh_per_second=10):
        run_in_parallel(
            process_embed_url, video_urls, job_progress, download_path
        )

def process_anime_download(url, start_episode=None, end_episode=None):
    """
    Processes the download of an anime from the specified URL.

    Args:
        url (str): The URL of the anime page to process.
        start_episode (int, optional): The starting episode number. Defaults to
                                       None.
        end_episode (int, optional): The ending episode number. Defaults to
                                     None.

    Raises:
        ValueError: If there is an issue with extracting data from 
                    the anime page.
    """
    soup = fetch_page(url)

    try:
        anime_name = extract_anime_name(soup)
        download_path = create_download_directory(anime_name)

        episode_ids = get_episode_ids(
            soup,
            start_episode=start_episode,
            end_episode=end_episode
        )
        episode_urls = generate_episode_urls(url, episode_ids)

        embed_urls = get_embed_urls(episode_urls)
        download_anime(anime_name, embed_urls, download_path)

    except ValueError as val_err:
        print(f"Value error: {val_err}")

def setup_parser():
    """
    Set up the argument parser for the anime download script.

    Returns:
        argparse.ArgumentParser: The configured argument parser instance.
    """
    parser = argparse.ArgumentParser(
        description="Download anime episodes from a given URL."
    )
    parser.add_argument('url', help="The URL of the Anime series to download.")
    parser.add_argument(
        '--start', type=int, default=None, help="The starting episode number."
    )
    parser.add_argument(
        '--end', type=int, default=None, help="The ending episode number."
    )
    return parser

def main():
    """
    Main function to download anime episodes from a given AnimeUnity URL.

    Command-line Arguments:
        <anime_url> (str): The URL of the anime page to download episodes from.
    """
    clear_terminal()
    parser = setup_parser()
    args = parser.parse_args()
    process_anime_download(args.url, args.start, args.end)

if __name__ == '__main__':
    main()
