import flet as ft
import os
import sys
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

from ui import theme as T
from core.state import AppState
from core.cue_parser import parse_cue_sheet
from core.cue_splitter_logic import split_cue_audio
from utils.logger import logger


def choose_file(prompt: str, file_type: str = None) -> str:
    """Opens a native file selection dialog."""
    if sys.platform == 'darwin':
        try:
            type_str = f' of type {{"{file_type}"}}' if file_type else ''
            cmd = ['osascript', '-e', 'tell app "System Events" to activate', 
                   '-e', f'tell app "System Events" to return POSIX path of (choose file with prompt "{prompt}"{type_str})']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"macOS choose_file failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        type_tuples = [(f"{file_type.upper()} Files", f"*.{file_type}")] if file_type else [("All Files", "*.*")]
        path = filedialog.askopenfilename(title=prompt, filetypes=type_tuples)
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback choose_file failed: {e}")
        return ""


def choose_directory(prompt: str) -> str:
    """Opens a native directory selection dialog."""
    if sys.platform == 'darwin':
        try:
            cmd = ['osascript', '-e', 'tell app "System Events" to activate', 
                   '-e', f'tell app "System Events" to return POSIX path of (choose folder with prompt "{prompt}")']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"macOS choose_directory failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title=prompt)
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback choose_directory failed: {e}")
        return ""


