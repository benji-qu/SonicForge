import flet as ft
import time
from typing import Callable, Optional

from core.state import AppState
from core.metadata import save_metadata_to_flac
from ui import theme as T
from utils.logger import logger
from utils.paths import CACHE_DIR


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

        # ── Tag fields ─────────────────────────────────────────────────────────
        self.track_field  = T.styled_field("Track Number")
        self.title_field  = T.styled_field("Title")
        self.artist_field = T.styled_field("Artist")
        self.album_field  = T.styled_field("Album")
        self.year_field   = T.styled_field("Year")
        self.genre_field  = T.styled_field("Genre")

        # ── Artwork placeholder ────────────────────────────────────────────────
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
            width=160, height=160,
            on_click=lambda e: self.on_select_local_artwork(),
            content=self._artwork_placeholder,
            tooltip="Click to select an artwork",
            border_radius=8,
            ink=True,
        )

        # ── Fetch artwork button ───────────────────────────────────────────────
        fetch_btn = ft.OutlinedButton(
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
            height=34,
        )

        # ── Auto-number tracks button ──────────────────────────────────────────
        self.auto_number_btn = ft.OutlinedButton(
            "Auto-Number Tracks",
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            on_click=self.auto_number_tracks,
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            ),
            height=34,
        )

        # ── Rename files button ────────────────────────────────────────────────
        self.rename_files_btn = ft.OutlinedButton(
            "Rename Files",
            icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
            on_click=lambda e: self.on_rename_files(),
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            ),
            height=34,
        )

        # ── Auto-Tag Album button ──────────────────────────────────────────────
        self.autotag_btn = ft.OutlinedButton(
            "Auto-Tag Album",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=lambda e: self.on_autotag_album(),
            style=ft.ButtonStyle(
                color=T.PRIMARY,
                side=ft.BorderSide(1.2, T.PRIMARY),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            ),
            height=34,
        )

        # ── Gradient Save button ───────────────────────────────────────────────
        save_btn = T.gradient_button(
            text="Save Tags",
            icon=ft.Icons.SAVE_OUTLINED,
            on_click=self.save_metadata,
        )

        # ── Card content ───────────────────────────────────────────────────────
        self.controls = [
            T.card(
                content=ft.Column(
                    [
                        ft.Text("Tag Editor", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT),
                        ft.Text(
                            "Select tracks on the left, then edit fields below.",
                            size=10,
                            color=T.MUTED,
                        ),
                        ft.Divider(height=1, color=T.BORDER),
                        ft.Row(
                            [
                                self.cover_art_container,
                                ft.Column(
                                    [
                                        self.rename_files_btn,
                                        self.auto_number_btn,
                                        self.autotag_btn,
                                        fetch_btn,
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.START,
                                    spacing=6,
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.track_field,
                        self.title_field,
                        self.artist_field,
                        self.album_field,
                        self.year_field,
                        self.genre_field,
                        save_btn,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            )
        ]

        self.app_state.add_listener(self.update_ui)

    # ── State sync ─────────────────────────────────────────────────────────────

    def update_ui(self):
        """Updates the input fields to reflect the current selection."""
        if not self.app_state.selected_file_indices:
            self.track_field.value  = ""
            self.title_field.value  = ""
            self.artist_field.value = ""
            self.album_field.value  = ""
            self.year_field.value   = ""
            self.genre_field.value  = ""
            self.cover_art_container.content = self._artwork_placeholder
            if self.page:
                self.page.update()
            return

        try:
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

            for idx in self.app_state.selected_file_indices:
                if idx == first_idx:
                    continue
                meta = self.app_state.current_files[idx]['metadata']
                if meta.get('tracknumber', '') != c_track:  c_track  = ""
                if meta.get('title',       '') != c_title:  c_title  = ""
                if meta.get('artist',      '') != c_artist: c_artist = ""
                if meta.get('album',       '') != c_album:  c_album  = ""
                if meta.get('genre',       '') != c_genre:  c_genre  = ""
                if get_year(meta)              != c_year:   c_year   = ""
                if meta.get('cover_art',  None) != c_cover: c_cover  = None

            display_bytes = self.app_state.selected_cover_art_bytes or c_cover

            if display_bytes:
                filename   = f"preview_{int(time.time())}.jpg"
                cache_path = CACHE_DIR / filename
                with open(cache_path, "wb") as f:
                    f.write(display_bytes)
                self.cover_art_container.content = ft.Image(
                    src=str(cache_path), width=120, height=120,
                    fit="cover", border_radius=8,
                )
            else:
                self.cover_art_container.content = self._artwork_placeholder

            self.track_field.value  = c_track
            self.title_field.value  = c_title
            self.artist_field.value = c_artist
            self.album_field.value  = c_album
            self.year_field.value   = c_year
            self.genre_field.value  = c_genre

            logger.debug(f"Tag editor updated: artist={c_artist!r}, title={c_title!r}")
            if self.page:
                self.page.update()
        except Exception as e:
            logger.error(f"Error updating tag editor UI: {e}", exc_info=True)

    # ── Save logic ─────────────────────────────────────────────────────────────

    def save_metadata(self, e):
        """Saves the edited metadata back to the audio files."""
        if not self.app_state.selected_file_indices:
            logger.warning("Attempted to save metadata with no files selected.")
            return

        logger.info(f"Saving metadata for {len(self.app_state.selected_file_indices)} files.")
        for idx in self.app_state.selected_file_indices:
            file_data = self.app_state.current_files[idx]
            meta      = file_data['metadata']
            single    = len(self.app_state.selected_file_indices) == 1

            if self.track_field.value.strip()  or single: meta['tracknumber'] = self.track_field.value
            if self.title_field.value.strip()   or single: meta['title']       = self.title_field.value
            if self.artist_field.value.strip()  or single: meta['artist']      = self.artist_field.value
            if self.album_field.value.strip()   or single: meta['album']       = self.album_field.value
            if self.year_field.value.strip()    or single: meta['date']        = self.year_field.value
            if self.genre_field.value.strip()   or single: meta['genre']       = self.genre_field.value

            if self.app_state.selected_cover_art_bytes:
                meta['cover_art'] = self.app_state.selected_cover_art_bytes

            try:
                save_metadata_to_flac(file_data['path'], meta, meta.get('cover_art'))
            except Exception as ex:
                logger.error(f"Error saving to {file_data['path']}: {ex}", exc_info=True)

        if self.on_save_complete:
            self.on_save_complete(len(self.app_state.selected_file_indices))

    def auto_number_tracks(self, e):
        """Sequentially numbers the track numbers of selected files."""
        if not self.app_state.selected_file_indices:
            logger.warning("Attempted to auto-number with no files selected.")
            return

        logger.info(f"Auto-numbering {len(self.app_state.selected_file_indices)} tracks.")
        
        # Sort indices to match their current listing/visual order in the table
        selected_indices = sorted(list(self.app_state.selected_file_indices))
        
        for i, idx in enumerate(selected_indices, start=1):
            file_data = self.app_state.current_files[idx]
            meta = file_data['metadata']
            meta['tracknumber'] = f"{i:02d}"
            
            try:
                save_metadata_to_flac(file_data['path'], meta, meta.get('cover_art'))
            except Exception as ex:
                logger.error(f"Error saving auto-number to {file_data['path']}: {ex}", exc_info=True)
                
        if self.on_save_complete:
            self.on_save_complete(len(selected_indices))
