"""
Media Converter Module.
Wraps FFmpeg commands for re-encoding, container conversion, and audio extraction.
Supports MP4, MKV, WebM, MOV, and MP3, plus H.264, H.265, AV1, VP9, AAC, Opus, FLAC.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import config
from app.constants import find_binary
from core.media_inspector import MediaInspector
from core.download_destination import destination_manager


class ConversionError(Exception):
    """Custom exception raised when FFmpeg conversion or remuxing fails."""
    pass


class MediaConverter:
    """Provides robust FFmpeg conversion routines with intelligent stream inspection."""

    @staticmethod
    def get_ffmpeg_path() -> Optional[str]:
        """Return path to ffmpeg binary if available."""
        return find_binary("ffmpeg")

    @classmethod
    def convert_media(
        cls,
        source_file: str,
        target_format: str,
        target_video_codec: str = "Keep Original Codec",
        target_audio_codec: str = "Keep Original",
        output_dir: Optional[str] = None
    ) -> str:
        """
        Convert downloaded media to requested container and video/audio codecs.
        target_format: 'MP4', 'MKV', 'WebM', 'MOV', 'MP3 (Audio Only)'
        target_video_codec: 'Keep Original Codec', 'H.264 (AVC)', 'H.265 (HEVC)', 'AV1', 'VP9'
        target_audio_codec: 'Keep Original', 'AAC', 'MP3', 'Opus', 'FLAC'
        """
        source_path = Path(source_file)
        if not source_path.exists():
            raise ConversionError(f"Source file not found: {source_file}")

        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin:
            raise ConversionError("FFmpeg was not found in system PATH. Please ensure FFmpeg is installed.")

        if output_dir:
            dest_folder = destination_manager.resolve_task_destination(output_dir)
        else:
            dest_folder = source_path.parent
        dest_folder.mkdir(parents=True, exist_ok=True)

        preserve_original = config.get("preserve_original_video", False)

        # 1. Handle Audio Extraction to MP3
        if "MP3" in target_format.upper():
            return cls._extract_audio(source_path, dest_folder, ffmpeg_bin, "mp3", preserve_original)

        # 2. Handle Video Container & Codec Conversion
        return cls._convert_video(
            source_path,
            dest_folder,
            target_format,
            target_video_codec,
            target_audio_codec,
            ffmpeg_bin,
            preserve_original
        )

    @classmethod
    def _extract_audio(
        cls,
        source_path: Path,
        dest_folder: Path,
        ffmpeg_bin: str,
        audio_ext: str = "mp3",
        preserve_original: bool = False
    ) -> str:
        """Extract audio stream with high quality."""
        target_ext = f".{audio_ext.lower()}"
        if source_path.suffix.lower() == target_ext:
            return str(source_path)

        target_file = dest_folder / f"{source_path.stem}{target_ext}"
        temp_file = dest_folder / f"{source_path.stem}_audio_tmp{target_ext}"

        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass

        if audio_ext.lower() == "mp3":
            codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif audio_ext.lower() == "flac":
            codec_args = ["-c:a", "flac"]
        elif audio_ext.lower() == "opus":
            codec_args = ["-c:a", "libopus", "-b:a", "160k"]
        else:
            codec_args = ["-c:a", "aac", "-b:a", "192k"]

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            "-vn",
            *codec_args,
            str(temp_file)
        ]

        cls._execute_ffmpeg(cmd, f"Audio extraction to {audio_ext.upper()} failed")

        if target_file.exists():
            try:
                target_file.unlink()
            except OSError:
                pass
        temp_file.rename(target_file)

        if not preserve_original and source_path.exists() and source_path != target_file:
            try:
                source_path.unlink()
            except OSError:
                pass

        return str(target_file)

    @classmethod
    def _convert_video(
        cls,
        source_path: Path,
        dest_folder: Path,
        target_format: str,
        target_vcodec: str,
        target_acodec: str,
        ffmpeg_bin: str,
        preserve_original: bool = False
    ) -> str:
        """Process video conversion with stream copy optimization and container rules."""
        ext_map = {
            "MP4": ".mp4",
            "MKV": ".mkv",
            "WEBM": ".webm",
            "MOV": ".mov"
        }
        fmt_key = target_format.split()[0].upper()
        target_ext = ext_map.get(fmt_key, ".mp4")
        source_ext = source_path.suffix.lower()

        # Inspect current video streams
        info = MediaInspector.inspect_file(str(source_path))
        current_vcodec = (info.get("video_codec") or "").lower()
        current_acodec = (info.get("audio_codec") or "").lower()

        # 1. Determine Video Codec Arguments
        wants_h264 = "H.264" in target_vcodec or "AVC" in target_vcodec
        wants_hevc = "H.265" in target_vcodec or "HEVC" in target_vcodec
        wants_av1 = "AV1" in target_vcodec
        wants_vp9 = "VP9" in target_vcodec
        wants_keep_v = "Keep Original" in target_vcodec

        video_args = ["-c:v", "copy"]
        video_needs_transcode = False

        if wants_h264:
            if current_vcodec in ("h264", "avc1") and source_ext == target_ext:
                video_args = ["-c:v", "copy"]
            else:
                video_needs_transcode = True
                video_args = ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p"]
        elif wants_hevc:
            if current_vcodec in ("hevc", "h265") and source_ext == target_ext:
                video_args = ["-c:v", "copy"]
            else:
                video_needs_transcode = True
                video_args = ["-c:v", "libx265", "-crf", "28", "-preset", "medium", "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]
        elif wants_av1:
            if "av01" in current_vcodec or "av1" in current_vcodec:
                video_args = ["-c:v", "copy"]
            else:
                video_needs_transcode = True
                enc = "libsvtav1" if MediaInspector.has_encoder("libsvtav1") else "libaom-av1"
                video_args = ["-c:v", enc, "-crf", "30", "-preset", "6", "-pix_fmt", "yuv420p"]
        elif wants_vp9:
            if "vp9" in current_vcodec:
                video_args = ["-c:v", "copy"]
            else:
                video_needs_transcode = True
                video_args = ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0"]
        elif wants_keep_v:
            # Special container constraint: WebM requires VP8, VP9, or AV1
            if target_ext == ".webm" and current_vcodec not in ("vp9", "vp8", "av01", "av1"):
                video_needs_transcode = True
                video_args = ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0"]
            else:
                video_args = ["-c:v", "copy"]

        # 2. Determine Audio Codec Arguments
        wants_aac = "AAC" in target_acodec
        wants_mp3 = "MP3" in target_acodec
        wants_opus = "OPUS" in target_acodec.upper()
        wants_flac = "FLAC" in target_acodec.upper()
        wants_keep_a = "Keep Original" in target_acodec or not target_acodec

        audio_args = ["-c:a", "copy"]
        audio_needs_transcode = False

        if wants_aac:
            audio_needs_transcode = (current_acodec != "aac")
            audio_args = ["-c:a", "aac", "-b:a", "192k"]
        elif wants_mp3:
            audio_needs_transcode = (current_acodec != "mp3")
            audio_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif wants_opus:
            audio_needs_transcode = ("opus" not in current_acodec)
            audio_args = ["-c:a", "libopus", "-b:a", "128k"]
        elif wants_flac:
            audio_needs_transcode = ("flac" not in current_acodec)
            audio_args = ["-c:a", "flac"]
        elif wants_keep_a:
            # Container audio constraints
            if target_ext == ".webm" and current_acodec not in ("opus", "vorbis"):
                audio_needs_transcode = True
                audio_args = ["-c:a", "libopus", "-b:a", "128k"]
            elif target_ext == ".mp4" and current_acodec not in ("aac", "mp3", "m4a", ""):
                audio_needs_transcode = True
                audio_args = ["-c:a", "aac", "-b:a", "192k"]
            elif target_ext == ".mov" and current_acodec not in ("aac", "alac", "pcm", ""):
                audio_needs_transcode = True
                audio_args = ["-c:a", "aac", "-b:a", "192k"]

        # If already matching container, video codec, and audio codec, skip conversion!
        if not video_needs_transcode and not audio_needs_transcode and source_ext == target_ext:
            return str(source_path)

        # Clear output filename tag
        suffix_tag = ""
        if wants_hevc and video_needs_transcode:
            suffix_tag = "_hevc"
        elif wants_av1 and video_needs_transcode:
            suffix_tag = "_av1"
        elif wants_vp9 and video_needs_transcode:
            suffix_tag = "_vp9"
        elif wants_h264 and video_needs_transcode and source_ext == target_ext:
            suffix_tag = "_h264"

        target_file = dest_folder / f"{source_path.stem}{suffix_tag}{target_ext}"
        temp_file = dest_folder / f"{source_path.stem}_conv_tmp{target_ext}"

        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            *video_args,
            *audio_args,
            str(temp_file)
        ]

        cls._execute_ffmpeg(cmd, "Media conversion failed")

        if target_file.exists() and target_file != source_path:
            try:
                target_file.unlink()
            except OSError:
                pass

        temp_file.rename(target_file)

        # Remove source file unless user opted to preserve original video
        if not preserve_original and source_path.exists() and source_path != target_file and suffix_tag == "":
            try:
                source_path.unlink()
            except OSError:
                pass

        return str(target_file)

    @staticmethod
    def _execute_ffmpeg(cmd: List[str], error_prefix: str) -> None:
        """Execute FFmpeg command without showing black command window on Windows."""
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=3600
            )
            if proc.returncode != 0:
                err_lines = proc.stderr.strip().splitlines()
                last_err = err_lines[-1] if err_lines else "Unknown error"
                raise ConversionError(f"{error_prefix}: {last_err}")
        except subprocess.TimeoutExpired:
            raise ConversionError(f"{error_prefix}: Process timed out")
        except Exception as e:
            if isinstance(e, ConversionError):
                raise
            raise ConversionError(f"{error_prefix}: {str(e)}")
