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
from ui.rename_dialog import RenameDialog
from ui.autotag_dialog import AutoTagDialog
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

        # ── Window constraints ──────────────────────────────────────────────────
        self.page.window.width = 1280
        self.page.window.height = 720
        self.page.window.resizable = True

        self.page.on_keyboard_event = self.on_keyboard
        self.page.on_close = self.on_close
        self.app_state = AppState()

        # ── Child components ───────────────────────────────────────────────────
        self.artwork_dialog = ArtworkDialog(self.page, self.app_state, self.set_status)
        self.rename_dialog = RenameDialog(self.page, self.app_state, self.set_status)
        self.autotag_dialog = AutoTagDialog(
            self.page,
            self.app_state,
            self.set_status,
            on_save_complete=self.on_save_complete
        )
        self.file_table = FileTable(self.app_state)
        self.tag_editor = TagEditor(
            self.app_state,
            on_fetch_artwork=self.artwork_dialog.open_for,
            on_select_local_artwork=self.handle_local_artwork,
            on_rename_files=self.rename_dialog.open,
            on_autotag_album=self.autotag_dialog.open,
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

        # ── Status bar (permanent) ────────────────────────────────────────────
        self.status_icon = ft.Icon(ft.Icons.INFO_OUTLINE, color=T.MUTED, size=14)
        self.status_text = ft.Text("Pick a folder to start", color=T.MUTED, size=13)
        self.status_bar = ft.Container(
            content=ft.Row(
                [self.status_icon, self.status_text],
                spacing=8,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, T.SECONDARY),
            padding=ft.Padding.symmetric(horizontal=24, vertical=8),
            visible=True,
        )

        # ── Tab Contents ───────────────────────────────────────────────────────
        self.tags_content = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=self.file_table, 
                        expand=2, 
                        padding=ft.Padding.only(left=16, top=16, bottom=16, right=8)
                    ),
                    ft.Container(
                        content=self.tag_editor,  
                        expand=1, 
                        padding=ft.Padding.only(left=8, top=16, bottom=16, right=16)
                    ),
                ],
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,  # Make columns the exact same height!
            ),
            expand=True,
            visible=True,
        )

        self.cue_content = ft.Container(
            content=self._placeholder_tab(
                "CUE Splitter",
                "Split a CUE + FLAC pair into individual tracks",
                ft.Icons.CONTENT_CUT,
                "Coming in the Future",
            ),
            expand=True,
            visible=False,
            padding=16,
        )

        self.convert_content = ft.Container(
            content=self._placeholder_tab(
                "Convert",
                "Transcode FLAC files to OGG and other formats",
                ft.Icons.SWAP_HORIZ,
                "Coming in the Future",
            ),
            expand=True,
            visible=False,
            padding=16,
        )

        # ── Custom Segmented Tab Bar ───────────────────────────────────────────
        self.active_tab_index = 0
        self.tab_buttons_row = ft.Row(spacing=10, tight=True)
        self.update_tab_buttons()
        
        tab_bar_container = ft.Container(
            content=self.tab_buttons_row,
            padding=ft.Padding.only(left=24, top=14, bottom=0),
        )

        self.page.add(header, self.status_bar, tab_bar_container, self.tags_content, self.cue_content, self.convert_content)
        self.clean_cache()
        logger.info("SonicForgeApp initialised successfully.")

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

    def switch_tab(self, idx: int):
        """Switches the active tab and refreshes the layout."""
        self.active_tab_index = idx
        self.tags_content.visible = (idx == 0)
        self.cue_content.visible = (idx == 1)
        self.convert_content.visible = (idx == 2)
        
        self.update_tab_buttons()
        self.page.update()

    def update_tab_buttons(self):
        """Rebuilds the custom tab button row reflecting active state."""
        self.tab_buttons_row.controls.clear()
        tabs_spec = [
            ("Tags", ft.Icons.LABEL_OUTLINE, 0),
            ("CUE Splitter", ft.Icons.CONTENT_CUT, 1),
            ("Convert", ft.Icons.SWAP_HORIZ, 2),
        ]
        
        for name, icon, idx in tabs_spec:
            is_active = (self.active_tab_index == idx)
            btn = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, color=T.PRIMARY if is_active else T.MUTED, size=15),
                        ft.Text(name, color=T.TEXT if is_active else T.MUTED, size=12, weight=ft.FontWeight.W_500),
                    ],
                    spacing=6,
                    tight=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.08, T.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1.2, T.PRIMARY if is_active else T.BORDER),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                on_click=lambda e, i=idx: self.switch_tab(i),
                ink=True,
            )
            self.tab_buttons_row.controls.append(btn)

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
        """Updates the status bar text and style."""
        if not text:
            # Revert to default/idle state
            if not self.app_state.current_files:
                text = "Pick a folder to start"
                self.status_icon.name = ft.Icons.INFO_OUTLINE
                self.status_icon.color = T.MUTED
            else:
                text = f"Ready — {len(self.app_state.current_files)} files loaded"
                self.status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
                self.status_icon.color = T.SUCCESS
        else:
            # Set dynamic status based on text content
            if "✓" in text or "successfully" in text or "Saved" in text or "Renamed" in text or "processed" in text or "downloaded" in text:
                self.status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
                self.status_icon.color = T.SUCCESS
            elif "error" in text.lower() or "fail" in text.lower():
                self.status_icon.name = ft.Icons.ERROR_OUTLINE
                self.status_icon.color = ft.Colors.RED_400
            elif "loading" in text.lower() or "downloading" in text.lower() or "renaming" in text.lower() or "searching" in text.lower():
                self.status_icon.name = ft.Icons.HOURGLASS_EMPTY_OUTLINED
                self.status_icon.color = T.PRIMARY
            else:
                self.status_icon.name = ft.Icons.INFO_OUTLINE
                self.status_icon.color = T.SECONDARY

        self.status_text.value = text
        self.status_text.color = self.status_icon.color
        self.page.update()

    def load_directory(self, e):
        """Loads all FLAC files from a user-selected directory (threaded to avoid UI freeze)."""
        path = open_directory_dialog()
        if not path or not os.path.isdir(path):
            logger.debug("Directory selection cancelled or invalid.")
            return

        logger.info(f"Loading directory: {path}")
        self.set_status(f"Loading files from {path}")

        def _load():
            from concurrent.futures import ThreadPoolExecutor
            p = Path(path)
            flac_files = sorted(list(p.glob('*.flac')))

            if not flac_files:
                logger.warning("No FLAC files found in directory.")
                self.set_status("No FLAC files found in the selected directory.")
                return

            logger.debug(f"Parsing metadata for {len(flac_files)} files in parallel.")
            with ThreadPoolExecutor() as executor:
                metadata_results = list(executor.map(get_metadata, [str(f) for f in flac_files]))

            files_data = [
                {'path': str(f), 'metadata': meta}
                for f, meta in zip(flac_files, metadata_results)
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
            from concurrent.futures import ThreadPoolExecutor
            logger.debug("Refreshing metadata for loaded files in parallel after save.")
            paths = [f['path'] for f in self.app_state.current_files]
            
            with ThreadPoolExecutor() as executor:
                metadata_results = list(executor.map(get_metadata, paths))

            files_data = [
                {'path': p, 'metadata': meta}
                for p, meta in zip(paths, metadata_results)
            ]
            # Use load_files() to properly reset selection and notify listeners
            self.app_state.load_files(files_data)

        threading.Thread(target=_refresh, daemon=True).start()


def main(page: ft.Page):
    SonicForgeApp(page)
