import mutagen
from mutagen.flac import FLAC, Picture
import base64
from typing import Dict, Any, Optional

from utils.logger import logger

def get_metadata(file_path: str) -> Dict[str, Any]:
    """
    Reads metadata from an audio file and standardizes it.
    
    Args:
        file_path: The absolute path to the audio file.
        
    Returns:
        A dictionary containing the parsed metadata and cover art.
    """
    try:
        audio = mutagen.File(file_path)
        if audio is None:
            logger.warning(f"Could not read metadata for {file_path}. mutagen returned None.")
            return {}
            
        metadata = {}
        for key, val in audio.items():
            if isinstance(val, list):
                metadata[key.lower()] = ", ".join([str(v) for v in val])
            else:
                metadata[key.lower()] = str(val)
                
        # Try to extract cover art
        cover_art = None
        if isinstance(audio, FLAC) and audio.pictures:
            cover_art = audio.pictures[0].data
            
        metadata['cover_art'] = cover_art
        logger.debug(f"Successfully read metadata for {file_path}")
        return metadata
    except Exception as e:
        logger.error(f"Error reading metadata from {file_path}: {e}", exc_info=True)
        return {}

def save_metadata_to_flac(flac_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Writes metadata back to a FLAC file.
    
    Args:
        flac_path: Path to the FLAC file.
        tags: Dictionary of string tags to write.
        cover_art: Optional bytes of the cover art image.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        audio = FLAC(flac_path)  # Use FLAC directly for type safety
        
        for key, value in tags.items():
            if key.lower() == 'cover_art':
                continue
            audio[key] = str(value)
            
        if cover_art:
            pic = Picture()
            pic.type = 3  # Front cover
            pic.mime = "image/jpeg"
            if cover_art.startswith(b'\x89PNG'):
                pic.mime = "image/png"
            pic.desc = "Cover"
            pic.data = cover_art
            audio.clear_pictures()
            audio.add_picture(pic)
            
        audio.save()
        logger.info(f"Successfully saved FLAC metadata to {flac_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save FLAC metadata to {flac_path}: {e}", exc_info=True)
        return False

def write_metadata_to_ogg(ogg_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Writes metadata to an OGG Opus/Vorbis file.
    
    Args:
        ogg_path: Path to the OGG file.
        tags: Dictionary of tags.
        cover_art: Optional bytes of the cover art image.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        audio = mutagen.File(ogg_path)
        if audio is None:
            logger.error(f"Cannot save metadata to {ogg_path}. File unsupported.")
            return False
            
        audio.delete()
            
        for key, value in tags.items():
            if key.lower() == 'cover_art':
                continue
            audio[key] = str(value)
            
        if cover_art:
            pic = Picture()
            pic.type = 3
            pic.mime = "image/jpeg"
            if cover_art.startswith(b'\x89PNG'):
                pic.mime = "image/png"
                
            pic.desc = "Cover"
            pic.data = cover_art
            picture_data = pic.write()
            encoded_data = base64.b64encode(picture_data).decode("ascii")
            audio["metadata_block_picture"] = [encoded_data]
            
        audio.save()
        logger.info(f"Successfully saved OGG metadata to {ogg_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save OGG metadata to {ogg_path}: {e}", exc_info=True)
        return False


def generate_filename(pattern: str, metadata: dict, original_path: str) -> str:
    """
    Generates a standardized filename based on a pattern template and metadata tags.
    
    Supported placeholders:
      - {track}       : Raw track number (e.g., "1", "01/12")
      - {track:02d}   : Double-digit track number (e.g., "01", "02")
      - {title}       : Track title
      - {artist}      : Artist name
      - {album}       : Album name
      - {year}        : Release year
      - {genre}       : Music genre
    
    Args:
        pattern: The naming template (e.g., "{track:02d} - {title}")
        metadata: Standardized metadata tags dictionary
        original_path: Original path of the file
        
    Returns:
        The generated filename string including the original file extension.
    """
    import os
    from pathlib import Path
    
    original_name = Path(original_path).name
    ext = Path(original_path).suffix
    
    # Extract values with clear, descriptive fallbacks
    track_val = metadata.get('tracknumber', '').strip()
    title_val = metadata.get('title', '').strip()
    artist_val = metadata.get('artist', '').strip()
    album_val = metadata.get('album', '').strip()
    year_val = metadata.get('date', metadata.get('year', '')).strip()
    genre_val = metadata.get('genre', '').strip()
    
    # Setup format dictionary
    fmt_dict = {
        'title': title_val or "Unknown Title",
        'artist': artist_val or "Unknown Artist",
        'album': album_val or "Unknown Album",
        'year': year_val or "Unknown Year",
        'genre': genre_val or "Unknown Genre",
    }
    
    # Handle track formatting specially
    track_num = 0
    try:
        # Strip trailing total counts (e.g., "01/12" -> "01")
        clean_track = track_val.split('/')[0].strip()
        track_num = int(clean_track)
    except Exception:
        pass
        
    fmt_dict['track'] = track_val or "00"
    
    # Handle the specific double-digit track placeholder manually if possible
    # to avoid str.format exceptions on arbitrary format descriptors
    if "{track:02d}" in pattern:
        if track_num > 0:
            pattern = pattern.replace("{track:02d}", f"{track_num:02d}")
        else:
            pattern = pattern.replace("{track:02d}", track_val or "00")
            
    try:
        new_name = pattern.format(**fmt_dict)
    except Exception as e:
        logger.warning(f"Failed standard format for pattern '{pattern}': {e}. Falling back to basic replace.")
        new_name = pattern
        for k, v in fmt_dict.items():
            new_name = new_name.replace(f"{{{k}}}", str(v))
            
    # Sanitize name to remove OS-forbidden characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        new_name = new_name.replace(char, '_')
        
    # Standardize whitespace (remove duplicate spaces, strip outer spaces)
    new_name = " ".join(new_name.split())
    
    # Ensure correct extension suffix
    if not new_name.lower().endswith(ext.lower()):
        new_name += ext
        
    return new_name

