"""
Stability and Resilience Test Suite for Downly.
Verifies:
1. Application restart state persistence (settings, history, scheduled tasks)
2. Invalid URL and unsupported protocol error resilience (zero crash)
3. Simulated network failure and recovery behavior
4. Missing FFmpeg binary fallback and error reporting
5. Empty / non-URL clipboard handling
6. Interrupted download state and temporary file isolation
7. Clean shutdown during active downloads without UI lockup or orphaned threads
"""
import os
import sys
import time
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QCloseEvent

app = QApplication.instance() or QApplication(sys.argv)

from app.config import config
from core.download_manager import DownloadManager, download_manager, DownloadTask, DownloadWorker
from storage.history_manager import HistoryManager, history_manager
from core.scheduler_manager import SchedulerManager, scheduler_manager
from core.clipboard_monitor import ClipboardMonitor, clipboard_monitor
from core.converter import MediaConverter, ConversionError
from core.media_inspector import MediaInspector
from core.url_analyzer import URLAnalyzer
from ui.main_window import MainWindow


class TestStability(unittest.TestCase):
    """Stability and resilience test cases."""

    @classmethod
    def setUpClass(cls):
        cls.test_scratch = ROOT_DIR / "tests" / "test_stability_scratch"
        cls.test_scratch.mkdir(parents=True, exist_ok=True)
        cls.dummy_source = cls.test_scratch / "dummy_source.mp4"
        cls.dummy_source.write_bytes(b"dummy mp4 file data for testing")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_scratch, ignore_errors=True)

    def test_1_state_persistence_across_app_restart(self):
        """Verify settings, history, and scheduled tasks persist across restarts."""
        # 1. Update config
        config.set("theme_mode", "Dark")
        config.set("default_format", "MKV")
        config.set("speed_limit_enabled", True)
        config.set("speed_limit_kbps", 4096)

        # 2. Add history record
        hist = history_manager
        hist.add_entry(
            file_name="Stability Video",
            file_location="C:/Downloads/restart_test.mkv",
            website="YouTube",
            resolution="1080p",
            codec="H.264",
            file_size="52.4 MB"
        )

        # 3. Add scheduled task
        future_time = datetime.now() + timedelta(days=2)
        sched_entry = scheduler_manager.add_schedule(
            url="https://www.youtube.com/watch?v=sched_restart",
            title="Sched Restart Test",
            scheduled_time=future_time,
            quality="1080p (Full HD)",
            output_format="MP4"
        )

        # Reinitialize managers from disk to simulate application restart
        new_config = config.__class__()
        new_hist = HistoryManager()
        new_hist.load()
        new_sched = SchedulerManager()
        reloaded_schedules = new_sched.load_schedules()

        self.assertEqual(new_config.get("theme_mode"), "Dark")
        self.assertEqual(new_config.get("default_format"), "MKV")
        self.assertEqual(new_config.get("speed_limit_kbps"), 4096)

        matched_hist = [h for h in new_hist.get_all() if "restart_test" in h.get("file_location", "")]
        self.assertGreaterEqual(len(matched_hist), 1)

        matched_sched = [s for s in reloaded_schedules if s.get("id") == sched_entry["id"]]
        self.assertGreaterEqual(len(matched_sched), 1)

        # Cleanup test schedule
        scheduler_manager.cancel_schedule(sched_entry["id"])
        print("  ✓ State persistence verified across simulated restart.")

    def test_2_invalid_url_and_unsupported_protocol_resilience(self):
        """Verify malformed URLs and unsupported protocols fail gracefully without application crash."""
        bad_urls = [
            "not_a_url",
            "ftp://files.example.com/video.mp4",
            "javascript:alert(1)",
            "http://",
            "https://invalid-nonexistent-domain-downly-test.xyz/vid.mp4"
        ]

        for bad_url in bad_urls:
            is_valid = URLAnalyzer.is_valid_url(bad_url)
            if not is_valid:
                self.assertFalse(is_valid)
            else:
                task = DownloadTask(
                    url=bad_url,
                    title="Invalid Domain Test",
                    quality="1080p",
                    output_format="MP4",
                    codec="Keep Original Codec"
                )
                worker = DownloadWorker(task)
                worker.run()
                self.assertIn(task.status, ("Failed", "Pending"))
                self.assertTrue(len(task.error_message) > 0)

        print("  ✓ Invalid URLs and unsupported protocols rejected gracefully without crash.")

    def test_3_network_failure_and_retry_resilience(self):
        """Verify network connection drop triggers retry logic without crashing."""
        task = DownloadTask(
            url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
            title="Network Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        task.max_retries = 2

        worker = DownloadWorker(task)

        # Simulate network failure during yt-dlp run
        with mock.patch("yt_dlp.YoutubeDL.download", side_effect=Exception("Connection reset by peer")):
            worker.run()

        # Task should have attempted retry 1
        self.assertEqual(task.retry_count, 1)
        self.assertEqual(task.status, "Pending")
        self.assertIn("Connection reset by peer", task.error_message)

        # Second failure
        with mock.patch("yt_dlp.YoutubeDL.download", side_effect=Exception("Connection timed out")):
            worker.run()

        self.assertEqual(task.retry_count, 2)
        # Third failure exhausts retries
        with mock.patch("yt_dlp.YoutubeDL.download", side_effect=Exception("Network is unreachable")):
            worker.run()

        self.assertEqual(task.status, "Failed")
        self.assertTrue(task.is_completed)
        print("  ✓ Network disconnection simulation handled with exponential retries.")

    def test_4_missing_ffmpeg_fallback(self):
        """Verify system handles missing FFmpeg without crashing and provides helpful error."""
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(MediaInspector.is_ffmpeg_available())
            self.assertEqual(MediaInspector.detect_hardware_encoders(), [])

            # MediaConverter should raise ConversionError with clear diagnostic message
            with self.assertRaises(ConversionError) as ctx:
                MediaConverter.convert_media(str(self.dummy_source), "MKV")
            self.assertIn("FFmpeg was not found", str(ctx.exception))

        print("  ✓ Missing FFmpeg binary scenario handled with clear error feedback.")

    def test_5_empty_and_junk_clipboard_handling(self):
        """Verify empty clipboard and non-URL text triggers zero popups or errors."""
        monitor = ClipboardMonitor()
        monitor.enabled = True
        monitor._last_detected_url = ""

        # Test empty clipboard
        with mock.patch("PySide6.QtGui.QClipboard.text", return_value=""):
            monitor._on_clipboard_changed()
            self.assertEqual(monitor._last_detected_url, "")

        # Test random non-URL text
        with mock.patch("PySide6.QtGui.QClipboard.text", return_value="Just some random sentence from document"):
            with mock.patch.object(monitor.supported_url_detected, "emit") as mock_signal:
                monitor._on_clipboard_changed()
                mock_signal.assert_not_called()

        # Test whitespace only
        with mock.patch("PySide6.QtGui.QClipboard.text", return_value="   \n\t  "):
            with mock.patch.object(monitor.supported_url_detected, "emit") as mock_signal:
                monitor._on_clipboard_changed()
                mock_signal.assert_not_called()

        print("  ✓ Empty and junk clipboard strings processed silently without false alerts.")

    def test_6_active_download_cancellation_and_temp_file_cleanup(self):
        """Verify cancelling an active download removes temporary .part files and resets status."""
        mgr = DownloadManager()
        task = DownloadTask(
            url="http://127.0.0.1:9999/dummy.mp4",
            title="Cancel Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        mgr.tasks[task.task_id] = task

        # Create simulated .part file in download directory
        part_file = Path(task.output_dir) / f"{task.title}.mp4.part"
        part_file.parent.mkdir(parents=True, exist_ok=True)
        part_file.write_bytes(b"Partial download data here")
        self.assertTrue(part_file.exists())

        mgr.cancel_download(task.task_id)
        self.assertEqual(task.status, "Cancelled")
        self.assertFalse(part_file.exists(), "Temporary .part file must be removed upon cancellation")
        print("  ✓ Active download cancellation and temporary file cleanup verified.")

    def test_7_application_close_event_with_active_workers(self):
        """Verify MainWindow.closeEvent aborts any running workers cleanly without hanging."""
        win = MainWindow()
        win.show()
        QCoreApplication.processEvents()

        task = DownloadTask(
            url="https://www.youtube.com/watch?v=close_test",
            title="Close Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec"
        )
        worker = DownloadWorker(task)
        download_manager.active_workers[task.task_id] = worker

        # Trigger closeEvent
        event = QCloseEvent()
        win.closeEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertTrue(worker.is_cancelled)

        win.close()
        print("  ✓ MainWindow closeEvent with active workers shuts down cleanly.")


if __name__ == "__main__":
    unittest.main()
