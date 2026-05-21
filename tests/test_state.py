import pytest
from core.state import AppState

def test_app_state_initialization():
    state = AppState()
    assert state.current_files == []
    assert len(state.selected_file_indices) == 0
    assert state.selected_cover_art_bytes is None
    assert state.shift_pressed is False
    assert state.ctrl_pressed is False
    assert state.last_selected_index is None

def test_app_state_load_files():
    state = AppState()
    files = [{'path': 'file1.flac', 'metadata': {}}, {'path': 'file2.flac', 'metadata': {}}]
    state.load_files(files)
    assert len(state.current_files) == 2
    assert len(state.selected_file_indices) == 0
    assert state.last_selected_index is None

def test_app_state_set_selection():
    state = AppState()
    state.set_selection([0, 1])
    assert 0 in state.selected_file_indices
    assert 1 in state.selected_file_indices
    assert len(state.selected_file_indices) == 2

def test_app_state_listener_notification():
    state = AppState()
    called = False
    
    def listener():
        nonlocal called
        called = True
        
    state.add_listener(listener)
    state.notify()
    assert called is True
