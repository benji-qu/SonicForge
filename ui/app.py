import flet as ft
from pathlib import Path
import os
import subprocess
import sys
import threading

from core.state import AppState
from core.image_utils import process_local_image
from core.metadata import get_metadata
from ui.file_table import FileTable
from ui.tag_editor import TagEditor
from ui.artwork_dialog import ArtworkDialog
from ui import theme as T
from utils.logger import logger
from utils.paths import CACHE_DIR


def open_directory_dialog():
    """Opens a native directory selection dialog."""
    logger.debug("Opening directory dialog")
    if sys.platform == 'darwin':
        try:
            cmd = ['osascript', '-e', 'tell app "System Events" to activate', '-e', 'tell app "System Events" to return POSIX path of (choose folder with prompt "Select FLAC Directory")']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"macOS directory dialog failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="Select FLAC Directory")
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback directory dialog failed: {e}")
        return ""


def open_file_dialog():
    """Opens a native file selection dialog for images."""
    logger.debug("Opening file dialog for image selection")
    if sys.platform == 'darwin':
        try:
            cmd = ['osascript', '-e', 'tell app "System Events" to activate', '-e', 'tell app "System Events" to return POSIX path of (choose file with prompt "Select Cover Art (JPG/PNG)")']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"macOS file dialog failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(title="Select Cover Art", filetypes=[("Images", "*.jpg *.jpeg *.png")])
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback file dialog failed: {e}")
        return ""


