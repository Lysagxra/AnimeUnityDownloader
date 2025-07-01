"""Module for automating the process of scraping anime videos based on episode ranges.

Utilities functions to crawl anime websites, retrieve episode information, and collect
video URLs for each episode.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

import httpx

from helpers.config import (
    CRAWLER_WORKERS,
    prepare_headers,
)

from .crawler_utils import (
    extract_host_domain,
    fetch_with_retries,
    validate_episode_range,
    validate_url,
)

if TYPE_CHECKING:
    from requests import BeautifulSoup

HEADERS = prepare_headers()

class Crawler:
    """class responsible for crawling an anime.

    Extract episode IDs, generate embed URLs, and retrieve video URLs for a specified
    range of episodes.
    """

    def __init__(
        self,
        url: str,
        start_episode: int | None,
        end_episode: int | None,
        max_workers: int = CRAWLER_WORKERS,
    ) -> None:
        """Initialize the crawler."""
        self.host_domain = extract_host_domain(url)
        self.api_url = self._generate_api_url(url)
        self.num_episodes = self._get_num_episodes()
        self.start_episode = start_episode
        self.end_episode = end_episode
        self.semaphore = asyncio.Semaphore(max_workers)

    async def collect_video_urls(self) -> list[str]:
        """Collect a list of video URLs by concurrently fetching each embed URL."""
        episode_ids = await self._collect_episode_ids()
        embed_urls = self._generate_episode_embed_urls(episode_ids)
        tasks = [self._get_video_url(embed_url) for embed_url in embed_urls]
        return await asyncio.gather(*tasks)

    # Static methods
    @staticmethod
    def extract_anime_name(soup: BeautifulSoup, url: str = None) -> str:
        """Extract the anime name from the provided BeautifulSoup object."""
        try:
            # First try the original method
            title_container = soup.find("h1", {"class": "title"})
            if title_container is not None:
                return title_container.get_text().strip()
            
            # Fallback: Extract from HTML title tag
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title_text = title_tag.string
                logging.info(f"Using title tag: {title_text}")
                
                # Extract anime name from AnimeUnity title format
                if "AnimeUnity ~" in title_text:
                    anime_name = title_text.split("AnimeUnity ~")[1].split("Streaming")[0].strip()
                    if anime_name:
                        return anime_name
                
                # Fallback: Just use the title with cleanup  
                title_text = title_text.replace("AnimeUnity", "").replace("~", "").strip()
                if title_text:
                    return title_text

            # If all else fails, try meta og:title
            og_title = soup.find("meta", property="og:title")
            if og_title:
                return og_title.get("content", "Unknown Anime")
            
            # Last resort: extract from URL
            if url:
                import re
                # URL pattern: /anime/ID-anime-name
                match = re.search(r'/anime/\d+-(.+)$', url)
                if match:
                    anime_name = match.group(1).replace('-', ' ').title()
                    logging.info(f"Extracted anime name from URL: {anime_name}")
                    return anime_name
            
            logging.error("Could not extract anime name from any source")
            return "Unknown Anime"

        except AttributeError as attr_err:
            message = f"Error extracting anime name: {attr_err}"
            logging.exception(message)
            return "Unknown Anime"

    # Private methods
    def _get_num_episodes(self, timeout: int = 10) -> int:
        """Retrieve total number of episodes for the selected media."""
        response = httpx.get(
            url=self.api_url,
            headers=HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        response_json = response.json()
        return response_json["episodes_count"]

    def _generate_api_url(self, url: str) -> str | None:
        """Generate the API URL based on the provided base URL."""
        validated_url = validate_url(url)
        escaped_host_domain = re.escape(self.host_domain)
        match = re.match(
            rf"https://{escaped_host_domain}/anime/(\d+-[^/]+)",
            validated_url,
        )

        if match:
            anime_id = match.group(1)
            return f"https://{self.host_domain}/info_api/{anime_id}"

        logging.error("URL format is incorrect.")
        return None

    async def _get_episode_id(self, episode_indx: int) -> str | None:
        """Fetch the ID of the specified episode from an API."""
        episode_api_url = f"{self.api_url}/{episode_indx}"
        params = {
            "start_range": episode_indx,
            "end_range": episode_indx + 1,
        }

        response = await fetch_with_retries(
            episode_api_url,
            self.semaphore,
            headers=HEADERS,
            params=params,
        )
        if response:
            episode_info = response.json().get("episodes", [])
            return episode_info[-1]["id"] if episode_info else None

        return None

    async def _collect_episode_ids(self) -> list[str]:
        """Retrieve a list of episode IDs from a given URL."""
        start_episode, end_episode = validate_episode_range(
            self.start_episode,
            self.end_episode,
            self.num_episodes,
        )

        start_index = start_episode - 1 if start_episode else 0
        end_index = end_episode if end_episode else self.num_episodes

        tasks = [
            self._get_episode_id(episode_indx)
            for episode_indx in range(start_index, end_index)
        ]
        return await asyncio.gather(*tasks)

    def _generate_episode_embed_urls(self, episode_ids: str) -> list[str]:
        """Generate a list of embed URLs for a series of episodes."""
        return [
            f"https://{self.host_domain}/embed-url/{episode_id}"
            for episode_id in episode_ids
        ]

    async def _get_video_url(self, embed_url: str) -> str | None:
        """Fetch the video URL from an embed URL."""
        response = await fetch_with_retries(
            embed_url,
            self.semaphore,
            headers=HEADERS,
        )
        if response:
            return response.text.strip()

        return None
