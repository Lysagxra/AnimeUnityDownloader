"""Configuration module for managing constants and settings used across the project.

These configurations aim to improve modularity and readability by consolidating settings
into a single location.
"""

import random

DOWNLOAD_FOLDER = "Downloads"  # The folder where downloaded files will be stored.
FILE = "URLs.txt"              # The name of the file containing URLs.

TASK_COLOR = "cyan"            # The color to be used for task-related messages.
CRAWLER_WORKERS = 8            # The maximum number of worker threads for crawling
                               # tasks.
DOWNLOAD_WORKERS = 2           # The maximum number of worker threads for downloading
                               # tasks.

# Constants for file sizes, expressed in bytes.
KB = 1024
MB = 1024 * KB

# Thresholds for file sizes and corresponding chunk sizes used during download.
# Each tuple represents: (file size threshold, chunk size to download in that range).
THRESHOLDS = [
    (50 * MB, 128 * KB),   # Less than 50 MB
    (100 * MB, 256 * KB),  # 50 MB to 100 MB
    (250 * MB, 1 * MB),    # 100 MB to 250 MB
]

# Default chunk size for files larger than the largest threshold.
LARGE_FILE_CHUNK_SIZE = 2 * MB

# User agent strings for rotation (updated and realistic)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class UserAgentRotator:
    """Simple user agent rotator class that mimics fake_useragent interface."""
    
    def __init__(self, user_agents=None):
        """Initialize the rotator with a list of user agents."""
        self.user_agents = user_agents or USER_AGENTS
    
    @property
    def firefox(self):
        """Get a random Firefox user agent."""
        firefox_agents = [ua for ua in self.user_agents if 'Firefox' in ua]
        return random.choice(firefox_agents) if firefox_agents else random.choice(self.user_agents)
    
    @property
    def chrome(self):
        """Get a random Chrome user agent."""
        chrome_agents = [ua for ua in self.user_agents if 'Chrome' in ua and 'Firefox' not in ua]
        return random.choice(chrome_agents) if chrome_agents else random.choice(self.user_agents)
    
    @property
    def safari(self):
        """Get a random Safari user agent."""
        safari_agents = [ua for ua in self.user_agents if 'Safari' in ua and 'Chrome' not in ua]
        return random.choice(safari_agents) if safari_agents else random.choice(self.user_agents)
    
    @property
    def random(self):
        """Get a random user agent."""
        return random.choice(self.user_agents)


# Creating a user-agent rotator
USER_AGENT_ROTATOR = UserAgentRotator()


def prepare_headers() -> dict:
    """Prepare a random HTTP headers with a user-agent string for making requests."""
    user_agent = str(USER_AGENT_ROTATOR.firefox)
    return {"User-Agent": user_agent}
