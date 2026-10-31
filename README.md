# Downly – Universal Video Downloader

Downly is a modern Windows desktop application for downloading videos from supported websites, selecting resolutions and audio formats, and converting codecs locally on your PC.

100% Local processing • No cloud backend • No online database • Free & open.

---

## Features

- **Direct URL Extraction**: Automatically detects supported platforms (YouTube, Vimeo, Twitter/X, TikTok, and many more).
- **Quality & Format Selection**: Choose resolutions (360p up to 4K 2160p) and container formats (MP4, MKV, MP3).
- **Local Codec Transcoding**: Convert to H.264 (AVC) or H.265 (HEVC), or keep the original stream without re-encoding.
- **Queue Management**: Monitor concurrent downloads with real-time speed, ETA, pause, resume, and cancellation.
- **Download History**: Keep track of downloaded files, with instant links to open files or their containing folders.
- **Local Privacy**: All settings and history are stored locally in standard JSON files. No telemetry, no remote backend.

---

## Technology Stack

- **Python 3.10+**
- **PySide6** (Qt for Python)
- **yt-dlp** (Media extraction engine)
- **FFmpeg & FFprobe** (Local media processing and conversion)
- **JSON** (Local settings & history persistence)

---

## Installation & Running

### 1. Set Up Virtual Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Launch the Application

```powershell
python main.py
```

---

## Project Structure

```text
Downly/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
│
├── app/
│   ├── __init__.py
│   ├── config.py               # Local JSON settings manager
│   └── constants.py            # Theme palette, defaults & options
│
├── ui/
│   ├── __init__.py
│   ├── styles.py               # Modern Windows QSS styling
│   ├── main_window.py          # MainWindow & page coordinator
│   ├── downloader_page.py      # Downloader view
│   ├── queue_page.py           # Download Queue view
│   ├── history_page.py         # History view
│   ├── settings_page.py        # Settings view
│   └── components/
│       ├── __init__.py
│       ├── card.py             # Reusable styled Card container
│       └── sidebar.py          # Modern navigation sidebar
│
├── core/
│   ├── __init__.py
│   ├── url_analyzer.py         # URL validator & platform detection
│   ├── extractor.py            # yt-dlp metadata extractor
│   ├── download_manager.py     # Queue & concurrency manager
│   ├── format_selector.py      # Stream filtering logic
│   ├── converter.py            # FFmpeg conversion routines
│   └── media_inspector.py      # FFprobe metadata inspector
│
├── storage/
│   ├── settings.json           # Local user preferences
│   └── history.json            # Local download records
│
├── assets/
│   ├── icons/
│   └── images/
│
└── downloads/                  # Default local downloads folder
```
