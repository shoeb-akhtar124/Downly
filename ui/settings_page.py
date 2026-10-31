"""
Settings Page.
Configures local preferences: download destination, format/codec defaults,
subtitles, concurrency, automatic retry, clipboard monitoring,
hardware acceleration, and GitHub updates.
Cleaned up according to user specifications (System Diagnostics & Theme dropdown removed).
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QDialog,
    QTextEdit, QProgressBar, QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QDesktopServices

from app.config import config
from app.constants import (
    APP_VERSION, DEFAULT_GITHUB_REPO,
    SUPPORTED_QUALITIES, SUPPORTED_FORMATS,
    SUPPORTED_VIDEO_CODECS, SUPPORTED_AUDIO_CODECS,
    SUPPORTED_SUBTITLE_LANGUAGES
)
from core.download_manager import download_manager
from core.media_inspector import MediaInspector
from core.clipboard_monitor import clipboard_monitor
from core.download_destination import destination_manager, DestinationError
from core.update_manager import CheckUpdateWorker, StageUpdateWorker, UpdateInfo
from ui.theme_manager import theme_manager
from ui.components.card import Card


class ReleaseNotesDialog(QDialog):
    """Modal dialog displaying release information, changelog, and confirmation controls."""

    def __init__(self, update_info: UpdateInfo, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle(f"New Update Available - {update_info.release_name}")
        self.resize(520, 420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel(f"🎉 Version {self.update_info.latest_version} is available!")
        header.setObjectName("dialogHeader")
        layout.addWidget(header)

        subhead = QLabel(f"You are currently running v{self.update_info.current_version}.")
        subhead.setObjectName("dialogSubhead")
        layout.addWidget(subhead)

        notes_label = QLabel("Release Notes:")
        notes_label.setObjectName("dialogNotesLabel")
        layout.addWidget(notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setPlainText(self.update_info.release_notes)
        layout.addWidget(self.notes_text)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("dialogStatus")
        layout.addWidget(self.status_lbl)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        web_btn = QPushButton("🌐 View on GitHub")
        web_btn.setObjectName("secondaryButton")
        web_btn.setCursor(Qt.PointingHandCursor)
        web_btn.clicked.connect(self._open_github)

        self.stage_btn = QPushButton("📦 Stage Update Package")
        self.stage_btn.setObjectName("primaryButton")
        self.stage_btn.setCursor(Qt.PointingHandCursor)
        self.stage_btn.clicked.connect(self._start_staging)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(web_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.stage_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open_github(self) -> None:
        if self.update_info.html_url:
            QDesktopServices.openUrl(QUrl(self.update_info.html_url))

    def _start_staging(self) -> None:
        if not self.update_info.download_url:
            QMessageBox.information(
                self,
                "Manual Download Required",
                "No direct executable asset was found in the release. Please download from GitHub directly."
            )
            self._open_github()
            return

        self.stage_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("Downloading staged update package...")

        self.worker = StageUpdateWorker(self.update_info, self)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.staged_success.connect(self._on_staged_success)
        self.worker.stage_failed.connect(self._on_staged_failed)
        self.worker.start()

    def _on_staged_success(self, path: str) -> None:
        self.status_lbl.setText("✓ Update package staged safely!")
        QMessageBox.information(
            self,
            "Update Staged Safely",
            f"The update has been safely downloaded and staged at:\n{path}\n\n"
            "Automatic silent replacement is disabled for safety. You can review and execute the installer when ready."
        )

    def _on_staged_failed(self, err: str) -> None:
        self.stage_btn.setEnabled(True)
        self.status_lbl.setText(f"⚠️ Staging failed: {err}")


class SettingsPage(QWidget):
    """View and adjust local application preferences and updates."""

    settings_updated = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._update_worker: Optional[CheckUpdateWorker] = None
        self._setup_ui()
        self.load_values()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent;")

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header Section
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        page_title = QLabel("Settings")
        page_title.setObjectName("pageTitle")
        header_text.addWidget(page_title)
        main_layout.addLayout(header_text)

        # 1. Storage Location Card
        dir_card = Card(title="Download Destination")
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)

        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Select download folder...")

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse_clicked)

        open_folder_btn = QPushButton("📂 Open Folder")
        open_folder_btn.setObjectName("secondaryButton")
        open_folder_btn.setCursor(Qt.PointingHandCursor)
        open_folder_btn.clicked.connect(self._on_open_folder_clicked)

        dir_layout.addWidget(self.dir_input, stretch=1)
        dir_layout.addWidget(browse_btn)
        dir_layout.addWidget(open_folder_btn)
        dir_card.add_layout(dir_layout)
        main_layout.addWidget(dir_card)

        # 2. Download Preferences Card
        pref_card = Card(title="Download Preferences")
        pref_grid = QGridLayout()
        pref_grid.setHorizontalSpacing(16)
        pref_grid.setVerticalSpacing(12)
        pref_grid.setColumnStretch(1, 1)
        pref_grid.setColumnStretch(3, 1)

        # Row 0: Concurrency and Fragment counts
        lbl_conc = QLabel("Max Concurrent Downloads:")
        lbl_conc.setStyleSheet("font-weight: 600;")
        self.concurrent_combo = QComboBox()
        self.concurrent_combo.addItems(["Automatic", "1", "2", "3", "4", "5"])

        lbl_frags = QLabel("Concurrent Fragments:")
        lbl_frags.setStyleSheet("font-weight: 600;")
        self.fragments_combo = QComboBox()
        self.fragments_combo.addItems(["Automatic", "1", "2", "4", "8", "16"])

        pref_grid.addWidget(lbl_conc, 0, 0)
        pref_grid.addWidget(self.concurrent_combo, 0, 1)
        pref_grid.addWidget(lbl_frags, 0, 2)
        pref_grid.addWidget(self.fragments_combo, 0, 3)

        # Row 1: Max Retries and Retry Delay
        lbl_retry_attempts = QLabel("Max Retry Attempts:")
        lbl_retry_attempts.setStyleSheet("font-weight: 600;")
        self.retry_combo = QComboBox()
        self.retry_combo.addItems(["Automatic", "1", "2", "3", "5", "10"])

        lbl_retry_delay = QLabel("Retry Delay (seconds):")
        lbl_retry_delay.setStyleSheet("font-weight: 600;")
        self.retry_delay_combo = QComboBox()
        self.retry_delay_combo.addItems(["Automatic", "1", "2", "5", "10", "15", "30"])

        pref_grid.addWidget(lbl_retry_attempts, 1, 0)
        pref_grid.addWidget(self.retry_combo, 1, 1)
        pref_grid.addWidget(lbl_retry_delay, 1, 2)
        pref_grid.addWidget(self.retry_delay_combo, 1, 3)

        # Toggles layout
        toggles_layout = QVBoxLayout()
        toggles_layout.setSpacing(8)

        self.clipboard_monitor_check = QCheckBox(
            "Enable Clipboard Monitoring (prompt when video links are copied to clipboard)"
        )
        self.auto_retry_check = QCheckBox(
            "Enable Automatic Retry (automatically recover from transient network drops)"
        )

        toggles_layout.addWidget(self.clipboard_monitor_check)
        toggles_layout.addWidget(self.auto_retry_check)

        pref_box = QVBoxLayout()
        pref_box.setSpacing(14)
        pref_box.addLayout(pref_grid)
        pref_box.addLayout(toggles_layout)
        pref_card.add_layout(pref_box)
        main_layout.addWidget(pref_card)

        # 3. Media & Subtitle Preferences Card
        media_card = Card(title="Media & Subtitle Preferences")
        media_grid = QGridLayout()
        media_grid.setHorizontalSpacing(16)
        media_grid.setVerticalSpacing(12)
        media_grid.setColumnStretch(1, 1)
        media_grid.setColumnStretch(3, 1)

        # Row 0: Quality and Format
        lbl_q = QLabel("Default Quality:")
        lbl_q.setStyleSheet("font-weight: 600;")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(SUPPORTED_QUALITIES)

        lbl_f = QLabel("Default Format:")
        lbl_f.setStyleSheet("font-weight: 600;")
        self.format_combo = QComboBox()
        self.format_combo.addItems(SUPPORTED_FORMATS)

        media_grid.addWidget(lbl_q, 0, 0)
        media_grid.addWidget(self.quality_combo, 0, 1)
        media_grid.addWidget(lbl_f, 0, 2)
        media_grid.addWidget(self.format_combo, 0, 3)

        # Row 1: Video Codec and Audio Codec
        lbl_vc = QLabel("Default Video Codec:")
        lbl_vc.setStyleSheet("font-weight: 600;")
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(SUPPORTED_VIDEO_CODECS)

        lbl_ac = QLabel("Default Audio Codec:")
        lbl_ac.setStyleSheet("font-weight: 600;")
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(SUPPORTED_AUDIO_CODECS)

        media_grid.addWidget(lbl_vc, 1, 0)
        media_grid.addWidget(self.video_codec_combo, 1, 1)
        media_grid.addWidget(lbl_ac, 1, 2)
        media_grid.addWidget(self.audio_codec_combo, 1, 3)

        # Row 2: Subtitle preferences
        lbl_sub_lang = QLabel("Default Subtitle Language:")
        lbl_sub_lang.setStyleSheet("font-weight: 600;")
        self.sub_lang_combo = QComboBox()
        for name, code in SUPPORTED_SUBTITLE_LANGUAGES:
            self.sub_lang_combo.addItem(f"{name} ({code})", code)

        media_grid.addWidget(lbl_sub_lang, 2, 0)
        media_grid.addWidget(self.sub_lang_combo, 2, 1)

        media_toggles = QVBoxLayout()
        media_toggles.setSpacing(6)

        self.subtitles_default_check = QCheckBox("Enable subtitle download by default when available")
        self.auto_convert_check = QCheckBox("Enable automatic format/codec conversion when required")
        self.preserve_original_check = QCheckBox("Preserve original downloaded media file after format/codec conversion")

        media_toggles.addWidget(self.subtitles_default_check)
        media_toggles.addWidget(self.auto_convert_check)
        media_toggles.addWidget(self.preserve_original_check)

        media_box = QVBoxLayout()
        media_box.setSpacing(14)
        media_box.addLayout(media_grid)
        media_box.addLayout(media_toggles)
        media_card.add_layout(media_box)
        main_layout.addWidget(media_card)

        # 4. Performance & Processing Card
        perf_card = Card(title="Performance & Hardware Acceleration")
        perf_grid = QGridLayout()
        perf_grid.setHorizontalSpacing(16)
        perf_grid.setVerticalSpacing(12)
        perf_grid.setColumnStretch(1, 1)
        perf_grid.setColumnStretch(3, 1)

        # Timeout & Max concurrent conversions
        lbl_timeout = QLabel("Connection Timeout (s):")
        lbl_timeout.setStyleSheet("font-weight: 600;")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)

        lbl_max_conv = QLabel("Max Concurrent Conversions:")
        lbl_max_conv.setStyleSheet("font-weight: 600;")
        self.max_conv_spin = QSpinBox()
        self.max_conv_spin.setRange(1, 4)
        self.max_conv_spin.setValue(2)

        perf_grid.addWidget(lbl_timeout, 0, 0)
        perf_grid.addWidget(self.timeout_spin, 0, 1)
        perf_grid.addWidget(lbl_max_conv, 0, 2)
        perf_grid.addWidget(self.max_conv_spin, 0, 3)

        # Hardware Acceleration Selection
        lbl_hw = QLabel("Hardware Acceleration:")
        lbl_hw.setStyleSheet("font-weight: 600;")
        self.hw_accel_combo = QComboBox()
        self._populate_hw_accel_options()

        perf_grid.addWidget(lbl_hw, 1, 0)
        perf_grid.addWidget(self.hw_accel_combo, 1, 1, 1, 3)

        perf_card.add_layout(perf_grid)
        main_layout.addWidget(perf_card)

        # 5. Application Updates Card
        update_card = Card(title="Application Updates")
        update_layout = QVBoxLayout()
        update_layout.setSpacing(12)

        ver_row = QHBoxLayout()
        lbl_ver_title = QLabel("Installed Version:")
        lbl_ver_title.setStyleSheet("font-weight: 600;")

        self.ver_val = QLabel(f"v{APP_VERSION} (Current)")
        ver_row.addWidget(lbl_ver_title)
        ver_row.addWidget(self.ver_val)
        ver_row.addStretch()
        update_layout.addLayout(ver_row)

        action_update_row = QHBoxLayout()
        self.check_update_btn = QPushButton("🔍 Check for Updates")
        self.check_update_btn.setObjectName("secondaryButton")
        self.check_update_btn.setCursor(Qt.PointingHandCursor)
        self.check_update_btn.clicked.connect(self._on_check_updates_clicked)

        self.update_status_lbl = QLabel("")
        self.update_status_lbl.setStyleSheet("font-size: 12px;")

        action_update_row.addWidget(self.check_update_btn)
        action_update_row.addWidget(self.update_status_lbl)
        action_update_row.addStretch()
        update_layout.addLayout(action_update_row)

        update_card.add_layout(update_layout)
        main_layout.addWidget(update_card)

        # Action Buttons Footer
        footer_layout = QHBoxLayout()
        self.feedback_label = QLabel("")
        self.feedback_label.setStyleSheet("font-weight: 700; font-size: 13px;")

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("resetButton")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset_clicked)

        save_btn = QPushButton("Save Preferences")
        save_btn.setObjectName("saveButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save_clicked)

        footer_layout.addWidget(self.feedback_label)
        footer_layout.addStretch()
        footer_layout.addWidget(reset_btn)
        footer_layout.addWidget(save_btn)
        main_layout.addLayout(footer_layout)

        main_layout.addStretch()

        scroll_area.setWidget(container)
        root_layout.addWidget(scroll_area)
        self._update_colors()

    def _update_colors(self) -> None:
        p = theme_manager.get_palette()
        self.ver_val.setStyleSheet(f"font-weight: 700; color: {p['primary_accent']};")
        self.feedback_label.setStyleSheet(f"color: {p['primary_accent']}; font-weight: 700; font-size: 13px;")

    def _on_theme_changed(self, theme_name: str) -> None:
        self._update_colors()

    def _populate_hw_accel_options(self) -> None:
        self.hw_accel_combo.clear()
        self.hw_accel_combo.addItem("Auto (Software Encoding / CPU)", "cpu")
        detected = MediaInspector.detect_hardware_encoders()
        for enc in detected:
            self.hw_accel_combo.addItem(f"Hardware GPU ({enc})", enc)

    @staticmethod
    def _set_combo_choice(combo: QComboBox, value: Any, default: str = "Automatic") -> None:
        target = str(value).strip() if value is not None else default
        idx = combo.findText(target)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            def_idx = combo.findText(default)
            combo.setCurrentIndex(def_idx if def_idx >= 0 else 0)

    def load_values(self) -> None:
        settings = config.get_all()
        self.dir_input.setText(str(destination_manager.get_destination()))

        # Download Preferences Dropdowns
        self._set_combo_choice(self.concurrent_combo, settings.get("max_concurrent_downloads", "Automatic"))
        self._set_combo_choice(self.fragments_combo, settings.get("concurrent_fragments", "Automatic"))
        self._set_combo_choice(self.retry_combo, settings.get("retry_attempts", "Automatic"))
        self._set_combo_choice(self.retry_delay_combo, settings.get("retry_delay", "Automatic"))
        self.clipboard_monitor_check.setChecked(settings.get("clipboard_monitoring", False))
        self.auto_retry_check.setChecked(settings.get("auto_retry", True))

        # Media Preferences
        quality = settings.get("default_quality", "1080p (Full HD)")
        idx = self.quality_combo.findText(quality)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)

        fmt = settings.get("default_format", "MP4")
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

        vcodec = settings.get("default_video_codec") or settings.get("default_codec", "Keep Original Codec")
        idx_v = self.video_codec_combo.findText(vcodec)
        if idx_v >= 0:
            self.video_codec_combo.setCurrentIndex(idx_v)

        acodec = settings.get("default_audio_codec", "Keep Original")
        idx_a = self.audio_codec_combo.findText(acodec)
        if idx_a >= 0:
            self.audio_codec_combo.setCurrentIndex(idx_a)

        self.subtitles_default_check.setChecked(settings.get("subtitles_enabled", False))
        def_sub_lang = settings.get("subtitle_language", "en")
        idx_sl = self.sub_lang_combo.findData(def_sub_lang)
        if idx_sl >= 0:
            self.sub_lang_combo.setCurrentIndex(idx_sl)

        self.auto_convert_check.setChecked(settings.get("auto_conversion_enabled", True))
        self.preserve_original_check.setChecked(settings.get("preserve_original_video", False))

        # Performance
        self.timeout_spin.setValue(settings.get("connection_timeout", 30))
        self.max_conv_spin.setValue(settings.get("max_concurrent_conversions", 2))

    def _on_browse_clicked(self) -> None:
        current = self.dir_input.text() or str(destination_manager.get_destination())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Default Download Directory", current
        )
        if folder:
            ok, msg = destination_manager.set_destination(folder)
            if ok:
                self.dir_input.setText(msg)
                self.feedback_label.setText("✓ Download folder saved!")
                QTimer.singleShot(3000, lambda: self.feedback_label.setText(""))
            else:
                QMessageBox.warning(self, "Invalid Directory", f"Could not set download directory:\n{msg}")

    def _on_open_folder_clicked(self) -> None:
        try:
            p = destination_manager.get_destination()
        except DestinationError as e:
            QMessageBox.warning(self, "Folder Error", str(e))
            return
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{os.path.normpath(str(p))}"')
        else:
            subprocess.run(["xdg-open", str(p)])

    def _on_check_updates_clicked(self) -> None:
        repo = config.get("github_repo", DEFAULT_GITHUB_REPO)
        self.check_update_btn.setEnabled(False)
        self.update_status_lbl.setText("Connecting to GitHub Releases...")

        self._update_worker = CheckUpdateWorker(repo, self)
        self._update_worker.update_found.connect(self._on_update_found)
        self._update_worker.up_to_date.connect(self._on_up_to_date)
        self._update_worker.check_failed.connect(self._on_check_failed)
        self._update_worker.start()

    def _on_update_found(self, info: UpdateInfo) -> None:
        self.check_update_btn.setEnabled(True)
        self.update_status_lbl.setText(f"🎉 Update available: v{info.latest_version}")
        dlg = ReleaseNotesDialog(info, self)
        dlg.exec()

    def _on_up_to_date(self, info: UpdateInfo) -> None:
        self.check_update_btn.setEnabled(True)
        self.update_status_lbl.setText(f"✓ Downly is up to date (v{info.current_version}).")
        QMessageBox.information(
            self,
            "Up to Date",
            f"You are running the latest version of Downly (v{info.current_version})."
        )

    def _on_check_failed(self, error_msg: str) -> None:
        self.check_update_btn.setEnabled(True)
        self.update_status_lbl.setText(f"⚠️ Check failed: {error_msg[:45]}...")
        QMessageBox.warning(self, "Update Check Failed", f"Could not verify updates:\n{error_msg}")

    def _on_save_clicked(self) -> None:
        dest_dir = self.dir_input.text().strip()
        ok, msg = destination_manager.set_destination(dest_dir)
        if not ok:
            QMessageBox.warning(self, "Invalid Directory", f"Could not access or set folder:\n{msg}")
            return

        config.set("default_quality", self.quality_combo.currentText())
        config.set("default_format", self.format_combo.currentText())
        config.set("default_video_codec", self.video_codec_combo.currentText())
        config.set("default_codec", self.video_codec_combo.currentText())
        config.set("default_audio_codec", self.audio_codec_combo.currentText())

        # Download Preferences
        config.set("max_concurrent_downloads", self.concurrent_combo.currentText())
        config.set("retry_attempts", self.retry_combo.currentText())
        config.set("retry_delay", self.retry_delay_combo.currentText())
        config.set("concurrent_fragments", self.fragments_combo.currentText())
        config.set("clipboard_monitoring", self.clipboard_monitor_check.isChecked())
        config.set("auto_retry", self.auto_retry_check.isChecked())

        # Media Preferences
        config.set("subtitles_enabled", self.subtitles_default_check.isChecked())
        config.set("subtitle_language", self.sub_lang_combo.currentData() or "en")
        config.set("auto_conversion_enabled", self.auto_convert_check.isChecked())
        config.set("preserve_original_video", self.preserve_original_check.isChecked())

        # Performance
        config.set("connection_timeout", self.timeout_spin.value())
        config.set("max_concurrent_conversions", self.max_conv_spin.value())
        config.set("hardware_acceleration", self.hw_accel_combo.currentData())

        download_manager.set_max_concurrent(self.concurrent_combo.currentText())
        clipboard_monitor.update_state()

        self.feedback_label.setText("✓ Preferences saved successfully")
        QTimer.singleShot(3000, lambda: self.feedback_label.setText(""))
        self.settings_updated.emit()

    def _on_reset_clicked(self) -> None:
        config.reset_to_defaults()
        self.load_values()
        download_manager.set_max_concurrent(self.concurrent_combo.currentText())
        clipboard_monitor.update_state()
        self.feedback_label.setText("✓ Reset to defaults")
        QTimer.singleShot(3000, lambda: self.feedback_label.setText(""))
        self.settings_updated.emit()
