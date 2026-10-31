"""
Downloader Page.
Contains URL input, format/codec selectors, subtitle selectors, video preview card,
batch downloader trigger, schedule trigger, playlist support, and download triggers.
Cleaned up according to user specifications (Speed/ETA, Platform/Duration/Author, and Source info bar removed).
"""
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QProgressBar, QGridLayout, QApplication, QMessageBox,
    QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage

from app.config import config
from app.constants import (
    SUPPORTED_QUALITIES, SUPPORTED_FORMATS, SUPPORTED_VIDEO_CODECS,
    SUPPORTED_CODECS, SUPPORTED_AUDIO_CODECS, SUPPORTED_SUBTITLE_LANGUAGES
)
from core.download_manager import download_manager, DownloadTask
from core.extractor import VideoExtractor, ExtractionError
from core.format_selector import FormatSelector
from core.url_analyzer import URLAnalyzer
from core.download_destination import destination_manager, DestinationError
from ui.theme_manager import theme_manager
from ui.components.card import Card
from ui.components.progress_dialog import DownloadProgressDialog
from ui.components.playlist_dialog import PlaylistDialog
from ui.components.batch_download_dialog import BatchDownloadDialog
from ui.components.schedule_dialog import ScheduleDialog


class AnalyzeWorker(QThread):
    """Background worker thread for URL analysis."""
    success = Signal(dict)
    failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            extractor = VideoExtractor()
            info = extractor.extract_info(self.url)
            self.success.emit(info)
        except ExtractionError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Unexpected error analyzing URL: {str(e)}")


