import pytest
from unittest.mock import patch, MagicMock
from core.api_client import (
    fetch_itunes_artwork,
    fetch_deezer_artwork,
    search_musicbrainz_releases,
    fetch_musicbrainz_release_tracks
)

@patch('core.api_client.requests.get')
def test_fetch_itunes_artwork_success(mock_get):
    # Mocking successful iTunes response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'results': [{
            'collectionName': 'Test Album',
            'artworkUrl100': 'http://example.com/100x100bb.jpg'
        }]
    }
    mock_get.return_value = mock_response

    results = fetch_itunes_artwork('Test Artist', 'Test Album')
    assert len(results) == 1
    assert results[0]['source'] == 'iTunes'
    assert results[0]['album_name'] == 'Test Album'
    assert results[0]['high_res_url'] == 'http://example.com/600x600bb.jpg'

@patch('core.api_client.requests.get')
def test_fetch_deezer_artwork_success(mock_get):
    # Mocking successful Deezer response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'data': [{
            'title': 'Deezer Album',
            'cover_medium': 'http://example.com/medium.jpg',
            'cover_xl': 'http://example.com/xl.jpg'
        }]
    }
    mock_get.return_value = mock_response

    results = fetch_deezer_artwork('Test Artist', 'Deezer Album')
    assert len(results) == 1
    assert results[0]['source'] == 'Deezer'
    assert results[0]['album_name'] == 'Deezer Album'
    assert results[0]['high_res_url'] == 'http://example.com/xl.jpg'

def test_fetch_itunes_artwork_empty_query():
    assert fetch_itunes_artwork('', '') == []

def test_fetch_deezer_artwork_empty_query():
    assert fetch_deezer_artwork('', '') == []


# ── MusicBrainz API Mock Tests ────────────────────────────────────────────────────

@patch('core.api_client.requests.get')
def test_search_musicbrainz_releases_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'releases': [{
            'id': 'test-uuid',
            'title': 'MB Album',
            'track-count': 12,
            'date': '2024-05-20',
            'country': 'US',
            'artist-credit': [{'name': 'MB Artist', 'joinphrase': ''}],
            'label-info-list': [{'label': {'name': 'MB Label'}}]
        }]
    }
    mock_get.return_value = mock_response

    results = search_musicbrainz_releases('MB Artist', 'MB Album')
    assert len(results) == 1
    assert results[0]['id'] == 'test-uuid'
    assert results[0]['title'] == 'MB Album'
    assert results[0]['artist'] == 'MB Artist'
    assert results[0]['date'] == '2024-05-20'
    assert results[0]['track_count'] == 12
    assert results[0]['country'] == 'US'
    assert results[0]['label'] == 'MB Label'
    assert results[0]['cover_url'] == 'https://coverartarchive.org/release/test-uuid/front-250'

@patch('core.api_client.requests.get')
def test_fetch_musicbrainz_release_tracks_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'media': [{
            'tracks': [
                {
                    'title': 'Track One',
                    'number': '1',
                    'length': 180000,
                    'artist-credit': [{'name': 'MB Artist', 'joinphrase': ''}]
                },
                {
                    'title': 'Track Two',
                    'number': '2',
                    'length': 245000,
                    'artist-credit': [{'name': 'MB Artist 2', 'joinphrase': ''}]
                }
            ]
        }]
    }
    mock_get.return_value = mock_response

    results = fetch_musicbrainz_release_tracks('test-uuid')
    assert len(results) == 2
    assert results[0]['tracknumber'] == '01'
    assert results[0]['title'] == 'Track One'
    assert results[0]['artist'] == 'MB Artist'
    assert results[0]['duration'] == '03:00'
    
    assert results[1]['tracknumber'] == '02'
    assert results[1]['title'] == 'Track Two'
    assert results[1]['artist'] == 'MB Artist 2'
    assert results[1]['duration'] == '04:05'

def test_search_musicbrainz_releases_empty():
    assert search_musicbrainz_releases('', '') == []

def test_fetch_musicbrainz_release_tracks_empty():
    assert fetch_musicbrainz_release_tracks('') == []

