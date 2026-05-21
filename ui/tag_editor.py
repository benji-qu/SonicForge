import flet as ft
import time
from typing import Callable, Optional

from core.state import AppState
from core.metadata import save_metadata_to_flac
from utils.logger import logger
from utils.paths import CACHE_DIR

class TagEditor(ft.Column):
    """
    UI Component for editing audio metadata tags.
    """
    def __init__(self, app_state: AppState, on_fetch_artwork: Callable[[str, str], None], on_select_local_artwork: Callable[[], None], on_save_complete: Optional[Callable[[int], None]] = None):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self.app_state = app_state
        self.on_fetch_artwork = on_fetch_artwork
        self.on_select_local_artwork = on_select_local_artwork
        self.on_save_complete = on_save_complete
        
        self.track_field = ft.TextField(label="Track Number")
        self.title_field = ft.TextField(label="Title")
        self.artist_field = ft.TextField(label="Artist")
        self.album_field = ft.TextField(label="Album")
        self.year_field = ft.TextField(label="Year")
        self.genre_field = ft.TextField(label="Genre")
        
        self.cover_art_placeholder = ft.Container(
            width=150, height=150, bgcolor="surfaceVariant", border_radius=10,
            content=ft.Text("Click to select\ncover art", text_align=ft.TextAlign.CENTER)
        )
        self.cover_art_container = ft.Container(
            width=150, height=150,
            on_click=lambda e: self.on_select_local_artwork(),
            content=self.cover_art_placeholder,
            tooltip="Click to select 500x500 square cover art"
        )
        self.app_state.add_listener(self.update_ui)
        
        fetch_art_btn = ft.ElevatedButton("Fetch Artwork Online", icon="search", on_click=lambda e: self.on_fetch_artwork(self.artist_field.value, self.album_field.value))
        
        self.controls = [
            ft.Text("Batch Tag Editor", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Select tracks on the left and edit fields here. Empty fields are ignored when multiple files are selected.", size=12, color="outline"),
            ft.Row([self.cover_art_container, fetch_art_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.track_field,
            self.title_field,
            self.artist_field,
            self.album_field,
            self.year_field,
            self.genre_field,
            ft.ElevatedButton("Save Tags to Selected Files", on_click=self.save_metadata)
        ]
        
    def update_ui(self):
        """Updates the input fields to reflect the current selection."""
        if not self.app_state.selected_file_indices:
            self.track_field.value = ""
            self.title_field.value = ""
            self.artist_field.value = ""
            self.album_field.value = ""
            self.year_field.value = ""
            self.genre_field.value = ""
            self.cover_art_container.content = self.cover_art_placeholder
            if self.page:
                self.page.update()
            return
            
        try:
            first_idx = next(iter(self.app_state.selected_file_indices))
            first_meta = self.app_state.current_files[first_idx]['metadata']
            
            def get_year(m): return m.get('date', m.get('year', ''))
            
            c_track = first_meta.get('tracknumber', '')
            c_title = first_meta.get('title', '')
            c_artist = first_meta.get('artist', '')
            c_album = first_meta.get('album', '')
            c_genre = first_meta.get('genre', '')
            c_year = get_year(first_meta)
            c_cover = first_meta.get('cover_art', None)
            
            for idx in self.app_state.selected_file_indices:
                if idx == first_idx: continue
                meta = self.app_state.current_files[idx]['metadata']
                if meta.get('tracknumber', '') != c_track: c_track = ""
                if meta.get('title', '') != c_title: c_title = ""
                if meta.get('artist', '') != c_artist: c_artist = ""
                if meta.get('album', '') != c_album: c_album = ""
                if meta.get('genre', '') != c_genre: c_genre = ""
                if get_year(meta) != c_year: c_year = ""
                if meta.get('cover_art', None) != c_cover: c_cover = None
                
            display_bytes = self.app_state.selected_cover_art_bytes or c_cover
            
            if display_bytes:
                filename = f"preview_{int(time.time())}.jpg"
                cache_path = CACHE_DIR / filename
                with open(cache_path, "wb") as f:
                    f.write(display_bytes)
                self.cover_art_container.content = ft.Image(src=str(cache_path), width=150, height=150, fit="cover", border_radius=10)
            else:
                self.cover_art_container.content = self.cover_art_placeholder
                
            self.track_field.value = c_track
            self.title_field.value = c_title
            self.artist_field.value = c_artist
            self.album_field.value = c_album
            self.year_field.value = c_year
            self.genre_field.value = c_genre
            
            logger.debug(f"Tag editor updated: artist={c_artist!r}, title={c_title!r}")
            if self.page:
                self.page.update()
        except Exception as e:
            logger.error(f"Error updating tag editor UI: {e}", exc_info=True)
        
    def save_metadata(self, e: ft.ControlEvent):
        """Saves the edited metadata back to the audio files."""
        if not self.app_state.selected_file_indices:
            logger.warning("Attempted to save metadata with no files selected.")
            return
            
        logger.info(f"Saving metadata for {len(self.app_state.selected_file_indices)} files.")
        for idx in self.app_state.selected_file_indices:
            file_data = self.app_state.current_files[idx]
            meta = file_data['metadata']
            
            if self.track_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['tracknumber'] = self.track_field.value
            if self.title_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['title'] = self.title_field.value
            if self.artist_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['artist'] = self.artist_field.value
            if self.album_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['album'] = self.album_field.value
            if self.year_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['date'] = self.year_field.value
            if self.genre_field.value.strip() or len(self.app_state.selected_file_indices) == 1:
                meta['genre'] = self.genre_field.value
                
            if self.app_state.selected_cover_art_bytes:
                meta['cover_art'] = self.app_state.selected_cover_art_bytes
                
            try:
                save_metadata_to_flac(file_data['path'], meta, meta.get('cover_art'))
            except Exception as ex:
                logger.error(f"Error saving to {file_data['path']}: {ex}", exc_info=True)
                
        if self.on_save_complete:
            self.on_save_complete(len(self.app_state.selected_file_indices))
