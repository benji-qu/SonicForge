import flet as ft
import os
import sys
import ctypes

from core.state import AppState
from ui import theme as T
from utils.logger import logger


def is_shift_pressed_global() -> bool:
    """Returns True if the Shift key is physically pressed down on macOS or Windows."""
    if sys.platform == 'darwin':
        try:
            cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
            cg.CGEventSourceKeyState.restype = ctypes.c_bool
            cg.CGEventSourceKeyState.argtypes = [ctypes.c_int, ctypes.c_int]
            return cg.CGEventSourceKeyState(0, 56)
        except Exception:
            pass
    elif sys.platform == 'win32':
        try:
            return (ctypes.windll.user32.GetKeyState(0x10) & 0x8000) != 0
        except Exception:
            pass
    return False



class FileTable(ft.Row):
    """
    UI Component displaying a selectable data table of audio files.
    """

    def __init__(self, app_state: AppState):
        super().__init__(expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.app_state = app_state
        self.app_state.add_listener(self.update_ui)

        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("File Name", color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Artist",    color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Title",     color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Album",     color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Track #",   color=T.PRIMARY, weight=ft.FontWeight.BOLD, size=11)),
            ],
            rows=[],
            show_checkbox_column=True,
            on_select_all=self.handle_select_all,
            # Table-level row colour: drives selected/hovered tints for all rows
            data_row_color={"selected": T.ROW_SEL, "hovered": T.ROW_HOV},
            heading_row_color={"hovered": ft.Colors.with_opacity(0.08, T.PRIMARY)},   # ~8 % blue on hover
            data_row_max_height=36,
            column_spacing=12,
            divider_thickness=0.5,
            checkbox_horizontal_margin=16,
        )

        # Wrap the DataTable in a frosted-glass card
        self.controls = [
            T.card(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.AUDIO_FILE_OUTLINED, color=T.PRIMARY, size=16),
                                        ft.Text("Tracks", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Divider(height=1, color=T.BORDER),
                        ft.Row(
                            controls=[self.table],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    spacing=8,
                ),
                padding=12,
                expand=True,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        ]
        self.visible = False

    def handle_select_all(self, e: ft.ControlEvent):
        """Handles clicks on the select-all header checkbox."""
        if str(e.data).lower() == "true":
            self.app_state.set_selection(range(len(self.app_state.current_files)))
        else:
            self.app_state.set_selection([])

    def make_on_change(self, idx: int):
        """Creates an event handler for a specific row's checkbox.

        Selection rules:
          - Shift+click : range-select all rows between last selected and this row
          - Standard click : select only this row (clearing all others)
        """
        def on_change(e: ft.ControlEvent):
            is_checked = str(e.data).lower() == "true"
            is_shift = self.app_state.shift_pressed or is_shift_pressed_global()

            if is_shift and self.app_state.last_selected_index is not None:
                # Multi-select (range): add every row between anchor and current row
                start = min(self.app_state.last_selected_index, idx)
                end   = max(self.app_state.last_selected_index, idx)
                for i in range(start, end + 1):
                    self.app_state.selected_file_indices.add(i)
            else:
                # Single-select (clicking mode): selects ONLY this row
                if is_checked:
                    self.app_state.set_selection([idx])
                else:
                    self.app_state.set_selection([])
                self.app_state.last_selected_index = idx

            self.app_state.notify()
        return on_change

    def update_ui(self):
        """Synchronizes the DataRow configurations with the global AppState."""
        self.visible = len(self.app_state.current_files) > 0

        try:
            if len(self.table.rows) != len(self.app_state.current_files):
                logger.debug("Rebuilding file table rows.")
                self.table.rows.clear()
                for i, file_data in enumerate(self.app_state.current_files):
                    name = os.path.basename(file_data['path'])
                    meta = file_data['metadata']
                    row = ft.DataRow(
                        selected=(i in self.app_state.selected_file_indices),
                        on_select_change=self.make_on_change(i),
                        cells=[
                            ft.DataCell(ft.Text(name,                           color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.DataCell(ft.Text(meta.get('artist',     ''),     color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.DataCell(ft.Text(meta.get('title',      ''),     color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.DataCell(ft.Text(meta.get('album',      ''),     color=T.TEXT,  size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.DataCell(ft.Text(meta.get('tracknumber',''),     color=T.MUTED, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ],
                    )
                    self.table.rows.append(row)
            else:
                for i, (row, file_data) in enumerate(zip(self.table.rows, self.app_state.current_files)):
                    meta = file_data['metadata']
                    row.selected               = (i in self.app_state.selected_file_indices)
                    row.cells[0].content.value = os.path.basename(file_data['path'])
                    row.cells[1].content.value = meta.get('artist',     '')
                    row.cells[2].content.value = meta.get('title',      '')
                    row.cells[3].content.value = meta.get('album',      '')
                    row.cells[4].content.value = meta.get('tracknumber','')

            self.update()
        except Exception as e:
            logger.error(f"Error updating file table UI: {e}", exc_info=True)
