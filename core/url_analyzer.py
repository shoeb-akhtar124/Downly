"""
URL Analyzer Module.
Validates input video URLs and identifies source platforms.
"""
from typing import Optional
from urllib.parse import urlparse
import re


class URLAnalyzer:
    """Analyzes and validates media URLs for supported video platforms."""

    PLATFORM_PATTERNS = [
        (re.compile(r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)'), "YouTube"),
        (re.compile(r'(?:https?://)?(?:www\.)?vimeo\.com'), "Vimeo"),
        (re.compile(r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)'), "X / Twitter"),
        (re.compile(r'(?:https?://)?(?:www\.)?(?:facebook\.com|fb\.watch)'), "Facebook"),
        (re.compile(r'(?:https?://)?(?:www\.)?instagram\.com'), "Instagram"),
        (re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com'), "TikTok"),
        (re.compile(r'(?:https?://)?(?:www\.)?dailymotion\.com'), "Dailymotion"),
        (re.compile(r'(?:https?://)?(?:www\.)?twitch\.tv'), "Twitch"),
        (re.compile(r'(?:https?://)?(?:www\.)?bilibili\.com'), "Bilibili"),
        (re.compile(r'(?:https?://)?(?:www\.)?reddit\.com'), "Reddit"),
        (re.compile(r'(?:https?://)?(?:www\.)?soundcloud\.com'), "SoundCloud"),
        (re.compile(r'(?:https?://)?(?:www\.)?rumble\.com'), "Rumble"),
        (re.compile(r'(?:https?://)?(?:www\.)?streamable\.com'), "Streamable"),
        (re.compile(r'(?:https?://)?(?:www\.)?archive\.org'), "Internet Archive"),
    ]

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """Strip whitespace and add https:// if scheme is missing."""
        if not url:
            return ""
        trimmed = url.strip()
        if not trimmed.startswith(("http://", "https://")):
            # If user pasted domain-first URL like youtube.com/...
            if "." in trimmed and not trimmed.startswith("/"):
                trimmed = "https://" + trimmed
        return trimmed

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Validate if the string is a well-formed web URL (http/https)."""
        normalized = cls.normalize_url(url)
        if not normalized:
            return False

        try:
            parsed = urlparse(normalized)
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                return False
            # Netloc must have at least one dot or be localhost
            if "." not in parsed.netloc and parsed.netloc.lower() != "localhost":
                return False
            return True
        except Exception:
            return False

    @classmethod
    def detect_platform(cls, url: str, extractor_key: Optional[str] = None) -> str:
        """Identify common video platforms for display branding."""
        if extractor_key and extractor_key.lower() not in ("generic", ""):
            # Map known yt-dlp extractor keys to clean names
            key_clean = extractor_key.replace("IE", "").strip()
            # If common known, map it
            lower_k = key_clean.lower()
            if "youtube" in lower_k:
                return "YouTube"
            elif "twitter" in lower_k or "x" == lower_k:
                return "X / Twitter"
            elif "vimeo" in lower_k:
                return "Vimeo"
            elif "tiktok" in lower_k:
                return "TikTok"
            elif "instagram" in lower_k:
                return "Instagram"
            return key_clean

        normalized = cls.normalize_url(url)
        for pattern, platform_name in cls.PLATFORM_PATTERNS:
            if pattern.search(normalized):
                return platform_name

        try:
            parsed = urlparse(normalized)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                parts = domain.split(".")
                if len(parts) >= 2:
                    return parts[0].capitalize()
                return domain.capitalize()
        except Exception:
            pass

        return "Web Media"
