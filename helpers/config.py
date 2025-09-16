"""Configuration module for managing constants and settings used across the project.

These configurations aim to improve modularity and readability by consolidating settings
into a single location.
"""

from argparse import ArgumentParser, Namespace

from fake_useragent import UserAgent

# ============================
# Paths and Files
# ============================
DOWNLOAD_FOLDER = "Downloads"  # The folder where downloaded files will be stored.
URLS_FILE = "URLs.txt"         # The file containing URLs to process.

# ============================
# Regex Patterns
# ============================
# Regex patterns to extract download URL and the anime name
DOWNLOAD_LINK_PATTERN = r"window\.downloadUrl\s*=\s*'(https?:\/\/[^\s']+)'"
ANIME_NAME_PATTERN = r"/anime/\d+-(.+)$"

# ============================
# Download Settings
# ============================
TASK_COLOR = "cyan"   # The color to be used for task-related messages.
BATCH_SIZE = 120      # The maximum number of episodes the API allows per request.
CRAWLER_WORKERS = 8   # The maximum number of worker threads for crawling tasks.
DOWNLOAD_WORKERS = 2  # The maximum number of worker threads for downloading tasks.

# Constants for file sizes, expressed in bytes
KB = 1024
MB = 1024 * KB

# Thresholds for file sizes and corresponding chunk sizes used during download.
THRESHOLDS = [
    (50 * MB, 128 * KB),   # Less than 50 MB
    (100 * MB, 256 * KB),  # 50 MB to 100 MB
    (250 * MB, 1 * MB),    # 100 MB to 250 MB
]

# Default chunk size for files larger than the largest threshold
LARGE_FILE_CHUNK_SIZE = 2 * MB

# ============================
# HTTP / Network
# ============================
# HTTP status codes
HTTP_STATUS_FORBIDDEN = 403

# Minimum content length to check if text is too short or missing basic HTML tags
MIN_CONTENT_LENGTH = 1000

# Common headers shared across all types of requests
COMMON_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    "DNT": "1",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}

# Headers for API / JSON endpoints
BASE_HEADERS = {
    **COMMON_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Headers for standard browser-like HTML requests
DEFAULT_HEADERS = {
    **COMMON_HEADERS,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Headers with explicit encoding and compression options
ENCODING_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept-Encoding": "gzip, deflate, br",
}

# ============================
# User-Agent Rotator
# ============================
# Creating a user-agent rotator
USER_AGENT_ROTATOR = UserAgent()


def prepare_headers() -> dict[str, str]:
    """Prepare a random HTTP headers with a user-agent string for making requests."""
    user_agent = str(USER_AGENT_ROTATOR.firefox)
    return {"User-Agent": user_agent}

# ============================
# Argument Parsing
# ============================
def add_common_arguments(parser: ArgumentParser) -> None:
    """Add arguments shared across parsers."""
    parser.add_argument(
        "--custom-path",
        type=str,
        default=None,
        help="The directory where the downloaded content will be saved.",
    )


def setup_parser(
        *, include_url: bool = False, include_filters: bool = False,
    ) -> ArgumentParser:
    """Set up parser with optional argument groups."""
    parser = ArgumentParser(description="Command-line arguments.")

    if include_url:
        parser.add_argument("url", type=str, help="The URL to process")

    if include_filters:
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

    add_common_arguments(parser)
    return parser


def parse_arguments(*, common_only: bool = False) -> Namespace:
    """Full argument parser (including URL, filters, and common)."""
    parser = (
        setup_parser() if common_only
        else setup_parser(include_url=True, include_filters=True)
    )
    return parser.parse_args()
