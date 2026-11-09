import flet as ft
import os
from pathlib import Path
import sys
import ctypes

from core.state import AppState
from ui import theme as T
from utils.dialogs import reveal_in_finder
from utils.logger import logger


def is_shift_pressed_global() -> bool:
    """Returns True if the Shift key is physically pressed down on macOS or Windows."""
    if sys.platform == 'darwin':
        try:
            cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
            cg.CGEventSourceKeyState.restype = ctypes.c_bool
            cg.CGEventSourceKeyState.argtypes = [ctypes.c_int, ctypes.c_int]
            # 56 = Left Shift, 60 = Right Shift
            return bool(cg.CGEventSourceKeyState(0, 56) or cg.CGEventSourceKeyState(0, 60))
        except Exception:
            pass
    elif sys.platform == 'win32':
        try:
            return (ctypes.windll.user32.GetKeyState(0x10) & 0x8000) != 0
        except Exception:
            pass
    return False


def is_cmd_or_ctrl_pressed_global() -> bool:
    """Returns True if Command (macOS) or Control (Windows/macOS) is physically pressed down."""
    if sys.platform == 'darwin':
        try:
            cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
            cg.CGEventSourceKeyState.restype = ctypes.c_bool
            cg.CGEventSourceKeyState.argtypes = [ctypes.c_int, ctypes.c_int]
            # 55 = Left Cmd, 54 = Right Cmd, 59 = Left Ctrl, 62 = Right Ctrl
            return bool(
                cg.CGEventSourceKeyState(0, 55)
                or cg.CGEventSourceKeyState(0, 54)
                or cg.CGEventSourceKeyState(0, 59)
                or cg.CGEventSourceKeyState(0, 62)
            )
        except Exception:
            pass
    elif sys.platform == 'win32':
        try:
            return (ctypes.windll.user32.GetKeyState(0x11) & 0x8000) != 0
        except Exception:
            pass
    return False


