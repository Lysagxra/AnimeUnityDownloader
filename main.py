"""
Main module of the project with PyQt6 GUI.

This module provides a GUI to manage multiple sets of URLs in separate tabs.
You can enter URLs in each tab, and start downloads independently.
It also supports a CLI mode with --nogui, where it runs the downloader normally.
"""

from __future__ import annotations

import sys
import asyncio
import threading
from argparse import ArgumentParser, Namespace

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QTextEdit, QTabWidget, QMessageBox, QMainWindow
)

# Import your existing functions
from anime_downloader import add_custom_path_argument, process_anime_download
from helpers.config import URLS_FILE
from helpers.file_utils import read_file, write_file
from helpers.general_utils import clear_terminal


def parse_arguments() -> Namespace:
    """Parse only the --custom-path argument."""
    parser = ArgumentParser(description="Download anime series from a list of URLs.")
    add_custom_path_argument(parser)
    parser.add_argument(
        "--nogui",
        action="store_true",
        help="Run without GUI (terminal mode).",
    )
    return parser.parse_args()


async def process_urls(urls: list[str], custom_path: str | None = None) -> None:
    """Validate and download items for a list of URLs."""
    for url in urls:
        await process_anime_download(url, custom_path=custom_path)


async def main(custom_path: str | None = None) -> None:
    """Run the script in non-GUI mode."""
    clear_terminal()

    # Read and process URLs, ignoring empty lines
    urls = [url.strip() for url in read_file(URLS_FILE) if url.strip()]
    await process_urls(urls, custom_path=custom_path)

    # Clear URLs file
    write_file(URLS_FILE)


def run_asyncio(coro):
    """Run an asyncio coroutine in a separate thread for GUI."""
    def runner():
        asyncio.run(coro)
    threading.Thread(target=runner, daemon=True).start()


class DownloadTab(QWidget):
    """A single tab for entering URLs and starting downloads."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.url_text = QTextEdit()
        layout.addWidget(self.url_text)

        start_btn = QPushButton("Start Download")
        start_btn.clicked.connect(self.start_download)
        layout.addWidget(start_btn)

        self.setLayout(layout)

    def start_download(self):
        urls = [u.strip() for u in self.url_text.toPlainText().splitlines() if u.strip()]
        if not urls:
            QMessageBox.warning(self, "No URLs", "Please enter at least one URL.")
            return
        run_asyncio(process_urls(urls))


class MainWindow(QMainWindow):
    """Main window containing the tab system."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Downloader - Multi Tab")
        self.resize(600, 400)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_counter = 0
        self.add_new_tab()  # Start with one tab

        add_tab_btn = QPushButton("Add Tab")
        add_tab_btn.clicked.connect(self.add_new_tab)
        self.addToolBar("Main").addWidget(add_tab_btn)

    def add_new_tab(self):
        self.tab_counter += 1
        tab = DownloadTab()
        self.tabs.addTab(tab, f"Tab {self.tab_counter}")


if __name__ == "__main__":
    args = parse_arguments()

    if args.nogui:
        asyncio.run(main(custom_path=args.custom_path))
    else:
        app = QApplication(sys.argv)
        win = MainWindow()
        win.show()
        sys.exit(app.exec())
