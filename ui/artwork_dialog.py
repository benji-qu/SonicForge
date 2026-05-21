import flet as ft
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from utils.logger import logger
from core.api_client import fetch_itunes_artwork, fetch_deezer_artwork
from core.image_utils import process_downloaded_image
from core.state import AppState

class ArtworkDialog:
    """
    UI Component for displaying online artwork search results.
    Opens immediately with a loading spinner, then populates results
    progressively as each API responds.
    """
    def __init__(self, page: ft.Page, app_state: AppState, set_status: Callable[[str], None]):
        self.page = page
        self.app_state = app_state
        self.set_status = set_status
        
        self._loading_indicator = ft.Column(
            [
                ft.ProgressRing(width=40, height=40),
                ft.Text("Searching for artwork...", size=13),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )
        
        self._results_row = ft.Row(wrap=True, spacing=10, scroll=ft.ScrollMode.AUTO, width=580)
        
        self._content = ft.Column(
            controls=[self._loading_indicator],
            scroll=ft.ScrollMode.AUTO,
            height=300,
            width=600,
        )
        
        self.dialog = ft.AlertDialog(
            title=ft.Text("Select Artwork"),
            content=self._content,
            actions=[ft.TextButton("Cancel", on_click=self.close)],
        )
        
    def close(self, e: Optional[ft.ControlEvent] = None):
        """Closes the dialog."""
        self.dialog.open = False
        self.page.update()
        
    def _show(self):
        """Ensures the dialog is mounted and visible."""
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
        
    def _add_result(self, r: dict):
        """Appends a single artwork result card to the dialog and refreshes."""
        def make_on_select(url: str):
            def on_select(ev):
                self.close()
                self.set_status("Downloading artwork...")
                def download():
                    try:
                        logger.info(f"Downloading high-res artwork from {url}")
                        resp = requests.get(url, timeout=10)
                        resp.raise_for_status()
                        img_bytes = process_downloaded_image(resp.content)
                        self.app_state.set_cover_art(img_bytes)
                        self.set_status("Artwork downloaded and processed!")
                    except Exception as ex:
                        logger.error(f"Failed to download image from {url}: {ex}", exc_info=True)
                        self.set_status("Failed to download image.")
                threading.Thread(target=download, daemon=True).start()
            return on_select
            
        img_btn = ft.Container(
            content=ft.Column([
                ft.Image(src=r['thumb_url'], width=100, height=100, fit="cover", border_radius=8),
                ft.Text(
                    f"[{r['source']}]\n{r['album_name'][:18]}",
                    size=10,
                    text_align=ft.TextAlign.CENTER,
                    width=100,
                )
            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=make_on_select(r['high_res_url']),
            tooltip=r['album_name'],
            padding=6,
            border_radius=8,
            ink=True,
        )
        self._results_row.controls.append(img_btn)
        self.page.update()

    def open_for(self, artist: str, album: str):
        """
        Opens the dialog immediately, then fetches iTunes and Deezer results
        concurrently, adding each to the dialog as they arrive.

        Args:
            artist: Artist name.
            album: Album name.
        """
        if not artist and not album:
            self.set_status("Please fill in Artist or Album first to search.")
            logger.warning("Attempted to search artwork with empty artist and album.")
            return

        # Reset state and open the dialog right away
        self._results_row.controls.clear()
        self._content.controls = [self._loading_indicator]
        self._show()

        def run_search():
            found_any = False
            fetchers = {
                "iTunes": lambda: fetch_itunes_artwork(artist, album),
                "Deezer": lambda: fetch_deezer_artwork(artist, album),
            }

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(fn): name for name, fn in fetchers.items()}
                
                first_result = True
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        results = future.result()
                        logger.debug(f"{source} returned {len(results)} results.")
                        for r in results:
                            if first_result:
                                # Switch from spinner to results grid on first hit
                                self._content.controls = [self._results_row]
                                first_result = False
                            self._add_result(r)
                            found_any = True
                    except Exception as e:
                        logger.error(f"{source} fetch failed: {e}", exc_info=True)

            if not found_any:
                self._content.controls = [
                    ft.Text("No artwork found. Try different artist/album names.", italic=True)
                ]
                self.page.update()
                self.set_status("No artwork found.")
            else:
                self.set_status("")

        threading.Thread(target=run_search, daemon=True).start()
