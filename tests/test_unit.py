"""
Unit Test Suite for Downly.
Tests:
1. URL validation & normalization (YouTube, Vimeo, Twitter, TikTok, Instagram, Reddit, Facebook, Generic)
2. Download queue management & states
3. Auto-retry logic (recoverable vs permanent errors)
4. Settings persistence (JSON storage outside install dir)
5. Metadata extraction (FFprobe inspection)
6. Scheduler logic (storage, triggers, missed schedules)
7. Clipboard monitoring (state toggling, URL detection, ignoring junk)
8. Speed & ETA calculation
9. History manager persistence
"""
import os
import sys
import json
import time
import shutil
import unittest
from unittest import mock
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication

# Ensure QApplication singleton exists for PySide6 signals/widgets
app = QApplication.instance() or QApplication(sys.argv)

from app.constants import (
    DEFAULT_SETTINGS, SETTINGS_FILE, HISTORY_FILE, SCHEDULES_FILE,
    USER_STORAGE_DIR, USER_DOWNLOADS_DIR, SUPPORTED_QUALITIES, SUPPORTED_FORMATS
)
from app.config import ConfigManager, config
from app.logger import get_logger, log_info, log_error
from core.url_analyzer import URLAnalyzer
from core.download_manager import (
    DownloadManager, DownloadTask, DownloadWorker, PERMANENT_ERRORS,
    resolve_retry_attempts, resolve_retry_delay
)
from core.media_inspector import MediaInspector
from core.extractor import VideoExtractor, ExtractionError
from core.scheduler_manager import SchedulerManager, scheduler_manager
from core.clipboard_monitor import ClipboardMonitor, clipboard_monitor
from storage.history_manager import HistoryManager, history_manager


class TestURLValidation(unittest.TestCase):
    """Test URL Analyzer validation, normalization, and platform identification."""

    def test_valid_urls(self):
        valid_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "YouTube"),
            ("https://youtu.be/dQw4w9WgXcQ", "YouTube"),
            ("https://vimeo.com/76979871", "Vimeo"),
            ("https://twitter.com/user/status/1234567890", "X / Twitter"),
            ("https://x.com/user/status/1234567890", "X / Twitter"),
            ("https://www.tiktok.com/@user/video/1234567890", "TikTok"),
            ("https://www.instagram.com/reel/C123456/", "Instagram"),
            ("https://www.reddit.com/r/videos/comments/12345/", "Reddit"),
            ("https://www.facebook.com/watch/?v=123456", "Facebook"),
            ("https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4", "Commondatastorage"),
        ]
        for url, expected_platform in valid_cases:
            with self.subTest(url=url):
                self.assertTrue(URLAnalyzer.is_valid_url(url), f"URL should be valid: {url}")
                platform = URLAnalyzer.detect_platform(url)
                self.assertEqual(platform, expected_platform, f"Platform mismatch for {url}: expected {expected_platform}, got {platform}")

    def test_invalid_urls(self):
        invalid_cases = [
            "",
            "   ",
            "not_a_url",
            "ftp://invalid.protocol/video.mp4",
            "http://",
            "https://",
            "javascript:alert(1)",
            "file:///C:/test.mp4",
        ]
        for url in invalid_cases:
            with self.subTest(url=url):
                self.assertFalse(URLAnalyzer.is_valid_url(url), f"URL should be invalid: {url}")

    def test_url_normalization(self):
        raw = "   https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s   "
        clean = URLAnalyzer.normalize_url(raw)
        self.assertEqual(clean, "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s")


