"""
Download Manager Module.
Coordinates download queue, concurrency, background worker threads,
pause/resume, auto-retry, real-time speed metrics (current, average, peak),
accurate ETA calculation, subtitle extraction, and error handling.
"""
import os
import re
import time
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, QThread, Signal

import yt_dlp

from app.config import config
from app.logger import log_info, log_error, log_warning
from core.converter import MediaConverter, ConversionError
from core.format_selector import FormatSelector
from core.media_inspector import MediaInspector
from core.download_destination import destination_manager, DestinationError
from storage.history_manager import history_manager

# Permanent non-recoverable error keywords
PERMANENT_ERRORS = [
    "private video", "sign in", "login", "drm", "encrypted",
    "requires payment", "membership", "unsupported url", "video unavailable",
    "not available in your country", "removed by the user", "account has been terminated",
    "404: not found", "http error 404", "http error 403", "http error 401",
    "looks truncated", "incomplete youtube id", "does not exist", "is not a valid url"
]


def resolve_max_concurrent(val: Any = None) -> int:
    """
    Resolves max concurrent downloads setting.
    If 'Automatic', intelligently allocates threads based on CPU core count:
      >= 8 cores: 4 downloads
      >= 4 cores: 3 downloads
      < 4 cores: 2 downloads
    """
    if val is None:
        val = config.get("max_concurrent_downloads", "Automatic")
    if str(val).strip().lower() == "automatic":
        cores = os.cpu_count() or 4
        return 4 if cores >= 8 else (3 if cores >= 4 else 2)
    try:
        return max(1, min(10, int(val)))
    except (ValueError, TypeError):
        return 3


def resolve_concurrent_fragments(val: Any = None) -> int:
    """
    Resolves concurrent fragment downloads for multi-threaded HLS/DASH chunk streams.
    If 'Automatic', allocates 4 fragments for fast parallel downloading.
    """
    if val is None:
        val = config.get("concurrent_fragments", "Automatic")
    if str(val).strip().lower() == "automatic":
        return 4
    try:
        return max(1, min(16, int(val)))
    except (ValueError, TypeError):
        return 1


def resolve_retry_attempts(val: Any = None) -> int:
    """
    Resolves maximum retry attempts.
    If 'Automatic', defaults to 3 attempts.
    """
    if val is None:
        val = config.get("retry_attempts", "Automatic")
    if str(val).strip().lower() == "automatic":
        return 3
    try:
        return max(0, min(10, int(val)))
    except (ValueError, TypeError):
        return 3


def resolve_retry_delay(val: Any = None) -> int:
    """
    Resolves retry delay in seconds.
    If 'Automatic', defaults to 5 seconds base delay.
    """
    if val is None:
        val = config.get("retry_delay", "Automatic")
    if str(val).strip().lower() == "automatic":
        return 5
    try:
        return max(1, min(60, int(val)))
    except (ValueError, TypeError):
        return 5


