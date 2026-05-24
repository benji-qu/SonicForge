import flet as ft
import threading
from typing import Callable, Optional, List, Dict, Any
import os

from utils.logger import logger
from core.api_client import search_musicbrainz_releases, fetch_musicbrainz_release_tracks
from core.metadata import save_metadata_to_flac
from core.state import AppState
from ui import theme as T


class AutoTagDialog:
    """
    UI Component for interactive MusicBrainz auto-tagging.
    Allows searching releases, viewing tracklist mapping, and saving tags.
    """

    def __init__(
        self,
        page: ft.Page,
        app_state: AppState,
        set_status: Callable[[str], None],
        on_save_complete: Optional[Callable[[int], None]] = None
    ):
        self.page = page
        self.app_state = app_state
        self.set_status = set_status
        self.on_save_complete = on_save_complete

        # Search Inputs
        self.artist_input = T.styled_field("Artist Query", expand=True)
        self.album_input = T.styled_field("Album/Release Query", expand=True)

        self.search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_color=T.PRIMARY,
            tooltip="Search MusicBrainz",
            on_click=self.handle_search_click
        )

        # Scrollable area for search results
        self.results_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            expand=True
        )

        self.results_container = ft.Container(
            content=self.results_column,
            bgcolor=T.BG,
            border=ft.Border.all(1, T.BORDER),
            border_radius=10,
            padding=10,
            height=280,
            expand=True,
        )

        # Scrollable mapping container for Stage 2
        self.mapping_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            expand=True
        )

        self.mapping_container = ft.Container(
            content=self.mapping_column,
            bgcolor=T.BG,
            border=ft.Border.all(1, T.BORDER),
            border_radius=10,
            padding=10,
            height=280,
            expand=True,
        )

        # Root layouts for each stage
        self.search_stage_layout = ft.Column(
            controls=[
                ft.Row(
                    [
                        self.artist_input,
                        self.album_input,
                        self.search_btn
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.Divider(height=1, color=T.BORDER),
                self.results_container
            ],
            spacing=12,
            height=360,
            width=620,
        )

        # We will initialize this dynamically in show_mapping_stage
        self.mapping_stage_layout = None

        # Base Alert Dialog setup
        self.dialog = ft.AlertDialog(
            title=ft.Text("Auto-Tag Album from MusicBrainz", weight=ft.FontWeight.BOLD, color=T.TEXT),
            content=self.search_stage_layout,
            bgcolor=T.SURFACE,
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Temporary holders for data during dialog stages
        self.searched_releases: List[Dict[str, Any]] = []
        self.selected_release: Optional[Dict[str, Any]] = None
        self.fetched_tracks: List[Dict[str, Any]] = []

    def close(self, e: Optional[ft.ControlEvent] = None):
        """Closes the dialog."""
        self.dialog.open = False
        self.page.update()

    def open(self):
        """Opens the auto-tag dialog with prefilled values from selection."""
        selected_indices = self.app_state.selected_file_indices
        if not selected_indices:
            self.set_status("Please select tracks first to auto-tag.")
            return

        # Prefill queries using metadata from the first selected file
        first_idx = next(iter(selected_indices))
        first_meta = self.app_state.current_files[first_idx]['metadata']
        
        self.artist_input.value = first_meta.get('artist', '')
        self.album_input.value = first_meta.get('album', '')

        # Reset inner state
        self.searched_releases.clear()
        self.selected_release = None
        self.fetched_tracks.clear()
        
        # Reset visual controls to Search Stage
        self.results_column.controls.clear()
        self.dialog.content = self.search_stage_layout
        
        # Rebuild standard search dialog actions
        self.dialog.actions = [
            ft.OutlinedButton(
                "Cancel",
                on_click=self.close,
                style=ft.ButtonStyle(
                    color=T.MUTED,
                    side=ft.BorderSide(1, T.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            )
        ]

        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
            
        self.dialog.open = True
        self.page.update()

        # Fire initial query if we have prefilled details
        if self.artist_input.value or self.album_input.value:
            self.trigger_search(self.artist_input.value, self.album_input.value)

    def handle_search_click(self, e):
        """Fires query based on manual changes to input text fields."""
        self.trigger_search(self.artist_input.value, self.album_input.value)

    def trigger_search(self, artist: str, album: str):
        """Starts asynchronous MusicBrainz query and displays progress spinner."""
        self.results_column.controls.clear()
        self.results_column.controls.append(
            ft.Row(
                [
                    ft.ProgressRing(width=28, height=28, color=T.PRIMARY),
                    ft.Text("Querying MusicBrainz…", size=13, color=T.MUTED)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            )
        )
        self.page.update()
        
        def run():
            results = search_musicbrainz_releases(artist, album)
            self.searched_releases = results
            
            self.results_column.controls.clear()
            if not results:
                self.results_column.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No matching releases found on MusicBrainz. Try refining queries.",
                            color=T.MUTED,
                            italic=True,
                            size=12
                        ),
                        alignment=ft.Alignment(0, 0),
                        expand=True,
                        margin=ft.Margin.symmetric(vertical=40)
                    )
                )
            else:
                for r in results:
                    self.results_column.controls.append(self.build_release_card(r))
            self.page.update()
            
        threading.Thread(target=run, daemon=True).start()

    def build_release_card(self, r: Dict[str, Any]) -> ft.Container:
        """Returns a styled horizontal release selection item card."""
        info_parts = []
        if r.get('date'):
            info_parts.append(r['date'][:4])  # Grab year
        if r.get('country') and r['country'] != 'Unknown':
            info_parts.append(r['country'])
        if r.get('track_count'):
            info_parts.append(f"{r['track_count']} tracks")
        if r.get('label') and r['label'] != 'Unknown Label':
            info_parts.append(r['label'])
            
        info_str = " • ".join(info_parts) or "No extra release info"

        # Image component with dynamic source
        cover_image = ft.Image(
            src=r['cover_url'],
            width=50,
            height=50,
            fit="cover",
            border_radius=6,
        )

        return ft.Container(
            content=ft.Row(
                [
                    cover_image,
                    ft.Column(
                        [
                            ft.Text(r['title'], weight=ft.FontWeight.BOLD, size=13, color=T.TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(r['artist'], size=11, color=T.PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(info_str, size=10, color=T.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=3,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.MUTED, size=20)
                ],
                spacing=12,
            ),
            bgcolor=T.SURFACE,
            border=ft.Border.all(1, T.BORDER),
            border_radius=8,
            padding=8,
            on_click=lambda e, rel=r: self.handle_release_select(rel),
            ink=True
        )

    def handle_release_select(self, release: Dict[str, Any]):
        """Starts asynchronous fetch for the selected release's tracks and shifts stage."""
        self.selected_release = release
        
        # Display progress indicators in the dialog
        self.results_column.controls.clear()
        self.results_column.controls.append(
            ft.Row(
                [
                    ft.ProgressRing(width=28, height=28, color=T.PRIMARY),
                    ft.Text("Retrieving complete track list…", size=13, color=T.MUTED)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            )
        )
        self.page.update()

        def run():
            tracks = fetch_musicbrainz_release_tracks(release['id'])
            self.fetched_tracks = tracks
            self.show_mapping_stage()

        threading.Thread(target=run, daemon=True).start()

    def show_mapping_stage(self):
        """Renders Stage 2: Interactive file mapping & confirmation."""
        selected_indices = sorted(list(self.app_state.selected_file_indices))
        local_files = [self.app_state.current_files[idx] for idx in selected_indices]

        self.mapping_column.controls.clear()

        # Render count mismatch warnings beautifully
        mismatch_banner = None
        if len(local_files) != len(self.fetched_tracks):
            mismatch_banner = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400, size=18),
                        ft.Text(
                            f"Mismatch: Selected {len(local_files)} tracks vs Release's {len(self.fetched_tracks)} tracks.",
                            color=ft.Colors.AMBER_400,
                            size=11,
                            weight=ft.FontWeight.W_500,
                        )
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_400),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.AMBER_400)),
                border_radius=8,
                padding=8,
            )
            self.mapping_column.controls.append(mismatch_banner)

        # Build mapping list items
        max_len = max(len(local_files), len(self.fetched_tracks))
        for i in range(max_len):
            local_name = ""
            fetched_title = ""
            fetched_artist = ""
            fetched_num = ""
            fetched_dur = ""

            if i < len(local_files):
                local_name = os.path.basename(local_files[i]['path'])
            if i < len(self.fetched_tracks):
                track = self.fetched_tracks[i]
                fetched_title = track.get('title', 'Unknown Title')
                fetched_artist = track.get('artist', '') or self.selected_release['artist']
                fetched_num = track.get('tracknumber', '00')
                fetched_dur = f"({track['duration']})" if track.get('duration') else ""

            row_content = []
            
            # Left: Local File
            if local_name:
                row_content.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MUSIC_NOTE, color=T.MUTED, size=14),
                            ft.Text(local_name, color=T.MUTED, size=11, weight=ft.FontWeight.NORMAL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                        ],
                        spacing=6,
                        expand=True
                    )
                )
            else:
                row_content.append(
                    ft.Text("— No File —", color=ft.Colors.RED_400, italic=True, size=11, expand=True)
                )

            # Center Arrow
            row_content.append(ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color=T.PRIMARY, size=12))

            # Right: MusicBrainz metadata mapping
            if fetched_title:
                meta_block = ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"{fetched_num}. {fetched_title}", color=T.TEXT, size=12, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                ft.Text(fetched_dur, color=T.MUTED, size=9) if fetched_dur else ft.Container()
                            ],
                            spacing=6,
                            tight=True
                        ),
                        ft.Text(fetched_artist, color=T.MUTED, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                    ],
                    spacing=2,
                    expand=True
                )
                row_content.append(meta_block)
            else:
                row_content.append(
                    ft.Text("— No Metadata —", color=ft.Colors.RED_400, italic=True, size=11, expand=True)
                )

            self.mapping_column.controls.append(
                ft.Container(
                    content=ft.Row(row_content, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=T.SURFACE,
                    border=ft.Border.all(0.8, T.BORDER),
                    border_radius=8,
                    padding=8,
                )
            )

        # Assemble layout
        self.mapping_stage_layout = ft.Column(
            controls=[
                ft.Text(f"Mapping Selected Files to {self.selected_release['title']}:", size=12, color=T.MUTED, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=T.BORDER),
                self.mapping_container
            ],
            spacing=12,
            height=360,
            width=620,
        )

        self.dialog.content = self.mapping_stage_layout
        
        # Update buttons for Mapping view
        self.dialog.actions = [
            ft.OutlinedButton(
                "Back",
                icon=ft.Icons.ARROW_BACK,
                on_click=self.handle_back_click,
                style=ft.ButtonStyle(
                    color=T.MUTED,
                    side=ft.BorderSide(1, T.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            ),
            T.gradient_button(
                text="Apply Tags",
                icon=ft.Icons.CHECK_CIRCLE,
                on_click=self.handle_apply_click,
                width=160,
            )
        ]
        self.page.update()

    def handle_back_click(self, e):
        """Swaps view back to standard release list Search stage."""
        # Restore results column list
        self.results_column.controls.clear()
        for r in self.searched_releases:
            self.results_column.controls.append(self.build_release_card(r))
            
        self.dialog.content = self.search_stage_layout
        self.dialog.actions = [
            ft.OutlinedButton(
                "Cancel",
                on_click=self.close,
                style=ft.ButtonStyle(
                    color=T.MUTED,
                    side=ft.BorderSide(1, T.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            )
        ]
        self.page.update()

    def handle_apply_click(self, e):
        """Applies the mapped tags to the files physically on disk."""
        self.close()
        
        selected_indices = sorted(list(self.app_state.selected_file_indices))
        local_files = [self.app_state.current_files[idx] for idx in selected_indices]
        
        logger.info(f"Applying MusicBrainz metadata tags to {len(local_files)} files.")
        self.set_status(f"Saving MusicBrainz metadata tags to {len(local_files)} file(s)…")

        def run_save():
            saved_count = 0
            # Retrieve release info
            album_title = self.selected_release['title']
            # release date or release year
            date_val = self.selected_release.get('date', '')

            # Save in background thread
            for i, file_data in enumerate(local_files):
                if i >= len(self.fetched_tracks):
                    break
                    
                meta = file_data['metadata']
                track_data = self.fetched_tracks[i]
                
                # Write fields
                meta['tracknumber'] = track_data['tracknumber']
                meta['title'] = track_data['title']
                meta['artist'] = track_data['artist'] or self.selected_release['artist']
                meta['album'] = album_title
                if date_val:
                    meta['date'] = date_val
                
                try:
                    save_metadata_to_flac(file_data['path'], meta, meta.get('cover_art'))
                    saved_count += 1
                except Exception as ex:
                    logger.error(f"Error saving auto-tagged metadata to {file_data['path']}: {ex}", exc_info=True)

            # Trigger complete refresh callback
            if self.on_save_complete:
                self.page.run_task(lambda: self.on_save_complete(saved_count))

        threading.Thread(target=run_save, daemon=True).start()
