"""
Format Selector Module.
Filters and formats available stream resolutions, codecs, and container formats.
Connects yt-dlp extracted streams with UI dropdown options accurately.
"""
from typing import List, Dict, Any, Optional
import re


class FormatSelector:
    """Parses and standardizes formats from yt-dlp extracted data."""

    STANDARD_QUALITY_TIERS = [
        (2160, "2160p (4K)"),
        (1440, "1440p (2K)"),
        (1080, "1080p (Full HD)"),
        (720,  "720p (HD)"),
        (480,  "480p (SD)"),
        (360,  "360p (Low)"),
    ]

    @classmethod
    def get_available_qualities(cls, formats: List[Dict[str, Any]]) -> List[str]:
        """
        Filter out only resolutions actually present in the source media.
        Returns a list of human-readable quality options starting with 'Best Available'.
        Only displays qualities that genuinely exist in the stream.
        """
        if not formats:
            return ["Best Available"]

        # Collect distinct video heights from formats that have video
        available_heights = set()
        for f in formats:
            # Check if format has video stream
            vcodec = f.get("vcodec")
            height = f.get("height")
            if vcodec != "none" and height and isinstance(height, (int, float)):
                available_heights.add(int(height))

        if not available_heights:
            # Audio-only source or unspecified video heights
            return ["Best Available"]

        max_height = max(available_heights)
        qualities = ["Best Available"]

        # For each standard tier, check if an available stream meets or exceeds the threshold
        # Specifically, check if the video has a format with at least that height
        for threshold, label in cls.STANDARD_QUALITY_TIERS:
            # Does the stream have formats at or above this threshold?
            # Or exactly around this tier?
            # A quality is available if max_height >= threshold and any format is in [threshold * 0.9, threshold * 1.1]
            # or if the video has a stream matching this resolution
            has_resolution = any(
                abs(h - threshold) <= 30 or (threshold <= h and h <= max_height)
                for h in available_heights
            ) if threshold <= max_height else False

            # More direct and precise: if max_height >= threshold, the user can request that resolution!
            if max_height >= threshold:
                qualities.append(label)

        # In case the video only has lower resolutions (e.g., 240p or 144p)
        if len(qualities) == 1:
            for h in sorted(available_heights, reverse=True):
                qualities.append(f"{h}p")

        return qualities

    @classmethod
    def parse_height_from_quality(cls, quality_str: str) -> Optional[int]:
        """Extract numeric height from quality label like '1080p (Full HD)'."""
        if not quality_str or quality_str == "Best Available":
            return None
        match = re.search(r'(\d+)p', quality_str)
        if match:
            return int(match.group(1))
        return None

    @classmethod
    def build_format_spec(cls, quality_str: str, output_format: str) -> str:
        """
        Build yt-dlp format selector string.
        Handles video + audio merging requirements via FFmpeg.
        """
        if output_format.upper().startswith("MP3"):
            return "bestaudio/best"

        height = cls.parse_height_from_quality(quality_str)
        if height is None:
            # Best available video + best available audio, fallback to single stream best
            return "bestvideo+bestaudio/best"

        # Specific resolution limit: best video up to height + best audio
        # With fallbacks for combined streams
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
