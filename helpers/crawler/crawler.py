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

from helpers.config import CRAWLER_WORKERS, prepare_headers

from .crawler_utils import (
    episode_in_range,
    extract_host_domain,
    fetch_with_retries,
    validate_episode_range,
    validate_url,
)

if TYPE_CHECKING:
    from requests import BeautifulSoup

HEADERS = prepare_headers()


class Crawler:
    """Class responsible for crawling an anime.

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
    def extract_anime_name(soup: BeautifulSoup) -> str:
        """Extract the anime name from the provided BeautifulSoup object."""
        try:
            title_container = soup.find("h1", {"class": "title"})
            if title_container is None:
                logging.error("Anime title tag not found.")

        except AttributeError as attr_err:
            message = f"Error extracting anime name: {attr_err}"
            logging.exception(message)

        return title_container.get_text().strip()

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

    async def _get_episode_ids(self) -> list[tuple[int, str]] | None:
        """Fetch the IDs of all the episodes from an API."""
        episode_api_url = f"{self.api_url}/0"
        params = {
            "start_range": 0,
            "end_range": self.num_episodes + 1,
        }

        response = await fetch_with_retries(
            episode_api_url,
            self.semaphore,
            headers=HEADERS,
            params=params,
        )
        if response:
            episode_info = response.json().get("episodes", [])
            return (
                [(ep["id"], ep["number"]) for ep in episode_info]
                if episode_info
                else None
            )

        return None

    async def _collect_episode_ids(self) -> list[int]:
        """Retrieve a list of episode IDs from a given URL."""
        validate_episode_range(self.start_episode, self.end_episode, self.num_episodes)

        episodes = await self._get_episode_ids()
        return [
            ep[0]
            for ep in episodes
            if episode_in_range(ep[1], self.start_episode, self.end_episode)
        ]

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
