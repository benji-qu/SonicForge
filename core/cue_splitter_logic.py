import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Callable
from pathlib import Path
from utils.logger import logger
from core.metadata import (
    get_metadata,
    generate_filename,
    save_metadata,
    save_metadata_to_flac,
    write_metadata_to_ogg,
)
import utils.paths  # Ensure PATH includes Homebrew/local binaries

def split_cue_audio(
    input_flac: str,
    output_dir: str,
    tracks: List[Dict[str, Any]],
    album_meta: Dict[str, Any],
    naming_pattern: str,
    output_format: str,  # "flac", "mp3", "m4a", "ogg", or "wav"
    progress_callback: Callable[[int, str], None]
):
    """
    Slices a continuous audio file using FFmpeg and writes metadata tags into the split tracks.
    Supports transcoding to FLAC, MP3, M4A, OGG, or WAV in parallel.
    
    Args:
        input_flac: Path to the continuous source audio file.
        output_dir: Directory where individual files will be saved.
        tracks: List of parsed track dictionaries.
        album_meta: Dictionary of album-level metadata.
        naming_pattern: Pattern for generating filenames (e.g. "{track:02d} - {title}")
        output_format: Target format ("flac", "mp3", "m4a", "ogg", or "wav").
        progress_callback: Callback invoked as progress updates (args: completed_count, status_message)
    """
    os.makedirs(output_dir, exist_ok=True)
    fmt = output_format.lower().strip().lstrip(".")
    
    total_tracks = len(tracks)
    logger.info(f"Starting CUE split for {total_tracks} tracks ({fmt}) from {input_flac} into {output_dir}")
    progress_callback(0, "Starting split process…")
    
    # Extract embedded cover art from the continuous source audio if available
    source_meta = get_metadata(input_flac)
    source_cover_art = source_meta.get('cover_art') if source_meta else None
    
    lock = threading.Lock()
    completed_count = 0

    def _split_single_track(track: Dict[str, Any]):
        nonlocal completed_count
        track_num = track['number']
        track_title = track['title'] or f"Track {track_num}"
        track_artist = track['artist'] or album_meta['artist'] or "Unknown Artist"
        album_title = album_meta['title'] or "Unknown Album"
        album_date = album_meta['date'] or ""
        
        with lock:
            progress_callback(completed_count, f"Splitting track {track_num}/{total_tracks:02d}: {track_title}…")
        
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
        filename = str(Path(filename).with_suffix(f".{fmt}"))
        output_path = os.path.join(output_dir, filename)
        
        start_time = track['start_time']
        end_time = track['end_time']
        
        # Slice track via FFmpeg (place -ss before -i for fast seektable-based input seeking)
        cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-i', input_flac]
        if end_time is not None:
            duration = end_time - start_time
            cmd += ['-t', str(duration)]
        
        if fmt == "ogg":
            cmd += ['-c:a', 'libvorbis', '-q:a', '6', output_path]
        elif fmt == "mp3":
            cmd += ['-c:a', 'libmp3lame', '-b:a', '320k', output_path]
        elif fmt == "m4a":
            cmd += ['-vn', '-c:a', 'aac', '-b:a', '256k', output_path]
        elif fmt == "wav":
            cmd += ['-c:a', 'pcm_s16le', output_path]
        else:
            cmd += ['-c:a', 'flac', output_path]
        
        try:
            logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Inject tags and cover art directly into the split track
            if fmt == "ogg":
                write_metadata_to_ogg(output_path, track_meta, source_cover_art)
            elif fmt == "flac":
                save_metadata_to_flac(output_path, track_meta, source_cover_art)
            else:
                save_metadata(output_path, track_meta, source_cover_art)

            
            logger.info(f"Successfully split and tagged: {output_path}")
            with lock:
                completed_count += 1
                progress_callback(completed_count, f"✓ Completed track {track_num}: {track_title}")
        except Exception as e:
            logger.error(f"Failed to split track {track_num}: {e}")
            with lock:
                completed_count += 1
                progress_callback(completed_count, f"⚠️ Error splitting track {track_num}: {track_title}")

    max_workers = min(total_tracks or 1, os.cpu_count() or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_split_single_track, tracks))
            
    logger.info("CUE splitting process finished.")
    progress_callback(total_tracks, f"✓ Successfully split {total_tracks} tracks!")