class SonicForgeApp:
    """Main application layout and controller."""

    def __init__(self, page: ft.Page):
        self.page = page

        # ── Page-level styling ─────────────────────────────────────────────────
        self.page.title = "SonicForge"
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.bgcolor = T.BG
        self.page.padding = 0
        self.page.theme = ft.Theme(color_scheme_seed=T.PRIMARY)
        self.page.dark_theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=T.PRIMARY,
                secondary=T.SECONDARY,
                surface=T.SURFACE,
                on_surface=T.TEXT,
                on_primary=ft.Colors.WHITE,
            ),
        )

        self.page.on_keyboard_event = self.on_keyboard
        self.page.on_close = self.on_close
        self.app_state = AppState()

        # ── Child components ───────────────────────────────────────────────────
        self.artwork_dialog = ArtworkDialog(self.page, self.app_state, self.set_status)
        self.file_table = FileTable(self.app_state)
        self.tag_editor = TagEditor(
            self.app_state,
            on_fetch_artwork=self.artwork_dialog.open_for,
            on_select_local_artwork=self.handle_local_artwork,
            on_save_complete=self.on_save_complete,
        )

        # ── Header bar ─────────────────────────────────────────────────────────
        logo = ft.Text(
            spans=[
                ft.TextSpan("Sonic", style=ft.TextStyle(color=T.PRIMARY, size=26, weight=ft.FontWeight.BOLD)),
                ft.TextSpan("Forge", style=ft.TextStyle(color=T.SECONDARY, size=26, weight=ft.FontWeight.BOLD)),
                ft.TextSpan(" ⚡",   style=ft.TextStyle(color=T.PRIMARY, size=24)),
            ]
        )

        open_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=T.PRIMARY, size=16),
                    ft.Text("Open Folder", color=T.PRIMARY, size=14, weight=ft.FontWeight.W_500),
                ],
                spacing=8,
                tight=True,
            ),
            border=ft.Border.all(1.5, T.PRIMARY),
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            on_click=self.load_directory,
            ink=True,
        )

        header = ft.Container(
            content=ft.Row(
                [logo, ft.Container(expand=True), open_btn],
            ),
            padding=ft.Padding.symmetric(horizontal=24, vertical=14),
            bgcolor=T.SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, T.BORDER)),
        )

        # ── Status bar (hidden when empty) ────────────────────────────────────
        self.status_text = ft.Text("", color=T.SECONDARY, size=13)
        self.status_bar = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.INFO_OUTLINE, color=T.SECONDARY, size=14), self.status_text],
                spacing=8,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, T.SECONDARY),
            padding=ft.Padding.symmetric(horizontal=24, vertical=8),
            visible=False,
        )

        # ── Tab 1: Tags ────────────────────────────────────────────────────────
        tags_content = ft.Container(
            content=ft.Row(
                [
                    ft.Container(content=self.file_table, expand=2, padding=16),
                    ft.Container(content=self.tag_editor,  expand=1, padding=ft.Padding.only(top=16, right=16, bottom=16)),
                ],
                expand=True,
            ),
            expand=True,
        )

        # ── Tab shell ─────────────────────────────────────────────────────────
        tabs = ft.Tabs(
            length=3,
            selected_index=0,
            animation_duration=200,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        indicator_color=T.PRIMARY,
                        label_color=T.TEXT,
                        unselected_label_color=T.MUTED,
                        divider_color=T.BORDER,
                        tabs=[
                            ft.Tab(
                                label="Tags",
                                icon=ft.Icons.LABEL_OUTLINE,
                            ),
                            ft.Tab(
                                label="CUE Splitter",
                                icon=ft.Icons.CONTENT_CUT,
                            ),
                            ft.Tab(
                                label="Convert",
                                icon=ft.Icons.SWAP_HORIZ,
                            ),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            tags_content,
                            self._placeholder_tab(
                                "CUE Splitter",
                                "Split a CUE + FLAC pair into individual tracks",
                                ft.Icons.CONTENT_CUT,
                                "Coming in the Future",
                            ),
                            self._placeholder_tab(
                                "Convert",
                                "Transcode FLAC files to OGG and other formats",
                                ft.Icons.SWAP_HORIZ,
                                "Coming in the Future",
                            ),
                        ],
                    ),
                ],
            ),
        )

        self.page.add(header, self.status_bar, tabs)
        self.clean_cache()
        logger.info("SonicForgeApp initialized successfully.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _placeholder_tab(self, title: str, subtitle: str, icon, badge: str) -> ft.Container:
        """Returns a centred 'coming soon' placeholder for future tabs."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=56, color=T.BORDER),
                    ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=T.MUTED),
                    ft.Text(subtitle, size=13, color=T.BORDER, text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Text(badge, size=11, color=T.PRIMARY),
                        border=ft.Border.all(1, T.PRIMARY),
                        border_radius=20,
                        padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                        margin=ft.Margin.only(top=8),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
        )

    # ── Event handlers ─────────────────────────────────────────────────────────

    def on_keyboard(self, e: ft.KeyboardEvent):
        """Global keyboard event listener for modifiers."""
        self.app_state.shift_pressed = e.shift
        self.app_state.ctrl_pressed = e.ctrl or e.meta

    def _clear_cache(self):
        """Deletes all temporary preview images from the cache directory."""
        logger.debug("Clearing .cache folder")
        for f in CACHE_DIR.glob("preview_*.jpg"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Could not remove cache file {f}: {e}")

    def on_close(self, e):
        """Called when the app window is closed. Purges the cache."""
        logger.info("App closing — purging .cache")
        self._clear_cache()

    def clean_cache(self):
        """Creates the cache directory on startup and clears any leftovers."""
        CACHE_DIR.mkdir(exist_ok=True)
        self._clear_cache()
        logger.debug(".cache folder ready")

    def set_status(self, text: str):
        """Updates the status bar text and toggles its visibility."""
        self.status_text.value = text
        self.status_bar.visible = bool(text)
        self.page.update()

    def load_directory(self, e):
        """Loads all FLAC files from a user-selected directory (threaded to avoid UI freeze)."""
        path = open_directory_dialog()
        if not path or not os.path.isdir(path):
            logger.debug("Directory selection cancelled or invalid.")
            return

        logger.info(f"Loading directory: {path}")
        self.set_status(f"Loading files from {path}…")

        def _load():
            p = Path(path)
            flac_files = sorted(list(p.glob('*.flac')))

            if not flac_files:
                logger.warning("No FLAC files found in directory.")
                self.set_status("No FLAC files found in the selected directory.")
                return

            files_data = [
                {'path': str(f), 'metadata': get_metadata(str(f))}
                for f in flac_files
            ]
            self.app_state.load_files(files_data)
            self.set_status(f"✓  Loaded {len(files_data)} FLAC files.")

        threading.Thread(target=_load, daemon=True).start()

    def handle_local_artwork(self):
        """Handles user selection of local artwork file."""
        path = open_file_dialog()
        if path and os.path.isfile(path):
            try:
                logger.info(f"Loading local artwork: {path}")
                img_bytes = process_local_image(path)
                self.app_state.set_cover_art(img_bytes)
            except Exception as ex:
                logger.error(f"Error processing image: {ex}", exc_info=True)
                self.set_status("Error processing image.")

    def on_save_complete(self, count: int):
        """Callback invoked when metadata is successfully saved. Re-reads files to sync state."""
        self.set_status(f"✓  Saved tags to {count} FLAC file(s)!")

        def _refresh():
            logger.debug("Refreshing metadata for loaded files after save.")
            files_data = [
                {'path': f['path'], 'metadata': get_metadata(f['path'])}
                for f in self.app_state.current_files
            ]
            # Use load_files() to properly reset selection and notify listeners
            self.app_state.load_files(files_data)

        threading.Thread(target=_refresh, daemon=True).start()


def main(page: ft.Page):
    SonicForgeApp(page)
