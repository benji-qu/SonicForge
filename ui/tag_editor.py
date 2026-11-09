import flet as ft
import io
import threading
from typing import Callable, Optional
from PIL import Image

from core.state import AppState
from core.metadata import save_metadata
from ui import theme as T
from utils.logger import logger


class TagEditor(ft.Column):
    """
    UI Component for editing audio metadata tags.
    """

    def __init__(
        self,
        app_state: AppState,
        on_fetch_artwork: Callable[[str, str], None],
        on_select_local_artwork: Callable[[], None],
        on_rename_files: Callable[[], None],
        on_autotag_album: Callable[[], None],
        on_save_complete: Optional[Callable[[int], None]] = None,
    ):
        super().__init__(expand=True, spacing=0)
        self.app_state = app_state
        self.on_fetch_artwork = on_fetch_artwork
        self.on_select_local_artwork = on_select_local_artwork
        self.on_rename_files = on_rename_files
        self.on_autotag_album = on_autotag_album
        self.on_save_complete = on_save_complete
        self._is_dirty = False
        self._updating_programmatically = False

        # ── Tag fields ─────────────────────────────────────────────────────────
        self.track_field  = T.styled_field("Track Number", on_change=self._mark_dirty)
        self.title_field  = T.styled_field("Title",        on_change=self._mark_dirty)
        self.artist_field = T.styled_field("Artist",       on_change=self._mark_dirty)
        self.album_field  = T.styled_field("Album",        on_change=self._mark_dirty)
        self.year_field   = T.styled_field("Year",         on_change=self._mark_dirty)
        self.genre_field  = T.styled_field("Genre",        on_change=self._mark_dirty)

        # ── Selection & Unsaved Badges ─────────────────────────────────────────
        self.selection_badge_text = ft.Text("0 selected", size=10, color=T.MUTED, weight=ft.FontWeight.W_500)
        self.selection_badge = ft.Container(
            content=self.selection_badge_text,
            bgcolor=ft.Colors.with_opacity(0.08, T.MUTED),
            border=ft.Border.all(1, T.BORDER),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        )

        self.unsaved_badge = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, size=6, color=ft.Colors.AMBER_400),
                    ft.Text("Unsaved", size=10, color=ft.Colors.AMBER_400, weight=ft.FontWeight.BOLD),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_400)),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            visible=False,
        )

        # ── Artwork placeholder & resolution info ──────────────────────────────
        self._artwork_placeholder = ft.Container(
            width=120, height=120,
            border_radius=8,
            gradient=T.GRADIENT_ARTWORK,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.MUSIC_NOTE, color=ft.Colors.WHITE54, size=32),
                    ft.Text("Click to change", color=ft.Colors.WHITE38, size=9),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
        )

        self.cover_art_container = ft.Container(
            width=124, height=124,
            on_click=lambda e: self.on_select_local_artwork(),
            content=self._artwork_placeholder,
            tooltip="Click to choose cover art from disk",
            border_radius=8,
            ink=True,
        )

        self.artwork_info_text = ft.Text("No cover art", size=9, color=T.MUTED)
        self.clear_staged_art_btn = ft.TextButton(
            "Revert staged art",
            icon=ft.Icons.UNDO,
            on_click=self.revert_staged_artwork,
            style=ft.ButtonStyle(
                color=ft.Colors.AMBER_400,
                padding=ft.Padding.symmetric(horizontal=4, vertical=0),
                text_style=ft.TextStyle(size=9),
            ),
            height=20,
            visible=False,
        )

        # ── Action buttons ─────────────────────────────────────────────────────
        self.fetch_btn = ft.OutlinedButton(
            "Fetch Artwork Online",
            icon=ft.Icons.SEARCH,
            on_click=lambda e: self.on_fetch_artwork(
                self.artist_field.value, self.album_field.value
            ),
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            ),
            height=32,
        )

        self.auto_number_btn = ft.OutlinedButton(
            "Auto-Number Tracks",
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            on_click=self.auto_number_tracks,
            disabled=True,
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            ),
            height=32,
        )

        self.rename_files_btn = ft.OutlinedButton(
            "Rename Files (⌘R)",
            icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
            on_click=lambda e: self.on_rename_files(),
            disabled=True,
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            ),
            height=32,
        )

        self.autotag_btn = ft.OutlinedButton(
            "Auto-Tag Album",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=lambda e: self.on_autotag_album(),
            disabled=True,
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            ),
            height=32,
        )

        # ── Gradient Save button ───────────────────────────────────────────────
        self.save_btn = T.gradient_button(
            text="Save Tags (⌘S)",
            icon=ft.Icons.SAVE_OUTLINED,
            on_click=self.save_metadata,
            opacity=0.45,
            disabled=True,
        )

        # ── Card content ───────────────────────────────────────────────────────
        self.controls = [
            T.card(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("Tag Editor", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                ft.Container(expand=True),
                                self.unsaved_badge,
                                self.selection_badge,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                        ),
                        ft.Text(
                            "Select tracks on the left, then edit fields below.",
                            size=10,
                            color=T.MUTED,
                        ),
                        ft.Divider(height=1, color=T.BORDER),
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        self.cover_art_container,
                                        self.artwork_info_text,
                                        self.clear_staged_art_btn,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                ),
                                ft.Column(
                                    [
                                        self.rename_files_btn,
                                        self.autotag_btn,
                                        self.auto_number_btn,
                                        self.fetch_btn,
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                    spacing=6,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.track_field,
                        self.title_field,
                        self.artist_field,
                        self.album_field,
                        ft.Row(
                            [
                                ft.Container(content=self.year_field, expand=1),
                                ft.Container(content=self.genre_field, expand=2),
                            ],
                            spacing=8,
                        ),
                        self.save_btn,
                    ],
                    spacing=9,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=18,
                expand=True,
            )
        ]

        self.app_state.add_listener(self.update_ui)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _mark_dirty(self, e=None):
        """Flags the form as having unsaved edits."""
        if self._updating_programmatically or not self.app_state.selected_file_indices:
            return
        if not self._is_dirty:
            self._is_dirty = True
            self.unsaved_badge.visible = True
            if self.page:
                self.page.update()

    def revert_staged_artwork(self, e=None):
        """Clears newly staged cover art and restores existing embedded cover art."""
        self.app_state.set_cover_art(None)

    @staticmethod
    def _inspect_image_info(img_bytes: Optional[bytes]) -> str:
        """Returns a compact resolution & format summary for cover art bytes."""
        if not img_bytes:
            return "No cover art"
        try:
            with Image.open(io.BytesIO(img_bytes)) as im:
                fmt = (im.format or "IMG").upper()
                return f"{im.width}×{im.height} {fmt} ({len(img_bytes) // 1024} KB)"
        except Exception:
            return f"{len(img_bytes) // 1024} KB image"

    # ── State sync ─────────────────────────────────────────────────────────────

    def update_ui(self):
        """Updates the input fields to reflect the current selection."""
        self._updating_programmatically = True
        try:
            sel_count = len(self.app_state.selected_file_indices)
            has_selection = sel_count > 0

            # Update selection badge & button states
            self.selection_badge_text.value = (
                f"{sel_count} track{'s' if sel_count != 1 else ''} selected"
                if has_selection else "None selected"
            )
            self.selection_badge_text.color = T.PRIMARY if has_selection else T.MUTED
            self.selection_badge.bgcolor = (
                ft.Colors.with_opacity(0.12, T.PRIMARY)
                if has_selection else ft.Colors.with_opacity(0.08, T.MUTED)
            )
            self.selection_badge.border = ft.Border.all(
                1, T.PRIMARY if has_selection else T.BORDER
            )

            self.auto_number_btn.disabled = not has_selection
            self.rename_files_btn.disabled = not has_selection
            self.autotag_btn.disabled = not has_selection
            self.save_btn.disabled = not has_selection
            self.save_btn.opacity = 1.0 if has_selection else 0.45

            all_fields = (
                self.track_field,
                self.title_field,
                self.artist_field,
                self.album_field,
                self.year_field,
                self.genre_field,
            )

            if not has_selection:
                for fld in all_fields:
                    fld.value = ""
                    fld.hint_text = None
                self.cover_art_container.content = self._artwork_placeholder
                self.artwork_info_text.value = "No cover art"
                self.clear_staged_art_btn.visible = False
                self._is_dirty = False
                self.unsaved_badge.visible = False
                if self.page:
                    self.page.update()
                return

            first_idx  = next(iter(self.app_state.selected_file_indices))
            first_meta = self.app_state.current_files[first_idx]['metadata']

            def get_year(m): return m.get('date', m.get('year', ''))

            c_track  = first_meta.get('tracknumber', '')
            c_title  = first_meta.get('title',       '')
            c_artist = first_meta.get('artist',      '')
            c_album  = first_meta.get('album',       '')
            c_genre  = first_meta.get('genre',       '')
            c_year   = get_year(first_meta)
            c_cover  = first_meta.get('cover_art',   None)

            mixed_track = mixed_title = mixed_artist = mixed_album = mixed_genre = mixed_year = mixed_cover = False

            for idx in self.app_state.selected_file_indices:
                if idx == first_idx:
                    continue
                meta = self.app_state.current_files[idx]['metadata']
                if meta.get('tracknumber', '') != c_track:
                    c_track = ""
                    mixed_track = True
                if meta.get('title', '') != c_title:
                    c_title = ""
                    mixed_title = True
                if meta.get('artist', '') != c_artist:
                    c_artist = ""
                    mixed_artist = True
                if meta.get('album', '') != c_album:
                    c_album = ""
                    mixed_album = True
                if meta.get('genre', '') != c_genre:
                    c_genre = ""
                    mixed_genre = True
                if get_year(meta) != c_year:
                    c_year = ""
                    mixed_year = True
                if meta.get('cover_art', None) != c_cover:
                    c_cover = None
                    mixed_cover = True

            staged_bytes = self.app_state.selected_cover_art_bytes
            display_bytes = staged_bytes or c_cover

            if display_bytes:
                self.cover_art_container.content = ft.Image(
                    src=display_bytes, width=124, height=124,
                    fit="cover", border_radius=8,
                )
                self.artwork_info_text.value = self._inspect_image_info(display_bytes)
            else:
                self.cover_art_container.content = self._artwork_placeholder
                self.artwork_info_text.value = "Multiple covers" if mixed_cover else "No cover art"

            self.clear_staged_art_btn.visible = staged_bytes is not None

            mixed_hint = "< Multiple values — leave blank to keep >"
            self.track_field.value  = c_track
            self.track_field.hint_text = mixed_hint if mixed_track else None
            self.title_field.value  = c_title
            self.title_field.hint_text = mixed_hint if mixed_title else None
            self.artist_field.value = c_artist
            self.artist_field.hint_text = mixed_hint if mixed_artist else None
            self.album_field.value  = c_album
            self.album_field.hint_text = mixed_hint if mixed_album else None
            self.year_field.value   = c_year
            self.year_field.hint_text = "< Mixed >" if mixed_year else None
            self.genre_field.value  = c_genre
            self.genre_field.hint_text = "< Multiple values >" if mixed_genre else None

            self._is_dirty = staged_bytes is not None
            self.unsaved_badge.visible = self._is_dirty

            logger.debug(f"Tag editor updated: artist={c_artist!r}, title={c_title!r}")
            if self.page:
                self.page.update()
        except Exception as e:
            logger.error(f"Error updating tag editor UI: {e}", exc_info=True)
        finally:
            self._updating_programmatically = False

    # ── Save logic ─────────────────────────────────────────────────────────────

    def save_metadata(self, e=None):
        """Saves the edited metadata back to the audio files in a background thread."""
        if not self.app_state.selected_file_indices:
            logger.warning("Attempted to save metadata with no files selected.")
            return

        selected_indices = sorted(list(self.app_state.selected_file_indices))
        single = len(selected_indices) == 1
        track_val  = self.track_field.value
        title_val  = self.title_field.value
        artist_val = self.artist_field.value
        album_val  = self.album_field.value
        year_val   = self.year_field.value
        genre_val  = self.genre_field.value
        cover_bytes = self.app_state.selected_cover_art_bytes

        logger.info(f"Saving metadata for {len(selected_indices)} files.")

        def _save():
            for idx in selected_indices:
                file_data = self.app_state.current_files[idx]
                meta      = file_data['metadata']

                if track_val.strip()  or single: meta['tracknumber'] = track_val
                if title_val.strip()  or single: meta['title']       = title_val
                if artist_val.strip() or single: meta['artist']      = artist_val
                if album_val.strip()  or single: meta['album']       = album_val
                if year_val.strip()   or single: meta['date']        = year_val
                if genre_val.strip()  or single: meta['genre']       = genre_val

                if cover_bytes:
                    meta['cover_art'] = cover_bytes

                try:
                    save_metadata(file_data['path'], meta, meta.get('cover_art'))
                except Exception as ex:
                    logger.error(f"Error saving to {file_data['path']}: {ex}", exc_info=True)

            self.app_state.selected_cover_art_bytes = None
            self._is_dirty = False
            self.unsaved_badge.visible = False
            if self.on_save_complete:
                self.on_save_complete(len(selected_indices))

        threading.Thread(target=_save, daemon=True).start()

    def auto_number_tracks(self, e=None):
        """Sequentially numbers the track numbers of selected files in a background thread."""
        if not self.app_state.selected_file_indices:
            logger.warning("Attempted to auto-number with no files selected.")
            return

        # Sort indices to match their current listing/visual order in the table
        selected_indices = sorted(list(self.app_state.selected_file_indices))
        logger.info(f"Auto-numbering {len(selected_indices)} tracks.")

        def _number():
            for i, idx in enumerate(selected_indices, start=1):
                file_data = self.app_state.current_files[idx]
                meta = file_data['metadata']
                meta['tracknumber'] = f"{i:02d}"

                try:
                    save_metadata(file_data['path'], meta, meta.get('cover_art'))
                except Exception as ex:
                    logger.error(f"Error saving auto-number to {file_data['path']}: {ex}", exc_info=True)

            if self.on_save_complete:
                self.on_save_complete(len(selected_indices))

        threading.Thread(target=_number, daemon=True).start()