class CueSplitterTab(ft.Row):
    """
    UI Tab Component for splitting a continuous FLAC file using a CUE sheet.
    """

    def __init__(self, page: ft.Page, app_state: AppState, set_status: Any):
        super().__init__(expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH, spacing=16)
        self.page_ref = page
        self.app_state = app_state
        self.set_status = set_status

        # Dynamic State Variables
        self.parsed_cue_data: Optional[Dict[str, Any]] = None
        self.track_checkboxes: List[ft.Checkbox] = []

        # ── Left Column Elements (Inputs & Settings) ───────────────────────────
        self.cue_path_field = T.styled_field("CUE Sheet Path", read_only=True, expand=True)
        self.flac_path_field = T.styled_field("Audio FLAC Path", read_only=True, expand=True)
        self.output_dir_field = T.styled_field("Output Directory", read_only=True, expand=True)

        self.naming_pattern_field = ft.Dropdown(
            label="Choose Naming Pattern",
            label_style=ft.TextStyle(color=T.MUTED, size=10),
            color=T.TEXT,
            bgcolor=T.INPUT_BG,
            border_color=T.BORDER,
            focused_border_color=T.SECONDARY,
            value="{track:02d} - {title}",  # Default naming scheme
            options=[
                ft.DropdownOption("{track:02d} - {title}", "01 - Track Title.flac"),
                ft.DropdownOption("{artist} - {title}", "Artist - Track Title.flac"),
                ft.DropdownOption("{track:02d}. {artist} - {title}", "01. Artist - Track Title.flac"),
                ft.DropdownOption("{track:02d} - {artist} - {title}", "01 - Artist - Track Title.flac"),
                ft.DropdownOption("{artist} - {album} - {track:02d} - {title}", "Artist - Album - 01 - Track Title.flac"),
            ],
            border_radius=6,
            height=38,
            expand=True,
        )

        # Metadata Overrides & Format Selection
        self.override_artist_field = T.styled_field("Album Artist", expand=True)
        self.override_album_field = T.styled_field("Album Title", expand=True)
        self.override_year_field = T.styled_field("Year", width=100)
        
        self.format_dropdown = ft.Dropdown(
            label="Output Format",
            label_style=ft.TextStyle(color=T.MUTED, size=10),
            color=T.TEXT,
            bgcolor=T.INPUT_BG,
            border_color=T.BORDER,
            focused_border_color=T.SECONDARY,
            value="flac",
            options=[
                ft.DropdownOption("flac", "FLAC (Lossless)"),
                ft.DropdownOption("ogg", "OGG Vorbis (Compressed)"),
            ],
            border_radius=6,
            height=38,
            expand=True
        )

        # Progress elements
        self.progress_bar = ft.ProgressBar(value=0, visible=False, color=T.PRIMARY, height=4)
        self.console_log = ft.ListView(
            spacing=4,
            expand=True,
        )

        console_card = ft.Container(
            content=self.console_log,
            bgcolor=T.BG,
            border=ft.Border.all(1, T.BORDER),
            border_radius=10,
            padding=10,
            height=130,
        )

        self.split_btn = T.gradient_button(
            text="Split Continuous Audio",
            icon=ft.Icons.CONTENT_CUT,
            on_click=self.handle_split_click,
        )

        # File Select Action Handlers
        select_cue_row = ft.Row(
            [
                self.cue_path_field,
                ft.IconButton(ft.Icons.FOLDER_OPEN_OUTLINED, on_click=self.browse_cue, tooltip="Browse CUE Sheet")
            ],
            spacing=6,
        )

        select_flac_row = ft.Row(
            [
                self.flac_path_field,
                ft.IconButton(ft.Icons.AUDIO_FILE_OUTLINED, on_click=self.browse_flac, tooltip="Browse Audio FLAC")
            ],
            spacing=6,
        )

        select_output_row = ft.Row(
            [
                self.output_dir_field,
                ft.IconButton(ft.Icons.CREATE_NEW_FOLDER_OUTLINED, on_click=self.browse_output, tooltip="Browse Output Directory")
            ],
            spacing=6,
        )

        left_column = ft.Column(
            [
                T.card(
                    content=ft.Column(
                        [
                            ft.Text("File Inputs", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            select_cue_row,
                            select_flac_row,
                            select_output_row,
                        ],
                        spacing=10,
                    ),
                    padding=16,
                ),
                T.card(
                    content=ft.Column(
                        [
                            ft.Text("Settings & Naming Pattern", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            ft.Row(
                                [
                                    self.naming_pattern_field,
                                    self.format_dropdown,
                                ],
                                spacing=10,
                            ),
                            ft.Row(
                                [
                                    self.override_artist_field,
                                    self.override_album_field,
                                    self.override_year_field,
                                ],
                                spacing=10,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=16,
                ),
                T.card(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("Execution Log", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                    ft.Container(expand=True),
                                    self.progress_bar,
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            console_card,
                            self.split_btn,
                        ],
                        spacing=10,
                        expand=True,
                    ),
                    padding=16,
                    expand=True,
                )
            ],
            expand=1,
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # ── Right Column Elements (Parsed Tracklist Preview) ─────────────────────
        self.album_title_text = ft.Text("No CUE sheet loaded", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT)
        self.album_artist_text = ft.Text("Choose a CUE file on the left to start.", size=11, color=T.MUTED)
        
        self.tracks_column = ft.ListView(
            spacing=8,
            expand=True
        )

        self.select_all_checkbox = ft.Checkbox(
            label="Select All Tracks",
            label_style=ft.TextStyle(size=11, color=T.MUTED),
            value=True,
            on_change=self.handle_select_all_change,
            fill_color=T.PRIMARY,
        )

        right_column = ft.Column(
            [
                T.card(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.ALBUM, color=T.PRIMARY, size=28),
                                    ft.Column(
                                        [
                                            self.album_title_text,
                                            self.album_artist_text,
                                        ],
                                        spacing=2,
                                    ),
                                ],
                                spacing=12,
                            ),
                            ft.Divider(height=1, color=T.BORDER),
                            ft.Row([self.select_all_checkbox], alignment=ft.MainAxisAlignment.START),
                            ft.Container(
                                content=self.tracks_column,
                                bgcolor=T.BG,
                                border=ft.Border.all(1, T.BORDER),
                                border_radius=10,
                                padding=10,
                                expand=True,
                            )
                        ],
                        spacing=10,
                        expand=True,
                    ),
                    padding=20,
                    expand=True,
                )
            ],
            expand=1,
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.controls = [
            ft.Container(content=left_column, expand=1, padding=ft.Padding.only(left=16, top=16, bottom=16, right=8)),
            ft.Container(content=right_column, expand=1, padding=ft.Padding.only(left=8, top=16, bottom=16, right=16)),
        ]

    # ── Browse Actions ─────────────────────────────────────────────────────────

    def browse_cue(self, e):
        """Browse handler for CUE Sheet."""
        path = choose_file("Select CUE Sheet File", "cue")
        if not path:
            return
            
        self.cue_path_field.value = path
        self.console_log.controls.append(ft.Text(f"Loaded CUE: {os.path.basename(path)}", color=T.PRIMARY, size=11))
        self.page_ref.update()
        
        # Load and parse CUE Sheet
        try:
            data = parse_cue_sheet(path)
            self.parsed_cue_data = data
            
            # Auto-update Album details
            meta = data['metadata']
            self.album_title_text.value = meta['title'] or "Unknown Album"
            self.album_artist_text.value = f"{meta['artist'] or 'Unknown Artist'} • {meta['date'] or 'Unknown Year'}"
            
            # Prefill settings overrides
            self.override_artist_field.value = meta['artist'] or ""
            self.override_album_field.value = meta['title'] or ""
            self.override_year_field.value = meta['date'] or ""
            
            # Auto-detection of associated FLAC file
            cue_dir = os.path.dirname(path)
            default_flac_filename = meta['file'] or os.path.basename(path).replace(".cue", ".flac")
            detected_flac_path = os.path.join(cue_dir, default_flac_filename)
            
            if os.path.exists(detected_flac_path):
                self.flac_path_field.value = detected_flac_path
                self.console_log.controls.append(ft.Text("✓ Automatically matched continuous FLAC audio file.", color=T.SUCCESS, size=11))
            else:
                # Try simple directory glob search for any FLAC as fallback
                flacs = list(Path(cue_dir).glob("*.flac"))
                if len(flacs) == 1:
                    self.flac_path_field.value = str(flacs[0])
                    self.console_log.controls.append(ft.Text(f"✓ Automatically detected FLAC: {flacs[0].name}", color=T.SUCCESS, size=11))
            
            # Auto-set output directory
            self.output_dir_field.value = os.path.join(cue_dir, "Split Tracks")
            
            # Build Track preview rows
            self.build_tracklist_preview()
            self.set_status("")
        except Exception as ex:
            logger.error(f"Error parsing CUE sheet: {ex}", exc_info=True)
            self.console_log.controls.append(ft.Text(f"⚠️ Error parsing CUE: {ex}", color=ft.Colors.RED_400, size=11))
            self.set_status("Error loading CUE Sheet.")
            
        self.page_ref.update()

    def browse_flac(self, e):
        """Browse handler for FLAC audio."""
        path = choose_file("Select continuous FLAC File", "flac")
        if path:
            self.flac_path_field.value = path
            self.page_ref.update()

    def browse_output(self, e):
        """Browse handler for Output Directory."""
        path = choose_directory("Select Output Folder for Slices")
        if path:
            self.output_dir_field.value = path
            self.page_ref.update()

    # ── Tracklist Rendering ──────────────────────────────────────────────────

    def build_tracklist_preview(self):
        """Populates the right column scrollable container with the parsed tracks."""
        self.tracks_column.controls.clear()
        self.track_checkboxes.clear()
        
        if not self.parsed_cue_data or not self.parsed_cue_data['tracks']:
            return
            
        for t in self.parsed_cue_data['tracks']:
            # Duration Calculation
            duration_str = ""
            if t['end_time'] is not None:
                diff = t['end_time'] - t['start_time']
                mins = int(diff // 60)
                secs = int(diff % 60)
                duration_str = f"{mins:02d}:{secs:02d}"
                
            cb = ft.Checkbox(
                value=True,
                fill_color=T.PRIMARY,
            )
            self.track_checkboxes.append(cb)
            
            # Start time label
            start_mins = int(t['start_time'] // 60)
            start_secs = int(t['start_time'] % 60)
            start_str = f"{start_mins:02d}:{start_secs:02d}"

            track_card = ft.Container(
                content=ft.Row(
                    [
                        cb,
                        ft.Text(t['number'], color=T.MUTED, size=11, weight=ft.FontWeight.BOLD),
                        ft.Column(
                            [
                                ft.Text(t['title'] or "Unknown Track", color=T.TEXT, size=12, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(t['artist'] or "Unknown Artist", color=T.MUTED, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Column(
                            [
                                ft.Text(duration_str, color=T.TEXT, size=11) if duration_str else ft.Container(),
                                ft.Text(f"at {start_str}", color=T.MUTED, size=9),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=2,
                        )
                    ],
                    spacing=12,
                ),
                bgcolor=T.SURFACE,
                border=ft.Border.all(0.8, T.BORDER),
                border_radius=8,
                padding=8,
            )
            self.tracks_column.controls.append(track_card)
        self.select_all_checkbox.value = True

    def handle_select_all_change(self, e):
        """Toggles all track checkboxes matching header Select All check state."""
        val = self.select_all_checkbox.value
        for cb in self.track_checkboxes:
            cb.value = val
        self.page_ref.update()

    # ── Audio Slicing Implementation ──────────────────────────────────────────

    def handle_split_click(self, e):
        """Triggers audio splitting in a secure background thread."""
        if not self.cue_path_field.value or not os.path.exists(self.cue_path_field.value):
            self.set_status("Please load a valid CUE Sheet first.")
            return
        if not self.flac_path_field.value or not os.path.exists(self.flac_path_field.value):
            self.set_status("Please select a valid continuous FLAC audio file.")
            return
        if not self.output_dir_field.value:
            self.set_status("Please specify an output directory.")
            return
            
        # Collect checked tracks
        selected_tracks = []
        for i, cb in enumerate(self.track_checkboxes):
            if cb.value:
                selected_tracks.append(self.parsed_cue_data['tracks'][i])
                
        if not selected_tracks:
            self.set_status("No tracks selected. Please check at least one track.")
            return
            
        # Collect overrides & output format
        edited_artist = self.override_artist_field.value.strip()
        edited_album = self.override_album_field.value.strip()
        edited_year = self.override_year_field.value.strip()
        output_format = self.format_dropdown.value or "flac"

        edited_meta = {
            'artist': edited_artist or self.parsed_cue_data['metadata']['artist'],
            'title': edited_album or self.parsed_cue_data['metadata']['title'],
            'date': edited_year or self.parsed_cue_data['metadata']['date'],
        }

        # UI locks
        self.split_btn.disabled = True
        self.split_btn.content.controls[1].value = "Splitting tracks…"
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.console_log.controls.clear()
        self.page_ref.update()
        
        def run():
            def progress(count: int, msg: str):
                self.console_log.controls.append(
                    ft.Text(msg, color=T.TEXT if "⚠️" not in msg and "✓" not in msg else (T.SUCCESS if "✓" in msg else ft.Colors.RED_400), size=11)
                )
                self.progress_bar.value = count / len(selected_tracks)
                self.page_ref.update()
                
            try:
                split_cue_audio(
                    input_flac=self.flac_path_field.value,
                    output_dir=self.output_dir_field.value,
                    tracks=selected_tracks,
                    album_meta=edited_meta,
                    naming_pattern=self.naming_pattern_field.value or "{track:02d} - {title}",
                    output_format=output_format,
                    progress_callback=progress
                )
                self.console_log.controls.append(
                    ft.Text("✓ Slicing process finished.", color=T.SUCCESS, size=11, weight=ft.FontWeight.BOLD)
                )
                self.set_status("✓ CUE Split successfully completed!")
            except Exception as ex:
                logger.error(f"Error splitting CUE: {ex}", exc_info=True)
                self.console_log.controls.append(ft.Text(f"❌ Critical Error: {ex}", color=ft.Colors.RED_400, size=12, weight=ft.FontWeight.BOLD))
                self.set_status("Critical error occurred during split.")
            finally:
                self.split_btn.disabled = False
                self.split_btn.content.controls[1].value = "Split Continuous Audio"
                self.progress_bar.visible = False
                self.page_ref.update()
                
        threading.Thread(target=run, daemon=True).start()
