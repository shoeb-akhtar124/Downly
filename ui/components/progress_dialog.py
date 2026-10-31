"""
Download Progress Dialog Component.
Compact floating download progress window inspired by classic IDM / download managers.
Displays real-time file details, transfer speed, resume capability, and controls.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QGridLayout, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal

from core.download_manager import download_manager, DownloadTask
from ui.theme_manager import theme_manager


class DownloadProgressDialog(QDialog):
    """Floating compact download progress window."""

    pause_requested = Signal(str)
    resume_requested = Signal(str)
    cancel_requested = Signal(str)

    def __init__(self, task: DownloadTask, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self.task_id = task.task_id

        self.setWindowTitle(f"Downloading - {task.title[:30]}...")
        self.setFixedSize(520, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._is_paused = (task.status == "Paused")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        # File title header
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        p = theme_manager.get_palette()

        self.lbl_title = QLabel(self.task.title)
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {p['main_text']};")
        self.lbl_title.setWordWrap(True)

        self.lbl_url = QLabel(self.task.url)
        self.lbl_url.setStyleSheet(f"font-size: 11px; color: {p['secondary_text']};")
        self.lbl_url.setText(self.task.url[:65] + ("..." if len(self.task.url) > 65 else ""))

        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_url)
        layout.addLayout(title_box)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setValue(int(self.task.progress))
        layout.addWidget(self.progress_bar)

        # Metrics Grid (IDM-style)
        metrics_card = QFrame()
        metrics_card.setObjectName("surfaceCard")
        metrics_layout = QGridLayout(metrics_card)
        metrics_layout.setContentsMargins(14, 12, 14, 12)
        metrics_layout.setHorizontalSpacing(16)
        metrics_layout.setVerticalSpacing(8)

        def add_row(row, label_text, val_widget):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: 12px; color: {p['secondary_text']}; font-weight: 500;")
            val_widget.setStyleSheet(f"font-size: 12px; color: {p['main_text']}; font-weight: 600;")
            metrics_layout.addWidget(lbl, row, 0)
            metrics_layout.addWidget(val_widget, row, 1)

        self.val_status = QLabel(self.task.status)
        self.val_size = QLabel(self.task.file_size_str or "Calculating...")
        self.val_speed = QLabel(self.task.speed_str or "—")
        self.val_avg_speed = QLabel(getattr(self.task, "average_speed_str", "—"))
        self.val_peak_speed = QLabel(getattr(self.task, "peak_speed_str", "—"))
        self.val_eta = QLabel(self.task.eta_str or "—")
        self.val_resume = QLabel("Yes (HTTP/Streams)")

        add_row(0, "Status:", self.val_status)
        add_row(1, "File Size:", self.val_size)
        add_row(2, "Transfer Speed:", self.val_speed)
        add_row(3, "Average Speed:", self.val_avg_speed)
        add_row(4, "Peak Speed:", self.val_peak_speed)
        add_row(5, "Time Left:", self.val_eta)
        add_row(6, "Resume Support:", self.val_resume)

        layout.addWidget(metrics_card)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.pause_resume_btn = QPushButton("⏸ Pause" if not self._is_paused else "▶ Resume")
        self.pause_resume_btn.setObjectName("secondaryButton")
        self.pause_resume_btn.setCursor(Qt.PointingHandCursor)
        self.pause_resume_btn.clicked.connect(self._toggle_pause_resume)

        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_download)

        self.open_folder_btn = QPushButton("📂 Open Folder")
        self.open_folder_btn.setObjectName("secondaryButton")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._open_folder)

        close_btn = QPushButton("Close Window")
        close_btn.setObjectName("secondaryButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.pause_resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        """Listen to download manager events for this task."""
        download_manager.task_progress.connect(self._on_progress)
        download_manager.task_extended_progress.connect(self._on_extended_progress)
        download_manager.task_status_changed.connect(self._on_status)
        download_manager.task_completed.connect(self._on_completed)
        download_manager.task_failed.connect(self._on_failed)

    def _on_progress(self, task_id: str, percent: float, speed: str, eta: str) -> None:
        if task_id == self.task_id:
            self.progress_bar.setValue(int(percent))
            self.val_speed.setText(speed or "—")
            self.val_eta.setText(eta or "—")
            self.val_status.setText(f"Downloading ({int(percent)}%)")

    def _on_extended_progress(
        self, task_id: str, percent: float, speed: str, avg_speed: str, peak_speed: str, eta: str
    ) -> None:
        if task_id == self.task_id:
            self.progress_bar.setValue(int(percent))
            self.val_speed.setText(speed or "—")
            self.val_avg_speed.setText(avg_speed or "—")
            self.val_peak_speed.setText(peak_speed or "—")
            self.val_eta.setText(eta or "—")
            self.val_status.setText(f"Downloading ({int(percent)}%)")

    def _on_status(self, task_id: str, status: str, message: str) -> None:
        if task_id == self.task_id:
            self.val_status.setText(status)
            if status == "Paused":
                self._is_paused = True
                self.pause_resume_btn.setText("▶ Resume")
            elif status == "Downloading":
                self._is_paused = False
                self.pause_resume_btn.setText("⏸ Pause")

    def _on_completed(self, task: DownloadTask) -> None:
        p = theme_manager.get_palette()
        if task.task_id == self.task_id:
            self.progress_bar.setValue(100)
            self.val_status.setText("✓ Completed")
            self.val_status.setStyleSheet(f"color: {p['success']}; font-weight: 700;")
            self.val_size.setText(task.file_size_str)
            self.val_speed.setText("0 B/s")
            self.val_eta.setText("Finished")
            self.pause_resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)

    def _on_failed(self, task_id: str, err: str) -> None:
        p = theme_manager.get_palette()
        if task_id == self.task_id:
            self.val_status.setText("❌ Failed")
            self.val_status.setStyleSheet(f"color: {p['error']}; font-weight: 700;")
            self.val_speed.setText("—")
            self.val_eta.setText(f"Error: {err[:35]}")
            self.pause_resume_btn.setEnabled(False)

    def _toggle_pause_resume(self) -> None:
        if self._is_paused:
            download_manager.resume_download(self.task_id)
            self._is_paused = False
            self.pause_resume_btn.setText("⏸ Pause")
        else:
            download_manager.pause_download(self.task_id)
            self._is_paused = True
            self.pause_resume_btn.setText("▶ Resume")

    def _cancel_download(self) -> None:
        reply = QMessageBox.question(
            self,
            "Cancel Download",
            f"Are you sure you want to abort downloading '{self.task.title}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            download_manager.cancel_download(self.task_id)
            self.reject()

    def _open_folder(self) -> None:
        folder = self.task.download_dir
        if folder and os.path.exists(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.run(["xdg-open", folder])

