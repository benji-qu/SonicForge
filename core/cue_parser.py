import re
from typing import Dict, List, Any, Optional
from utils.logger import logger

def parse_cue_time(time_str: str) -> float:
    """
    Converts a CUE time offset MM:SS:FF to total seconds.
    FF represents CD audio frames (75 frames per second).
    """
    parts = time_str.split(':')
    if len(parts) == 3:
        try:
            mins = int(parts[0])
            secs = int(parts[1])
            frames = int(parts[2])
            return mins * 60.0 + secs + frames / 75.0
        except ValueError:
            pass
    return 0.0

def parse_cue_sheet(cue_path: str) -> Dict[str, Any]:
    """
    Parses a .cue file and returns a dictionary of album metadata and track lists.
    """
    try:
        with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read CUE sheet at {cue_path}: {e}")
        return {'metadata': {}, 'tracks': []}

    lines = content.splitlines()
    album_meta = {'artist': '', 'title': '', 'file': '', 'date': ''}
    tracks = []
    current_track = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Global or track-level performer
        m_perf = re.match(r'PERFORMER\s+"([^"]+)"', line, re.IGNORECASE)
        if m_perf:
            perf_val = m_perf.group(1)
            if current_track is not None:
                current_track['artist'] = perf_val
            else:
                album_meta['artist'] = perf_val
            continue

        # Global or track-level title
        m_title = re.match(r'TITLE\s+"([^"]+)"', line, re.IGNORECASE)
        if m_title:
            title_val = m_title.group(1)
            if current_track is not None:
                current_track['title'] = title_val
            else:
                album_meta['title'] = title_val
            continue

        # Release year/date (REM DATE 2004)
        m_date = re.match(r'REM\s+DATE\s+"?(\d{4})"?', line, re.IGNORECASE)
        if m_date:
            album_meta['date'] = m_date.group(1)
            continue

        # File reference
        m_file = re.match(r'FILE\s+"([^"]+)"\s+\w+', line, re.IGNORECASE)
        if m_file:
            album_meta['file'] = m_file.group(1)
            continue

        # Track definition
        m_track = re.match(r'TRACK\s+(\d+)\s+AUDIO', line, re.IGNORECASE)
        if m_track:
            track_num = int(m_track.group(1))
            current_track = {
                'number': f"{track_num:02d}",
                'title': '',
                'artist': '',
                'start_time': 0.0,
                'end_time': None
            }
            tracks.append(current_track)
            continue

        # Track start time index 01
        m_index = re.match(r'INDEX\s+01\s+(\d{2}:\d{2}:\d{2})', line, re.IGNORECASE)
        if m_index and current_track is not None:
            current_track['start_time'] = parse_cue_time(m_index.group(1))
            continue

    # Fill track artists with album artist fallback if empty
    for t in tracks:
        if not t['artist']:
            t['artist'] = album_meta['artist']

    # Calculate end times sequentially
    for i in range(len(tracks) - 1):
        tracks[i]['end_time'] = tracks[i+1]['start_time']

    return {'metadata': album_meta, 'tracks': tracks}