class TestDownloadQueueManager(unittest.TestCase):
    """Test DownloadManager queue, states, and concurrency controls."""

    def setUp(self):
        self.manager = DownloadManager(max_concurrent=2)
        self.manager.tasks.clear()
        self.manager.queue.clear()
        self.manager.active_workers.clear()
        # Patch DownloadWorker.start so no real network threads run during unit tests
        self.patcher = mock.patch.object(DownloadWorker, "start", return_value=None)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.manager.tasks.clear()
        self.manager.queue.clear()
        self.manager.active_workers.clear()

    def test_task_creation_and_states(self):
        task = self.manager.add_download(
            url="https://www.youtube.com/watch?v=test_queue_1",
            title="Queue Test Video 1",
            quality="1080p (Full HD)",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.status, "Pending")
        self.assertIn(task.task_id, self.manager.tasks)
        self.assertIn(task.task_id, self.manager.queue)

    def test_concurrency_limit_enforcement(self):
        self.manager.max_concurrent = 2

        task1 = self.manager.add_download(url="https://test.com/1", title="Task 1", quality="1080p", output_format="MP4", codec="Keep Original Codec")
        task2 = self.manager.add_download(url="https://test.com/2", title="Task 2", quality="1080p", output_format="MP4", codec="Keep Original Codec")
        task3 = self.manager.add_download(url="https://test.com/3", title="Task 3", quality="1080p", output_format="MP4", codec="Keep Original Codec")

        # Simulate workers running for task 1 and task 2
        self.manager.active_workers[task1.task_id] = mock.MagicMock()
        self.manager.active_workers[task2.task_id] = mock.MagicMock()
        task1.status = "Downloading"
        task2.status = "Downloading"

        self.manager.process_queue()
        # Task 3 must remain Pending because active workers = 2 (max_concurrent = 2)
        self.assertEqual(task3.status, "Pending")
        self.assertEqual(len(self.manager.active_workers), 2)

    def test_pause_resume_cancel(self):
        task = self.manager.add_download(url="https://test.com/ctrl", title="Control Task", quality="1080p", output_format="MP4", codec="Keep Original Codec")
        tid = task.task_id

        # Pause
        self.manager.pause_download(tid)
        self.assertEqual(task.status, "Paused")

        # Resume
        self.manager.resume_download(tid)
        self.assertEqual(task.status, "Pending")

        # Cancel
        self.manager.cancel_download(tid)
        self.assertEqual(task.status, "Cancelled")
        self.assertNotIn(tid, self.manager.queue)

    def test_clear_finished(self):
        t1 = self.manager.add_download(url="https://test.com/comp", title="T1", quality="1080p", output_format="MP4", codec="Keep Original Codec")
        t2 = self.manager.add_download(url="https://test.com/fail", title="T2", quality="1080p", output_format="MP4", codec="Keep Original Codec")
        t3 = self.manager.add_download(url="https://test.com/active", title="T3", quality="1080p", output_format="MP4", codec="Keep Original Codec")

        t1.status = "Completed"
        t2.status = "Failed"
        t3.status = "Pending"

        self.manager.clear_finished()
        self.assertNotIn(t1.task_id, self.manager.tasks)
        self.assertNotIn(t2.task_id, self.manager.tasks)
        self.assertIn(t3.task_id, self.manager.tasks)


