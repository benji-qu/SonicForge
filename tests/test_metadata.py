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


@patch('core.metadata.mutagen.File')
def test_get_metadata_mp4_and_id3_normalization(mock_mutagen_file):
    mock_audio = MagicMock()
    mock_audio.items.return_value = [
        ('\xa9nam', ['M4A Song']),
        ('\xa9ART', ['M4A Artist']),
        ('\xa9alb', ['M4A Album']),
        ('\xa9day', ['2025']),
        ('trkn', [(4, 10)]),
        ('\xa9gen', ['Synthwave']),
    ]
    mock_audio.get.return_value = [b'fake_m4a_cover']
    mock_audio.tags = {'covr': [b'fake_m4a_cover']}
    mock_mutagen_file.return_value = mock_audio

    meta = get_metadata('track.m4a')
    assert meta['title'] == 'M4A Song'
    assert meta['artist'] == 'M4A Artist'
    assert meta['album'] == 'M4A Album'
    assert meta['date'] == '2025'
    assert meta['tracknumber'] == '4/10'
    assert meta['genre'] == 'Synthwave'
    assert meta['cover_art'] == b'fake_m4a_cover'


@patch('core.metadata.write_metadata_to_mp3', return_value=True)
@patch('core.metadata.write_metadata_to_m4a', return_value=True)
@patch('core.metadata.write_metadata_to_ogg', return_value=True)
@patch('core.metadata.save_metadata_to_flac', return_value=True)
def test_save_metadata_dispatch(mock_flac, mock_ogg, mock_m4a, mock_mp3):
    from core.metadata import save_metadata

    tags = {'title': 'Song'}
    assert save_metadata('a.flac', tags, b'img') is True
    mock_flac.assert_called_once_with('a.flac', tags, b'img')

    assert save_metadata('b.ogg', tags, b'img') is True
    mock_ogg.assert_called_once_with('b.ogg', tags, b'img')

    assert save_metadata('c.m4a', tags, b'img') is True
    mock_m4a.assert_called_once_with('c.m4a', tags, b'img')

    assert save_metadata('d.mp3', tags, b'img') is True
    mock_mp3.assert_called_once_with('d.mp3', tags, b'img')


