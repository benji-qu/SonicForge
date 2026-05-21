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
