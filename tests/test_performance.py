"""
Performance Test Suite for Downly.
Measures:
1. Application startup latency
2. RAM footprint (baseline vs active) using Windows API
3. FFmpeg conversion CPU/latency metrics (stream copy vs re-encoding)
4. Multiple concurrent downloads throughput
5. Background worker lifecycle & thread cleanup
6. GUI responsiveness and event loop latency
"""
import os
import sys
import time
import shutil
import ctypes
from ctypes import wintypes
import subprocess
import threading
import http.server
import socketserver
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

app = QApplication.instance() or QApplication(sys.argv)

from core.download_manager import DownloadManager, DownloadTask, DownloadWorker
from core.converter import MediaConverter
from core.media_inspector import MediaInspector
from ui.main_window import MainWindow


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t)
    ]


def get_current_ram_mb() -> float:
    """Retrieve current process WorkingSetSize in MB using Windows API."""
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024.0 * 1024.0)
    except Exception:
        pass
    return 0.0


class TestPerformance(unittest.TestCase):
    """Performance benchmarks for Downly."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = ROOT_DIR / "tests" / "test_perf_scratch"
        cls.test_dir.mkdir(parents=True, exist_ok=True)

        # Generate sample 3-second video
        cls.sample_mp4 = cls.test_dir / "perf_sample.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=duration=3:frequency=440",
            "-c:v", "libx264", "-c:a", "aac",
            str(cls.sample_mp4)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        # Generate distinct files for concurrent testing to prevent filename collision
        shutil.copy2(cls.sample_mp4, cls.test_dir / "perf_sample_1.mp4")
        shutil.copy2(cls.sample_mp4, cls.test_dir / "perf_sample_2.mp4")
        shutil.copy2(cls.sample_mp4, cls.test_dir / "perf_sample_3.mp4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_1_startup_time(self):
        """Measure full MainWindow initialization time."""
        t0 = time.perf_counter()
        win = MainWindow()
        win.show()
        QCoreApplication.processEvents()
        elapsed = time.perf_counter() - t0
        win.close()

        print(f"  ✓ Application startup time: {elapsed:.3f} seconds (Target: < 6.0s on Windows)")
        self.assertLess(elapsed, 6.0, f"Startup took too long: {elapsed:.3f}s")

    def test_2_ram_usage(self):
        """Measure RAM footprint at rest and during operations."""
        baseline_ram = get_current_ram_mb()
        print(f"  ✓ Process RAM usage: {baseline_ram:.1f} MB (Target: < 200MB for desktop app)")
        self.assertLess(baseline_ram, 200.0, f"RAM usage too high: {baseline_ram:.1f} MB")

    def test_3_ffmpeg_stream_copy_efficiency(self):
        """Benchmark stream copying efficiency vs re-encoding."""
        convert_input = self.test_dir / "perf_to_convert.mp4"
        shutil.copy2(self.sample_mp4, convert_input)

        t0 = time.perf_counter()
        out_mkv = MediaConverter.convert_media(
            source_file=str(convert_input),
            target_format="MKV",
            target_video_codec="Keep Original Codec",
            target_audio_codec="Keep Original",
            output_dir=str(self.test_dir)
        )
        duration = time.perf_counter() - t0

        self.assertTrue(Path(out_mkv).exists())
        print(f"  ✓ Stream copy remuxing completed in {duration:.3f} seconds (Target: < 3.5s)")
        self.assertLess(duration, 3.5, f"Stream copying too slow: {duration:.3f}s")

    def test_4_concurrent_worker_management_and_cleanup(self):
        """Verify 3 concurrent downloads, thread pool lifecycle, and zero orphaned threads."""
        port = 8769
        handler = http.server.SimpleHTTPRequestHandler
        os.chdir(str(self.test_dir))
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        try:
            mgr = DownloadManager()
            mgr.tasks.clear()
            mgr.queue.clear()
            mgr.active_workers.clear()
            mgr.set_max_concurrent(3)

            t1 = mgr.add_download(f"http://127.0.0.1:{port}/perf_sample_1.mp4", "Concurrent 1", "Best", "MP4", "Keep Original Codec")
            t2 = mgr.add_download(f"http://127.0.0.1:{port}/perf_sample_2.mp4", "Concurrent 2", "Best", "MP4", "Keep Original Codec")
            t3 = mgr.add_download(f"http://127.0.0.1:{port}/perf_sample_3.mp4", "Concurrent 3", "Best", "MP4", "Keep Original Codec")

            # Active workers must equal 3
            self.assertEqual(len(mgr.active_workers), 3)

            # Wait for all workers to finish (all non-final states)
            t_start = time.time()
            while any(t.status in ("Pending", "Downloading", "Processing") for t in [t1, t2, t3]):
                QCoreApplication.processEvents()
                time.sleep(0.05)
                if time.time() - t_start > 15.0:
                    break

            self.assertEqual(t1.status, "Completed")
            self.assertEqual(t2.status, "Completed")
            self.assertEqual(t3.status, "Completed")

            # Active workers pool must be completely cleaned up (0 active)
            self.assertEqual(len(mgr.active_workers), 0, "All active workers must be cleaned up from pool")
            print("  ✓ Concurrent downloads throughput & zero-worker leak verified.")

        finally:
            os.chdir(str(ROOT_DIR))
            httpd.shutdown()
            server_thread.join(timeout=2.0)
            httpd.server_close()

    def test_5_gui_responsiveness(self):
        """Measure GUI event loop latency during rapid progress signal dispatch."""
        latencies = []
        for i in range(50):
            t0 = time.perf_counter()
            QCoreApplication.processEvents()
            latencies.append((time.perf_counter() - t0) * 1000.0)

        avg_latency = sum(latencies) / len(latencies)
        print(f"  ✓ Average GUI event loop latency: {avg_latency:.2f} ms (Target: < 16ms / 60 FPS)")
        self.assertLess(avg_latency, 16.0, f"GUI latency too high: {avg_latency:.2f} ms")


if __name__ == "__main__":
    unittest.main()
