import pytest
from unittest.mock import patch, MagicMock
import os

from core.transcoder import transcode_file, inject_metadata

@patch('core.transcoder.subprocess.run')
@patch('core.transcoder.inject_metadata')
@patch('core.transcoder.os.makedirs')
def test_transcode_file_mp3(mock_makedirs, mock_inject, mock_run):
    metadata = {'title': 'Song A', 'artist': 'Artist A'}
    
    output_path = transcode_file(
        input_path='/src/song.flac',
        output_dir='/dest',
        target_format='mp3',
        quality='320kbps',
        metadata=metadata,
        cover_art=b'fakeimage'
    )
    
    # Verify directory was created
    mock_makedirs.assert_called_once_with('/dest', exist_ok=True)
    
    # Verify FFmpeg was invoked with correct MP3 arguments
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert 'ffmpeg' in args
    assert '-i' in args
    assert '/src/song.flac' in args
    assert '-c:a' in args
    assert 'libmp3lame' in args
    assert '-b:a' in args
    assert '320k' in args
    assert args[-1] == os.path.join('/dest', 'song.mp3')
    
    # Verify metadata injector was called
    mock_inject.assert_called_once_with(
        os.path.join('/dest', 'song.mp3'),
        'mp3',
        metadata,
        b'fakeimage'
    )
    assert output_path == os.path.join('/dest', 'song.mp3')


@patch('core.transcoder.subprocess.run')
@patch('core.transcoder.inject_metadata')
@patch('core.transcoder.os.makedirs')
def test_transcode_file_ogg(mock_makedirs, mock_inject, mock_run):
    metadata = {'title': 'Song B'}
    
    output_path = transcode_file(
        input_path='/src/song.flac',
        output_dir='/dest',
        target_format='ogg',
        quality='q8',
        metadata=metadata,
        cover_art=None
    )
    
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert 'libvorbis' in args
    assert '-q:a' in args
    assert '8' in args
    assert args[-1] == os.path.join('/dest', 'song.ogg')


@patch('core.transcoder.subprocess.run')
@patch('core.transcoder.inject_metadata')
@patch('core.transcoder.os.makedirs')
def test_transcode_file_wav(mock_makedirs, mock_inject, mock_run):
    output_path = transcode_file(
        input_path='/src/song.flac',
        output_dir='/dest',
        target_format='wav',
        quality='lossless',
        metadata={},
        cover_art=None
    )
    
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert 'pcm_s16le' in args
    assert args[-1] == os.path.join('/dest', 'song.wav')


@patch('core.transcoder.save_metadata_to_flac')
def test_inject_metadata_flac(mock_save_flac):
    metadata = {'title': 'Test Title', 'artist': 'Test Artist', 'cover_art': b'ignored'}
    inject_metadata('/dest/song.flac', 'flac', metadata, b'fake_art')
    
    # Verify FLAC tags write uses the core/metadata helper
    mock_save_flac.assert_called_once_with(
        '/dest/song.flac',
        {'title': 'Test Title', 'artist': 'Test Artist'},
        b'fake_art'
    )


@patch('core.transcoder.write_metadata_to_ogg')
def test_inject_metadata_ogg(mock_save_ogg):
    metadata = {'title': 'Test Title', 'cover_art': b'ignored'}
    inject_metadata('/dest/song.ogg', 'ogg', metadata, b'fake_art')
    
    mock_save_ogg.assert_called_once_with(
        '/dest/song.ogg',
        {'title': 'Test Title'},
        b'fake_art'
    )


@patch('core.transcoder.ID3')
@patch('core.transcoder.APIC')
@patch('core.transcoder.MP3')
@patch('core.transcoder.EasyID3')
def test_inject_metadata_mp3(mock_easy_id3, mock_mp3, mock_apic, mock_id3):
    # Setup mocks
    mock_audio_easy = MagicMock()
    mock_easy_id3.return_value = mock_audio_easy
    
    mock_audio_mp3 = MagicMock()
    mock_audio_mp3.tags = MagicMock()
    mock_mp3.return_value = mock_audio_mp3
    
    metadata = {'title': 'MP3 Title', 'artist': 'MP3 Artist', 'genre': 'Metal'}
    inject_metadata('/dest/song.mp3', 'mp3', metadata, b'mp3_art')
    
    # Check that EasyID3 keys were mapped and set
    mock_audio_easy.__setitem__.assert_any_call('title', 'MP3 Title')
    mock_audio_easy.__setitem__.assert_any_call('artist', 'MP3 Artist')
    mock_audio_easy.__setitem__.assert_any_call('genre', 'Metal')
    mock_audio_easy.save.assert_called_once()
    
    # Check that APIC cover art was appended using standard MP3 classes
    mock_mp3.assert_called_once_with('/dest/song.mp3', ID3=mock_id3)
    mock_apic.assert_called_once_with(
        encoding=3,
        mime='image/jpeg',
        type=3,
        desc='Cover',
        data=b'mp3_art'
    )
    mock_audio_mp3.tags.add.assert_called_once()
    mock_audio_mp3.save.assert_called_once()
