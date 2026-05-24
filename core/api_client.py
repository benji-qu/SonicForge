import requests
import urllib.parse
from typing import List, Dict, Any

from utils.logger import logger

def fetch_itunes_artwork(artist: str, album: str) -> List[Dict[str, str]]:
    """
    Fetches artwork from the iTunes Search API.
    
    Args:
        artist: Name of the artist.
        album: Name of the album.
        
    Returns:
        List of dictionaries containing artwork URLs and metadata.
    """
    term = f"{artist} {album}".strip()
    if not term: 
        return []
        
    query = urllib.parse.quote_plus(term)
    url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=5"
    
    try:
        logger.debug(f"Fetching iTunes artwork for: {term}")
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        results = data.get('results', [])
        
        parsed = []
        for r in results:
            thumb_url = r.get('artworkUrl100', '')
            if not thumb_url: 
                continue
            high_res_url = thumb_url.replace('100x100bb', '600x600bb')
            parsed.append({
                'source': 'iTunes',
                'album_name': r.get('collectionName', 'Unknown'),
                'thumb_url': thumb_url,
                'high_res_url': high_res_url
            })
        return parsed
    except Exception as e:
        logger.error(f"iTunes search failed: {e}")
        return []

def fetch_deezer_artwork(artist: str, album: str) -> List[Dict[str, str]]:
    """
    Fetches artwork from the Deezer API.
    
    Args:
        artist: Name of the artist.
        album: Name of the album.
        
    Returns:
        List of dictionaries containing artwork URLs and metadata.
    """
    if not artist and not album: 
        return []
        
    url = f"https://api.deezer.com/search/album?q=artist:\"{artist}\" album:\"{album}\"&limit=5"
    
    try:
        logger.debug(f"Fetching Deezer artwork for artist={artist}, album={album}")
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        results = data.get('data', [])
        
        parsed = []
        for r in results:
            thumb_url = r.get('cover_medium', '')
            if not thumb_url: 
                continue
            high_res_url = r.get('cover_xl', '')
            if not high_res_url: 
                high_res_url = r.get('cover_big', thumb_url)
                
            parsed.append({
                'source': 'Deezer',
                'album_name': r.get('title', 'Unknown'),
                'thumb_url': thumb_url,
                'high_res_url': high_res_url
            })
        return parsed
    except Exception as e:
        logger.error(f"Deezer search failed: {e}")
        return []

def search_artwork(artist: str, album: str) -> List[Dict[str, str]]:
    """
    Searches multiple external APIs for album artwork.
    
    Args:
        artist: Name of the artist.
        album: Name of the album.
        
    Returns:
        Combined list of artwork suggestions from all sources.
    """
    logger.info(f"Starting unified artwork search for artist='{artist}', album='{album}'")
    itunes = fetch_itunes_artwork(artist, album)
    deezer = fetch_deezer_artwork(artist, album)
    return itunes + deezer


# ── MusicBrainz API Integration ──────────────────────────────────────────────────

MUSICBRAINZ_HEADERS = {
    "User-Agent": "SonicForge/1.0.0 ( contact@example.com )"
}

def search_musicbrainz_releases(artist: str, album: str) -> List[Dict[str, Any]]:
    """
    Searches MusicBrainz for releases matching artist and album/release name.
    
    Args:
        artist: Name of the artist.
        album: Name of the album.
        
    Returns:
        List of dictionaries containing release metadata and cover thumbnails.
    """
    if not artist and not album:
        return []
        
    # Build query
    parts = []
    if artist:
        parts.append(f'artist:"{artist}"')
    if album:
        parts.append(f'release:"{album}"')
    query = " AND ".join(parts)
    
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://musicbrainz.org/ws/2/release/?query={encoded_query}&fmt=json&limit=10"
    
    try:
        logger.info(f"Searching MusicBrainz with query: {query}")
        resp = requests.get(url, headers=MUSICBRAINZ_HEADERS, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        
        releases = data.get("releases", [])
        results = []
        for r in releases:
            rel_id = r.get("id", "")
            title = r.get("title", "Unknown Album")
            track_count = r.get("track-count", 0)
            date = r.get("date", "Unknown Year")
            country = r.get("country", "Unknown")
            
            # Extract artist credit
            artist_credit = r.get("artist-credit", [])
            artist_name = "Unknown Artist"
            if artist_credit:
                artist_name = "".join([ac.get("name", "") + ac.get("joinphrase", "") for ac in artist_credit]).strip()
            
            # Extract label
            label_info = r.get("label-info-list", [])
            label_name = "Unknown Label"
            if label_info and label_info[0].get("label"):
                label_name = label_info[0]["label"].get("name", "Unknown Label")
                
            results.append({
                "id": rel_id,
                "title": title,
                "artist": artist_name,
                "date": date,
                "track_count": track_count,
                "country": country,
                "label": label_name,
                "cover_url": f"https://coverartarchive.org/release/{rel_id}/front-250"
            })
        return results
    except Exception as e:
        logger.error(f"MusicBrainz search failed: {e}")
        return []

def fetch_musicbrainz_release_tracks(release_id: str) -> List[Dict[str, Any]]:
    """
    Fetches detailed tracklist for a specific MusicBrainz release ID.
    
    Args:
        release_id: MusicBrainz release UUID.
        
    Returns:
        List of track dictionaries containing metadata.
    """
    if not release_id:
        return []
        
    url = f"https://musicbrainz.org/ws/2/release/{release_id}?inc=recordings+artists&fmt=json"
    
    try:
        logger.info(f"Fetching MusicBrainz tracks for release: {release_id}")
        resp = requests.get(url, headers=MUSICBRAINZ_HEADERS, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        
        media_list = data.get("media", [])
        tracks_data = []
        
        for media in media_list:
            for track in media.get("tracks", []):
                title = track.get("title", "Unknown Title")
                num_str = track.get("number", "")
                try:
                    num_val = int(num_str)
                    num_str = f"{num_val:02d}"
                except ValueError:
                    pass
                
                # Try to get length in ms
                length_ms = track.get("length") or track.get("recording", {}).get("length")
                duration_str = ""
                if length_ms:
                    total_sec = length_ms // 1000
                    minutes = total_sec // 60
                    seconds = total_sec % 60
                    duration_str = f"{minutes:02d}:{seconds:02d}"
                
                artist_credit = track.get("artist-credit", [])
                artist_name = ""
                if artist_credit:
                    artist_name = "".join([ac.get("name", "") + ac.get("joinphrase", "") for ac in artist_credit]).strip()
                
                tracks_data.append({
                    "tracknumber": num_str,
                    "title": title,
                    "artist": artist_name,
                    "duration": duration_str
                })
        return tracks_data
    except Exception as e:
        logger.error(f"MusicBrainz track fetch failed for release {release_id}: {e}")
        return []
