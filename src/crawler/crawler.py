"""Module for automating the process of scraping anime videos based on episode ranges.

Utilities functions to crawl anime websites, retrieve episode information, and collect
video URLs for each episode.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from src.config import (
    ANIME_NAME_PATTERN,
    BATCH_SIZE,
    CRAWLER_WORKERS,
    DEFAULT_LANGUAGE,
    prepare_headers,
)
from src.general_utils import fetch_page_httpx

from .crawler_utils import (
    episode_in_range,
    extract_host_domain,
    extract_inertia_props,
    extract_name_from_title_tag,
    fetch_with_retries,
    validate_episode_range,
    validate_url,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

HEADERS = prepare_headers()


def _safe_float(value: str) -> float | None:
    """Convert a string to float, returning None if conversion fails."""
    try:
        return float(value)

    except (ValueError, TypeError):
        return None


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
        episodes: list[int] | None = None,
        soup: BeautifulSoup | None = None,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        """Initialize the crawler."""
        self.host_domain = extract_host_domain(url)
        self.soup = soup if soup is not None else fetch_page_httpx(validate_url(url))
        self.props = extract_inertia_props(self.soup)
        self.anime_info = self.props.get("anime", {})
        self.anime_id = self.anime_info["id"]
        self.num_episodes = self._get_num_episodes()
        self.start_episode = start_episode
        self.end_episode = end_episode
        self.episodes = episodes
        self.language = language.lower()
        self.semaphore = asyncio.Semaphore(CRAWLER_WORKERS)

    async def collect_video_urls(self) -> list[str]:
        """Collect a list of video URLs by concurrently fetching each embed URL."""
        episodes = await self.collect_episodes()
        return [video_url for _, video_url in episodes]

    async def collect_episodes(self) -> list[tuple[str, str | None]]:
        """Collect (episode number, video URL) pairs for the selected episodes."""
        episodes = await self._collect_episode_ids()
        return [
            (
                str(number),
                f"https://{self.host_domain}/episode-videos/{video_id}/download",
            )
            for video_id, number in episodes
        ]

    # Static methods
    @staticmethod
    def extract_anime_name(soup: BeautifulSoup, url: str | None = None) -> str | None:
        """Extract the anime name from the provided BeautifulSoup object."""
        try:
            app_node = soup.find(id="app")
            if app_node is not None and app_node.has_attr("data-page"):
                props = extract_inertia_props(soup)
                anime = props.get("anime", {})
                title = anime.get("title") or anime.get("title_ja")
                if title:
                    return title.strip()

            # First try the original method
            title_container = soup.find("h1", {"class": "title"})
            if title_container is not None:
                return title_container.get_text().strip()

            # Fallback: Extract from HTML title tag
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return extract_name_from_title_tag(title_tag)

            # If all else fails, try meta og:title
            og_title = soup.find("meta", property="og:title")
            if og_title:
                return og_title.get("content", "")

            # Last resort: Extract from URL
            if url:
                # URL pattern: /anime/ID-anime-name
                match = re.search(ANIME_NAME_PATTERN, url)
                if match:
                    return match.group(1).replace("-", " ").title()

        except AttributeError as attr_err:
            message = f"Error extracting anime name: {attr_err}"
            logging.exception(message)
            return ""

        logging.error("Could not extract anime name from any source")
        return None

    # Private methods
    def _get_num_episodes(self) -> int:
        """Retrieve total number of episodes for the selected media."""
        loaded = self.props.get("loadedEpisodes") or {}
        return int(loaded.get("total") or self.anime_info.get("total_episodes") or 0)

    def _select_video_id(self, episode_info: dict) -> int | None:
        """Select the episode-video ID matching the preferred language."""
        videos = episode_info.get("videos") or []
        if not videos:
            return None

        visible = [v for v in videos if not v.get("is_hidden")] or videos
        chosen = next(
            (v for v in visible if str(v.get("language", "")).lower() == self.language),
            visible[0],
        )
        return chosen.get("id")

    async def _get_episode_ids(self) -> list[tuple[int, str]]:
        """Fetch all (episode_video_id, episode_number) pairs across paginated chunks."""
        loaded = self.props.get("loadedEpisodes") or {}
        initial_episodes = loaded.get("episodes") or []
        tab_size = int(loaded.get("tab_size") or BATCH_SIZE)

        all_episode_infos: list[dict] = list(initial_episodes)
        seen_ids = {ep["id"] for ep in all_episode_infos if "id" in ep}

        episode_api_url = f"https://{self.host_domain}/api/anime/{self.anime_id}/episodes"
        start = len(all_episode_infos) + 1

        while start <= self.num_episodes:
            response = await fetch_with_retries(
                episode_api_url,
                self.semaphore,
                headers=HEADERS,
                params={"start": start},
            )
            if not response:
                break

            payload = response.json()
            chunk = payload if isinstance(payload, list) else payload.get("episodes", [])
            if not chunk:
                break

            added = 0
            for ep in chunk:
                if ep.get("id") not in seen_ids:
                    seen_ids.add(ep["id"])
                    all_episode_infos.append(ep)
                    added += 1

            if added == 0:
                break
            start += tab_size

        results: list[tuple[int, str]] = []
        for info in all_episode_infos:
            video_id = self._select_video_id(info)
            if video_id is not None:
                results.append((video_id, str(info["number"])))
        return results

    async def _collect_episode_ids(self) -> list[tuple[int, str]]:
        """Retrieve (episode ID, episode number) pairs from a given URL."""
        episodes = await self._get_episode_ids()
        if self.episodes:
            episodes_set = {float(episode) for episode in self.episodes}
            return [
                episode
                for episode in episodes
                if _safe_float(episode[1]) in episodes_set
            ]

        validate_episode_range(self.start_episode, self.end_episode, self.num_episodes)
        return [
            episode
            for episode in episodes
            if episode_in_range(episode[1], self.start_episode, self.end_episode)
        ]