class FileTable(ft.Row):
    """
    UI Component displaying a sortable, filterable, selectable data table of audio files.
    """

    def __init__(self, app_state: AppState, on_load_directory: ft.ControlEvent):
        super().__init__(expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.app_state = app_state
        self.on_load_directory = on_load_directory
        self.app_state.add_listener(self.update_ui)

        self.filter_query: str = ""
        self.sort_col_idx: int = 0
        self.sort_asc: bool = True

        # ── Search / Filter Input ──────────────────────────────────────────────
        self.search_input = ft.TextField(
            hint_text="Filter tracks…",
            hint_style=ft.TextStyle(color=T.MUTED, size=11),
            prefix_icon=ft.Icons.SEARCH,
            color=T.TEXT,
            bgcolor=T.INPUT_BG,
            border_color=T.BORDER,
            focused_border_color=T.SECONDARY,
            cursor_color=T.SECONDARY,
            border_radius=6,
            height=30,
            width=185,
            text_size=11,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            on_change=self.handle_filter_change,
        )

        # ── Folder Breadcrumb & Reveal in Finder ───────────────────────────────
        self.folder_label = ft.Text(
            "",
            size=11,
            color=T.MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.reveal_btn = ft.IconButton(
            icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
            icon_size=14,
            icon_color=T.MUTED,
            tooltip="Reveal Folder in Finder",
            on_click=self.handle_reveal_folder,
            width=26,
            height=26,
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
        )

        self.table = ft.DataTable(
            sort_column_index=self.sort_col_idx,
            sort_ascending=self.sort_asc,
            columns=[
                ft.DataColumn(
                    ft.Text("File Name", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(0, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("Fmt", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(1, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("Artist", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(2, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("Title", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(3, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("Album", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(4, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("#", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    numeric=True,
                    on_sort=lambda e: self.handle_sort(5, e.ascending),
                ),
                ft.DataColumn(
                    ft.Text("Year", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11),
                    on_sort=lambda e: self.handle_sort(6, e.ascending),
                ),
            ],
            rows=[],
            show_checkbox_column=True,
            on_select_all=self.handle_select_all,
            data_row_color={"selected": T.ROW_SEL, "hovered": T.ROW_HOV},
            heading_row_color={"hovered": ft.Colors.with_opacity(0.08, T.PRIMARY)},
            data_row_max_height=36,
            column_spacing=10,
            divider_thickness=0.5,
            checkbox_horizontal_margin=12,
        )

        # Tracks Table Card (displayed when files are loaded)
        self.tracks_header_row = ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUDIO_FILE_OUTLINED, color=T.PRIMARY, size=16),
                        ft.Text("Tracks", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=12, color=T.MUTED),
                                    self.folder_label,
                                    self.reveal_btn,
                                ],
                                spacing=4,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.05, T.TEXT),
                            border_radius=6,
                            padding=ft.Padding.only(left=8, right=4, top=2, bottom=2),
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.search_input,
                        ft.OutlinedButton(
                            "Open Folder (⌘O)",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self.on_load_directory,
                            style=ft.ButtonStyle(
                                color=T.PRIMARY,
                                side=ft.BorderSide(1.2, T.PRIMARY),
                                shape=ft.RoundedRectangleBorder(radius=6),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            ),
                            height=30,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.table_card = T.card(
            content=ft.Column(
                controls=[
                    self.tracks_header_row,
                    ft.Divider(height=1, color=T.BORDER),
                    ft.Row(
                        controls=[self.table],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                spacing=8,
            ),
            padding=12,
            expand=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        # Onboarding Placeholder Card (displayed when empty)
        self.onboarding_card = T.card(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, size=48, color=T.MUTED),
                    ft.Text("No Folder Loaded", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Text(
                        "Open a folder containing audio files (FLAC, MP3, M4A, OGG, WAV, AIFF, etc.) to start editing metadata.",
                        size=11,
                        color=T.MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    T.gradient_button(
                        text="Open Folder (⌘O)",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=self.on_load_directory,
                        width=190,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=24,
            expand=True,
        )

        self.controls = [self.onboarding_card]
        self.visible = True

    def handle_reveal_folder(self, e):
        """Opens the currently loaded folder in Finder."""
        if self.app_state.current_files:
            folder = os.path.dirname(self.app_state.current_files[0]['path'])
            reveal_in_finder(folder)

    def handle_filter_change(self, e):
        """Filters visible rows in the table based on the search query."""
        self.filter_query = (self.search_input.value or "").strip().lower()
        self.update_ui()

    def handle_sort(self, col_idx: int, ascending: bool):
        """Sorts `app_state.current_files` by the clicked column while preserving selection."""
        self.sort_col_idx = col_idx
        self.sort_asc = ascending
        self.table.sort_column_index = col_idx
        self.table.sort_ascending = ascending

        if not self.app_state.current_files:
            return

        selected_paths = {
            self.app_state.current_files[i]['path']
            for i in self.app_state.selected_file_indices
            if i < len(self.app_state.current_files)
        }

        def sort_key(item):
            path = item['path']
            meta = item['metadata']
            if col_idx == 0:
                return os.path.basename(path).lower()
            elif col_idx == 1:
                return Path(path).suffix.lower()
            elif col_idx == 2:
                return meta.get('artist', '').lower()
            elif col_idx == 3:
                return meta.get('title', '').lower()
            elif col_idx == 4:
                return meta.get('album', '').lower()
            elif col_idx == 5:
                raw_trk = str(meta.get('tracknumber', '0')).split('/')[0].strip()
                return int(raw_trk) if raw_trk.isdigit() else 9999
            elif col_idx == 6:
                return str(meta.get('date', meta.get('year', ''))).lower()
            return os.path.basename(path).lower()

        self.app_state.current_files.sort(key=sort_key, reverse=not ascending)
        self.app_state.selected_file_indices = {
            i for i, f in enumerate(self.app_state.current_files) if f['path'] in selected_paths
        }
        self.app_state.notify()

    def _visible_indices(self):
        """Returns indices of `current_files` matching the active filter query."""
        if not self.filter_query:
            return list(range(len(self.app_state.current_files)))
        q = self.filter_query
        matched = []
        for i, f in enumerate(self.app_state.current_files):
            name = os.path.basename(f['path']).lower()
            meta = f['metadata']
            haystack = " ".join([
                name,
                meta.get('artist', '').lower(),
                meta.get('title', '').lower(),
                meta.get('album', '').lower(),
                str(meta.get('date', meta.get('year', ''))).lower(),
            ])
            if q in haystack:
                matched.append(i)
        return matched

    def handle_select_all(self, e: ft.ControlEvent):
        """Handles clicks on the select-all header checkbox (respects active filter)."""
        vis = self._visible_indices()
        if str(e.data).lower() == "true":
            self.app_state.set_selection(vis)
        else:
            self.app_state.set_selection([])

    def make_on_change(self, idx: int):
        """Creates an event handler for a specific row's checkbox."""
        def on_change(e: ft.ControlEvent):
            is_checked = str(e.data).lower() == "true"
            is_shift = self.app_state.shift_pressed or is_shift_pressed_global()
            is_cmd_ctrl = self.app_state.ctrl_pressed or is_cmd_or_ctrl_pressed_global()

            if is_shift and self.app_state.last_selected_index is not None:
                start = min(self.app_state.last_selected_index, idx)
                end   = max(self.app_state.last_selected_index, idx)
                new_sel = set(self.app_state.selected_file_indices)
                for i in range(start, end + 1):
                    new_sel.add(i)
                self.app_state.set_selection(new_sel)
                return
            elif is_cmd_ctrl:
                new_sel = set(self.app_state.selected_file_indices)
                if is_checked:
                    new_sel.add(idx)
                else:
                    new_sel.discard(idx)
                self.app_state.last_selected_index = idx
                self.app_state.set_selection(new_sel)
                return
            else:
                self.app_state.last_selected_index = idx
                if is_checked:
                    self.app_state.set_selection([idx])
                else:
                    self.app_state.set_selection([])
                return

        return on_change

    def update_ui(self):
        """Synchronizes the DataRow configurations with the global AppState."""
        self.visible = True

        if len(self.app_state.current_files) == 0:
            self.controls = [self.onboarding_card]
            try:
                self.update()
            except Exception:
                pass
            return

        self.controls = [self.table_card]

        try:
            folder_path = os.path.dirname(self.app_state.current_files[0]['path'])
            self.folder_label.value = os.path.basename(folder_path) or folder_path
            self.folder_label.tooltip = folder_path

            vis_indices = self._visible_indices()
            self.table.rows.clear()

            for i in vis_indices:
                file_data = self.app_state.current_files[i]
                path = file_data['path']
                name = os.path.basename(path)
                ext = Path(path).suffix.upper().lstrip('.')
                meta = file_data['metadata']
                year_val = str(meta.get('date', meta.get('year', '')))[:4]

                fmt_badge = ft.Container(
                    content=ft.Text(ext, color=T.PRIMARY, size=9, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.with_opacity(0.12, T.PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                )

                row = ft.DataRow(
                    selected=(i in self.app_state.selected_file_indices),
                    on_select_change=self.make_on_change(i),
                    cells=[
                        ft.DataCell(ft.Text(name,                       color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(fmt_badge),
                        ft.DataCell(ft.Text(meta.get('artist',     ''), color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Text(meta.get('title',      ''), color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Text(meta.get('album',      ''), color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Text(meta.get('tracknumber',''), color=T.MUTED, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Text(year_val,                   color=T.MUTED, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                    ],
                )
                self.table.rows.append(row)

            self.update()
        except Exception as e:
            logger.error(f"Error updating file table UI: {e}", exc_info=True)
