import flet as ft
import os
import sys
import threading
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from ui import theme as T
from core.state import AppState
from core.transcoder import transcode_file
from utils.logger import logger

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


class ConvertTab(ft.Row):
    """
    UI Tab Component for transcoding audio files to different formats.
    """

    def __init__(self, page: ft.Page, app_state: AppState, set_status: Any, on_load_directory: Any = None):
        super().__init__(expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH, spacing=16)
        self.page_ref = page
        self.app_state = app_state
        self.set_status = set_status
        self.on_load_directory = on_load_directory

        # Internal state
        self.source_files: List[Dict[str, Any]] = []
        self.file_checkboxes: List[ft.Checkbox] = []
        self.ignore_state_change = False

        # Register state listener
        self.app_state.add_listener(self.on_state_change)

        # ── Left Column Elements ───────────────────────────────────────────────
        self.format_dropdown = ft.Dropdown(
            label="Target Format",
            label_style=ft.TextStyle(color=T.MUTED, size=10),
            color=T.TEXT,
            bgcolor=T.INPUT_BG,
            border_color=T.BORDER,
            focused_border_color=T.SECONDARY,
            value="mp3",
            options=[
                ft.DropdownOption("mp3", "MP3 (Compressed)"),
                ft.DropdownOption("ogg", "OGG Vorbis (Compressed)"),
                ft.DropdownOption("wav", "WAV (Uncompressed)"),
            ],
            on_select=self.handle_format_change,
            border_radius=6,
            height=38,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            expand=True
        )

        self.quality_dropdown = ft.Dropdown(
            label="Quality Preset",
            label_style=ft.TextStyle(color=T.MUTED, size=10),
            color=T.TEXT,
            bgcolor=T.INPUT_BG,
            border_color=T.BORDER,
            focused_border_color=T.SECONDARY,
            value="320k",
            options=[
                ft.DropdownOption("320k", "320 kbps (High Quality)"),
                ft.DropdownOption("256k", "256 kbps"),
                ft.DropdownOption("192k", "192 kbps (Medium Quality)"),
                ft.DropdownOption("128k", "128 kbps (Low Quality)"),
            ],
            border_radius=6,
            height=38,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            expand=True
        )

        self.output_dir_field = T.styled_field(
            "Output Directory", 
            read_only=True, 
            expand=True,
            value="",
            hint_text="Defaults to ./Converted/ folder"
        )

        # Log & Progress
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
            height=160,
        )

        self.convert_btn = T.gradient_button(
            text="Start Batch Transcode",
            icon=ft.Icons.SWAP_HORIZ,
            on_click=self.handle_convert_click,
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
                            ft.Text("Transcode Presets", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            ft.Row(
                                [
                                    self.format_dropdown,
                                    self.quality_dropdown,
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
                            ft.Text("Output Directory", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            select_output_row,
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
                            self.convert_btn,
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

        # ── Right Column Elements ──────────────────────────────────────────────
        self.right_header_text = ft.Text("No files loaded", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT)
        self.right_subtitle_text = ft.Text("Load directory in main tab or select specific tracks to transcode.", size=11, color=T.MUTED)

        self.select_all_checkbox = ft.Checkbox(
            label="Select All Files",
            label_style=ft.TextStyle(size=11, color=T.MUTED),
            value=True,
            on_change=self.handle_select_all_change,
            fill_color=T.PRIMARY,
        )

        self.files_list = ft.ListView(
            spacing=8,
            expand=True
        )

        right_column = ft.Column(
            [
                T.card(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.LIBRARY_MUSIC, color=T.PRIMARY, size=28),
                                    ft.Column(
                                        [
                                            self.right_header_text,
                                            self.right_subtitle_text,
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                        on_click=self.on_load_directory,
                                        tooltip="Open Folder...",
                                        icon_color=T.PRIMARY,
                                        visible=self.on_load_directory is not None,
                                    )
                                ],
                                spacing=12,
                            ),
                            ft.Divider(height=1, color=T.BORDER),
                            ft.Row([self.select_all_checkbox], alignment=ft.MainAxisAlignment.START),
                            ft.Container(
                                content=self.files_list,
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

        # Init list
        self.load_from_state()

    # ── Change Handlers ───────────────────────────────────────────────────────

    def handle_format_change(self, e):
        """Updates quality options depending on the chosen target format."""
        fmt = self.format_dropdown.value
        if fmt == "mp3":
            self.quality_dropdown.options = [
                ft.DropdownOption("320k", "320 kbps (High Quality)"),
                ft.DropdownOption("256k", "256 kbps"),
                ft.DropdownOption("192k", "192 kbps (Medium Quality)"),
                ft.DropdownOption("128k", "128 kbps (Low Quality)"),
            ]
            self.quality_dropdown.value = "320k"
            self.quality_dropdown.disabled = False
        elif fmt == "ogg":
            self.quality_dropdown.options = [
                ft.DropdownOption("q8", "q8 (High Quality - ~256kbps)"),
                ft.DropdownOption("q6", "q6 (Medium Quality - ~192kbps)"),
                ft.DropdownOption("q4", "q4 (Low Quality - ~128kbps)"),
            ]
            self.quality_dropdown.value = "q6"
            self.quality_dropdown.disabled = False
        elif fmt == "wav":
            self.quality_dropdown.options = [
                ft.DropdownOption("lossless", "Lossless / Original Quality")
            ]
            self.quality_dropdown.value = "lossless"
            self.quality_dropdown.disabled = True
            
        self.page_ref.update()

    def browse_output(self, e):
        """Browse handler for Output Directory."""
        path = choose_directory("Select Target Folder for Transcoded Files")
        if path:
            self.output_dir_field.value = path
            self.page_ref.update()

    def handle_select_all_change(self, e):
        """Toggles all checkboxes in the list."""
        val = self.select_all_checkbox.value
        for cb in self.file_checkboxes:
            cb.value = val
        self.page_ref.update()

    def handle_checkbox_change(self, e):
        """Updates the Select All checkbox based on individual selections."""
        self.select_all_checkbox.value = all(cb.value for cb in self.file_checkboxes) if self.file_checkboxes else False
        self.page_ref.update()

    # ── Dynamic Import from State ─────────────────────────────────────────────

    def on_state_change(self):
        """Listener invoked when the main AppState changes."""
        if self.ignore_state_change:
            return
        self.load_from_state()
        self.page_ref.update()

    def load_from_state(self):
        """Loads and pre-selects files from AppState."""
        self.source_files = list(self.app_state.current_files)
        self.file_checkboxes.clear()
        self.files_list.controls.clear()

        if not self.source_files:
            self.right_header_text.value = "No files loaded"
            self.right_subtitle_text.value = "Load a directory directly here or in the Tags tab first."
            self.output_dir_field.value = ""
            
            # Show a beautiful onboarding container with an "Open Folder..." button
            self.files_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=48, color=T.MUTED),
                            ft.Text("No Audio Files Loaded", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            ft.Text("Import a folder of FLAC files to start transcoding.", size=11, color=T.MUTED, text_align=ft.TextAlign.CENTER),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=ft.Colors.WHITE, size=15),
                                        ft.Text("Open Folder...", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=12),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                bgcolor=T.SECONDARY,
                                border_radius=8,
                                on_click=self.on_load_directory,
                                ink=True,
                                height=36,
                                width=150,
                                margin=ft.Margin.only(top=8),
                                visible=self.on_load_directory is not None,
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=40),
                    alignment=ft.Alignment.CENTER,
                )
            )
            return

        # Album title summary
        first_file = self.source_files[0]
        parent_dir = os.path.dirname(first_file['path'])
        
        # Set default output directory to a Converted subdirectory in parent
        if not self.output_dir_field.value:
            self.output_dir_field.value = os.path.join(parent_dir, "Converted")

        self.right_header_text.value = f"Source Workspace ({len(self.source_files)} files)"
        self.right_subtitle_text.value = f"Loaded from: {os.path.basename(parent_dir)}"

        # Build list cards
        selected_indices = self.app_state.selected_file_indices

        for idx, f_data in enumerate(self.source_files):
            file_path = f_data['path']
            filename = os.path.basename(file_path)
            orig_ext = Path(file_path).suffix.upper().replace('.', '')

            # If specific files are selected in the main tab, precheck only those
            is_checked = True
            if selected_indices:
                is_checked = (idx in selected_indices)

            cb = ft.Checkbox(
                value=is_checked,
                fill_color=T.PRIMARY,
                on_change=self.handle_checkbox_change,
            )
            self.file_checkboxes.append(cb)

            track_card = ft.Container(
                content=ft.Row(
                    [
                        cb,
                        ft.Icon(ft.Icons.MUSIC_NOTE, color=T.MUTED, size=16),
                        ft.Column(
                            [
                                ft.Text(filename, color=T.TEXT, size=12, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(os.path.dirname(file_path), color=T.MUTED, size=9, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(orig_ext, color=T.PRIMARY, size=9, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.1, T.PRIMARY),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        )
                    ],
                    spacing=12,
                ),
                bgcolor=T.SURFACE,
                border=ft.Border.all(0.8, T.BORDER),
                border_radius=8,
                padding=8,
            )
            self.files_list.controls.append(track_card)

        # Update Select All checkbox state
        self.select_all_checkbox.value = all(cb.value for cb in self.file_checkboxes) if self.file_checkboxes else False

    # ── Background Thread Transcode Execution ─────────────────────────────────

    def handle_convert_click(self, e):
        """Checks inputs and kicks off batch transcoding inside background thread."""
        if not self.source_files:
            self.set_status("No files available for conversion. Load a folder first.")
            return

        selected_files = []
        for idx, cb in enumerate(self.file_checkboxes):
            if cb.value:
                selected_files.append(self.source_files[idx])

        if not selected_files:
            self.set_status("Please check at least one file to convert.")
            return

        output_dir = self.output_dir_field.value.strip()
        if not output_dir:
            self.set_status("Please select a valid output directory.")
            return

        target_format = self.format_dropdown.value
        quality = self.quality_dropdown.value

        # Lock UI controls
        self.convert_btn.disabled = True
        self.convert_btn.content.controls[1].value = "Converting..."
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.console_log.controls.clear()
        self.page_ref.update()

        def run():
            success_count = 0
            error_count = 0
            total_source_size = 0
            total_output_size = 0
            
            self.console_log.controls.append(
                ft.Text(f"Starting batch transcode for {len(selected_files)} file(s) to {target_format.upper()}...", color=T.PRIMARY, size=11, weight=ft.FontWeight.BOLD)
            )
            self.page_ref.update()

            for i, f_data in enumerate(selected_files):
                file_path = f_data['path']
                filename = os.path.basename(file_path)
                
                def log_callback(msg: str):
                    color = T.TEXT
                    if "✓" in msg:
                        color = T.SUCCESS
                    elif "⚠️" in msg or "❌" in msg:
                        color = ft.Colors.RED_400
                        
                    self.console_log.controls.append(
                        ft.Text(msg, color=color, size=11)
                    )
                    self.page_ref.update()

                try:
                    # Get metadata tags & cover art
                    metadata = f_data.get('metadata', {})
                    cover_art = metadata.get('cover_art', self.app_state.selected_cover_art_bytes)
                    
                    out_path = transcode_file(
                        input_path=file_path,
                        output_dir=output_dir,
                        target_format=target_format,
                        quality=quality,
                        metadata=metadata,
                        cover_art=cover_art,
                        progress_callback=log_callback
                    )
                    success_count += 1
                    try:
                        total_source_size += os.path.getsize(file_path)
                        total_output_size += os.path.getsize(out_path)
                    except Exception:
                        pass
                except Exception as ex:
                    logger.error(f"Error transcoding {filename}: {ex}", exc_info=True)
                    log_callback(f"❌ Error converting {filename}: {ex}")
                    error_count += 1
                    
                # Update progress bar
                self.progress_bar.value = (i + 1) / len(selected_files)
                self.page_ref.update()

            # End State
            self.console_log.controls.append(
                ft.Text(f"✓ Transcoding finished. Successful: {success_count}, Failed: {error_count}", color=T.SUCCESS if error_count == 0 else ft.Colors.ORANGE_400, size=11, weight=ft.FontWeight.BOLD)
            )
            
            if success_count > 0 and total_source_size > 0:
                def format_size(b):
                    for u in ['B', 'KB', 'MB', 'GB']:
                        if b < 1024.0: return f"{b:.1f} {u}"
                        b /= 1024.0
                    return f"{b:.1f} TB"
                
                saved = total_source_size - total_output_size
                ratio = (saved / total_source_size) * 100
                
                if saved > 0:
                    summary_text = f"Total space saved: {format_size(saved)} (from {format_size(total_source_size)} down to {format_size(total_output_size)}, {ratio:.1f}% reduced)"
                elif saved < 0:
                    summary_text = f"Total size change: +{format_size(-saved)} larger (from {format_size(total_source_size)} up to {format_size(total_output_size)})"
                else:
                    summary_text = f"Total size: {format_size(total_output_size)} (no change)"
                    
                self.console_log.controls.append(
                    ft.Text(summary_text, color=T.PRIMARY, size=11, weight=ft.FontWeight.BOLD)
                )
                
            logger.info(f"Batch transcode completed. Success: {success_count}, Errors: {error_count}")
            
            if error_count > 0:
                self.set_status(f"✓ Transcoded {success_count} file(s). {error_count} failed.")
            else:
                self.set_status(f"✓ Transcoded {success_count} file(s) successfully!")

            # Unlock UI
            self.convert_btn.disabled = False
            self.convert_btn.content.controls[1].value = "Start Batch Transcode"
            self.progress_bar.visible = False
            self.page_ref.update()

        threading.Thread(target=run, daemon=True).start()