class ThumbnailLoaderWorker(QThread):
    """Background worker thread for downloading and caching video thumbnail."""
    loaded = Signal(QPixmap)

    def __init__(self, thumb_url: str):
        super().__init__()
        self.thumb_url = thumb_url

    def run(self):
        try:
            # Check local disk cache first
            cached_path = VideoExtractor.get_cached_thumbnail_path(self.thumb_url)
            if cached_path and cached_path.exists():
                pixmap = QPixmap(str(cached_path))
                if not pixmap.isNull():
                    self.loaded.emit(pixmap)
                    return

            # Download and cache
            req = urllib.request.Request(
                self.thumb_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()

            VideoExtractor.cache_thumbnail_bytes(self.thumb_url, data)
            image = QImage()
            if image.loadFromData(data):
                pixmap = QPixmap.fromImage(image)
                self.loaded.emit(pixmap)
        except Exception as e:
            print(f"[ThumbnailLoaderWorker] Could not load thumbnail: {e}")


class DownloaderPage(QWidget):
    """Primary view for analyzing media URLs and launching downloads."""

    analyze_requested = Signal(str)
    download_requested = Signal(dict)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.current_video_info: Optional[Dict[str, Any]] = None
        self.active_task_id: Optional[str] = None
        self._analyze_worker: Optional[AnalyzeWorker] = None
        self._thumbnail_worker: Optional[ThumbnailLoaderWorker] = None

        self._setup_ui()
        self._connect_signals()
        self.apply_defaults()
        self._update_theme_styles()
        theme_manager.theme_changed.connect(lambda _: self._update_theme_styles())

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
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Section with Quick Action Buttons
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        page_title = QLabel("Video Downloader")
        page_title.setObjectName("pageTitle")
        header_text.addWidget(page_title)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        # Batch & Scheduler Shortcuts
        btn_batch = QPushButton("📦 Batch Download")
        btn_batch.setObjectName("batchButton")
        btn_batch.setCursor(Qt.PointingHandCursor)
        btn_batch.clicked.connect(self._open_batch_dialog)

        btn_schedule = QPushButton("⏰ Schedule")
        btn_schedule.setObjectName("scheduleButton")
        btn_schedule.setCursor(Qt.PointingHandCursor)
        btn_schedule.clicked.connect(self._open_schedule_dialog)

        # Header Theme Toggle (Requirement 3: kept here)
        self.theme_toggle_btn = QPushButton("☀️ Light Mode" if theme_manager.is_dark() else "🌙 Dark Mode")
        self.theme_toggle_btn.setObjectName("themeToggleButton")
        self.theme_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_btn.setToolTip("Switch to Light Mode" if theme_manager.is_dark() else "Switch to Dark Mode")
        self.theme_toggle_btn.clicked.connect(self._toggle_theme)

        header_layout.addWidget(btn_batch)
        header_layout.addWidget(btn_schedule)
        header_layout.addWidget(self.theme_toggle_btn)
        main_layout.addLayout(header_layout)

        # 1. URL Input Card
        url_card = Card(title="Video URL")
        url_layout = QHBoxLayout()
        url_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._on_analyze_clicked)

        paste_btn = QPushButton("📋 Paste")
        paste_btn.setObjectName("pasteButton")
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.clicked.connect(self._on_paste_clicked)

        clear_btn = QPushButton("✕ Clear")
        clear_btn.setObjectName("clearButton")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear_clicked)

        self.analyze_btn = QPushButton("🔍 Analyze URL")
        self.analyze_btn.setObjectName("analyzeButton")
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._on_analyze_clicked)

        url_layout.addWidget(self.url_input, stretch=1)
        url_layout.addWidget(paste_btn)
        url_layout.addWidget(clear_btn)
        url_layout.addWidget(self.analyze_btn)
        url_card.add_layout(url_layout)

        main_layout.addWidget(url_card)

        # 2. Video Preview & Options Card
        self.preview_card = Card(title="Video Information & Output Options")

        preview_grid = QGridLayout()
        preview_grid.setHorizontalSpacing(16)
        preview_grid.setVerticalSpacing(12)

        # Left side: Thumbnail Placeholder
        self.thumbnail_box = QLabel("No Video Analyzed")
        self.thumbnail_box.setFixedSize(220, 130)
        self.thumbnail_box.setAlignment(Qt.AlignCenter)
        self.thumbnail_box.setStyleSheet(
            "background-color: #111513; border: 1.5px dashed #29332E; "
            "border-radius: 8px; color: #A0AAA4; font-weight: 500;"
        )
        preview_grid.addWidget(self.thumbnail_box, 0, 0, 3, 1)

        # Right side: Video Title
        self.title_label = QLabel("Title: Waiting for URL analysis...")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #F5F7F6;")
        preview_grid.addWidget(self.title_label, 0, 1, 1, 3)

        # Format & Codec Selectors Row
        selectors_layout = QHBoxLayout()
        selectors_layout.setSpacing(12)

        # Quality
        quality_box = QVBoxLayout()
        quality_box.setSpacing(4)
        self.lbl_quality = QLabel("Quality")
        self.lbl_quality.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(SUPPORTED_QUALITIES)
        quality_box.addWidget(self.lbl_quality)
        quality_box.addWidget(self.quality_combo)
        selectors_layout.addLayout(quality_box)

        # Format
        format_box = QVBoxLayout()
        format_box.setSpacing(4)
        self.lbl_format = QLabel("Output Format")
        self.lbl_format.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.format_combo = QComboBox()
        self.format_combo.addItems(SUPPORTED_FORMATS)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        format_box.addWidget(self.lbl_format)
        format_box.addWidget(self.format_combo)
        selectors_layout.addLayout(format_box)

        # Codec
        codec_box = QVBoxLayout()
        codec_box.setSpacing(4)
        self.lbl_codec = QLabel("Video Codec")
        self.lbl_codec.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(SUPPORTED_CODECS)
        codec_box.addWidget(self.lbl_codec)
        codec_box.addWidget(self.codec_combo)
        selectors_layout.addLayout(codec_box)

        preview_grid.addLayout(selectors_layout, 1, 1, 1, 3)

        # Subtitles Row
        sub_layout = QHBoxLayout()
        sub_layout.setSpacing(12)

        self.subtitles_check = QCheckBox("Download Subtitles")
        self.subtitles_check.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.subtitles_check.stateChanged.connect(self._on_subtitles_toggled)

        self.sub_lang_combo = QComboBox()
        for name, code in SUPPORTED_SUBTITLE_LANGUAGES:
            self.sub_lang_combo.addItem(f"{name} ({code})", code)
        self.sub_lang_combo.setEnabled(False)

        self.sub_mode_combo = QComboBox()
        self.sub_mode_combo.addItem("Separate File (.srt/.vtt)", "sidecar")
        self.sub_mode_combo.addItem("Embed into Video", "embed")
        self.sub_mode_combo.addItem("Subtitles Only (No Video)", "only")
        self.sub_mode_combo.setEnabled(False)

        sub_layout.addWidget(self.subtitles_check)
        sub_layout.addWidget(QLabel("Language:"))
        sub_layout.addWidget(self.sub_lang_combo)
        sub_layout.addWidget(QLabel("Mode:"))
        sub_layout.addWidget(self.sub_mode_combo)
        sub_layout.addStretch()

        preview_grid.addLayout(sub_layout, 2, 1, 1, 3)

        # Download Action Button (Always displays icon and word 'Download')
        self.download_btn = QPushButton("⬇️ Download")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setFixedHeight(44)
        self.download_btn.clicked.connect(self._on_download_clicked)
        preview_grid.addWidget(self.download_btn, 3, 1, 1, 3)

        self.preview_card.add_layout(preview_grid)
        main_layout.addWidget(self.preview_card)

        # 3. Current Activity Card
        self.activity_card = Card(title="Download Status")
        activity_layout = QVBoxLayout()
        activity_layout.setSpacing(8)

        status_header = QHBoxLayout()
        self.status_text = QLabel("Ready for input. Paste a URL to begin.")
        self.status_text.setStyleSheet("font-size: 13px; color: #F5F7F6; font-weight: 500;")

        self.open_dialog_btn = QPushButton("🔍 Progress Window")
        self.open_dialog_btn.setObjectName("actionButton")
        self.open_dialog_btn.setCursor(Qt.PointingHandCursor)
        self.open_dialog_btn.clicked.connect(self._on_open_progress_dialog)

        status_header.addWidget(self.status_text)
        status_header.addStretch()
        status_header.addWidget(self.open_dialog_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        activity_layout.addLayout(status_header)
        activity_layout.addWidget(self.progress_bar)

        self.activity_card.add_layout(activity_layout)
        main_layout.addWidget(self.activity_card)
        main_layout.addStretch()

        scroll_area.setWidget(container)
        root_layout.addWidget(scroll_area)

    def _toggle_theme(self) -> None:
        theme_manager.toggle_theme()

    def _update_theme_styles(self) -> None:
        """Update dynamic colors for labels, buttons, and thumbnail when theme toggles."""
        p = theme_manager.get_palette()
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.setText("☀️ Light Mode" if theme_manager.is_dark() else "🌙 Dark Mode")
            self.theme_toggle_btn.setToolTip("Switch to Light Mode" if theme_manager.is_dark() else "Switch to Dark Mode")
        if not self.thumbnail_box.pixmap():
            self.thumbnail_box.setStyleSheet(
                f"background-color: {p['input_bg']}; border: 1.5px dashed {p['borders']}; "
                f"border-radius: 8px; color: {p['secondary_text']}; font-weight: 500;"
            )
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {p['main_text']};")
        self.status_text.setStyleSheet(f"font-size: 13px; color: {p['main_text']}; font-weight: 500;")
        if hasattr(self, "lbl_quality"):
            self.lbl_quality.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        if hasattr(self, "lbl_format"):
            self.lbl_format.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        if hasattr(self, "lbl_codec"):
            self.lbl_codec.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")

    def _connect_signals(self) -> None:
        """Connect download manager events to update status card."""
        download_manager.task_progress.connect(self._on_manager_progress)
        download_manager.task_extended_progress.connect(self._on_manager_extended_progress)
        download_manager.task_status_changed.connect(self._on_manager_status)
        download_manager.task_completed.connect(self._on_manager_completed)
        download_manager.task_failed.connect(self._on_manager_failed)

    def apply_defaults(self) -> None:
        """Apply default configuration options from settings."""
        settings = config.get_all()
        q = settings.get("default_quality", "1080p (Full HD)")
        idx_q = self.quality_combo.findText(q)
        if idx_q >= 0:
            self.quality_combo.setCurrentIndex(idx_q)

        fmt = settings.get("default_format", "MP4")
        idx_f = self.format_combo.findText(fmt)
        if idx_f >= 0:
            self.format_combo.setCurrentIndex(idx_f)

        codec = settings.get("default_video_codec", "Keep Original Codec")
        idx_c = self.codec_combo.findText(codec)
        if idx_c >= 0:
            self.codec_combo.setCurrentIndex(idx_c)

        subs_enabled = settings.get("subtitles_enabled", False)
        self.subtitles_check.setChecked(subs_enabled)
        self._on_subtitles_toggled(subs_enabled)

    def _on_subtitles_toggled(self, checked: bool) -> None:
        self.sub_lang_combo.setEnabled(bool(checked))
        self.sub_mode_combo.setEnabled(bool(checked))

    def _on_format_changed(self, fmt_text: str) -> None:
        """Adapt codec controls if audio-only format is chosen."""
        is_audio = "MP3" in fmt_text.upper()
        self.codec_combo.setEnabled(not is_audio)
        if is_audio:
            self.lbl_codec.setText("Video Codec (N/A for MP3)")
        else:
            self.lbl_codec.setText("Video Codec")

    def _on_paste_clicked(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_input.setText(text.strip())

    def _on_clear_clicked(self) -> None:
        self.url_input.clear()
        self.current_video_info = None
        self.title_label.setText("Title: Waiting for URL analysis...")
        self.thumbnail_box.clear()
        self.thumbnail_box.setText("No Video Analyzed")
        p = theme_manager.get_palette()
        self.thumbnail_box.setStyleSheet(
            f"background-color: {p['input_bg']}; border: 1.5px dashed {p['borders']}; "
            f"border-radius: 8px; color: {p['secondary_text']}; font-weight: 500;"
        )
        self.quality_combo.clear()
        self.quality_combo.addItems(SUPPORTED_QUALITIES)
        self.apply_defaults()
        self.status_text.setText("Ready for input. Paste a URL to begin.")
        self.progress_bar.setValue(0)

    def _on_analyze_clicked(self) -> None:
        raw_url = self.url_input.text().strip()
        if not raw_url:
            self.status_text.setText("⚠️ Please enter or paste a valid video URL.")
            return

        normalized = URLAnalyzer.normalize_url(raw_url)
        if not URLAnalyzer.is_valid_url(normalized):
            self.status_text.setText("⚠️ Invalid URL. Please provide a complete web address.")
            return

        platform_hint = URLAnalyzer.detect_platform(normalized)
        self.status_text.setText(f"🔍 Analyzing {platform_hint} media...")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("⏳ Analyzing...")

        self._analyze_worker = AnalyzeWorker(normalized)
        self._analyze_worker.success.connect(self._on_analysis_success)
        self._analyze_worker.failed.connect(self._on_analysis_failed)
        self._analyze_worker.start()

    def _on_analysis_success(self, info: Dict[str, Any]) -> None:
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍 Analyze URL")
        self.current_video_info = info

        # If playlist detected, offer to open playlist dialog
        if info.get("is_playlist"):
            self.title_label.setText(f"Playlist: {info.get('title', 'Unknown')}")
            self.status_text.setText(f"✓ Playlist detected: {info.get('item_count')} items ready.")

            # Load first thumbnail
            thumb_url = info.get("thumbnail")
            if thumb_url:
                self._thumbnail_worker = ThumbnailLoaderWorker(thumb_url)
                self._thumbnail_worker.loaded.connect(self._on_thumbnail_loaded)
                self._thumbnail_worker.start()

            # Open PlaylistDialog
            dlg = PlaylistDialog(info, self)
            dlg.exec()
            return

        # Single video analysis
        self.title_label.setText(f"Title: {info.get('title', 'Unknown')}")
        self.status_text.setText(f"✓ Video analyzed successfully: {info.get('title')[:50]}...")

        # Update Quality dropdown with genuine available formats
        formats = info.get("formats", [])
        avail_qualities = FormatSelector.get_available_qualities(formats)
        self.quality_combo.clear()
        self.quality_combo.addItems(avail_qualities)

        default_pref = config.get("default_quality", "1080p (Full HD)")
        idx = self.quality_combo.findText(default_pref)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        else:
            self.quality_combo.setCurrentIndex(0)

        # Update available subtitles if present
        subs = info.get("subtitles", [])
        if subs:
            self.sub_lang_combo.clear()
            for code, name in subs:
                self.sub_lang_combo.addItem(name, code)

        # Asynchronously load cached thumbnail
        thumb_url = info.get("thumbnail")
        if thumb_url:
            self.thumbnail_box.setText("Loading preview...")
            self._thumbnail_worker = ThumbnailLoaderWorker(thumb_url)
            self._thumbnail_worker.loaded.connect(self._on_thumbnail_loaded)
            self._thumbnail_worker.start()
        else:
            self.thumbnail_box.setText("No Preview")

    def _on_analysis_failed(self, error_message: str) -> None:
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍 Analyze URL")
        self.status_text.setText(f"⚠️ {error_message}")
        QMessageBox.warning(self, "Analysis Failed", error_message)

    def _on_thumbnail_loaded(self, pixmap: QPixmap) -> None:
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_box.width(),
                self.thumbnail_box.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.thumbnail_box.setPixmap(scaled)
            self.thumbnail_box.setStyleSheet(
                "border: 1px solid #29332E; border-radius: 8px; background-color: #080B0A;"
            )

    def _open_batch_dialog(self) -> None:
        dlg = BatchDownloadDialog(self)
        dlg.exec()

    def _open_schedule_dialog(self) -> None:
        url = self.url_input.text().strip()
        title = self.title_label.text().replace("Title: ", "") if self.current_video_info else ""
        dlg = ScheduleDialog(initial_url=url, initial_title=title, parent=self)
        dlg.exec()

    def _on_open_progress_dialog(self) -> None:
        if self.active_task_id and self.active_task_id in download_manager.tasks:
            task = download_manager.tasks[self.active_task_id]
            dlg = DownloadProgressDialog(task, self)
            dlg.exec()
        else:
            tasks = list(download_manager.tasks.values())
            if tasks:
                dlg = DownloadProgressDialog(tasks[-1], self)
                dlg.exec()
            else:
                QMessageBox.information(self, "No Active Task", "There is no active download to inspect.")

    def _on_download_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.status_text.setText("⚠️ Please provide a video URL first.")
            return

        normalized = URLAnalyzer.normalize_url(url)
        quality = self.quality_combo.currentText()
        out_format = self.format_combo.currentText()
        codec = self.codec_combo.currentText()

        title = "Video Download"
        platform = URLAnalyzer.detect_platform(normalized)
        thumbnail = ""
        if self.current_video_info and self.current_video_info.get("url") == normalized:
            title = self.current_video_info.get("title", title)
            platform = self.current_video_info.get("platform", platform)
            thumbnail = self.current_video_info.get("thumbnail", "")

        # Subtitle preferences
        want_subs = self.subtitles_check.isChecked()
        sub_lang = self.sub_lang_combo.currentData() or "en"
        sub_mode = self.sub_mode_combo.currentData() or "sidecar"
        embed_subs = (sub_mode == "embed")
        sub_only = (sub_mode == "only")

        self.progress_bar.setValue(0)
        self.status_text.setText(f"Initiating download: {title[:50]}...")

        try:
            target_dest = destination_manager.get_destination()
        except DestinationError as e:
            self.status_text.setText(f"⚠️ Destination error: {e}")
            QMessageBox.warning(self, "Download Folder Error", str(e))
            return

        audio_codec = config.get("default_audio_codec", "Keep Original")
        task = download_manager.add_download(
            url=normalized,
            title=title,
            quality=quality,
            output_format=out_format,
            codec=codec,
            thumbnail=thumbnail,
            platform=platform,
            download_dir=str(target_dest),
            audio_codec=audio_codec,
            subtitles=want_subs,
            subtitle_lang=sub_lang,
            embed_subtitles=embed_subs,
            subtitle_only=sub_only
        )
        self.active_task_id = task.task_id

    def _on_manager_progress(self, task_id: str, percent: float, speed: str, eta: str) -> None:
        if self.active_task_id == task_id:
            self.progress_bar.setValue(int(percent))

    def _on_manager_extended_progress(
        self, task_id: str, percent: float, speed: str, avg: str, peak: str, eta: str
    ) -> None:
        if self.active_task_id == task_id:
            self.progress_bar.setValue(int(percent))

    def _on_manager_status(self, task_id: str, status: str, message: str) -> None:
        if self.active_task_id == task_id:
            self.status_text.setText(f"Status [{status}]: {message}")

    def _on_manager_completed(self, task: DownloadTask) -> None:
        if self.active_task_id == task.task_id:
            self.progress_bar.setValue(100)
            self.status_text.setText(f"✓ Download Completed: {Path(task.final_file_path).name} ({task.file_size_str})")

    def _on_manager_failed(self, task_id: str, error_msg: str) -> None:
        if self.active_task_id == task_id:
            self.status_text.setText(f"❌ Error: {error_msg}")
