import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC, TRCK, TCON
from mutagen.mp4 import MP4, MP4Cover
import base64
from pathlib import Path
from typing import Dict, Any, Optional

from utils.logger import logger

SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".ogg",
    ".oga",
    ".opus",
    ".m4a",
    ".mp4",
    ".aac",
    ".wav",
    ".aiff",
    ".aif",
    ".wv",
    ".ape",
    ".wma",
}

# Mapping from raw ID3 / MP4 / ASF tag keys to standard SonicForge keys
_KEY_ALIASES = {
    # ID3 frames (MP3, WAV, AIFF)
    "tit2": "title",
    "tpe1": "artist",
    "talb": "album",
    "tdrc": "date",
    "tyer": "date",
    "trck": "tracknumber",
    "tcon": "genre",
    # MP4 / M4A atoms
    "\xa9nam": "title",
    "\xa9art": "artist",
    "\xa9alb": "album",
    "\xa9day": "date",
    "trkn": "tracknumber",
    "\xa9gen": "genre",
    # ASF / WMA attributes
    "author": "artist",
    "wm/albumtitle": "album",
    "wm/year": "date",
    "wm/tracknumber": "tracknumber",
    "wm/genre": "genre",
    # Common APEv2 / Vorbis variants
    "track": "tracknumber",
    "year": "date",
}


def _extract_cover_art(audio: Any) -> Optional[bytes]:
    """Extracts embedded front cover art bytes from any mutagen audio object."""
    try:
        # 1. FLAC pictures
        if isinstance(audio, FLAC) and audio.pictures:
            return audio.pictures[0].data

        # 2. MP4 / M4A 'covr' atom
        if isinstance(audio, MP4) or (isinstance(getattr(audio, "tags", None), dict) and "covr" in audio.tags):
            covr = audio.get("covr")
            if covr:
                return bytes(covr[0])

        # 3. OGG Vorbis / Opus 'metadata_block_picture'
        b64_list = audio.get("metadata_block_picture") if hasattr(audio, "get") else None
        if isinstance(b64_list, list) and b64_list and isinstance(b64_list[0], str):
            raw = base64.b64decode(b64_list[0])
            pic = Picture(raw)
            return pic.data

        # 4. ID3 APIC frames (MP3, WAV, AIFF)
        tags = getattr(audio, "tags", None)
        if isinstance(tags, ID3) or (tags is not None and hasattr(tags, "getall")):
            apics = tags.getall("APIC")
            if apics and isinstance(getattr(apics[0], "data", None), (bytes, bytearray)):
                return bytes(apics[0].data)
    except Exception as e:
        logger.debug(f"Could not extract cover art: {e}")
    return None


def get_metadata(file_path: str) -> Dict[str, Any]:
    """
    Reads metadata from an audio file (FLAC, MP3, OGG, M4A, WAV, AIFF, etc.) and standardises it.
    
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
            
        metadata: Dict[str, Any] = {}
        for key, val in audio.items():
            key_str = str(key)
            key_lower = key_str.lower()

            # Skip raw binary picture frames in text dictionary
            if key_lower.startswith("apic") or key_lower in ("covr", "metadata_block_picture"):
                continue

            std_key = _KEY_ALIASES.get(key_lower, key_lower)

            # Handle MP4 tuple track numbers e.g. [(1, 12)]
            if key_lower == "trkn" and isinstance(val, list) and val and isinstance(val[0], tuple):
                trk, tot = val[0][0], val[0][1] if len(val[0]) > 1 else 0
                str_val = f"{trk}/{tot}" if tot else str(trk)
            elif hasattr(val, "text"):
                # ID3 frame object (TIT2, TPE1, etc.)
                str_val = ", ".join(str(v) for v in val.text)
            elif isinstance(val, list):
                str_val = ", ".join(str(v) for v in val)
            else:
                str_val = str(val)

            metadata[std_key] = str_val
                
        # Try to extract cover art across all supported formats
        metadata['cover_art'] = _extract_cover_art(audio)
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


def write_metadata_to_mp3(mp3_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Writes metadata and cover art to an MP3 file using EasyID3 and ID3 APIC frames.
    """
    try:
        try:
            audio = EasyID3(mp3_path)
        except mutagen.id3.ID3NoHeaderError:
            audio = mutagen.File(mp3_path, easy=True)
            if audio is None:
                return False
            audio.add_tags()

        key_map = {
            "title": "title",
            "artist": "artist",
            "album": "album",
            "date": "date",
            "year": "date",
            "tracknumber": "tracknumber",
            "track": "tracknumber",
            "genre": "genre",
        }

        for k, v in tags.items():
            if k.lower() == "cover_art" or v is None:
                continue
            easy_key = key_map.get(k.lower())
            if easy_key:
                audio[easy_key] = str(v)
        audio.save()

        if cover_art:
            mp3_file = MP3(mp3_path, ID3=ID3)
            if mp3_file.tags is None:
                mp3_file.add_tags()
            mp3_file.tags.delall("APIC")
            mime = "image/png" if cover_art.startswith(b"\x89PNG") else "image/jpeg"
            mp3_file.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=cover_art,
                )
            )
            mp3_file.save()
        logger.info(f"Successfully saved MP3 metadata to {mp3_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save MP3 metadata to {mp3_path}: {e}", exc_info=True)
        return False


