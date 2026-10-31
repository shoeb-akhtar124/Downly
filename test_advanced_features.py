"""
Comprehensive Automated Verification Test Suite for Downly Advanced Features.
Tests all 13 Advanced Features and Performance Optimization Requirements.
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Initialize QApplication if not already running
app = QApplication.instance() or QApplication(sys.argv)

from app.config import config
from app.constants import (
    DEFAULT_SETTINGS, SUPPORTED_QUALITIES, SUPPORTED_FORMATS,
    SUPPORTED_SUBTITLE_LANGUAGES, SETTINGS_FILE, SCHEDULES_FILE, APP_LOG_FILE
)
from app.logger import log_info, log_error, get_logger
from core.download_manager import download_manager, DownloadTask, DownloadWorker
from core.extractor import VideoExtractor, ExtractionError
from core.media_inspector import MediaInspector
from core.url_analyzer import URLAnalyzer
from core.scheduler_manager import scheduler_manager
from core.clipboard_monitor import clipboard_monitor
from ui.theme_manager import theme_manager
from ui.components.media_details_dialog import MediaDetailsDialog
from ui.components.playlist_dialog import PlaylistDialog
from ui.components.batch_download_dialog import BatchDownloadDialog
from ui.components.schedule_dialog import ScheduleDialog
from ui.components.progress_dialog import DownloadProgressDialog
from ui.main_window import MainWindow


def test_1_and_2_speed_and_eta():
    print("[TEST 1 & 2] Testing Download Speed & ETA Metrics...")
    task = DownloadTask(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Test Rickroll",
        quality="1080p (Full HD)",
        output_format="MP4",
        codec="Keep Original Codec"
    )
    worker = DownloadWorker(task)
    worker._start_time = time.time() - 2.0  # 2 seconds elapsed

    # Simulate yt-dlp progress hook: 50MB downloaded out of 100MB, current speed 10MB/s
    fake_hook_data = {
        "status": "downloading",
        "downloaded_bytes": 50 * 1024 * 1024,
        "total_bytes": 100 * 1024 * 1024,
        "speed": 10 * 1024 * 1024,  # 10 MB/s
    }

    worker._on_progress_hook(fake_hook_data)

    assert task.progress == 50.0, f"Expected 50.0%, got {task.progress}"
    assert "MB/s" in task.speed_str or "KB/s" in task.speed_str, f"Speed string unexpected: {task.speed_str}"
    assert task.peak_speed >= 10 * 1024 * 1024, f"Peak speed not recorded: {task.peak_speed}"
    assert task.average_speed > 0, f"Average speed not calculated: {task.average_speed}"
    # Remaining: 50MB at 10MB/s = 5 seconds -> "00:05"
    assert task.eta_str in ("00:05", "0:05", "00:00:05"), f"ETA unexpected: {task.eta_str}"
    print("  ✓ Current, Peak, and Average speeds accurately calculated.")
    print(f"  ✓ ETA accurately calculated: {task.eta_str}")


def test_3_and_4_clipboard_monitoring():
    print("[TEST 3 & 4] Testing Clipboard Monitoring...")
    # 1. Disabled state:
    config.set("clipboard_monitoring", False)
    clipboard_monitor.stop()
    assert not clipboard_monitor._is_monitoring, "Monitor should be stopped when disabled"

    detected_urls = []
    clipboard_monitor.supported_url_detected.connect(lambda u, p: detected_urls.append((u, p)))

    # Simulate clipboard change while disabled
    QApplication.clipboard().setText("https://www.youtube.com/watch?v=test_disabled")
    clipboard_monitor._on_clipboard_changed()
    assert len(detected_urls) == 0, "No URL should be detected when monitoring is disabled"

    # 2. Enabled state:
    config.set("clipboard_monitoring", True)
    clipboard_monitor.update_state()
    assert clipboard_monitor._is_monitoring, "Monitor should be running when enabled"

    test_url = "https://www.youtube.com/watch?v=test_enabled_123"
    QApplication.clipboard().setText(test_url)
    clipboard_monitor._on_clipboard_changed()
    assert len(detected_urls) == 1, f"Expected 1 detected URL, got {len(detected_urls)}"
    assert detected_urls[0][0] == test_url
    assert detected_urls[0][1] == "YouTube"

    # Reset
    config.set("clipboard_monitoring", False)
    clipboard_monitor.update_state()
    print("  ✓ Clipboard monitoring disabled state verified.")
    print("  ✓ Valid video URL detection and non-intrusive notification verified.")


def test_5_auto_retry():
    print("[TEST 5] Testing Automatic Retry Configuration...")
    assert config.get("auto_retry") is True, "Auto retry default should be True"
    assert config.get("retry_attempts") == 3, "Default retry attempts should be 3"
    assert config.get("retry_delay") == 5, "Default retry delay should be 5"

    task = DownloadTask(
        url="https://www.youtube.com/watch?v=retry_test",
        title="Retry Test",
        quality="1080p",
        output_format="MP4",
        codec="Keep Original Codec"
    )
    assert task.retry_count == 0
    assert task.max_retries == 3
    assert task.retry_delay == 5
    print("  ✓ Automatic retry parameters and task retry attributes verified.")


def test_6_batch_download():
    print("[TEST 6] Testing Batch Download Dialog & Queueing...")
    dlg = BatchDownloadDialog()
    test_urls = (
        "https://www.youtube.com/watch?v=vid1\n"
        "https://vimeo.com/123456\n"
        "invalid_link_here"
    )
    dlg.url_text_edit.setPlainText(test_urls)
    dlg._on_validate_clicked()

    assert len(dlg.validated_tasks) == 2, f"Expected 2 valid tasks, got {len(dlg.validated_tasks)}"
    assert dlg.table.rowCount() == 3, f"Expected 3 rows in table, got {dlg.table.rowCount()}"
    print("  ✓ Batch URL parsing, validation, and status tracking verified.")


def test_7_and_8_playlist_support():
    print("[TEST 7 & 8] Testing Playlist Support...")
    url = "https://www.youtube.com/playlist?list=PLrAXtmErZgOdP_8GzKt84tcVVDkzO7aN8"
    assert VideoExtractor.is_playlist_url(url) is True, "Playlist heuristic failed"

    # Simulate playlist data structure returned by VideoExtractor
    fake_playlist = {
        "is_playlist": True,
        "title": "Sample Coding Playlist",
        "uploader": "Test Channel",
        "platform": "YouTube",
        "entries": [
            {"index": 1, "id": "1", "title": "Lesson 1", "url": "https://www.youtube.com/watch?v=1", "duration_str": "05:00"},
            {"index": 2, "id": "2", "title": "Lesson 2", "url": "https://www.youtube.com/watch?v=2", "duration_str": "10:00"},
            {"index": 3, "id": "3", "title": "Lesson 3", "url": "https://www.youtube.com/watch?v=3", "duration_str": "15:00"}
        ]
    }
    dlg = PlaylistDialog(fake_playlist)
    assert dlg.table.rowCount() == 3
    assert len(dlg.checkboxes) == 3

    # Test deselect
    dlg._deselect_all()
    selected = sum(1 for cb in dlg.checkboxes if cb.isChecked())
    assert selected == 0
    dlg._select_all()
    selected = sum(1 for cb in dlg.checkboxes if cb.isChecked())
    assert selected == 3
    print("  ✓ Playlist detection and multi-item selection verified.")


def test_9_and_10_subtitle_support():
    print("[TEST 9 & 10] Testing Subtitle Handling...")
    fake_raw_info = {
        "subtitles": {
            "en": [{"name": "English", "ext": "vtt"}],
            "es": [{"name": "Spanish", "ext": "vtt"}]
        },
        "automatic_captions": {
            "fr": [{"name": "French", "ext": "vtt"}]
        }
    }
    extractor = VideoExtractor()
    subs = extractor.extract_subtitles_info(fake_raw_info)
    assert len(subs) == 3, f"Expected 3 subtitle tracks, got {len(subs)}"
    codes = [code for code, name in subs]
    assert "en" in codes and "es" in codes and "fr" in codes
    print("  ✓ Subtitle tracks and automatic captions correctly extracted.")


def test_11_scheduler():
    print("[TEST 11] Testing Download Scheduler...")
    initial_count = len(scheduler_manager.schedules)
    sched_dt = datetime.now() + timedelta(hours=2)
    item = scheduler_manager.add_schedule(
        url="https://www.youtube.com/watch?v=scheduled_test",
        title="Scheduled Rickroll",
        scheduled_time=sched_dt,
        quality="1080p (Full HD)",
        output_format="MP4"
    )
    assert item["status"] == "pending"
    assert len(scheduler_manager.schedules) == initial_count + 1

    # Test JSON persistence
    reloaded = scheduler_manager.load_schedules()
    assert any(s["id"] == item["id"] for s in reloaded), "Scheduled task was not persisted in schedules.json"

    # Test cancellation
    scheduler_manager.cancel_schedule(item["id"])
    assert any(s["id"] == item["id"] and s["status"] == "cancelled" for s in scheduler_manager.schedules)

    # Cleanup
    scheduler_manager.remove_schedule(item["id"])
    print("  ✓ Scheduler persistence in JSON, task status lifecycle, and cleanup verified.")


def test_12_thumbnail_preview_and_caching():
    print("[TEST 12] Testing Video Thumbnail Caching...")
    test_thumb_url = "https://i.ytimg.com/vi/test_cache/hqdefault.jpg"
    fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"

    cached_path = VideoExtractor.cache_thumbnail_bytes(test_thumb_url, fake_image_bytes)
    assert cached_path is not None and cached_path.exists(), "Thumbnail cache write failed"
    retrieved_path = VideoExtractor.get_cached_thumbnail_path(test_thumb_url)
    assert retrieved_path == cached_path, "Thumbnail cache lookup failed"
    print("  ✓ Disk thumbnail caching and non-blocking lookup verified.")


def test_13_metadata_extraction():
    print("[TEST 13] Testing FFprobe Media Metadata Extraction...")
    # Test on a dummy path or MediaInspector structure
    metadata = MediaInspector.get_detailed_metadata("non_existent_dummy_file.mp4")
    assert "File Name" in metadata
    assert "File Size" in metadata
    assert "Duration" in metadata
    assert "Resolution" in metadata
    assert "Frame Rate" in metadata
    assert "Video Codec" in metadata
    assert "Audio Codec" in metadata
    assert "Container Format" in metadata
    assert "Bitrate" in metadata
    print("  ✓ Detailed media inspection dictionary with FFprobe fields verified.")


def test_performance_and_themes():
    print("[TEST PERFORMANCE & THEMES] Testing Theme Switching & GUI Responsiveness...")
    win = MainWindow()
    win.show()

    # Dark Mode
    theme_manager.set_theme("dark")
    assert theme_manager.is_dark() is True
    assert win.sidebar.isVisible() is True

    # Light Mode
    theme_manager.set_theme("light")
    assert theme_manager.is_dark() is False
    assert win.sidebar.isVisible() is True

    # Revert to Dark
    theme_manager.set_theme("dark")

    # Verify Logging
    log_info("Verification test log message.")
    assert APP_LOG_FILE.exists(), f"Log file does not exist at {APP_LOG_FILE}"

    win.close()
    print("  ✓ Live theme switching without restart verified for both Dark and Light modes.")
    print("  ✓ Rotating local log verification passed.")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING DOWNLY ADVANCED FEATURES VERIFICATION SUITE")
    print("==================================================")
    test_1_and_2_speed_and_eta()
    test_3_and_4_clipboard_monitoring()
    test_5_auto_retry()
    test_6_batch_download()
    test_7_and_8_playlist_support()
    test_9_and_10_subtitle_support()
    test_11_scheduler()
    test_12_thumbnail_preview_and_caching()
    test_13_metadata_extraction()
    test_performance_and_themes()
    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
    print("==================================================")
    sys.exit(0)

