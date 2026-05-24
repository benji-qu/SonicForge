import pytest
from unittest.mock import patch, mock_open
from core.cue_parser import parse_cue_time, parse_cue_sheet

def test_parse_cue_time():
    assert parse_cue_time("00:00:00") == 0.0
    assert parse_cue_time("01:30:00") == 90.0
    assert parse_cue_time("02:30:15") == 150.2  # 15 frames / 75 = 0.2s
    assert parse_cue_time("00:00:74") == 74 / 75.0
    assert parse_cue_time("invalid") == 0.0

def test_parse_cue_sheet_success():
    mock_cue_data = """
    PERFORMER "Adele"
    TITLE "21"
    REM DATE 2011
    FILE "Adele - 21.flac" WAVE
      TRACK 01 AUDIO
        TITLE "Intro"
        PERFORMER "Adele"
        INDEX 01 00:00:00
      TRACK 02 AUDIO
        TITLE "Rolling in the Deep"
        INDEX 01 02:30:15
      TRACK 03 AUDIO
        TITLE "Rumour Has It"
        INDEX 01 06:15:00
    """
    
    with patch("builtins.open", mock_open(read_data=mock_cue_data)):
        result = parse_cue_sheet("dummy.cue")
        
    assert result['metadata']['artist'] == "Adele"
    assert result['metadata']['title'] == "21"
    assert result['metadata']['date'] == "2011"
    assert result['metadata']['file'] == "Adele - 21.flac"
    
    assert len(result['tracks']) == 3
    
    t1 = result['tracks'][0]
    assert t1['number'] == "01"
    assert t1['title'] == "Intro"
    assert t1['artist'] == "Adele"
    assert t1['start_time'] == 0.0
    assert t1['end_time'] == 150.2
    
    t2 = result['tracks'][1]
    assert t2['number'] == "02"
    assert t2['title'] == "Rolling in the Deep"
    assert t2['artist'] == "Adele"  # Inherited from global performer
    assert t2['start_time'] == 150.2
    assert t2['end_time'] == 375.0
    
    t3 = result['tracks'][2]
    assert t3['number'] == "03"
    assert t3['title'] == "Rumour Has It"
    assert t3['start_time'] == 375.0
    assert t3['end_time'] is None
