# Changelog

## [v1.5.0] - 2026-11-09

### Added
- **Multi-Format Audio & Tagging Support**:
  - Added universal metadata and cover art reading/writing ([`get_metadata`](core/metadata.py), [`save_metadata`](core/metadata.py)) for **MP3** (ID3v2.3 + `APIC`), **M4A / MP4 / AAC** (`©nam`, `©ART`, `©alb`, `©day`, `trkn`, `©gen`, `covr`), **FLAC**, **OGG Vorbis**, **Opus**, **WAV** (RIFF ID3), **AIFF**, **WavPack**, **APE**, and **WMA**.
  - Added **M4A (AAC)** and **FLAC** target formats to the batch audio transcoder ([`core/transcoder.py`](core/transcoder.py), [`ui/convert_tab.py`](ui/convert_tab.py)).
  - Expanded the **CUE Splitter** ([`core/cue_splitter_logic.py`](core/cue_splitter_logic.py), [`ui/cue_splitter_tab.py`](ui/cue_splitter_tab.py)) to accept any continuous audio format and output directly to **FLAC**, **MP3 (320 kbps)**, **M4A / AAC (256 kbps)**, **OGG Vorbis (q6)**, or **WAV**.
- **UI & UX Enhancements**:
  - **Unified Top Header Bar** ([`ui/app.py`](ui/app.py)): Combined application branding, segmented tab navigation (`Tags`, `CUE Splitter`, `Convert`), and status indicator into a single sleek top bar, with an `1280×820` centered startup window.
  - **Sortable & Filterable File Table** ([`ui/file_table.py`](ui/file_table.py)): Added **Fmt** format badges, **Year** column, clickable column sorting (`File Name`, `Fmt`, `Artist`, `Title`, `Album`, `#`, `Year`), real-time track search/filtering, and a folder breadcrumb with a **Reveal in Finder** button.
  - **Enhanced Tag Editor** ([`ui/tag_editor.py`](ui/tag_editor.py)): Added `< Multiple values — leave blank to keep >` placeholders for mixed multi-select values, live selection count & unsaved-changes badges, smart button disabling when no tracks are selected, cover art resolution/format inspection, and a **Revert staged art** button.
  - **Keyboard Shortcuts**: Added `⌘O` (Open Folder), `⌘S` (Save Tags), `⌘R` (Rename Files), `⌘A` (Select/Deselect All), and `⌘1`/`⌘2`/`⌘3` (Switch Tabs).
  - **One-Click "Open in Finder" & Auto-Scroll Logs**: Added **Open in Finder** buttons and auto-scrolling execution logs in the **Convert** and **CUE Splitter** tabs.
- **Zero-Dependency Native macOS Bundle (`SonicForge.spec`, `utils/paths.py`)**:
  - Bundled `ffmpeg` and all required dynamic libraries inside `SonicForge.app/Contents/Frameworks/` so users need zero external dependencies or Homebrew installations.
  - Embedded a pre-branded `SonicForge.app` Flet client inside `Contents/Resources/flet_client/` and switched from single-file temp extraction to `COLLECT` bundle layout, cutting startup time from ~8s to ~1s and ensuring the macOS Dock and menu bar display **SonicForge** and its custom squircle icon.

### Fixed & Optimized
- **Parallel Processing**: Parallelized CUE track splitting and batch audio transcoding using `ThreadPoolExecutor` across CPU cores, and placed `-ss` before `-i` in FFmpeg for fast input seeking.
- **Non-Blocking UI & In-Memory Artwork Previews**: Moved tag saving and auto-numbering to background threads and rendered cover art directly from in-memory bytes instead of writing temporary `.cache/preview_*.jpg` files on every click.
- **Bug Fixes**:
  - Fixed `Ctrl`/`⌘` multi-select key detection in [`ui/file_table.py`](ui/file_table.py).
  - Fixed CUE parser `INDEX 00` pregap handling and timestamps exceeding 99 minutes in [`core/cue_parser.py`](core/cue_parser.py).
  - URL-encoded special characters (`&`, `#`, `?`, `/`) in Deezer and MusicBrainz API queries ([`core/api_client.py`](core/api_client.py)).
  - Centralized and escaped AppleScript dialogs in [`utils/dialogs.py`](utils/dialogs.py) and moved app logs/cache to `~/Library/Application Support/SonicForge` so packaged `.app` bundles never write to read-only paths.
