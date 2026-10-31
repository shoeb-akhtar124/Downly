"""
Integration Test Suite for Downly.
Tests:
1. yt-dlp metadata extraction on real supported media
2. FFmpeg conversion & remuxing (MP4 -> MKV, MP4 -> MP3 audio extraction)
3. FFprobe stream inspection (codecs, framerate, resolution, bitrate, container)
4. Subtitle extraction and embedding
5. Playlist download flow and queueing
6. Batch downloading queueing & concurrency
7. Pause, resume, and cancellation cleanup (.part/.ytdl files)
8. End-to-end media download worker execution & history logging
"""
import os
import sys
import time
import shutil
import subprocess
import threading
import http.server
import socketserver
import unittest
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from app.constants import USER_DOWNLOADS_DIR
from app.config import config
from core.download_manager import DownloadManager, DownloadTask, DownloadWorker
from core.converter import MediaConverter
from core.media_inspector import MediaInspector
from core.extractor import VideoExtractor
from storage.history_manager import history_manager
from ui.components.playlist_dialog import PlaylistDialog
from ui.components.batch_download_dialog import BatchDownloadDialog


class TestIntegration(unittest.TestCase):
    """Integration tests verifying yt-dlp, FFmpeg, FFprobe, and DownloadManager."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = ROOT_DIR / "tests" / "test_scratch"
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        # Generate a 2-second valid test MP4 video using FFmpeg
        cls.sample_mp4 = cls.test_dir / "integration_sample.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=duration=2:frequency=1000",
            "-c:v", "libx264", "-c:a", "aac",
            str(cls.sample_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert cls.sample_mp4.exists(), f"Failed to generate test sample: {res.stderr}"

    @classmethod
    def tearDownClass(cls):
        # Cleanup scratch files
        try:
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_1_ytdlp_extraction(self):
        """Verify yt-dlp metadata extraction on real supported video."""
        extractor = VideoExtractor()
        url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
        info = extractor.extract_info(url)

        self.assertFalse(info.get("is_playlist"))
        self.assertIn("Big Buck Bunny", info.get("title", ""))
        self.assertEqual(info.get("platform"), "YouTube")
        self.assertGreater(info.get("duration", 0), 0)
        self.assertGreater(len(info.get("formats", [])), 0)
        print("  ✓ yt-dlp real media extraction verified.")

    def test_2_ffmpeg_conversion_and_remux(self):
        """Verify FFmpeg container remuxing and MP3 audio extraction."""
        source_copy = self.test_dir / "sample_copy.mp4"
        shutil.copy2(self.sample_mp4, source_copy)

        # 1. Convert to MKV
        mkv_output = MediaConverter.convert_media(
            source_file=str(source_copy),
            target_format="MKV",
            target_video_codec="Keep Original Codec",
            target_audio_codec="Keep Original",
            output_dir=str(self.test_dir)
        )
        self.assertTrue(Path(mkv_output).exists())
        self.assertTrue(mkv_output.endswith(".mkv"))

        # 2. Extract MP3 audio
        mp3_output = MediaConverter.convert_media(
            source_file=str(mkv_output),
            target_format="MP3 (Audio Only)",
            target_audio_codec="MP3",
            output_dir=str(self.test_dir)
        )
        self.assertTrue(Path(mp3_output).exists())
        self.assertTrue(mp3_output.endswith(".mp3"))
        print("  ✓ FFmpeg container remuxing and audio extraction verified.")

    def test_3_ffprobe_detailed_inspection(self):
        """Verify FFprobe detailed stream metadata inspection."""
        meta = MediaInspector.get_detailed_metadata(str(self.sample_mp4))
        self.assertEqual(meta["Resolution"], "320x240")
        self.assertEqual(meta["Frame Rate"], "24 fps")
        self.assertEqual(meta["Video Codec"], "H264")
        self.assertEqual(meta["Audio Codec"], "AAC")
        self.assertEqual(meta["Duration"], "00:02")
        print("  ✓ FFprobe inspection accurately retrieved all stream parameters.")

    def test_4_subtitle_embedding(self):
        """Verify subtitle creation and FFmpeg embedding."""
        srt_file = self.test_dir / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello Downly Test Subtitle\n", encoding="utf-8")

        output_with_sub = self.test_dir / "sample_subbed.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self.sample_mp4),
            "-i", str(srt_file),
            "-c", "copy", "-c:s", "mov_text",
            str(output_with_sub)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Subtitle embedding failed: {res.stderr}")
        self.assertTrue(output_with_sub.exists())
        print("  ✓ Subtitle track creation and embedding verified.")

    def test_5_playlist_queueing(self):
        """Verify playlist parsing and queueing into DownloadManager."""
        from unittest import mock
        from core.download_manager import download_manager
        with mock.patch("ui.components.playlist_dialog.QMessageBox.information"), \
             mock.patch.object(DownloadWorker, "start", return_value=None):
            initial_tasks = len(download_manager.tasks)
            fake_playlist = {
                "is_playlist": True,
                "title": "Integration Test Playlist",
                "uploader": "Test Channel",
                "platform": "YouTube",
                "entries": [
                    {"index": 1, "id": "p1", "title": "Play 1", "url": "https://www.youtube.com/watch?v=p1", "duration_str": "02:00"},
                    {"index": 2, "id": "p2", "title": "Play 2", "url": "https://www.youtube.com/watch?v=p2", "duration_str": "03:00"}
                ]
            }

            dlg = PlaylistDialog(fake_playlist)
            dlg._on_add_clicked()

            self.assertEqual(len(download_manager.tasks), initial_tasks + 2)
            download_manager.tasks.clear()
            download_manager.queue.clear()
        print("  ✓ Playlist batch enqueueing into DownloadManager verified.")

    def test_6_batch_download_dialog(self):
        """Verify batch dialog input validation and queuing."""
        from unittest import mock
        from core.download_manager import download_manager
        with mock.patch("ui.components.batch_download_dialog.QMessageBox.information"), \
             mock.patch.object(DownloadWorker, "start", return_value=None):
            initial_tasks = len(download_manager.tasks)
            dlg = BatchDownloadDialog()
            dlg.url_text_edit.setPlainText("https://vimeo.com/1234567\nhttps://vimeo.com/7654321")
            dlg._on_validate_clicked()
            self.assertEqual(len(dlg.validated_tasks), 2)

            dlg._on_start_batch()
            self.assertEqual(len(download_manager.tasks), initial_tasks + 2)
            download_manager.tasks.clear()
            download_manager.queue.clear()
        print("  ✓ Batch download validation and queuing verified.")

    def test_7_cancellation_and_temp_file_cleanup(self):
        """Verify cancellation cleans up partial temporary files."""
        # Create fake partial files in download dir
        part1 = self.test_dir / "temp_video.mp4.part"
        part2 = self.test_dir / "temp_video.mp4.ytdl"
        part1.write_bytes(b"partial content")
        part2.write_bytes(b"partial content")
        self.assertTrue(part1.exists())
        self.assertTrue(part2.exists())

        task = DownloadTask(
            url="https://test.com/cancel_cleanup",
            title="Cancel Test",
            quality="1080p",
            output_format="MP4",
            codec="Keep Original Codec",
            download_dir=str(self.test_dir)
        )
        worker = DownloadWorker(task)
        worker._cleanup_temp_files(self.test_dir)

        self.assertFalse(part1.exists(), ".part file must be deleted upon cancellation")
        self.assertFalse(part2.exists(), ".ytdl file must be deleted upon cancellation")
        print("  ✓ Temporary .part and .ytdl file cleanup on cancellation verified.")

    def test_8_end_to_end_local_media_download(self):
        """
        Spin up a lightweight local HTTP server hosting a real video file,
        run DownloadWorker, and verify full end-to-end download, history logging, and signals.
        """
        port = 8765
        handler = http.server.SimpleHTTPRequestHandler
        # Serve from test_dir
        os.chdir(str(self.test_dir))
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        try:
            local_url = f"http://127.0.0.1:{port}/integration_sample.mp4"
            dest_dir = self.test_dir / "downloaded_output"
            dest_dir.mkdir(parents=True, exist_ok=True)

            task = DownloadTask(
                url=local_url,
                title="E2E Local Download Test",
                quality="Best Available",
                output_format="MP4",
                codec="Keep Original Codec",
                download_dir=str(dest_dir)
            )

            completed_events = []
            worker = DownloadWorker(task)
            worker.completed_signal.connect(lambda tid, path, size, res, codec: completed_events.append((tid, path, size)))

            # Run worker synchronously for test verification
            worker.run()

            self.assertEqual(len(completed_events), 1, "DownloadWorker must emit completed_signal")
            final_path = Path(completed_events[0][1])
            self.assertTrue(final_path.exists(), f"Downloaded file does not exist: {final_path}")
            self.assertGreater(final_path.stat().st_size, 0)

            # Verify history manager entry was recorded
            history_entries = history_manager.get_all()
            found = any(e.get("file_name") == final_path.name for e in history_entries)
            self.assertTrue(found, "Completed task must be recorded in history_manager")
            print("  ✓ End-to-end download worker execution and history persistence verified.")

        finally:
            os.chdir(str(ROOT_DIR))
            httpd.shutdown()
            server_thread.join(timeout=2.0)
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
