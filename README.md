# SonicForge

A professional batch audio tag editor for FLAC files, built with Python and Flet.

## Features

- 📁 Load an entire directory of FLAC files at once
- ✏️ Batch-edit metadata tags (Title, Artist, Album, Track #, Year, Genre)
- 🖼️ Set cover art from a local file or fetch it online from iTunes & Deezer
- ☑️ Smart multi-selection (click, Shift+click, Ctrl+click, select-all)
- 💾 Saves tags directly to the original FLAC files

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
# macOS — double-click or run directly:
./SonicForge.command

# Or from the terminal:
python3 main.py
```

## Testing

```bash
python3 -m pytest tests/ -v
```

## Requirements

- Python 3.11+
- macOS (native dialog support via `osascript`; Linux/Windows fall back to tkinter)
