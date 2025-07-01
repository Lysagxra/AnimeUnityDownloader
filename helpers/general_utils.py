"""Utilities for fetching web pages, managing directories, and clearing the terminal.

This module includes functions to handle common tasks such as sending HTTP requests,
parsing HTML, creating download directories, and  clearing the terminal, making it
reusable across projects.
"""

import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import httpx
import requests
from bs4 import BeautifulSoup

from .config import DOWNLOAD_FOLDER, prepare_headers


def add_random_delay(min_delay: float = 0.5, max_delay: float = 2.0) -> None:
    """Add a random delay to avoid being detected as a bot."""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()
    
    # Create a new session per worker
    session = requests.Session()
    headers = prepare_headers()
    
    # Add additional headers to look more like a real browser
    headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })

    try:
        # First attempt: normal request
        response = session.get(url, headers=headers, timeout=timeout, stream=False)
        response.raise_for_status()
        
        # Handle text content
        text_content = response.text
        
        # If we get binary/compressed content that wasn't auto-decompressed, try manual decompression
        if len(text_content) < 1000 or not any(tag in text_content.lower() for tag in ['<html', '<head', '<title']):
            try:
                import gzip
                try:
                    import brotli
                    brotli_available = True
                except ImportError:
                    brotli_available = False
                
                # Try brotli decompression if available
                if brotli_available and 'br' in response.headers.get('content-encoding', ''):
                    text_content = brotli.decompress(response.content).decode('utf-8')
                # Try gzip decompression
                elif 'gzip' in response.headers.get('content-encoding', ''):
                    text_content = gzip.decompress(response.content).decode('utf-8')
            except Exception as e:
                logging.warning(f"Manual decompression failed: {e}")
                # Use original content
                text_content = response.text
        
        return BeautifulSoup(text_content, "html.parser")

    except requests.RequestException as req_err:
        if hasattr(req_err, 'response') and req_err.response is not None:
            if req_err.response.status_code == 403:
                logging.error(f"Access forbidden (403) for URL: {url}")
                logging.error("The website may be blocking bot traffic. Consider:")
                logging.error("1. Using a VPN or different IP address")
                logging.error("2. Adding delays between requests")
                logging.error("3. Using proxy rotation")
        
        message = f"Error fetching page {url}: {req_err}"
        logging.exception(message)
        sys.exit(1)


def fetch_page_httpx(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage using HTTPX with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()
    
    headers = prepare_headers()
    
    # Add additional headers to look more like a real browser
    headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    
    try:
        # Create httpx client with proper decompression
        with httpx.Client(
            headers=headers, 
            timeout=timeout, 
            follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Check if content is HTML
            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type.lower():
                logging.warning(f"Unexpected content type: {content_type}")
            
            # Get the properly decoded text content
            html_content = response.text
            
            # Debug logging
            logging.info(f"Fetched {len(html_content)} characters from {url}")
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Verify we got actual HTML
            if not soup.find('html') and not soup.find('head'):
                logging.warning("Response doesn't appear to be valid HTML")
                # Try different parsing
                soup = BeautifulSoup(html_content, "lxml")
            
            return soup
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logging.error(f"Access forbidden (403) for URL: {url}")
            logging.error("The website may be blocking bot traffic. Consider:")
            logging.error("1. Using a VPN or different IP address")
            logging.error("2. Adding delays between requests")
            logging.error("3. Using proxy rotation")
            raise
        else:
            raise


def sanitize_directory_name(directory_name: str) -> str:
    """Sanitize a given directory name.

    Replace invalid characters with underscores. Handles the invalid characters specific
    to Windows, macOS, and Linux.
    """
    invalid_chars_dict = {
        "nt": r'[\\/:*?"<>|]',  # Windows
        "posix": r"[/:]",  # macOS and Linux
    }
    invalid_chars = invalid_chars_dict.get(os.name)
    return re.sub(invalid_chars, "_", directory_name)


def create_download_directory(directory_name: str) -> str:
    """Create a directory for downloads if it doesn't exist."""
    download_path = Path(DOWNLOAD_FOLDER) / sanitize_directory_name(directory_name)

    try:
        Path(download_path).mkdir(parents=True, exist_ok=True)
        return download_path

    except OSError as os_err:
        message = f"Error creating directory: {os_err}"
        logging.exception(message)
        sys.exit(1)


def clear_terminal() -> None:
    """Clear the terminal screen based on the operating system."""
    commands = {
        "nt": "cls",       # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        os.system(command)  # noqa: S605
