"""
Video Extractor Module.
Interfaces with yt-dlp to inspect video metadata, available streams, playlists,
and subtitle tracks.
"""
import re
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import yt_dlp

from app.constants import THUMBNAILS_CACHE_DIR
from core.url_analyzer import URLAnalyzer


class ExtractionError(Exception):
    """Custom exception raised when video metadata extraction fails."""
    pass


class VideoExtractor:
    """Extracts metadata, formats, playlists, and subtitles via yt-dlp."""

    @staticmethod
    def format_duration(seconds: Optional[float]) -> str:
        """Convert duration in seconds to HH:MM:SS or MM:SS."""
        if seconds is None or seconds <= 0:
            return "Live / Unknown"
        total_sec = int(round(seconds))
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    @classmethod
    def _find_best_thumbnail(cls, info: Dict[str, Any]) -> Optional[str]:
        """Find the most suitable thumbnail URL."""
        direct = info.get("thumbnail")
        if direct and direct.startswith("http"):
            return direct

        thumbnails: List[Dict[str, Any]] = info.get("thumbnails", [])
        if not thumbnails:
            return None

        def sort_key(t: Dict[str, Any]):
            pref = t.get("preference", 0) or 0
            width = t.get("width", 0) or 0
            height = t.get("height", 0) or 0
            return (pref, width * height)

        sorted_thumbs = sorted(thumbnails, key=sort_key, reverse=True)
        for t in sorted_thumbs:
            url = t.get("url")
            if url and url.startswith("http"):
                return url
        return None

    @classmethod
    def get_cached_thumbnail_path(cls, thumb_url: str) -> Optional[Path]:
        """Check if thumbnail is already cached on disk."""
        if not thumb_url:
            return None
        h = hashlib.md5(thumb_url.encode("utf-8")).hexdigest()
        cache_path = THUMBNAILS_CACHE_DIR / f"{h}.jpg"
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        return None

    @classmethod
    def cache_thumbnail_bytes(cls, thumb_url: str, data: bytes) -> Optional[Path]:
        """Save thumbnail bytes into local cache directory."""
        if not thumb_url or not data:
            return None
        try:
            THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            h = hashlib.md5(thumb_url.encode("utf-8")).hexdigest()
            cache_path = THUMBNAILS_CACHE_DIR / f"{h}.jpg"
            cache_path.write_bytes(data)
            return cache_path
        except Exception:
            return None

    @staticmethod
    def is_playlist_url(url: str) -> bool:
        """Heuristic check whether URL likely refers to a playlist."""
        url_lower = url.lower()
        if "list=" in url_lower and "index=" not in url_lower:
            return True
        if "/playlist" in url_lower or "/sets/" in url_lower or "/album/" in url_lower:
            return True
        return False

    def extract_playlist_info(self, url: str) -> Dict[str, Any]:
        """
        Extract playlist metadata and list of child video items without downloading.
        """
        clean_url = URLAnalyzer.normalize_url(url)
        if not URLAnalyzer.is_valid_url(clean_url):
            raise ExtractionError("Invalid URL format.")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "nocheckcertificate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                raw_info = ydl.extract_info(clean_url, download=False)
        except Exception as e:
            msg = str(e)
            clean_msg = re.sub(r'^(?:ERROR:\s*)?(?:\[[^\]]+\]\s*)?', '', msg).strip()
            raise ExtractionError(clean_msg or "Failed to extract playlist information.")

        if not raw_info:
            raise ExtractionError("No playlist information found.")

        title = raw_info.get("title") or "Unnamed Playlist"
        entries_raw = raw_info.get("entries") or []
        entries = []
        for i, item in enumerate(entries_raw):
            if not item:
                continue
            item_id = item.get("id") or str(i + 1)
            item_title = item.get("title") or f"Video {i + 1}"
            item_url = item.get("url") or item.get("webpage_url")
            if item_url and not item_url.startswith("http"):
                # Complete relative URLs
                if "youtube" in clean_url or "youtu.be" in clean_url:
                    item_url = f"https://www.youtube.com/watch?v={item_id}"
                else:
                    item_url = clean_url
            elif not item_url:
                item_url = f"https://www.youtube.com/watch?v={item_id}"

            dur = item.get("duration")
            entries.append({
                "index": i + 1,
                "id": item_id,
                "title": item_title,
                "url": item_url,
                "duration": dur,
                "duration_str": self.format_duration(dur),
                "uploader": item.get("uploader") or item.get("channel") or "Unknown",
                "thumbnail": self._find_best_thumbnail(item) or ""
            })

        return {
            "is_playlist": True,
            "id": raw_info.get("id", ""),
            "title": title,
            "url": clean_url,
            "item_count": len(entries),
            "uploader": raw_info.get("uploader") or raw_info.get("channel") or "Unknown",
            "entries": entries
        }

    def extract_subtitles_info(self, raw_info: Dict[str, Any]) -> List[Tuple[str, str]]:
        """
        Parse subtitles and automatic captions from raw yt-dlp metadata.
        Returns a sorted list of unique (lang_code, lang_name) tuples.
        """
        langs: Dict[str, str] = {}
        # Manual subtitles
        subs = raw_info.get("subtitles") or {}
        for code, track_list in subs.items():
            name = code
            if track_list and isinstance(track_list, list) and len(track_list) > 0:
                name = track_list[0].get("name") or code
            langs[code] = f"{name} ({code})"

        # Automatic captions
        auto_subs = raw_info.get("automatic_captions") or {}
        for code, track_list in auto_subs.items():
            if code not in langs:
                name = code
                if track_list and isinstance(track_list, list) and len(track_list) > 0:
                    name = track_list[0].get("name") or code
                langs[code] = f"{name} [Auto] ({code})"

        # Sort: English first if available, then alphabetically
        sorted_items = sorted(
            langs.items(),
            key=lambda x: (0 if x[0].startswith("en") else 1, x[1].lower())
        )
        return sorted_items

    def extract_info(self, url: str) -> Dict[str, Any]:
        """
        Extract media information without downloading media files.
        Returns a clean dictionary containing title, platform, duration,
        uploader, thumbnail URL, available formats, and subtitle tracks.
        """
        clean_url = URLAnalyzer.normalize_url(url)
        if not URLAnalyzer.is_valid_url(clean_url):
            raise ExtractionError("Invalid URL format. Please provide a valid web link.")

        # Check if playlist
        is_playlist = self.is_playlist_url(clean_url)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": not is_playlist,
            "extract_flat": False,
            "nocheckcertificate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                raw_info = ydl.extract_info(clean_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if "Private video" in msg:
                raise ExtractionError("This video is private and cannot be downloaded.")
            elif "Sign in" in msg or "login" in msg.lower():
                raise ExtractionError("Authentication or login is required to access this video.")
            elif "Join this channel" in msg:
                raise ExtractionError("This video requires a paid channel membership.")
            elif "DRM" in msg or "encrypted" in msg.lower():
                raise ExtractionError("This video is DRM-protected and cannot be extracted.")
            elif "Video unavailable" in msg or "not available" in msg.lower():
                raise ExtractionError("The requested video is unavailable or has been removed.")
            elif "Unsupported URL" in msg:
                raise ExtractionError("This website or URL format is not supported.")
            else:
                clean_msg = re.sub(r'^(?:ERROR:\s*)?(?:\[[^\]]+\]\s*)?', '', msg).strip()
                raise ExtractionError(clean_msg or "Failed to access video stream.")
        except Exception as e:
            raise ExtractionError(f"Extraction error: {str(e)}")

        if not raw_info:
            raise ExtractionError("No video information could be retrieved.")

        # In case yt-dlp returned a playlist object
        if raw_info.get("_type") == "playlist":
            entries = list(raw_info.get("entries") or [])
            if entries:
                return {
                    "is_playlist": True,
                    "id": raw_info.get("id", ""),
                    "url": clean_url,
                    "title": raw_info.get("title") or "Playlist",
                    "platform": URLAnalyzer.detect_platform(clean_url),
                    "item_count": len(entries),
                    "uploader": raw_info.get("uploader") or "Unknown",
                    "thumbnail": self._find_best_thumbnail(raw_info) or (self._find_best_thumbnail(entries[0]) if entries[0] else ""),
                    "entries": [
                        {
                            "index": idx + 1,
                            "id": ent.get("id"),
                            "title": ent.get("title") or f"Item {idx + 1}",
                            "url": ent.get("url") or ent.get("webpage_url") or f"https://www.youtube.com/watch?v={ent.get('id')}",
                            "duration": ent.get("duration"),
                            "duration_str": self.format_duration(ent.get("duration")),
                            "uploader": ent.get("uploader") or "",
                            "thumbnail": self._find_best_thumbnail(ent) or ""
                        }
                        for idx, ent in enumerate(entries) if ent
                    ],
                    "raw_info": raw_info
                }

        title = raw_info.get("title") or "Untitled Media"
        duration_sec = raw_info.get("duration")
        duration_str = self.format_duration(duration_sec)
        uploader = (
            raw_info.get("uploader")
            or raw_info.get("channel")
            or raw_info.get("creator")
            or raw_info.get("uploader_id")
            or "Unknown"
        )
        extractor_key = raw_info.get("extractor_key") or raw_info.get("extractor")
        platform = URLAnalyzer.detect_platform(clean_url, extractor_key)
        thumbnail = self._find_best_thumbnail(raw_info)
        formats = raw_info.get("formats", [])
        subtitles = self.extract_subtitles_info(raw_info)

        return {
            "is_playlist": False,
            "id": raw_info.get("id", ""),
            "url": clean_url,
            "webpage_url": raw_info.get("webpage_url") or clean_url,
            "title": title,
            "platform": platform,
            "duration": duration_sec,
            "duration_str": duration_str,
            "uploader": uploader,
            "thumbnail": thumbnail,
            "formats": formats,
            "subtitles": subtitles,
            "raw_info": raw_info
        }
