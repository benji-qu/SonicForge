import pytest
from unittest.mock import patch, MagicMock
from core.api_client import fetch_itunes_artwork, fetch_deezer_artwork

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
