"""Utilities for downloading episodes distributed only as HLS streams.

Some episodes expose an empty `window.downloadUrl` in their embed page, leaving the HLS
master playlist as the only source. These helpers rebuild the playlist URL from the
embed page scripts, pick the best rendition and remux it into an MP4 with ffmpeg.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urljoin, urlparse

import requests

from .config import (
    HLS_CAN_PLAY_FHD_PATTERN,
    HLS_EXPIRES_PATTERN,
    HLS_PLAYLIST_URL_PATTERN,
    HLS_TOKEN_PATTERN,
    prepare_headers,
)

if TYPE_CHECKING:
    from pathlib import Path

    from bs4 import Tag


def is_ffmpeg_available() -> bool:
    """Check whether ffmpeg is installed and reachable from PATH."""
    return shutil.which("ffmpeg") is not None


def extract_master_playlist_url(script_items: list[Tag]) -> str | None:
    """Build the HLS master playlist URL from the embed page scripts."""
    for item in script_items:
        text = item.text
        url_match = re.search(HLS_PLAYLIST_URL_PATTERN, text)
        token_match = re.search(HLS_TOKEN_PATTERN, text)
        expires_match = re.search(HLS_EXPIRES_PATTERN, text)

        if url_match and token_match and expires_match:
            params = {
                "token": token_match.group(1),
                "expires": expires_match.group(1),
            }
            if re.search(HLS_CAN_PLAY_FHD_PATTERN, text):
                params["h"] = "1"

            base_url = url_match.group(1)
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}{urlencode(params)}"

    return None


def prepare_hls_headers(playlist_url: str) -> dict[str, str]:
    """Prepare the headers expected by the HLS host."""
    parsed_url = urlparse(playlist_url)
    headers = prepare_headers()
    headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    return headers


def select_best_rendition(master_url: str, headers: dict[str, str]) -> str:
    """Return the media playlist URL with the highest bandwidth."""
    response = requests.get(master_url, headers=headers, timeout=10)
    response.raise_for_status()

    best_url, best_bandwidth = master_url, -1
    lines = response.text.splitlines()
    for indx, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and indx + 1 < len(lines):
            match = re.search(r"BANDWIDTH=(\d+)", line)
            bandwidth = int(match.group(1)) if match else 0
            if bandwidth > best_bandwidth:
                best_url = urljoin(master_url, lines[indx + 1].strip())
                best_bandwidth = bandwidth

    return best_url


def get_playlist_duration(media_url: str, headers: dict[str, str]) -> float:
    """Compute the total duration in seconds of a media playlist."""
    response = requests.get(media_url, headers=headers, timeout=10)
    response.raise_for_status()
    durations = re.findall(r"#EXTINF:([\d.]+)", response.text)
    return sum(float(duration) for duration in durations)


def build_ffmpeg_command(
    media_url: str, headers: dict[str, str], output_path: Path,
) -> list[str]:
    """Build the ffmpeg command that remuxes the HLS stream into an MP4 file."""
    header_lines = "".join(
        f"{key}: {value}\r\n" for key, value in headers.items() if key != "User-Agent"
    )
    return [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
        "-user_agent", headers["User-Agent"],
        "-headers", header_lines,
        "-i", media_url,
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        "-progress", "pipe:1", "-nostats",
        str(output_path),
    ]


def track_ffmpeg_progress(
    process: subprocess.Popen, duration: float, task_info: tuple,
) -> None:
    """Update the progress bar from the ffmpeg `-progress` output."""
    job_progress, task, _ = task_info
    for line in process.stdout:
        key, _, value = line.strip().partition("=")
        if key == "out_time_us" and value.isdigit() and duration > 0:
            progress_percentage = min(int(value) / 1_000_000 / duration * 100, 99)
            job_progress.update(task, completed=progress_percentage)


def run_ffmpeg_with_progress(
    media_url: str,
    headers: dict[str, str],
    final_path: Path,
    duration: float,
    task_info: tuple,
) -> bool:
    """Remux the HLS stream into an MP4 file while updating the progress bar."""
    job_progress, task, overall_task = task_info
    temp_path = final_path.with_suffix(".part.mp4")
    command = build_ffmpeg_command(media_url, headers, temp_path)

    with subprocess.Popen(  # noqa: S603
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ) as process:
        track_ffmpeg_progress(process, duration, task_info)
        stderr = process.stderr.read()

    if process.returncode != 0:
        message = f"ffmpeg failed for {final_path.name}: {stderr.strip()}"
        logging.error(message)
        temp_path.unlink(missing_ok=True)
        return False

    temp_path.replace(final_path)
    job_progress.update(task, completed=100, visible=False)
    job_progress.advance(overall_task)
    return True


def download_hls_episode(
    script_items: list[Tag],
    video_url: str,
    final_path: Path,
    task_info: tuple,
) -> bool:
    """Download an episode from its HLS stream, returning whether it succeeded."""
    if not is_ffmpeg_available():
        message = f"ffmpeg is required to download {video_url}"
        logging.error(message)
        return False

    master_url = extract_master_playlist_url(script_items)
    if master_url is None:
        message = f"Error extracting the download link for {video_url}"
        logging.error(message)
        return False

    headers = prepare_hls_headers(master_url)

    try:
        media_url = select_best_rendition(master_url, headers)
        duration = get_playlist_duration(media_url, headers)

    except requests.RequestException as req_err:
        message = f"Error fetching the HLS playlist for {video_url}: {req_err}"
        logging.error(message)  # noqa: TRY400
        return False

    return run_ffmpeg_with_progress(media_url, headers, final_path, duration, task_info)
