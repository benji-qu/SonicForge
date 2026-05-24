import pytest
from unittest.mock import patch, MagicMock
from core.metadata import get_metadata

@patch('core.metadata.mutagen.File')
def test_get_metadata_success(mock_mutagen_file):
    # Mocking a mutagen audio object
    mock_audio = MagicMock()
    # Provide a dictionary-like .items() method
    mock_audio.items.return_value = [('artist', ['Test Artist']), ('album', 'Test Album')]
    mock_mutagen_file.return_value = mock_audio
    
    metadata = get_metadata('dummy.flac')
    
    assert metadata['artist'] == 'Test Artist'
    assert metadata['album'] == 'Test Album'
    assert metadata['cover_art'] is None

@patch('core.metadata.mutagen.File')
def test_get_metadata_unsupported_file(mock_mutagen_file):
    mock_mutagen_file.return_value = None
    
    metadata = get_metadata('unsupported.xyz')
    assert metadata == {}


def test_generate_filename_standard():
    from core.metadata import generate_filename
    meta = {'tracknumber': '3', 'title': 'My Track'}
    new_name = generate_filename('{track:02d} - {title}', meta, '/path/to/song.flac')
    assert new_name == '03 - My Track.flac'


def test_generate_filename_missing_tags():
    from core.metadata import generate_filename
    meta = {'title': 'My Track'}  # Artist missing
    new_name = generate_filename('{artist} - {title}', meta, '/path/to/song.flac')
    assert new_name == 'Unknown Artist - My Track.flac'


def test_generate_filename_with_total_count():
    from core.metadata import generate_filename
    meta = {'tracknumber': '05/12', 'title': 'Great Song'}
    new_name = generate_filename('{track:02d} - {title}', meta, '/path/to/song.flac')
    assert new_name == '05 - Great Song.flac'


def test_generate_filename_invalid_chars():
    from core.metadata import generate_filename
    meta = {'artist': 'AC/DC', 'title': 'Who/What?'}
    new_name = generate_filename('{artist} - {title}', meta, '/path/to/song.flac')
    # Slashes and question marks replaced by underscores, duplicates consolidated
    assert new_name == 'AC_DC - Who_What_.flac'

