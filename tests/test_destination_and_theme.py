"""
Comprehensive Test Suite for:
1. Centralized Download Destination Management (Default, Custom, Spaces, Unicode, Audio, FFmpeg, Changing, Inaccessible)
2. Theme Consistency (Dark and Light modes, button visibility, labels, QSS generation, persistence)
3. Minor UI Changes (Explanatory text removed, Local Logs removed, GitHub Repo section removed)
"""
import os
import sys
import time
import shutil
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

app = QApplication.instance() or QApplication(sys.argv)

from app.constants import USER_DOWNLOADS_DIR, ROOT_DIR
from app.config import config
from core.download_destination import destination_manager, DestinationError
from core.download_manager import DownloadManager, DownloadTask, DownloadWorker
from core.converter import MediaConverter
from ui.theme_manager import theme_manager, THEME_PALETTES
from ui.main_window import MainWindow
from ui.downloader_page import DownloaderPage
from ui.settings_page import SettingsPage
from ui.history_page import HistoryPage


class TestDestinationAndTheme(unittest.TestCase):
    """Test suite for destination fixes and theme consistency."""

    @classmethod
    def setUpClass(cls):
        cls.scratch_dir = ROOT_DIR / "tests" / "test_dest_scratch"
        cls.scratch_dir.mkdir(parents=True, exist_ok=True)

        # Generate sample test video
        cls.sample_mp4 = cls.scratch_dir / "sample_source.mp4"
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=duration=2:frequency=1000",
            "-c:v", "libx264", "-c:a", "aac",
            str(cls.sample_mp4)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.scratch_dir, ignore_errors=True)

    def test_1_default_download_folder(self):
        """Verify default destination resolves to user's personal Downloads/Downly folder."""
        # Reset destination to default
        config.set("download_dir", str(USER_DOWNLOADS_DIR))
        dest = destination_manager.get_destination()
        self.assertEqual(dest.resolve(), USER_DOWNLOADS_DIR.resolve())
        self.assertTrue(dest.exists())
        self.assertTrue(dest.is_dir())
        self.assertNotEqual(dest.resolve(), ROOT_DIR.resolve())
        self.assertFalse(str(dest).startswith(str(ROOT_DIR / "downloads")))
        print(f"  ✓ Default destination verified: {dest}")

    def test_2_custom_folder_with_spaces_and_unicode(self):
        """Verify destination handling with spaces, special characters, and Unicode."""
        # Folder with spaces
        spaced_dir = self.scratch_dir / "My Downly Media Library"
        ok, msg = destination_manager.set_destination(str(spaced_dir))
        self.assertTrue(ok)
        self.assertEqual(destination_manager.get_destination(), spaced_dir.resolve())
        self.assertTrue(spaced_dir.exists())

        # Folder with Unicode & symbols
        unicode_dir = self.scratch_dir / "Downly_Téléchargements_⚡_中文"
        ok2, msg2 = destination_manager.set_destination(str(unicode_dir))
        self.assertTrue(ok2)
        self.assertEqual(destination_manager.get_destination(), unicode_dir.resolve())
        self.assertTrue(unicode_dir.exists())
        print("  ✓ Custom folder paths with spaces and Unicode characters verified.")

    def test_3_ffmpeg_conversion_in_selected_destination(self):
        """Verify FFmpeg remuxing and transcoding strictly saves inside the selected destination."""
        target_dir = self.scratch_dir / "Destination_Conversion_Test"
        destination_manager.set_destination(str(target_dir))

        # Copy sample source into scratch
        input_file = self.scratch_dir / "test_conv_src.mp4"
        shutil.copy2(self.sample_mp4, input_file)

        out_mkv = MediaConverter.convert_media(
            source_file=str(input_file),
            target_format="MKV",
            target_video_codec="Keep Original Codec",
            target_audio_codec="Keep Original",
            output_dir=str(target_dir)
        )

        out_path = Path(out_mkv)
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.parent.resolve(), target_dir.resolve())
        self.assertNotEqual(out_path.parent.resolve(), (ROOT_DIR / "downloads").resolve())
        print(f"  ✓ FFmpeg conversion saved strictly in destination: {out_mkv}")

    def test_4_audio_extraction_in_selected_destination(self):
        """Verify audio extraction saves directly inside user's selected destination."""
        target_dir = self.scratch_dir / "Destination_Audio_Test"
        destination_manager.set_destination(str(target_dir))

        input_file = self.scratch_dir / "test_audio_src.mp4"
        shutil.copy2(self.sample_mp4, input_file)

        out_mp3 = MediaConverter.convert_media(
            source_file=str(input_file),
            target_format="MP3 (Audio Only)",
            output_dir=str(target_dir)
        )

        out_path = Path(out_mp3)
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.parent.resolve(), target_dir.resolve())
        self.assertEqual(out_path.suffix.lower(), ".mp3")
        self.assertNotEqual(out_path.parent.resolve(), (ROOT_DIR / "downloads").resolve())
        print(f"  ✓ Audio extraction saved strictly in destination: {out_mp3}")

    def test_5_changing_destination_between_downloads(self):
        """
        Verify that changing the destination assigns the new destination to new tasks
        while queued tasks retain the destination assigned when created.
        """
        dir_a = self.scratch_dir / "Folder_A"
        dir_b = self.scratch_dir / "Folder_B"

        from unittest import mock
        with mock.patch.object(DownloadWorker, "start", return_value=None):
            destination_manager.set_destination(str(dir_a))
            mgr = DownloadManager()
            # Task 1 created when Dir A is active
            t1 = mgr.add_download(
                url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
                title="Task 1",
                quality="1080p",
                output_format="MP4",
                codec="Keep Original Codec"
            )
            self.assertEqual(Path(t1.download_dir).resolve(), dir_a.resolve())

            # Change global destination to Dir B
            destination_manager.set_destination(str(dir_b))

            # Task 2 created when Dir B is active
            t2 = mgr.add_download(
                url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
                title="Task 2",
                quality="1080p",
                output_format="MP4",
                codec="Keep Original Codec"
            )
            self.assertEqual(Path(t2.download_dir).resolve(), dir_b.resolve())
            # Task 1 must still retain Dir A!
            self.assertEqual(Path(t1.download_dir).resolve(), dir_a.resolve())
        print("  ✓ Destination change between downloads correctly preserves queued destinations.")

    def test_6_invalid_or_unwritable_destination_rejection(self):
        """Verify invalid or inaccessible folders are rejected with clear error and no project fallback."""
        # Unwritable / invalid filename characters on Windows (e.g. containing '<>')
        bad_path = "Z:\\NonExistentDrive_Downly_12345\\Forbidden<>Folder"
        ok, msg = destination_manager.set_destination(bad_path)
        self.assertFalse(ok)
        self.assertTrue(len(msg) > 0)

        # Destination must not have reverted to project root
        current_dest = destination_manager.get_destination()
        self.assertNotEqual(current_dest.resolve(), ROOT_DIR.resolve())
        self.assertNotEqual(current_dest.resolve(), (ROOT_DIR / "downloads").resolve())
        print("  ✓ Inaccessible/invalid destinations rejected with clear diagnostic message.")

    def test_7_theme_switching_and_button_visibility(self):
        """Verify Dark and Light mode styling, button contrast, and live updates."""
        # Test Dark Mode (Buttons have WHITE text)
        theme_manager.set_theme("dark")
        self.assertEqual(theme_manager.current_theme, "dark")
        pal_dark = theme_manager.get_palette()
        self.assertEqual(pal_dark["btn_primary_text"], "#FFFFFF")
        self.assertEqual(pal_dark["btn_analyze_text"], "#FFFFFF")
        self.assertEqual(pal_dark["btn_download_text"], "#FFFFFF")
        self.assertEqual(pal_dark["btn_save_text"], "#FFFFFF")

        # Test Light Mode (Buttons have BLACK text)
        theme_manager.set_theme("light")
        self.assertEqual(theme_manager.current_theme, "light")
        pal_light = theme_manager.get_palette()
        self.assertEqual(pal_light["btn_primary_text"], "#17211B")
        self.assertEqual(pal_light["btn_analyze_text"], "#17211B")
        self.assertEqual(pal_light["btn_download_text"], "#17211B")
        self.assertEqual(pal_light["btn_save_text"], "#17211B")

        # Instantiate DownloaderPage and check Download Button
        dl_page = DownloaderPage()
        # In Light mode: button must display BOTH icon and text 'Download'
        self.assertEqual(dl_page.download_btn.text(), "⬇️ Download")
        self.assertEqual(dl_page.analyze_btn.text(), "🔍 Analyze URL")

        # Switch back to Dark mode
        theme_manager.set_theme("dark")
        self.assertEqual(dl_page.download_btn.text(), "⬇️ Download")
        self.assertEqual(dl_page.analyze_btn.text(), "🔍 Analyze URL")
        print("  ✓ Theme switching, Download button label ('⬇️ Download'), and contrast verified.")

    def test_8_minor_ui_removals_verification(self):
        """Verify Local Logs and GitHub Repo sections are removed from Settings."""
        settings_page = SettingsPage()

        # 1. Local Logs button must not exist
        self.assertFalse(hasattr(settings_page, "btn_view_logs"))
        self.assertFalse(hasattr(settings_page, "_open_log_file"))

        # 2. GitHub Repo input must not exist
        self.assertFalse(hasattr(settings_page, "repo_input"))

        # 3. Check for Updates button exists and is functional
        self.assertTrue(hasattr(settings_page, "check_update_btn"))
        # Explanatory idle text should be empty
        self.assertEqual(settings_page.update_status_lbl.text(), "")

        print("  ✓ Verified removal of Local Logs and GitHub Repository sections from Settings.")

    def test_9_final_ui_fixes(self):
        """Verify all final UI fixes: diagnostics removal, theme switcher, buttons, chevrons, and removals."""
        settings_page = SettingsPage()
        dl_page = DownloaderPage()
        hist_page = HistoryPage()
        main_win = MainWindow()

        # 1. System Diagnostics removed from Settings
        self.assertFalse(hasattr(settings_page, "lbl_ytdlp_val"))
        self.assertFalse(hasattr(settings_page, "lbl_ffmpeg_val"))
        self.assertFalse(hasattr(settings_page, "lbl_encoders_val"))

        # 2. Appearance & Theme section removed from Settings
        self.assertFalse(hasattr(settings_page, "theme_combo"))

        # 3. Dedicated theme switching control in Downloader header
        self.assertTrue(hasattr(dl_page, "theme_toggle_btn"))
        current_t = theme_manager.current_theme
        new_t = theme_manager.toggle_theme()
        self.assertNotEqual(current_t, new_t)
        theme_manager.set_theme("dark")

        # 4. Critical Button Styling and Labels
        self.assertEqual(dl_page.analyze_btn.objectName(), "analyzeButton")
        self.assertEqual(dl_page.download_btn.objectName(), "downloadButton")
        self.assertEqual(dl_page.download_btn.text(), "⬇️ Download")

        # Check QSS contains distinct rules for analyzeButton, downloadButton, saveButton
        qss_dark = theme_manager.get_stylesheet()
        self.assertIn("QPushButton#analyzeButton", qss_dark)
        self.assertIn("QPushButton#downloadButton", qss_dark)
        self.assertIn("QPushButton#saveButton", qss_dark)
        self.assertIn("QComboBoxPrivateContainer", qss_dark)
        self.assertIn("QComboBox::down-arrow", qss_dark)
        self.assertIn("chevron_dark.svg", qss_dark)

        # 5. Downloader: Speed/ETA and Metadata and Source Bar are removed
        self.assertFalse(hasattr(dl_page, "speed_eta_label"))
        self.assertFalse(hasattr(dl_page, "meta_label"))
        self.assertFalse(hasattr(dl_page, "source_bar"))
        self.assertFalse(hasattr(dl_page, "lbl_source_platform"))
        self.assertFalse(hasattr(dl_page, "lbl_source_url"))

        # 6. Sidebar: Theme toggle, version badge, and NAVIGATION heading are removed
        self.assertFalse(hasattr(main_win.sidebar, "theme_btn"))
        self.assertFalse(hasattr(main_win.sidebar, "version_badge"))
        self.assertFalse(hasattr(main_win.sidebar, "nav_label"))

        # 7. Application version moved to bottom-left of sidebar; removed from bottom-right of MainWindow
        self.assertTrue(hasattr(main_win.sidebar, "version_label"))
        self.assertIn("v1.", main_win.sidebar.version_label.text())
        self.assertFalse(hasattr(main_win, "version_label"))

        # 8. History Page Folder button exists
        self.assertTrue(hasattr(hist_page, "_open_folder"))

        print("  ✓ Final UI fixes verified: clean Settings, theme toggle, buttons, and source location info.")


if __name__ == "__main__":
    unittest.main()
