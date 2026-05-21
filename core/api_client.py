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