class TestRetryLogic(unittest.TestCase):
    """Test auto-retry distinguishing recoverable vs permanent errors."""

    def test_permanent_errors_detection(self):
        permanent_samples = [
            "ERROR: Private video. Sign in if you've been granted access to this video",
            "This video is DRM-protected and cannot be downloaded",
            "HTTP Error 404: Not Found",
            "Sign in to confirm you’re not a bot",
            "Video unavailable. This video has been removed by the user"
        ]
        for msg in permanent_samples:
            is_perm = any(perm in msg.lower() for perm in PERMANENT_ERRORS)
            self.assertTrue(is_perm, f"Message should be recognized as permanent: {msg}")

    def test_recoverable_errors_detection(self):
        recoverable_samples = [
            "Connection reset by peer",
            "Read timed out (read timeout=30)",
            "HTTP Error 503: Service Unavailable",
            "Failed to establish a new connection: [Errno 11001] getaddrinfo failed",
            "fragment 12 failed to download"
        ]
        for msg in recoverable_samples:
            is_perm = any(perm in msg.lower() for perm in PERMANENT_ERRORS)
            self.assertFalse(is_perm, f"Message should be recognized as recoverable: {msg}")

    def test_retry_attributes(self):
        task = DownloadTask(
            url="https://test.com/video",
            title="Retry Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        self.assertEqual(task.retry_count, 0)
        self.assertEqual(task.max_retries, resolve_retry_attempts(config.get("retry_attempts", 3)))
        self.assertEqual(task.retry_delay, resolve_retry_delay(config.get("retry_delay", 5)))


class TestSettingsPersistence(unittest.TestCase):
    """Test persistent local settings management."""

    def test_settings_save_and_reload(self):
        cfg = ConfigManager()
        cfg.set("test_key_xyz", 12345)
        self.assertEqual(cfg.get("test_key_xyz"), 12345)

        # Create a fresh ConfigManager instance and verify it reads the persisted file
        fresh_cfg = ConfigManager()
        fresh_cfg.load()
        self.assertEqual(fresh_cfg.get("test_key_xyz"), 12345)

        # Cleanup test key
        if "test_key_xyz" in fresh_cfg._settings:
            del fresh_cfg._settings["test_key_xyz"]
            fresh_cfg.save()

    def test_settings_location_is_outside_install_dir(self):
        # Settings must reside in AppData / USER_STORAGE_DIR
        self.assertTrue(str(SETTINGS_FILE).startswith(str(USER_STORAGE_DIR)))


class TestMetadataExtraction(unittest.TestCase):
    """Test FFprobe inspection and metadata formatting."""

    def test_media_inspector_structure(self):
        meta = MediaInspector.get_detailed_metadata("dummy_sample.mp4")
        expected_keys = [
            "File Name", "File Size", "Duration", "Resolution",
            "Frame Rate", "Video Codec", "Audio Codec", "Container Format", "Bitrate"
        ]
        for k in expected_keys:
            self.assertIn(k, meta, f"Metadata must contain key: {k}")

    def test_size_formatting(self):
        self.assertEqual(MediaInspector.format_size(0), "—")
        self.assertEqual(MediaInspector.format_size(1024), "1.0 KB")
        self.assertEqual(MediaInspector.format_size(1024 * 1024 * 15), "15.0 MB")
        self.assertEqual(MediaInspector.format_size(1024 * 1024 * 1024 * 2), "2.0 GB")


class TestSchedulerLogic(unittest.TestCase):
    """Test persistent scheduling, missed schedule detection, and triggers."""

    def setUp(self):
        self.sched = scheduler_manager
        self.test_ids = []

    def tearDown(self):
        for sid in self.test_ids:
            self.sched.remove_schedule(sid)

    def test_add_and_cancel_schedule(self):
        future_time = datetime.now() + timedelta(hours=1)
        item = self.sched.add_schedule(
            url="https://test.com/sched_unit",
            title="Unit Sched Test",
            scheduled_time=future_time,
            quality="720p (HD)",
            output_format="MP4"
        )
        self.test_ids.append(item["id"])
        self.assertEqual(item["status"], "pending")

        # Cancel schedule
        ok = self.sched.cancel_schedule(item["id"])
        self.assertTrue(ok)
        reloaded = self.sched.load_schedules()
        found = next((s for s in reloaded if s["id"] == item["id"]), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["status"], "cancelled")

    def test_missed_schedule_detection(self):
        # Schedule in the past (> 48 hours overdue)
        past_time = datetime.now() - timedelta(hours=50)
        item = self.sched.add_schedule(
            url="https://test.com/overdue",
            title="Overdue Test",
            scheduled_time=past_time
        )
        self.test_ids.append(item["id"])

        # Run schedule check
        self.sched._check_pending_schedules()
        found = next((s for s in self.sched.schedules if s["id"] == item["id"]), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["status"], "missed")


class TestClipboardMonitoring(unittest.TestCase):
    """Test clipboard monitor state toggling and URL filtering."""

    def test_toggle_state(self):
        config.set("clipboard_monitoring", False)
        clipboard_monitor.update_state()
        self.assertFalse(clipboard_monitor._is_monitoring)

        config.set("clipboard_monitoring", True)
        clipboard_monitor.update_state()
        self.assertTrue(clipboard_monitor._is_monitoring)

        config.set("clipboard_monitoring", False)
        clipboard_monitor.update_state()

    def test_non_url_text_ignored(self):
        config.set("clipboard_monitoring", True)
        clipboard_monitor.update_state()

        detected = []
        clipboard_monitor.supported_url_detected.connect(lambda u, p: detected.append(u))

        # Put arbitrary text in clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("Hello this is just normal text not a url!")
        clipboard_monitor._on_clipboard_changed()

        self.assertEqual(len(detected), 0, "Non-URL text must not trigger detection")

        config.set("clipboard_monitoring", False)
        clipboard_monitor.update_state()


class TestSpeedAndETACalculations(unittest.TestCase):
    """Test accurate download speed and ETA formulas."""

    def test_eta_calculation(self):
        task = DownloadTask(
            url="https://test.com/speed_test",
            title="Speed Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        worker = DownloadWorker(task)
        worker._start_time = time.time() - 5.0

        # 80MB of 100MB downloaded, speed = 4MB/s (4,194,304 B/s)
        # Remaining: 20MB / 4MB/s = 5 seconds -> "00:05"
        worker._on_progress_hook({
            "status": "downloading",
            "downloaded_bytes": 80 * 1024 * 1024,
            "total_bytes": 100 * 1024 * 1024,
            "speed": 4 * 1024 * 1024
        })

        self.assertEqual(task.progress, 80.0)
        self.assertEqual(task.eta_str, "00:05")
        self.assertIn("MB/s", task.speed_str)
        self.assertGreater(task.peak_speed, 0)
        self.assertGreater(task.average_speed, 0)


class TestHistoryManager(unittest.TestCase):
    """Test history manager record addition, retrieval, and removal."""

    def test_add_and_remove_history(self):
        initial_count = len(history_manager.get_all())
        entry = history_manager.add_entry(
            file_name="test_video_file.mp4",
            file_location=r"C:\Users\test\Downloads\test_video_file.mp4",
            website="YouTube",
            resolution="1080p",
            codec="H.264",
            file_size="25.4 MB"
        )
        self.assertEqual(len(history_manager.get_all()), initial_count + 1)
        self.assertEqual(entry["file_name"], "test_video_file.mp4")

        # Verify removal
        history_manager.remove_entry(entry["id"])
        self.assertEqual(len(history_manager.get_all()), initial_count)


if __name__ == "__main__":
    unittest.main()
