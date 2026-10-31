"""
Media Details Dialog Component.
Inspects downloaded media files with FFprobe and displays detailed metadata:
File name, size, duration, resolution, frame rate, video/audio codecs, container, and bitrate.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QFrame, QWidget
)
from PySide6.QtCore import Qt

from core.media_inspector import MediaInspector
from ui.theme_manager import theme_manager


class MediaDetailsDialog(QDialog):
    """Clean metadata dialog displaying FFprobe-inspected stream information."""

    def __init__(self, file_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle("Download Details - Media Properties")
        self.setFixedSize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        p = theme_manager.get_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        header_lbl = QLabel("Media File Details & Properties")
        header_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['main_text']};")
        sub_lbl = QLabel("Technical stream parameters inspected via FFprobe")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {p['secondary_text']};")
        title_box.addWidget(header_lbl)
        title_box.addWidget(sub_lbl)
        layout.addLayout(title_box)

        # Extract metadata
        details: Dict[str, str] = MediaInspector.get_detailed_metadata(self.file_path)

        # Grid Card
        grid_card = QFrame()
        grid_card.setObjectName("surfaceCard")
        grid_card.setStyleSheet(
            f"background-color: {p['card_bg']}; border: 1px solid {p['borders']}; border-radius: 8px;"
        )
        grid = QGridLayout(grid_card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        fields = [
            ("File Name", details.get("File Name", "—")),
            ("File Size", details.get("File Size", "—")),
            ("Duration", details.get("Duration", "—")),
            ("Resolution", details.get("Resolution", "—")),
            ("Frame Rate", details.get("Frame Rate", "—")),
            ("Video Codec", details.get("Video Codec", "—")),
            ("Audio Codec", details.get("Audio Codec", "—")),
            ("Audio Channels", details.get("Audio Channels", "—")),
            ("Audio Sample Rate", details.get("Audio Sample Rate", "—")),
            ("Bitrate", details.get("Bitrate", "—")),
            ("Container Format", details.get("Container Format", "—")),
        ]

        for row, (lbl_txt, val_txt) in enumerate(fields):
            lbl = QLabel(f"{lbl_txt}:")
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {p['secondary_text']};")
            val = QLabel(str(val_txt))
            val.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {p['main_text']};")
            val.setWordWrap(True)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        layout.addWidget(grid_card)

        # Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(10)

        open_folder_btn = QPushButton("📂 Open Location")
        open_folder_btn.setObjectName("secondaryButton")
        open_folder_btn.setCursor(Qt.PointingHandCursor)
        open_folder_btn.clicked.connect(self._open_location)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)

        footer.addWidget(open_folder_btn)
        footer.addStretch()
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _open_location(self) -> None:
        p = Path(self.file_path)
        folder = p.parent if p.is_file() else p
        if folder.exists():
            if sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.run(["xdg-open", str(folder)])
