"""Read-only dialog for the bundled English MIRA user manual."""

from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
)


MANUAL_FILENAME = "USER_MANUAL_ENG.md"


def user_manual_path() -> str:
    """Return the manual path for both source and PyInstaller execution."""
    if getattr(sys, "frozen", False):
        # PyInstaller extracts bundled data into _MEIPASS, including onefile builds.
        base = sys._MEIPASS
    else:
        # viewer/ is directly below the project root that owns the live manual.
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, MANUAL_FILENAME)


class UserManualDialog(QDialog):
    """Render the English Markdown manual with Qt's built-in Markdown support."""

    def __init__(self, manual_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MIRA User Manual")
        self.resize(900, 700)

        path = manual_path or user_manual_path()
        # Let the caller report a concise, user-facing warning if packaging is broken.
        with open(path, "r", encoding="utf-8") as manual_file:
            markdown = manual_file.read()

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setMarkdown(markdown)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.addWidget(browser)
        layout.addWidget(buttons)