class DownloadTask:
    """Represents an individual download job and its real-time state."""

    def __init__(
        self,
        url: str,
        title: str,
        quality: str,
        output_format: str,
        codec: str,
        thumbnail: str = "",
        platform: str = "Web Media",
        download_dir: Optional[str] = None,
        task_id: Optional[str] = None,
        audio_codec: str = "Keep Original",
        subtitles: bool = False,
        subtitle_lang: str = "en",
        embed_subtitles: bool = False,
        subtitle_only: bool = False
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.url = url
        self.title = title
        self.quality = quality
        self.output_format = output_format
        self.codec = codec
        self.audio_codec = audio_codec
        self.thumbnail = thumbnail
        self.platform = platform
        # Centralized destination resolution ensuring absolute path outside project root
        self.download_dir = str(destination_manager.resolve_task_destination(download_dir))

        # Subtitle preferences
        self.subtitles = subtitles
        self.subtitle_lang = subtitle_lang
        self.embed_subtitles = embed_subtitles
        self.subtitle_only = subtitle_only

        # State: "Pending", "Downloading", "Processing", "Paused", "Completed", "Failed", "Cancelled"
        self.status = "Pending"
        self.progress: float = 0.0

        # Speed and ETA Metrics
        self.speed_str: str = "—"
        self.average_speed_str: str = "—"
        self.peak_speed_str: str = "—"
        self.current_speed: float = 0.0
        self.average_speed: float = 0.0
        self.peak_speed: float = 0.0
        self.eta_str: str = "—"
        self.downloaded_bytes: int = 0
        self.total_bytes: int = 0

        # Auto-retry tracking
        self.retry_count: int = 0
        self.max_retries: int = resolve_retry_attempts(config.get("retry_attempts", "Automatic"))
        self.retry_delay: int = resolve_retry_delay(config.get("retry_delay", "Automatic"))

        self.error_message: str = ""
        self.final_file_path: str = ""
        self.file_size_str: str = "—"
        self.final_codec: str = codec
        self.final_resolution: str = quality


class DownloadWorker(QThread):
    """Background worker executing the download and conversion in an isolated thread."""

    progress_signal = Signal(str, float, str, str)  # task_id, percent, speed, eta
    extended_progress_signal = Signal(str, float, str, str, str, str)  # task_id, percent, speed, avg, peak, eta
    status_signal = Signal(str, str, str)           # task_id, status, status_detail
    completed_signal = Signal(str, str, str, str, str) # task_id, path, size, res, codec
    failed_signal = Signal(str, str)                 # task_id, error_message

    def __init__(self, task: DownloadTask):
        super().__init__()
        self.task = task
        self._is_cancelled = False
        self._is_paused = False
        self._downloaded_file: Optional[str] = None
        self._start_time: float = 0.0
        self._peak_speed: float = 0.0
        self._last_progress_update: float = 0.0

    def cancel(self) -> None:
        """Mark worker as cancelled to abort download safely."""
        self._is_cancelled = True

    def pause(self) -> None:
        """Mark worker as paused to interrupt download stream cleanly."""
        self._is_paused = True

    def run(self) -> None:
        """Execute yt-dlp download, retry loops, and format/codec post-processing."""
        try:
            dest_dir = destination_manager.resolve_task_destination(self.task.download_dir)
            self.task.download_dir = str(dest_dir)
        except DestinationError as e:
            msg = f"Cannot access download folder: {e}"
            log_error(f"[{self.task.task_id}] {msg}")
            self.failed_signal.emit(self.task.task_id, msg)
            return
        except OSError as e:
            msg = f"Cannot create download directory: {e}"
            log_error(f"[{self.task.task_id}] {msg}")
            self.failed_signal.emit(self.task.task_id, msg)
            return

        # Check disk space (at least 50MB free)
        try:
            free_bytes = shutil.disk_usage(str(dest_dir)).free
            if free_bytes < 50 * 1024 * 1024:
                msg = "Insufficient disk space in download directory."
                log_error(f"[{self.task.task_id}] {msg}")
                self.failed_signal.emit(self.task.task_id, msg)
                return
        except Exception:
            pass

        format_spec = FormatSelector.build_format_spec(self.task.quality, self.task.output_format)
        is_audio_only = "MP3" in self.task.output_format.upper()
        ffmpeg_bin = MediaConverter.get_ffmpeg_path()

        socket_timeout = config.get("connection_timeout", 30)
        retries = resolve_retry_attempts(config.get("retry_attempts", "Automatic"))
        concurrent_frags = resolve_concurrent_fragments(config.get("concurrent_fragments", "Automatic"))
        auto_retry = config.get("auto_retry", True)

        ydl_opts: Dict[str, Any] = {
            "outtmpl": str(dest_dir / "%(title).200B.%(ext)s"),
            "format": format_spec,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "continuedl": True,
            "socket_timeout": socket_timeout,
            "retries": retries,
            "concurrent_fragment_downloads": concurrent_frags,
            "progress_hooks": [self._on_progress_hook],
            "postprocessor_hooks": [self._on_postprocessor_hook],
        }

        # Subtitle extraction options
        if self.task.subtitles:
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            if self.task.subtitle_lang:
                ydl_opts["subtitleslangs"] = [self.task.subtitle_lang, "en"]
            ydl_opts["subtitlesformat"] = "srt/vtt/best"
            if self.task.subtitle_only:
                ydl_opts["skip_download"] = True

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = ffmpeg_bin
            if not is_audio_only and not self.task.subtitle_only:
                target_container = "mkv" if "MKV" in self.task.output_format.upper() else "mp4"
                ydl_opts["merge_output_format"] = target_container

            if self.task.subtitles and self.task.embed_subtitles and not self.task.subtitle_only:
                ydl_opts.setdefault("postprocessors", []).append({
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": False
                })

        info = None
        attempt = 0
        max_attempts = self.task.max_retries if auto_retry else 0

        while True:
            if self._is_cancelled:
                self._cleanup_temp_files(dest_dir)
                self.status_signal.emit(self.task.task_id, "Cancelled", "Download cancelled.")
                return
            if self._is_paused:
                self.status_signal.emit(self.task.task_id, "Paused", "Download paused.")
                return

            self._start_time = time.time()
            self.status_signal.emit(
                self.task.task_id,
                "Downloading",
                f"Connecting to media stream...{' (Retry ' + str(attempt) + ')' if attempt > 0 else ''}"
            )
            log_info(f"[{self.task.task_id}] Starting download (attempt {attempt+1}): {self.task.url}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.task.url, download=True)
                break  # Successful extraction & download!
            except Exception as e:
                msg = str(e)
                if "DOWNLOAD_CANCELLED" in msg or self._is_cancelled:
                    self._cleanup_temp_files(dest_dir)
                    self.status_signal.emit(self.task.task_id, "Cancelled", "Download cancelled.")
                    return
                elif "DOWNLOAD_PAUSED" in msg or self._is_paused:
                    self.status_signal.emit(self.task.task_id, "Paused", "Download paused.")
                    return

                clean_msg = re.sub(r'^(?:ERROR:\s*)?(?:\[[^\]]+\]\s*)?', '', msg).strip()
                log_warning(f"[{self.task.task_id}] Download attempt {attempt+1} failed: {clean_msg}")

                # Check if this error is permanent (do not retry)
                is_permanent = any(perm in clean_msg.lower() for perm in PERMANENT_ERRORS)
                if is_permanent or attempt >= max_attempts:
                    log_error(f"[{self.task.task_id}] Download failed permanently: {clean_msg}")
                    self.failed_signal.emit(self.task.task_id, clean_msg or "Download failed.")
                    return

                # Recoverable error: wait for retry delay with cancel polling
                attempt += 1
                self.task.retry_count = attempt
                delay = self.task.retry_delay
                self.status_signal.emit(
                    self.task.task_id,
                    "Downloading",
                    f"Temporary network error. Retrying in {delay}s ({attempt}/{max_attempts})..."
                )

                for _ in range(delay * 10):
                    if self._is_cancelled:
                        self._cleanup_temp_files(dest_dir)
                        self.status_signal.emit(self.task.task_id, "Cancelled", "Download cancelled.")
                        return
                    if self._is_paused:
                        self.status_signal.emit(self.task.task_id, "Paused", "Download paused.")
                        return
                    time.sleep(0.1)

        if self._is_cancelled:
            self._cleanup_temp_files(dest_dir)
            self.status_signal.emit(self.task.task_id, "Cancelled", "Download cancelled.")
            return
        if self._is_paused:
            self.status_signal.emit(self.task.task_id, "Paused", "Download paused.")
            return

        # Determine downloaded file path
        downloaded_path = self._resolve_downloaded_file(info, dest_dir)
        if not downloaded_path or not downloaded_path.exists():
            # If subtitle-only download, look for .vtt or .srt
            if self.task.subtitle_only:
                candidates = list(dest_dir.glob("*.vtt")) + list(dest_dir.glob("*.srt"))
                if candidates:
                    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    downloaded_path = candidates[0]
            if not downloaded_path or not downloaded_path.exists():
                msg = "Downloaded file could not be located on disk."
                log_error(f"[{self.task.task_id}] {msg}")
                self.failed_signal.emit(self.task.task_id, msg)
                return

        # Format / Codec Conversion if requested and not subtitle-only
        final_file_path = str(downloaded_path)
        if not self.task.subtitle_only:
            try:
                target_ext = f".{self.task.output_format.lower().split()[0]}"
                audio_codec_pref = getattr(self.task, "audio_codec", "Keep Original")
                needs_conversion = (
                    is_audio_only
                    or ("Keep Original" not in self.task.codec)
                    or ("Keep Original" not in audio_codec_pref)
                    or (not downloaded_path.suffix.lower().endswith(target_ext))
                )
                if needs_conversion and ffmpeg_bin:
                    self.status_signal.emit(self.task.task_id, "Processing", "Converting media format & codec...")
                    final_file_path = MediaConverter.convert_media(
                        source_file=str(downloaded_path),
                        target_format=self.task.output_format,
                        target_video_codec=self.task.codec,
                        target_audio_codec=audio_codec_pref,
                        output_dir=str(dest_dir)
                    )
            except ConversionError as e:
                log_error(f"[{self.task.task_id}] Conversion error: {e}")
                self.failed_signal.emit(self.task.task_id, f"Conversion error: {e}")
                return
            except Exception as e:
                log_error(f"[{self.task.task_id}] Post-processing error: {e}")
                self.failed_signal.emit(self.task.task_id, f"Post-processing error: {e}")
                return

        # Inspect final file properties
        final_path_obj = Path(final_file_path)
        media_info = MediaInspector.inspect_file(str(final_path_obj))
        file_size_str = media_info.get("file_size_str") or MediaInspector.format_size(
            final_path_obj.stat().st_size if final_path_obj.exists() else 0
        )
        res = media_info.get("resolution") or self.task.quality
        codec = media_info.get("video_codec") or self.task.codec

        # Record into Download History
        try:
            history_manager.add_entry(
                file_name=final_path_obj.name,
                file_location=str(final_path_obj),
                website=self.task.platform,
                resolution=res,
                codec=codec.upper() if codec else self.task.codec,
                file_size=file_size_str
            )
        except Exception as e:
            log_warning(f"[{self.task.task_id}] Failed to save to history: {e}")

        log_info(f"[{self.task.task_id}] Download completed successfully: {final_file_path}")
        self.completed_signal.emit(
            self.task.task_id,
            final_file_path,
            file_size_str,
            res,
            codec
        )

    def _on_progress_hook(self, d: Dict[str, Any]) -> None:
        """Callback invoked by yt-dlp on progress events."""
        if self._is_cancelled:
            raise Exception("DOWNLOAD_CANCELLED")
        if self._is_paused:
            raise Exception("DOWNLOAD_PAUSED")

        status = d.get("status")
        if status == "downloading":
            now = time.time()
            # Throttle UI updates to max 10 times per second to prevent UI lagging
            if now - self._last_progress_update < 0.1:
                return
            self._last_progress_update = now

            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            self.task.downloaded_bytes = downloaded
            self.task.total_bytes = total

            if total and total > 0:
                percent = min(100.0, max(0.0, (downloaded / total) * 100.0))
            else:
                p_str = d.get("_percent_str", "0%").replace("%", "").strip()
                try:
                    percent = float(p_str)
                except ValueError:
                    percent = 0.0

            # Current Speed
            speed_val = d.get("speed")
            if speed_val and float(speed_val) > 0:
                cur_speed = float(speed_val)
                self.task.current_speed = cur_speed
                if cur_speed > self._peak_speed:
                    self._peak_speed = cur_speed
                    self.task.peak_speed = self._peak_speed
            else:
                cur_speed = self.task.current_speed

            # Average Speed
            elapsed = now - self._start_time
            if elapsed > 0.5 and downloaded > 0:
                avg_speed = downloaded / elapsed
                self.task.average_speed = avg_speed
            else:
                avg_speed = cur_speed

            # Formatted speeds
            cur_speed_str = f"{MediaInspector.format_size(cur_speed)}/s" if cur_speed > 0 else "—"
            peak_speed_str = f"{MediaInspector.format_size(self._peak_speed)}/s" if self._peak_speed > 0 else "—"
            avg_speed_str = f"{MediaInspector.format_size(avg_speed)}/s" if avg_speed > 0 else "—"

            self.task.speed_str = cur_speed_str
            self.task.average_speed_str = avg_speed_str
            self.task.peak_speed_str = peak_speed_str

            # ETA Calculation
            eta_str = "—"
            if cur_speed > 1024 and total > downloaded:
                remaining_bytes = total - downloaded
                eta_secs = int(remaining_bytes / cur_speed)
                h = eta_secs // 3600
                m = (eta_secs % 3600) // 60
                s = eta_secs % 60
                eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            elif d.get("_eta_str"):
                raw_eta = re.sub(r'\x1b\[[0-9;]*m', '', str(d.get("_eta_str"))).strip()
                if raw_eta and raw_eta != "None":
                    eta_str = raw_eta

            self.task.eta_str = eta_str
            self.task.progress = percent

            # Emit both standard and extended signals
            self.progress_signal.emit(self.task.task_id, percent, cur_speed_str, eta_str)
            self.extended_progress_signal.emit(
                self.task.task_id, percent, cur_speed_str, avg_speed_str, peak_speed_str, eta_str
            )

        elif status == "finished":
            fn = d.get("filename")
            if fn:
                self._downloaded_file = fn

    def _on_postprocessor_hook(self, d: Dict[str, Any]) -> None:
        """Callback invoked during yt-dlp post-processing."""
        if self._is_cancelled:
            raise Exception("DOWNLOAD_CANCELLED")
        if self._is_paused:
            raise Exception("DOWNLOAD_PAUSED")

        pp = d.get("postprocessor", "")
        status = d.get("status", "")
        if status == "started":
            self.status_signal.emit(self.task.task_id, "Processing", f"Processing {pp}...")

    def _cleanup_temp_files(self, dest_dir: Path) -> None:
        """Remove unneeded temporary .part and .ytdl files on cancellation."""
        try:
            for p in dest_dir.glob("*.part*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            for p in dest_dir.glob("*.ytdl"):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
        except Exception:
            pass

    def _resolve_downloaded_file(self, info: Optional[Dict[str, Any]], dest_dir: Path) -> Optional[Path]:
        """Locate completed file on disk from info dict or recorded hook."""
        if self._downloaded_file and Path(self._downloaded_file).exists():
            return Path(self._downloaded_file)

        if not info:
            return None

        req_downloads = info.get("requested_downloads")
        if req_downloads and isinstance(req_downloads, list):
            fp = req_downloads[0].get("filepath")
            if fp and Path(fp).exists():
                return Path(fp)

        fn = info.get("_filename")
        if fn and Path(fn).exists():
            return Path(fn)

        title_sanitized = "".join(c for c in info.get("title", "") if c.isalnum() or c in (" ", "_", "-")).strip()
        if title_sanitized:
            candidates = list(dest_dir.glob(f"*{title_sanitized[:30]}*"))
            candidates = [c for c in candidates if not c.suffix.endswith((".part", ".ytdl"))]
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return candidates[0]

        return None


class DownloadManager(QObject):
    """Coordinates download queue, concurrency limits, speed metrics, and workers."""

    task_added = Signal(object)                      # DownloadTask
    task_updated = Signal(object)                    # DownloadTask
    task_progress = Signal(str, float, str, str)     # task_id, percent, speed, eta
    task_extended_progress = Signal(str, float, str, str, str, str) # task_id, percent, speed, avg, peak, eta
    task_status_changed = Signal(str, str, str)      # task_id, status, message
    task_completed = Signal(object)                  # DownloadTask
    task_failed = Signal(str, str)                   # task_id, error_message

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DownloadManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_concurrent: Optional[Any] = None):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        self.max_concurrent = resolve_max_concurrent(max_concurrent)
        self.tasks: Dict[str, DownloadTask] = {}
        self.queue: List[str] = []
        self.active_workers: Dict[str, DownloadWorker] = {}

    def set_max_concurrent(self, max_concurrent: Any) -> None:
        """Update concurrency threshold and trigger queue processing."""
        self.max_concurrent = resolve_max_concurrent(max_concurrent)
        self.process_queue()

    def add_download(
        self,
        url: str,
        title: str,
        quality: str,
        output_format: str,
        codec: str,
        thumbnail: str = "",
        platform: str = "Web Media",
        download_dir: Optional[str] = None,
        audio_codec: str = "Keep Original",
        subtitles: bool = False,
        subtitle_lang: str = "en",
        embed_subtitles: bool = False,
        subtitle_only: bool = False
    ) -> DownloadTask:
        """Create a new download task, add it to queue, and process."""
        target_dir = download_dir or str(destination_manager.get_destination())
        task = DownloadTask(
            url=url,
            title=title,
            quality=quality,
            output_format=output_format,
            codec=codec,
            thumbnail=thumbnail,
            platform=platform,
            download_dir=target_dir,
            audio_codec=audio_codec,
            subtitles=subtitles,
            subtitle_lang=subtitle_lang,
            embed_subtitles=embed_subtitles,
            subtitle_only=subtitle_only
        )
        self.tasks[task.task_id] = task
        self.queue.append(task.task_id)
        log_info(f"Task queued: {task.title} (ID: {task.task_id})")
        self.task_added.emit(task)
        self.process_queue()
        return task

    def process_queue(self) -> None:
        """Schedule pending queued tasks up to the concurrency limit."""
        while len(self.active_workers) < self.max_concurrent:
            next_task_id = None
            for tid in self.queue:
                t = self.tasks.get(tid)
                if t and t.status in ("Pending", "Queued") and tid not in self.active_workers:
                    next_task_id = tid
                    break

            if not next_task_id:
                break

            task = self.tasks[next_task_id]
            self._start_worker(task)

    def _start_worker(self, task: DownloadTask) -> None:
        """Instantiate and start a background worker for the given task."""
        worker = DownloadWorker(task)
        self.active_workers[task.task_id] = worker

        worker.progress_signal.connect(self._on_worker_progress)
        worker.extended_progress_signal.connect(self._on_worker_extended_progress)
        worker.status_signal.connect(self._on_worker_status)
        worker.completed_signal.connect(self._on_worker_completed)
        worker.failed_signal.connect(self._on_worker_failed)

        worker.start()

    def _on_worker_progress(self, task_id: str, percent: float, speed: str, eta: str) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.progress = percent
            task.speed_str = speed
            task.eta_str = eta
            self.task_progress.emit(task_id, percent, speed, eta)

    def _on_worker_extended_progress(
        self, task_id: str, percent: float, speed: str, avg_speed: str, peak_speed: str, eta: str
    ) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.progress = percent
            task.speed_str = speed
            task.average_speed_str = avg_speed
            task.peak_speed_str = peak_speed
            task.eta_str = eta
            self.task_extended_progress.emit(task_id, percent, speed, avg_speed, peak_speed, eta)

    def _on_worker_status(self, task_id: str, status: str, message: str) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            self.task_status_changed.emit(task_id, status, message)
            if status in ("Paused", "Cancelled"):
                self._cleanup_worker(task_id)
                self.process_queue()

    def _on_worker_completed(self, task_id: str, path: str, size: str, res: str, codec: str) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.status = "Completed"
            task.progress = 100.0
            task.final_file_path = path
            task.file_size_str = size
            task.final_resolution = res
            task.final_codec = codec
            self.task_completed.emit(task)
            self.task_updated.emit(task)

        self._cleanup_worker(task_id)
        self.process_queue()

    def _on_worker_failed(self, task_id: str, error_message: str) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.status = "Failed"
            task.error_message = error_message
            self.task_failed.emit(task_id, error_message)
            self.task_updated.emit(task)

        self._cleanup_worker(task_id)
        self.process_queue()

    def _cleanup_worker(self, task_id: str) -> None:
        """Remove worker from active pool."""
        if task_id in self.active_workers:
            del self.active_workers[task_id]

    def pause_task(self, task_id: str) -> None:
        """Pause a running or queued download task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "Paused"
        if task_id in self.active_workers:
            worker = self.active_workers[task_id]
            worker.pause()
        self.task_status_changed.emit(task_id, "Paused", "Download paused.")
        self.task_updated.emit(task)

    def resume_task(self, task_id: str) -> None:
        """Resume a paused task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        if task.status == "Paused":
            task.status = "Pending"
            if task_id not in self.queue:
                self.queue.append(task_id)
            self.task_status_changed.emit(task_id, "Pending", "Queued for download...")
            self.task_updated.emit(task)
            self.process_queue()

    def cancel_task(self, task_id: str) -> None:
        """Cancel a running or queued task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "Cancelled"
        if task_id in self.queue:
            self.queue.remove(task_id)
        if task_id in self.active_workers:
            worker = self.active_workers[task_id]
            worker.cancel()
        self.task_status_changed.emit(task_id, "Cancelled", "Download cancelled.")
        self.task_updated.emit(task)

    def retry_task(self, task_id: str) -> None:
        """Retry a failed or cancelled task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "Pending"
        task.progress = 0.0
        task.error_message = ""
        task.retry_count = 0
        if task_id not in self.queue:
            self.queue.append(task_id)
        self.task_status_changed.emit(task_id, "Pending", "Queued for retry...")
        self.task_updated.emit(task)
        self.process_queue()

    # Convenience aliases
    pause_download = pause_task
    resume_download = resume_task
    cancel_download = cancel_task
    retry_download = retry_task

    def pause_all(self) -> None:
        """Pause all active and pending tasks."""
        for tid in list(self.active_workers.keys()):
            self.pause_task(tid)
        for tid in self.queue:
            t = self.tasks.get(tid)
            if t and t.status in ("Pending", "Queued"):
                t.status = "Paused"
                self.task_updated.emit(t)

    def resume_all(self) -> None:
        """Resume all paused tasks."""
        for tid, t in self.tasks.items():
            if t.status == "Paused":
                t.status = "Pending"
                if tid not in self.queue:
                    self.queue.append(tid)
                self.task_updated.emit(t)
        self.process_queue()

    def clear_finished(self) -> None:
        """Remove completed, cancelled, and failed tasks from tracking."""
        removable = [
            tid for tid, t in self.tasks.items()
            if t.status in ("Completed", "Cancelled", "Failed")
        ]
        for tid in removable:
            if tid in self.queue:
                self.queue.remove(tid)
            if tid in self.tasks:
                del self.tasks[tid]


# Global download manager singleton
download_manager = DownloadManager()
