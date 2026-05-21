from typing import List, Set, Callable, Optional, Any, Dict, Iterable

from utils.logger import logger

class AppState:
    """
    Central state manager for the SonicForge application.
    Implements a simple observer pattern to notify UI components of changes.
    """
    def __init__(self):
        self.current_files: List[Dict[str, Any]] = []
        self.selected_file_indices: Set[int] = set()
        self.selected_cover_art_bytes: Optional[bytes] = None
        self.listeners: List[Callable[[], None]] = []
        
        # Keyboard modifiers
        self.shift_pressed: bool = False
        self.ctrl_pressed: bool = False
        self.last_selected_index: Optional[int] = None
        
        logger.debug("AppState initialized")
        
    def add_listener(self, listener: Callable[[], None]):
        """Registers a callback to be invoked when state changes."""
        self.listeners.append(listener)
        
    def notify(self):
        """Notifies all registered listeners of a state change."""
        for listener in self.listeners:
            try:
                listener()
            except Exception as e:
                logger.error(f"Error in state listener: {e}", exc_info=True)
            
    def load_files(self, files: List[Dict[str, Any]]):
        """
        Loads a new batch of files into state, clearing existing selections.
        
        Args:
            files: A list of dictionaries containing file paths and metadata.
        """
        self.current_files = files
        self.selected_file_indices.clear()
        self.last_selected_index = None
        logger.info(f"Loaded {len(files)} files into state.")
        self.notify()
        
    def set_selection(self, indices: Iterable[int]):
        """
        Updates the selected file indices.
        
        Args:
            indices: An iterable of integers representing selected row indices.
        """
        self.selected_file_indices = set(indices)
        logger.debug(f"Updated selection. {len(self.selected_file_indices)} items selected.")
        self.notify()
        
    def set_cover_art(self, art_bytes: Optional[bytes]):
        """
        Sets the global cover art bytes to be applied to selected files.
        
        Args:
            art_bytes: Raw JPEG/PNG image bytes, or None to clear.
        """
        self.selected_cover_art_bytes = art_bytes
        logger.debug("Updated global cover art bytes in state.")
        self.notify()
