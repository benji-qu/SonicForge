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
