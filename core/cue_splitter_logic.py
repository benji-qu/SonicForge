import os
import subprocess
from typing import List, Dict, Any, Callable
from pathlib import Path
from utils.logger import logger
from core.metadata import generate_filename, save_metadata_to_flac, write_metadata_to_ogg

def split_cue_audio(
    input_flac: str,
    output_dir: str,
    tracks: List[Dict[str, Any]],
    album_meta: Dict[str, Any],
    naming_pattern: str,
    output_format: str,  # "flac" or "ogg"
    progress_callback: Callable[[int, str], None]
):
    """
    Slices a continuous FLAC file using FFmpeg and writes metadata tags into the split tracks.
    Supports transcoding to FLAC or OGG.
    
    Args:
        input_flac: Path to the large FLAC file.
        output_dir: Directory where individual files will be saved.
        tracks: List of parsed track dictionaries.
        album_meta: Dictionary of album-level metadata.
        naming_pattern: Pattern for generating filenames (e.g. "{track:02d} - {title}")
        output_format: Target format ("flac" or "ogg").
        progress_callback: Callback invoked as progress updates (args: completed_count, status_message)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    total_tracks = len(tracks)
    logger.info(f"Starting CUE split for {total_tracks} tracks ({output_format}) from {input_flac} into {output_dir}")
    progress_callback(0, "Starting split process…")
    
    for i, track in enumerate(tracks):
        track_num = track['number']
        track_title = track['title'] or f"Track {track_num}"
        track_artist = track['artist'] or album_meta['artist'] or "Unknown Artist"
        album_title = album_meta['title'] or "Unknown Album"
        album_date = album_meta['date'] or ""
        
        status_msg = f"Splitting track {track_num}/{total_tracks:02d}: {track_title}…"
        progress_callback(i, status_msg)
        
        # Build track metadata block
        track_meta = {
            'tracknumber': track_num,
            'title': track_title,
            'artist': track_artist,
            'album': album_title,
            'date': album_date,
        }
        
        # Generate target filename with correct extension
        filename = generate_filename(naming_pattern, track_meta, input_flac)
        if output_format == "ogg":
            filename = str(Path(filename).with_suffix(".ogg"))
        output_path = os.path.join(output_dir, filename)
        
        start_time = track['start_time']
        end_time = track['end_time']
        
        # Slice track via FFmpeg
        cmd = ['ffmpeg', '-y', '-i', input_flac, '-ss', str(start_time)]
        if end_time is not None:
            duration = end_time - start_time
            cmd += ['-t', str(duration)]
        
        if output_format == "ogg":
            cmd += ['-c:a', 'libvorbis', '-q:a', '6', output_path]
        else:
            cmd += ['-c:a', 'flac', output_path]
        
        try:
            logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Inject tags directly into the split track
            if output_format == "ogg":
                write_metadata_to_ogg(output_path, track_meta)
            else:
                save_metadata_to_flac(output_path, track_meta)
            
            logger.info(f"Successfully split and tagged: {output_path}")
        except Exception as e:
            logger.error(f"Failed to split track {track_num}: {e}")
            progress_callback(i, f"⚠️ Error splitting track {track_num}: {track_title}")
            continue
            
    logger.info("CUE splitting process finished.")
    progress_callback(total_tracks, f"✓ Successfully split {total_tracks} tracks!")
