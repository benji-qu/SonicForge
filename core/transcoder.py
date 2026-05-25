import os
import subprocess
from typing import Dict, Any, Callable, Optional
from pathlib import Path
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

from utils.logger import logger
from core.metadata import save_metadata_to_flac, write_metadata_to_ogg

def transcode_file(
    input_path: str,
    output_dir: str,
    target_format: str,        # "mp3", "ogg", "wav"
    quality: str,              # quality setting (e.g., "320kbps", "q6")
    metadata: Dict[str, Any],  # tags dict
    cover_art: Optional[bytes] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Transcodes an audio file to the target format and copies/injects metadata.
    
    Args:
        input_path: Absolute path to the source audio file.
        output_dir: Target directory where the converted file will be saved.
        target_format: Target audio format ("mp3", "ogg", "wav").
        quality: Bitrate or quality profile (e.g. "320k", "q6").
        metadata: Metadata tags to write into the output file.
        cover_art: Optional raw cover artwork image bytes.
        progress_callback: Optional callback for status logging.
        
    Returns:
        The absolute path to the transcoded output file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = Path(input_path).stem
    ext = f".{target_format.lower()}"
    output_path = os.path.join(output_dir, f"{base_name}{ext}")
    
    if progress_callback:
        progress_callback(f"Transcoding {base_name} to {target_format.upper()}…")
        
    # Build standard quality mappings to ffmpeg command
    cmd = ['ffmpeg', '-y', '-i', input_path]
    
    if target_format == 'mp3':
        # Strip trailing 'k' or 'kbps' to standardise to '320k', '256k', etc.
        bitrate = quality.lower().replace('kbps', '').strip()
        if not bitrate.endswith('k'):
            bitrate += 'k'
        cmd += ['-c:a', 'libmp3lame', '-b:a', bitrate]
    elif target_format == 'ogg':
        # Default OGG Vorbis quality (q6 corresponds to standard 192kbps)
        q_val = '6'
        if quality.lower().startswith('q'):
            q_val = quality[1:]
        elif quality.isdigit():
            q_val = quality
        cmd += ['-c:a', 'libvorbis', '-q:a', q_val]
    elif target_format == 'wav':
        cmd += ['-c:a', 'pcm_s16le']
    else:
        raise ValueError(f"Unsupported target format: {target_format}")
        
    cmd.append(output_path)
    
    logger.debug(f"Running transcode command: {' '.join(cmd)}")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    if progress_callback:
        progress_callback(f"Writing metadata to {base_name}{ext}…")
        
    # Inject metadata tags based on format
    inject_metadata(output_path, target_format, metadata, cover_art)
    
    if progress_callback:
        size_info = ""
        try:
            in_size = os.path.getsize(input_path)
            out_size = os.path.getsize(output_path)
            ratio = (1.0 - (out_size / in_size)) * 100 if in_size > 0 else 0
            
            def format_size(b):
                for u in ['B', 'KB', 'MB', 'GB']:
                    if b < 1024.0: return f"{b:.1f} {u}"
                    b /= 1024.0
                return f"{b:.1f} TB"
            
            if ratio > 0:
                size_info = f" ({format_size(out_size)} vs {format_size(in_size)}, -{ratio:.1f}% reduced)"
            elif ratio < 0:
                size_info = f" ({format_size(out_size)} vs {format_size(in_size)}, +{-ratio:.1f}% larger)"
            else:
                size_info = f" ({format_size(out_size)} vs {format_size(in_size)})"
        except Exception:
            pass
        progress_callback(f"✓ Completed: {base_name}{ext}{size_info}")
        
    return output_path

def inject_metadata(file_path: str, format_type: str, metadata: Dict[str, Any], cover_art: Optional[bytes] = None):
    """
    Injects metadata and cover art into the transcode output file.
    """
    # Clean tags dict to strip cover_art key and remove empty values
    tags = {}
    for k, v in metadata.items():
        if k.lower() == 'cover_art':
            continue
        if v is not None and str(v).strip():
            tags[k] = str(v)
            
    if format_type == 'flac':
        save_metadata_to_flac(file_path, tags, cover_art)
        
    elif format_type == 'ogg':
        write_metadata_to_ogg(file_path, tags, cover_art)
        
    elif format_type == 'mp3':
        try:
            # Load or create EasyID3 tags
            try:
                audio = EasyID3(file_path)
            except mutagen.id3.ID3NoHeaderError:
                audio = mutagen.File(file_path, easy=True)
                audio.add_tags()
                
            # Mapping of standard keys to EasyID3 keys
            key_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'date': 'date',
                'year': 'date',
                'tracknumber': 'tracknumber',
                'genre': 'genre',
                'track': 'tracknumber',
            }
            
            for k, v in tags.items():
                easy_key = key_map.get(k.lower())
                if easy_key:
                    audio[easy_key] = str(v)
            audio.save()
            
            # Embed cover art if provided (requires raw ID3 APIC frame)
            if cover_art:
                mp3_file = MP3(file_path, ID3=ID3)
                mime = "image/jpeg"
                if cover_art.startswith(b'\x89PNG'):
                    mime = "image/png"
                    
                mp3_file.tags.add(
                    APIC(
                        encoding=3,  # UTF-8
                        mime=mime,
                        type=3,      # Front cover
                        desc='Cover',
                        data=cover_art
                    )
                )
                mp3_file.save()
            logger.info(f"Successfully saved MP3 metadata to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save MP3 metadata for {file_path}: {e}", exc_info=True)
            
    elif format_type == 'wav':
        try:
            audio = mutagen.File(file_path)
            if audio is not None:
                for k, v in tags.items():
                    try:
                        audio[k] = str(v)
                    except Exception:
                        pass
                audio.save()
            logger.info(f"Successfully saved WAV metadata to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save WAV metadata for {file_path}: {e}", exc_info=True)