def write_metadata_to_m4a(m4a_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Writes metadata and cover art to an M4A / MP4 / ALAC audio file.
    """
    try:
        audio = MP4(m4a_path)
        if audio.tags is None:
            audio.add_tags()

        atom_map = {
            "title": "\xa9nam",
            "artist": "\xa9ART",
            "album": "\xa9alb",
            "date": "\xa9day",
            "year": "\xa9day",
            "genre": "\xa9gen",
        }

        for k, v in tags.items():
            k_low = k.lower()
            if k_low == "cover_art" or v is None:
                continue
            val_str = str(v)
            if k_low in ("tracknumber", "track"):
                parts = val_str.split("/")
                try:
                    trk = int(parts[0].strip()) if parts[0].strip() else 0
                except ValueError:
                    trk = 0
                try:
                    tot = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
                except ValueError:
                    tot = 0
                audio["trkn"] = [(trk, tot)]
            elif k_low in atom_map:
                audio[atom_map[k_low]] = [val_str]

        if cover_art:
            img_fmt = MP4Cover.FORMAT_PNG if cover_art.startswith(b"\x89PNG") else MP4Cover.FORMAT_JPEG
            audio["covr"] = [MP4Cover(cover_art, imageformat=img_fmt)]

        audio.save()
        logger.info(f"Successfully saved M4A/MP4 metadata to {m4a_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save M4A/MP4 metadata to {m4a_path}: {e}", exc_info=True)
        return False


def write_metadata_to_id3_container(file_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Writes ID3 metadata and cover art to WAV or AIFF files.
    """
    try:
        audio = mutagen.File(file_path)
        if audio is None:
            return False
        if audio.tags is None:
            audio.add_tags()

        frame_map = {
            "title": ("TIT2", TIT2),
            "artist": ("TPE1", TPE1),
            "album": ("TALB", TALB),
            "date": ("TDRC", TDRC),
            "year": ("TDRC", TDRC),
            "tracknumber": ("TRCK", TRCK),
            "track": ("TRCK", TRCK),
            "genre": ("TCON", TCON),
        }

        for k, v in tags.items():
            k_low = k.lower()
            if k_low == "cover_art" or v is None:
                continue
            if k_low in frame_map:
                frame_id, frame_cls = frame_map[k_low]
                audio.tags[frame_id] = frame_cls(encoding=3, text=[str(v)])

        if cover_art:
            if hasattr(audio.tags, "delall"):
                audio.tags.delall("APIC")
            mime = "image/png" if cover_art.startswith(b"\x89PNG") else "image/jpeg"
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=cover_art,
                )
            )

        audio.save()
        logger.info(f"Successfully saved ID3 container metadata to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save ID3 container metadata to {file_path}: {e}", exc_info=True)
        return False


def save_metadata(file_path: str, tags: Dict[str, Any], cover_art: Optional[bytes] = None) -> bool:
    """
    Universal metadata writer supporting FLAC, MP3, OGG/Opus, M4A/MP4, WAV, AIFF, WavPack, APE, and WMA.
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".flac":
        return save_metadata_to_flac(file_path, tags, cover_art)
    if ext in (".ogg", ".oga", ".opus"):
        return write_metadata_to_ogg(file_path, tags, cover_art)
    if ext == ".mp3":
        return write_metadata_to_mp3(file_path, tags, cover_art)
    if ext in (".m4a", ".mp4", ".aac"):
        return write_metadata_to_m4a(file_path, tags, cover_art)
    if ext in (".wav", ".aiff", ".aif"):
        return write_metadata_to_id3_container(file_path, tags, cover_art)

    # Generic fallback (WavPack .wv, Monkey's Audio .ape, WMA .wma, etc.)
    try:
        audio = mutagen.File(file_path, easy=True) or mutagen.File(file_path)
        if audio is None:
            logger.error(f"Unsupported audio format for saving metadata: {file_path}")
            return False
        for k, v in tags.items():
            if k.lower() == "cover_art" or v is None:
                continue
            try:
                audio[k] = str(v)
            except Exception:
                pass
        audio.save()
        logger.info(f"Successfully saved metadata to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save metadata to {file_path}: {e}", exc_info=True)
        return False


def generate_filename(pattern: str, metadata: dict, original_path: str) -> str:
    """
    Generates a standardised filename based on a pattern template and metadata tags.
    
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
        metadata: Standardised metadata tags dictionary
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
            
    # Sanitise name to remove OS-forbidden characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        new_name = new_name.replace(char, '_')
        
    # Standardise whitespace (remove duplicate spaces, strip outer spaces)
    new_name = " ".join(new_name.split())
    
    # Ensure correct extension suffix
    if not new_name.lower().endswith(ext.lower()):
        new_name += ext
        
    return new_name

