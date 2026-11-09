# SonicForge

![Screenshot of SonicForge UI 1](assets/image_tag_editor.png)


A fast, zero-dependency batch audio tag editor, CUE splitter, and audio transcoder for macOS, built with Python and Flet.

## Features

- 🎵 **Multi-Format Audio & Tag Support**: Read and write metadata and cover art across **FLAC**, **MP3** (ID3v2.3), **M4A / MP4 / AAC** (`covr`/`trkn`/`©nam`), **OGG Vorbis**, **Opus**, **WAV**, **AIFF**, **WavPack**, **APE**, and **WMA**.
- 📁 **Instant Parallel Loading**: Loads large music directories virtually instantaneously using concurrent thread pooling.
- 🔍 **Sortable & Filterable Track Table**: Sort by File Name, Format, Artist, Title, Album, Track #, or Year, filter tracks in real time, and reveal folders directly in Finder.
- ✏️ **Smart Multi-Selection & Batch Editing**: Native range (`Shift+Click`) and toggle (`⌘+Click`) selection, `< Multiple values — leave blank to keep >` hints, live selection & unsaved-change badges, cover art resolution info, and keyboard shortcuts (`⌘O`, `⌘S`, `⌘R`, `⌘A`, `⌘1–3`).
- 🌐 **MusicBrainz Auto-Tagging**: Connects to the MusicBrainz database to fetch standardized album metadata with side-by-side track mapping previews and count mismatch warnings.
- 🖼️ **Unified Artwork Search**: Search and fetch high-resolution front covers online from iTunes and Deezer concurrently, or select from local files with in-memory previewing.
- 🔢 **Auto-Number Tracks**: Sequentially indexes selected tracks (`01`, `02`, `03`...) in a background thread.
- 🏷️ **Batch File Renaming**: Dynamically rename files based on custom tag patterns (e.g. `{track:02d} - {title}`) with character sanitisation and a live Before → After preview dialog.
- ✂️ **Multi-Format CUE Splitter**: Slices continuous album audio files into individual tracks in parallel using a CUE sheet and bundled FFmpeg, outputting to **FLAC**, **MP3 (320 kbps)**, **M4A / AAC (256 kbps)**, **OGG Vorbis (q6)**, or **WAV** with automatic tag and cover art injection.
- 🔄 **Parallel Batch Audio Transcoder**: Batch transcode audio files concurrently across CPU cores to **MP3**, **M4A (AAC)**, **OGG Vorbis**, **FLAC**, and **WAV**, preserving all tags and embedded cover art.
- 📊 **Space-Saving Metrics**: Real-time size comparison and aggregate space-saving summary upon completion.
- 📦 **Zero External Dependencies (`.app`)**: Self-contained macOS `.app` bundle with `ffmpeg` and all dynamic libraries bundled inside `Contents/Frameworks/`.

## Project Structure

```
SonicForge/
├── core/               # Business logic (metadata I/O, API client, image processing, state)
├── ui/                 # Flet UI components (main app, file table, tag editor, artwork dialog)
├── utils/              # Shared utilities (logger)
├── tests/              # Pytest unit tests
├── assets/             # Static UI assets (icons, etc.)
├── main.py             # Application entry point
├── requirements.txt
└── pytest.ini
```

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# Run from the terminal:
python3 main.py 
``` 
Or double-click on `SonicForge.command`


## Packaging (Building `.app` for macOS)

To compile SonicForge into a standalone macOS `.app` that can be placed in your `/Applications` folder:

1. Install PyInstaller inside your virtual environment:
   ```bash
   pip install pyinstaller
   ```
2. Build the app bundle with the custom flat icon:
   ```bash
   flet pack main.py --icon assets/icon.icns --name "SonicForge"
   ```
This will generate `dist/SonicForge.app` which you can double-click or drag into your `/Applications` folder!

## Testing

```bash
python3 -m pytest tests/ -v
```

## Requirements

- Python 3.11+
- macOS (native dialog support via `osascript`; Linux/Windows fall back to tkinter)
- Dependencies listed in `requirements.txt`

