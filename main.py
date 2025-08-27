"""
Main module of the project with PyQt6 GUI.

This module provides a GUI to manage multiple sets of URLs in separate tabs.
You can enter URLs in each tab, and start downloads independently.
It uses the original async download functions.
"""

import sys
import asyncio
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QTextEdit, QTabWidget, QMessageBox, QMainWindow
)

# Import your existing functions
from anime_downloader import process_anime_download
from helpers.config import FILE
from helpers.file_utils import read_file, write_file
from helpers.general_utils import clear_terminal


async def process_urls(urls: list[str]) -> None:
    """Validate and download items for a list of URLs."""
    for url in urls:
        await process_anime_download(url)


async def main() -> None:
    """Run the script from file (non-GUI mode)."""
    clear_terminal()
    urls = read_file(FILE)
    await process_urls(urls)
    write_file(FILE)


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
    if len(sys.argv) > 1 and sys.argv[1] == "--nogui":
        # Run original script logic without GUI
        asyncio.run(main())
    else:
        app = QApplication(sys.argv)
        win = MainWindow()
        win.show()
        sys.exit(app.exec())
