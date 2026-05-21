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
        self.page.title = "SonicForge - Batch Tag Editor"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 20
        self.app_state = AppState()
        
        self.page.on_keyboard_event = self.on_keyboard
        self.page.on_close = self.on_close
        
        self.status_text = ft.Text("")
        
        self.artwork_dialog = ArtworkDialog(self.page, self.app_state, self.set_status)
        
        self.file_table = FileTable(self.app_state)
        self.tag_editor = TagEditor(
            self.app_state, 
            on_fetch_artwork=self.artwork_dialog.open_for,
            on_select_local_artwork=self.handle_local_artwork,
            on_save_complete=self.on_save_complete
        )
        
        self.load_btn = ft.ElevatedButton("Select Directory", on_click=self.load_directory)
        
        main_row = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Row([self.load_btn]),
                    self.file_table
                ]),
                expand=2
            ),
            ft.Container(
                content=self.tag_editor,
                expand=1,
                padding=20
            )
        ], expand=True)
        
        self.page.add(
            ft.Text("SonicForge", size=32, weight=ft.FontWeight.BOLD, color="primary"),
            self.status_text,
            main_row
        )
        
        self.clean_cache()
        logger.info("SonicForgeApp initialized successfully.")

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
        """Updates the status bar text."""
        self.status_text.value = text
        self.page.update()
        
    def load_directory(self, e: ft.ControlEvent):
        """Loads all FLAC files from a user-selected directory (threaded to avoid UI freeze)."""
        path = open_directory_dialog()
        if not path or not os.path.isdir(path):
            logger.debug("Directory selection cancelled or invalid.")
            return

        logger.info(f"Loading directory: {path}")
        self.set_status(f"Loading files from {path}...")

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
            self.set_status(f"Loaded {len(files_data)} FLAC files.")

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
                self.set_status(f"Error processing image.")
                
    def on_save_complete(self, count: int):
        """Callback invoked when metadata is successfully saved. Re-reads files to sync state."""
        self.set_status(f"Saved tags to {count} FLAC file(s)!")
        
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
