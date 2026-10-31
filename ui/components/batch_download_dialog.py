"""
Batch Download Dialog Component.
Provides multi-URL entry, validation, status tracking, and queued execution
under strict concurrency limits.
"""
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QFrame,
    QMessageBox, QWidget
)
from PySide6.QtCore import Qt

from app.constants import SUPPORTED_QUALITIES, SUPPORTED_FORMATS
from core.download_manager import download_manager
from core.download_destination import destination_manager
from core.url_analyzer import URLAnalyzer
from ui.theme_manager import theme_manager


class BatchDownloadDialog(QDialog):
    """Dialog allowing users to enter multiple media URLs, validate them, and queue downloads."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Batch Download Manager")
        self.resize(740, 500)
        self.setMinimumSize(580, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.validated_tasks: List[Dict[str, str]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        p = theme_manager.get_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("📦 Batch Media Download")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['main_text']};")
        sub_lbl = QLabel("Paste multiple video links (one URL per line) to queue them simultaneously.")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {p['secondary_text']};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        layout.addLayout(title_box)

        # Multi-line URL text edit
        self.url_text_edit = QTextEdit()
        self.url_text_edit.setPlaceholderText(
            "Paste URLs here (one per line)...\nhttps://www.youtube.com/watch?v=...\nhttps://vimeo.com/..."
        )
        self.url_text_edit.setFixedHeight(110)
        layout.addWidget(self.url_text_edit)

        # Action bar between input and table
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_validate = QPushButton("🔍 Validate Links")
        self.btn_validate.setObjectName("secondaryButton")
        self.btn_validate.setCursor(Qt.PointingHandCursor)
        self.btn_validate.clicked.connect(self._on_validate_clicked)

        btn_clear = QPushButton("Clear Input")
        btn_clear.setObjectName("secondaryButton")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(lambda: self.url_text_edit.clear())

        self.lbl_stats = QLabel("Tasks: 0 Ready  •  0 Invalid")
        self.lbl_stats.setStyleSheet(f"font-size: 12px; color: {p['secondary_text']}; font-weight: 500;")

        btn_bar.addWidget(self.btn_validate)
        btn_bar.addWidget(btn_clear)
        btn_bar.addStretch()
        btn_bar.addWidget(self.lbl_stats)
        layout.addLayout(btn_bar)

        # Table of validated links
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "URL", "Platform", "Validation"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Preset quality and format
        opts_frame = QFrame()
        opts_frame.setStyleSheet(
            f"background-color: {p['card_bg']}; border: 1px solid {p['borders']}; border-radius: 8px;"
        )
        opts_layout = QHBoxLayout(opts_frame)
        opts_layout.setContentsMargins(14, 10, 14, 10)
        opts_layout.setSpacing(12)

        lbl_q = QLabel("Batch Quality:")
        lbl_q.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(SUPPORTED_QUALITIES)

        lbl_fmt = QLabel("Batch Format:")
        lbl_fmt.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        self.combo_format = QComboBox()
        self.combo_format.addItems(SUPPORTED_FORMATS)

        opts_layout.addWidget(lbl_q)
        opts_layout.addWidget(self.combo_quality)
        opts_layout.addWidget(lbl_fmt)
        opts_layout.addWidget(self.combo_format)
        opts_layout.addStretch()
        layout.addWidget(opts_frame)

        # Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        self.btn_start = QPushButton("⬇️ Queue Validated Tasks")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setFixedHeight(36)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start_batch)

        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(self.btn_start)
        layout.addLayout(footer)

    def _on_validate_clicked(self) -> None:
        p = theme_manager.get_palette()
        raw_lines = self.url_text_edit.toPlainText().strip().splitlines()
        self.validated_tasks.clear()

        urls = []
        for line in raw_lines:
            clean = line.strip()
            if clean and not clean.startswith("#"):
                urls.append(clean)

        if not urls:
            QMessageBox.warning(self, "No URLs", "Please paste one or more media URLs to validate.")
            return

        self.table.setRowCount(len(urls))
        valid_count = 0
        invalid_count = 0

        for row, u in enumerate(urls):
            is_valid = URLAnalyzer.is_valid_url(u)
            platform = URLAnalyzer.detect_platform(u) if is_valid else "Unknown"

            # Index
            idx_item = QTableWidgetItem(str(row + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, idx_item)

            # URL
            url_item = QTableWidgetItem(u)
            self.table.setItem(row, 1, url_item)

            # Platform
            plat_item = QTableWidgetItem(platform)
            plat_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, plat_item)

            # Status
            status_item = QTableWidgetItem("✓ Ready" if is_valid else "✕ Invalid URL")
            status_item.setTextAlignment(Qt.AlignCenter)
            if is_valid:
                status_item.setForeground(Qt.GlobalColor(Qt.darkGreen))
                valid_count += 1
                self.validated_tasks.append({
                    "url": u,
                    "platform": platform
                })
            else:
                status_item.setForeground(Qt.GlobalColor(Qt.red))
                invalid_count += 1
            self.table.setItem(row, 3, status_item)

        self.lbl_stats.setText(f"Tasks: {valid_count} Ready  •  {invalid_count} Invalid")
        self.btn_start.setEnabled(valid_count > 0)
        self.btn_start.setText(f"⬇️ Queue Validated Tasks ({valid_count})")

    def _on_start_batch(self) -> None:
        quality = self.combo_quality.currentText()
        output_format = self.combo_format.currentText()
        codec = "Keep Original Codec"
        audio_codec = "Keep Original"
        dest_dir = str(destination_manager.get_destination())

        for task_info in self.validated_tasks:
            u = task_info["url"]
            plat = task_info["platform"]
            download_manager.add_download(
                url=u,
                title=f"{plat} Download",
                quality=quality,
                output_format=output_format,
                codec=codec,
                platform=plat,
                download_dir=dest_dir,
                audio_codec=audio_codec
            )

        QMessageBox.information(
            self,
            "Batch Downloads Queued",
            f"Successfully added {len(self.validated_tasks)} download(s) to the queue."
        )
        self.accept()
