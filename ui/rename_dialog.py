import flet as ft
import os
from pathlib import Path
from typing import Callable, Optional

from utils.logger import logger
from core.state import AppState
from core.metadata import generate_filename
from ui import theme as T


class RenameDialog:
    """
    UI Component for renaming selected FLAC files interactively.
    Allows selecting a naming pattern and displays a live Before -> After preview.
    """

    def __init__(self, page: ft.Page, app_state: AppState, set_status: Callable[[str], None]):
        self.page = page
        self.app_state = app_state
        self.set_status = set_status

        # ── Pattern selection dropdown ─────────────────────────────────────────
        self.pattern_dropdown = ft.Dropdown(
            label="Choose Naming Pattern",
            label_style=ft.TextStyle(color=T.MUTED, size=12),
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
            on_select=self.handle_pattern_change,
            border_radius=8,
            expand=True,
        )

        self.preview_list = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            expand=True,
        )

        preview_card = ft.Container(
            content=self.preview_list,
            bgcolor=T.BG,
            border=ft.Border.all(1, T.BORDER),
            border_radius=10,
            padding=12,
            height=200,
            expand=True,
        )

        self._content = ft.Column(
            controls=[
                ft.Row([self.pattern_dropdown], spacing=10),
                ft.Text("Filename Preview:", size=12, color=T.MUTED, weight=ft.FontWeight.BOLD),
                preview_card,
            ],
            spacing=12,
            height=320,
            width=600,
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Batch Rename Files", weight=ft.FontWeight.BOLD, color=T.TEXT),
            content=self._content,
            bgcolor=T.SURFACE,
            actions=[
                ft.OutlinedButton(
                    "Cancel",
                    on_click=self.close,
                    style=ft.ButtonStyle(
                        color=T.MUTED,
                        side=ft.BorderSide(1, T.BORDER),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
                ft.ElevatedButton(
                    "Apply Rename",
                    icon=ft.Icons.CHECK,
                    on_click=self.apply_rename,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                )
            ],
        )

    def close(self, e: Optional[ft.ControlEvent] = None):
        """Closes the dialog."""
        self.dialog.open = False
        self.page.update()

    def open(self):
        """Prepares and opens the dialog with a fresh preview."""
        if not self.app_state.selected_file_indices:
            self.set_status("Please select files first to rename.")
            return

        self.update_preview()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def handle_pattern_change(self, e):
        """Triggers live preview update when pattern selection changes."""
        self.update_preview()

    def update_preview(self):
        """Regenerates the list of Before -> After previews based on the pattern."""
        self.preview_list.controls.clear()
        pattern = self.pattern_dropdown.value or "{track:02d} - {title}"

        for idx in sorted(self.app_state.selected_file_indices):
            file_data = self.app_state.current_files[idx]
            old_name = os.path.basename(file_data['path'])
            new_name = generate_filename(pattern, file_data['metadata'], file_data['path'])

            # Display a nice double-column preview row
            row = ft.Row(
                [
                    ft.Icon(ft.Icons.MUSIC_NOTE, color=T.MUTED, size=16),
                    ft.Text(
                        old_name,
                        color=T.MUTED,
                        size=12,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color=T.PRIMARY, size=14),
                    ft.Text(
                        new_name,
                        color=T.TEXT if old_name != new_name else T.MUTED,
                        size=13,
                        weight=ft.FontWeight.W_500 if old_name != new_name else ft.FontWeight.NORMAL,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self.preview_list.controls.append(row)
        
        self.page.update()

    def apply_rename(self, e):
        """Applies the physical file renames on disk and updates the AppState."""
        self.close()
        pattern = self.pattern_dropdown.value or "{track:02d} - {title}"
        selected_indices = sorted(list(self.app_state.selected_file_indices))
        
        logger.info(f"Renaming {len(selected_indices)} selected files on disk.")
        self.set_status(f"Renaming {len(selected_indices)} file(s)…")

        renamed_count = 0
        error_count = 0

        # Create a new list to build updated file data records
        updated_files = list(self.app_state.current_files)
        new_selection_indices = set()

        for idx in selected_indices:
            file_data = updated_files[idx]
            old_path = file_data['path']
            directory = os.path.dirname(old_path)
            
            new_name = generate_filename(pattern, file_data['metadata'], old_path)
            new_path = os.path.join(directory, new_name)

            if old_path == new_path:
                logger.debug(f"File already matches target name: {new_name}")
                new_selection_indices.add(idx)
                continue

            try:
                # Safely rename file on disk
                if os.path.exists(new_path):
                    logger.warning(f"Rename target already exists: {new_path}. Skipping.")
                    error_count += 1
                    new_selection_indices.add(idx)
                    continue

                os.rename(old_path, new_path)
                logger.info(f"Renamed file: {old_path} -> {new_path}")
                
                # Update AppState file path record
                updated_files[idx]['path'] = new_path
                new_selection_indices.add(idx)
                renamed_count += 1
            except Exception as ex:
                logger.error(f"Error renaming {old_path} to {new_path}: {ex}", exc_info=True)
                error_count += 1
                new_selection_indices.add(idx)

        # Notify state update
        self.app_state.current_files = updated_files
        self.app_state.selected_file_indices = new_selection_indices
        self.app_state.notify()

        if error_count > 0:
            self.set_status(f"✓ Renamed {renamed_count} file(s). {error_count} failed.")
        else:
            self.set_status(f"✓ Renamed {renamed_count} file(s) successfully!")
