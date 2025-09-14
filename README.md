# AnimeUnity Downloader

> A Python-based tool for downloading anime series from AnimeUnity, featuring progress tracking for each episode. It efficiently extracts video URLs and manages downloads.

![Screenshot](https://github.com/Lysagxra/AnimeUnityDownloader/blob/660079e23bc16e8b1996b463e213aecbb1a56294/misc/Screenshot.png)

## Features

- Downloads multiple episodes concurrently.
- Supports [batch downloading](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#batch-download) via a list of URLs.
- Supports downloading a [specified range of episodes](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#single-anime-download).
- Supports [custom download location](https://github.com/Lysagxra/AnimeUnityDownloader/tree/main?tab=readme-ov-file#file-download-location).
- Tracks download progress with a progress bar.
- Automatically creates a directory structure for organized storage.

## Dependencies

- Python 3
- `requests` - for HTTP requests
- `BeautifulSoup` (bs4) - for HTML parsing
- `rich` - for progress display in terminal
- `fake_useragent` - for generating fake user agents for web scraping
- `httpx` - for making asynchronous HTTP requests

## Directory Structure

<details>

<summary>Expand Directory Structure</summary>

```
project-root/
├── helpers/
│ ├── crawlers/
│ │ ├── crawler.py        # Module for crawling tasks
│ │ └── crawler_utils.py  # Utilities for extracting media download links
│ ├── config.py           # Manages constants and settings used across the project
│ ├── download_utils.py   # Utilities for managing the download process
│ ├── file_utils.py       # Utilities for managing file operations
│ ├── general_utils.py    # Miscellaneous utility functions
│ └── progress_utils.py   # Tools for progress tracking and reporting
├── anime_downloader.py   # Module for downloading anime episodes
├── main.py               # Main script to run the downloader
└── URLs.txt              # Text file containing anime URLs
```

</details>

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Lysagxra/AnimeUnityDownloader.git
```

2. Navigate to the project directory:

```bash
cd AnimeUnityDownloader
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Single Anime Download

To download a single anime, you can use the `anime_downloader.py` script.

### Usage

Run the script followed by the anime URL you want to download:

```bash
python3 anime_downloader.py <anime_url> [--start <start_episode>] [--end <end_episode>]
```

- `<anime_url>`: The URL of the anime series.
- `--start <start_episode>`: The starting episode number (optional).
- `--end <end_episode>`: The ending episode number (optional).

### Examples

To download all episodes:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri
```

To download a specific range of episodes (e.g., episodes 5 to 10):
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --start 5 --end 10
```

To download episodes starting from a specific episode:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --start 5
```
In this case, the script will download all episodes starting from the `--start` episode to the last episode.

To download episodes up to a certain episode:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --end 10
```
In this case, the script will download all episodes starting from the first episode to the `--end` episode.

## Batch Download

### Usage

1. Create a `URLs.txt` file in the project root and list the anime URLs you want to download.

- Example of `URLs.txt`:

```
https://www.animeunity.so/anime/1517-yuru-yuri
https://www.animeunity.so/anime/3871-chainsaw-man
https://www.animeunity.so/anime/2598-made-in-abyss
```

- Ensure that each URL is on its own line without any extra spaces.
- You can add as many URLs as you need, following the same format.

2. Run the main script via the command line:

```bash
python3 main.py
```

## File Download Location

If the `--custom-path <custom_path>` argument is used, the downloaded files will be saved in `<custom_path>/Downloads`. Otherwise, the files will be saved in a `Downloads` folder created within the script's directory

### Usage

```bash
python3 main.py --custom-path <custom_path>
```

### Example

```bash
python3 main.py --custom-path /path/to/external/drive
```
