"""
Media Inspector Module.
Uses FFprobe to verify output stream codecs, resolutions, bitrates, and durations.
Also verifies availability of FFmpeg, FFprobe, and hardware acceleration encoders.
"""
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from app.constants import find_binary


class MediaInspector:
    """Reads media container streams and metadata via FFprobe."""

    _cached_encoders: Optional[Set[str]] = None
    _cached_hw_accel: Optional[List[str]] = None

    @staticmethod
    def get_ffmpeg_path() -> Optional[str]:
        """Return path to ffmpeg executable."""
        return find_binary("ffmpeg")

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Verify whether ffmpeg executable is available."""
        return find_binary("ffmpeg") is not None

    @staticmethod
    def get_ffprobe_path() -> Optional[str]:
        """Return path to ffprobe executable."""
        return find_binary("ffprobe")

    @staticmethod
    def is_ffprobe_available() -> bool:
        """Verify whether ffprobe executable is available."""
        return find_binary("ffprobe") is not None

    @staticmethod
    def format_size(size_bytes: Optional[int]) -> str:
        """Format bytes into readable string (e.g., 24.5 MB)."""
        if size_bytes is None or size_bytes <= 0:
            return "—"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    @classmethod
    def get_available_encoders(cls) -> Set[str]:
        """Query FFmpeg for all compiled encoder names."""
        if cls._cached_encoders is not None:
            return cls._cached_encoders

        cls._cached_encoders = set()
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin:
            return cls._cached_encoders

        try:
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            proc = subprocess.run(
                [ffmpeg_bin, "-encoders"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=10
            )
            for line in proc.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and len(parts[0]) == 6:
                    cls._cached_encoders.add(parts[1])
        except Exception:
            pass

        return cls._cached_encoders

    @classmethod
    def has_encoder(cls, encoder_name: str) -> bool:
        """Check if a specific encoder is compiled into FFmpeg."""
        return encoder_name in cls.get_available_encoders()

    @classmethod
    def detect_hardware_encoders(cls) -> List[str]:
        """Test and return actually working GPU hardware encoders on the host machine."""
        if cls._cached_hw_accel is not None:
            return cls._cached_hw_accel

        cls._cached_hw_accel = []
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin:
            return cls._cached_hw_accel

        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        candidates = [
            ("NVIDIA NVENC (CUDA)", "h264_nvenc"),
            ("Intel QuickSync (QSV)", "h264_qsv"),
            ("AMD AMF", "h264_amf")
        ]

        for label, enc in candidates:
            if cls.has_encoder(enc):
                try:
                    res = subprocess.run(
                        [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.05", "-c:v", enc, "-f", "null", "-"],
                        capture_output=True,
                        startupinfo=startupinfo,
                        timeout=4
                    )
                    if res.returncode == 0:
                        cls._cached_hw_accel.append(label)
                except Exception:
                    pass

        return cls._cached_hw_accel

    @classmethod
    def inspect_file(cls, file_path: str) -> Dict[str, Any]:
        """
        Inspect video/audio stream properties using FFprobe.
        Returns a dict with video_codec, audio_codec, width, height, resolution,
        framerate, bitrate, duration, container, and file_size.
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": "File does not exist"}

        result: Dict[str, Any] = {
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "file_size": path.stat().st_size,
            "file_size_str": cls.format_size(path.stat().st_size),
            "video_codec": None,
            "audio_codec": None,
            "width": None,
            "height": None,
            "resolution": "—",
            "resolution_full": "—",
            "framerate": "—",
            "bitrate": "—",
            "duration": None,
            "duration_str": "—",
            "audio_channels": "—",
            "audio_sample_rate": "—",
            "container": path.suffix.replace(".", "").upper(),
            "format_name": path.suffix.replace(".", "").upper()
        }

        ffprobe_bin = cls.get_ffprobe_path()
        if not ffprobe_bin:
            return result

        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path)
        ]

        try:
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=10
            )

            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout)
                streams = data.get("streams", [])
                format_info = data.get("format", {})

                if "duration" in format_info:
                    try:
                        dur = float(format_info["duration"])
                        result["duration"] = dur
                        m, s = divmod(int(dur), 60)
                        h, m = divmod(m, 60)
                        result["duration_str"] = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                    except (ValueError, TypeError):
                        pass

                if "bit_rate" in format_info:
                    try:
                        br = int(format_info["bit_rate"])
                        result["bitrate"] = f"{br // 1000} kbps"
                    except (ValueError, TypeError):
                        pass

                if format_info.get("format_long_name"):
                    result["container"] = format_info.get("format_long_name").split(",")[0].strip()

                for stream in streams:
                    codec_type = stream.get("codec_type")
                    if codec_type == "video" and not result["video_codec"]:
                        result["video_codec"] = stream.get("codec_name", "").upper()
                        w = stream.get("width")
                        h = stream.get("height")
                        result["width"] = w
                        result["height"] = h
                        if h:
                            result["resolution"] = f"{h}p"
                            if w:
                                result["resolution_full"] = f"{w}x{h}"

                        # Framerate calculation
                        r_fps = stream.get("r_frame_rate", "")
                        if "/" in r_fps:
                            try:
                                num, den = r_fps.split("/")
                                if float(den) > 0:
                                    fps_val = float(num) / float(den)
                                    result["framerate"] = f"{fps_val:.2f} fps" if fps_val % 1 else f"{int(fps_val)} fps"
                            except Exception:
                                pass
                        elif r_fps:
                            result["framerate"] = f"{r_fps} fps"

                    elif codec_type == "audio" and not result["audio_codec"]:
                        result["audio_codec"] = stream.get("codec_name", "").upper()
                        channels = stream.get("channels")
                        if channels:
                            result["audio_channels"] = f"{channels} (Stereo)" if channels == 2 else f"{channels} channels"
                        sr = stream.get("sample_rate")
                        if sr:
                            result["audio_sample_rate"] = f"{sr} Hz"

        except Exception as e:
            result["error"] = str(e)

        return result

    @classmethod
    def get_detailed_metadata(cls, file_path: str) -> Dict[str, str]:
        """
        Return structured key-value labels and values for UI Download Details dialog.
        """
        info = cls.inspect_file(file_path)
        return {
            "File Name": info.get("file_name", "—"),
            "File Size": info.get("file_size_str", "—"),
            "Duration": info.get("duration_str", "—"),
            "Resolution": info.get("resolution_full", info.get("resolution", "—")),
            "Frame Rate": info.get("framerate", "—"),
            "Video Codec": info.get("video_codec") or "None (Audio Only)",
            "Audio Codec": info.get("audio_codec") or "None",
            "Audio Channels": info.get("audio_channels", "—"),
            "Audio Sample Rate": info.get("audio_sample_rate", "—"),
            "Bitrate": info.get("bitrate", "—"),
            "Container Format": info.get("container", "—"),
            "File Path": info.get("file_path", file_path)
        }
