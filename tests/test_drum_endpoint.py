import json
import os
from unittest.mock import patch, MagicMock, call
import pytest
import numpy as np
from musictranslator.drum_analysis_service.app import app, SHARED_EXECUTOR
# Import DrumMLA for mocking purposes if needed in tests
from musictranslator.drum_analysis_service.DrumMLA import DrumMLA

@pytest.fixture
def client():
    """Configures the Flask app for testing and provides a test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# Dummy audio file paths for testing
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "test_audio")
if not os.path.exists(TEST_AUDIO_DIR):
    os.makedirs(TEST_AUDIO_DIR)

# Create dummy audio files for testing os.path.exists
@pytest.fixture(scope="module")
def create_dummy_audio_files():
    dummy_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")

    with open(dummy_file, 'w') as f:
        f.write("dummy wav content")

    yield # Yield control to tests

    # Teardown: clean up dummy file
    os.remove(dummy_file)
    # Remove directory after files are gone
    if not os.listdir(TEST_AUDIO_DIR):
        os.rmdir(TEST_AUDIO_DIR)


# Test the health check endpoint
def test_health_check(client):
    response = client.get('/drums/health')
    assert response.status_code == 200
    assert response.json == {"status": "OK", "message": "Drum Analysis service is running"}

# --- Mock Data for drum_analysis functions ---

MOCK_ANALYSIS_RESULT_UNCLASSIFIED = {
    "hits": [
        {
            "onset_time": 0.5,
            "duration": 0.1,
            "relative_volume": 0.123,
            "dominant_frequency": 440.0,
            "spectral_centroid": 500.0,
            "spectral_rolloff": 1500.0,
            "spectral_flux": 0.05,
            "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
        },
        {
            "onset_time": 1.2,
            "duration": 0.08,
            "relative_volume": 0.098,
            "dominant_frequency": 220.0,
            "spectral_centroid": 300.0,
            "spectral_rolloff": 1000.0,
            "spectral_flux": 0.03,
            "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        }
    ],
    "tempo": 120.5
}

# This is what DrumMLA.classify_drum_events would return based on
# MOCK_ANALYSIS_RESULT_UNCLASSIFIED['hits']
# The overall_tempo_bom will be carried through unchanged
MOCK_ANALYSIS_RESULT_CLASSIFIED = {
    "hits": [
        {
            "onset_time": 0.5,
            "duration": 0.1,
            "relative_volume": 0.123,
            "dominant_frequency": 440.0,
            "spectral_centroid": 500.0,
            "spectral_rolloff": 1500.0,
            "spectral_flux": 0.05,
            "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
            "drum_category": "snare_drum", # Example classification
            "category_confidence": 0.95, # Example confidence
            "drum_type": "closed_band",
            "type_confidence": 0.89,
            "qualifier": "rimshot",
            "qualifier_confidence": 0.85
        },
        {
            "onset_time": 1.2,
            "duration": 0.08,
            "relative_volume": 0.098,
            "dominant_frequency": 220.0,
            "spectral_centroid": 300.0,
            "spectral_rolloff": 1000.0,
            "spectral_flux": 0.03,
            "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
            "drum_category": "kick",
            "category_confidence": 0.94,
            "drum_type": "bass", # Example classification
            "type_confidence": 0.90, # Example confidence
            "qualifier": "no_qualifier",
            "qualifier_confidence": 0.0
        }
    ],
    "tempo": 120.5
}

# --- Unit Tests for the /api/analyze_drums endpoint ---

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
@patch('musictranslator.drum_analysis_service.app.drum_mla')
def test_analyze_drums_success(
    mock_drum_mla,
    mock_analyze_audio_concurrently,
    mock_load_audio_from_file,
    client,
    create_dummy_audio_files # Ensure dummy files exist
):
    """
    Tests the successful processing of an audio file and returns correct data.
    """
    # Configure mocks to return expected values
    # load_audio_from_file returns (y, sr) tuple
    mock_y_from_load, mock_sr_from_load = MagicMock(), 22050
    mock_load_audio_from_file.return_value = (mock_y_from_load, mock_sr_from_load)
    mock_analyze_audio_concurrently.return_value = MOCK_ANALYSIS_RESULT_UNCLASSIFIED

    # Configure the DrumMLA mock to return the classified results
    mock_drum_mla.classify_drum_events.return_value = MOCK_ANALYSIS_RESULT_CLASSIFIED['hits']

    # Prepare request data
    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")

    request_data = {
        "drums_path": test_file,
    }

    response = client.post('/api/analyze_drums', json=request_data)

    assert response.status_code == 200
    assert response.json == MOCK_ANALYSIS_RESULT_CLASSIFIED

    # Verify that drum_analysis functions were called correctly
    mock_load_audio_from_file.assert_called_once_with(test_file)
    assert mock_load_audio_from_file.call_count == 1

    mock_analyze_audio_concurrently.assert_called_once_with(
        mock_y_from_load, mock_sr_from_load
    )
    assert mock_analyze_audio_concurrently.call_count == 1

    # Verify that DrumMLA.classify_drum_events was called with
    # the unclassified results
    mock_drum_mla.classify_drum_events.assert_called_once_with(
        MOCK_ANALYSIS_RESULT_UNCLASSIFIED['hits'],
        min_category_confidence=0.7,
        min_type_confidence=0.5,
        min_qualifier_confidence=0.5,
        k=5,
        executor=SHARED_EXECUTOR
    )

@patch('musictranslator.drum_analysis_service.app.os.path.exists', return_value=False)
@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
@patch('musictranslator.drum_analysis_service.app.drum_mla')
def test_analyze_drums_endpoint_invalid_path(
    mock_drum_mla,
    mock_analyze_audio_concurrently,
    mock_load_audio_from_file,
    mock_os_path_exists,
    client
):
    """Do not create dummy files for this test, so os.path.exists will be False"""
    request_data = {
        "drums_path": "/path/to/nonexistent_drum_track.wav"
    }

    response = client.post('/api/analyze_drums', json=request_data)

    assert response.status_code == 400
    assert "error" in response.json
    assert "Drums path does not exist" in response.json['error']

    # Ensure no analysis functions were called
    mock_load_audio_from_file.assert_not_called()
    mock_analyze_audio_concurrently.assert_not_called()
    mock_drum_mla.classify_drum_events.assert_not_called()

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file', side_effect=Exception("Loading error"))
@patch('musictranslator.drum_analysis_service.app.drum_mla')
def test_analyze_drums_endpoint_loading_error(
    mock_drum_mla,
    mock_load_audio_from_file,
    client,
    create_dummy_audio_files
):
    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")
    request_data = {
        "drums_path": test_file
    }

    response = client.post('/api/analyze_drums', json=request_data)
    assert response.status_code == 500
    assert "error" in response.json
    assert "Internal server error during analysis" in response.json['error']
    mock_drum_mla.classify_drum_events.assert_not_called()

def test_analyze_drums_endpoint_invalid_json(client):
    response = client.post('/api/analyze_drums', data="not json data", content_type='text/plain')
    assert response.status_code == 415 # Unsupported Media Type
    assert "Invalid request" in response.json['error']

def test_analyze_drums_endpoint_missing_drums_path(client):
    response = client.post('/api/analyze_drums', json={"other_key": "value"})
    assert response.status_code == 400
    assert "Missing 'drums_path'" in response.json['error']

def test_analyze_drums_endpoint_path_not_string(client):
    """Tests handling of 'drums_path' being a non-string type."""
    response = client.post('/api/analyze_drums', json={"drums_path": 123})
    assert response.status_code == 400
    assert "Invalid 'drums_path': must be a string" in response.json['error']

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
@patch('musictranslator.drum_analysis_service.app.drum_mla')
def test_analyze_drums_no_hits_found(
    mock_drum_mla,
    mock_analyze_audio_concurrently,
    mock_load_audio_from_file,
    client,
    create_dummy_audio_files
):
    """
    Tests the scenario where analyze_audio_concurrently finds no
    drum hits.
    """
    # Make 'y' a MagicMock that has a .shape attribute
    mock_y = MagicMock()
    mock_y.shape = (1000,) # Assign a dummy shape attribute
    mock_load_audio_from_file.return_value = (mock_y, 22050)

    # Explicitly set the return value for the scenario
    mock_analyze_audio_concurrently.return_value = {
        "hits": [],
        "tempo": 85.0
    }

    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")
    request_data = {"drums_path": test_file}

    response = client.post('/api/analyze_drums', json=request_data)

    assert response.status_code == 200
    assert response.json == {
        "hits": [],
        "tempo": 85.0
    }

    mock_load_audio_from_file.assert_called_once_with(test_file)
    mock_analyze_audio_concurrently.assert_called_once_with(
        mock_y, 22050
    )
    mock_drum_mla.classify_drum_events.assert_not_called()

@patch('musictranslator.drum_analysis_service.app.drum_mla', new=None)
@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
def test_analyze_drums_mla_not_initialized(
    mock_analyze_audio_concurrently,
    mock_load_audio_from_file,
    client,
    create_dummy_audio_files
):
    """
    Tests the scenario where DrumMLA is not initialized during app
    startup, and the service should return unclassified hits with
    'other/unknown' and 0 confidence.
    """
    # Capture the MagicMock instance returned by mock_load_audio_from_file\
    mock_y_audio = MagicMock()
    mock_load_audio_from_file.return_value = (mock_y_audio, 22050)

    mock_analyze_audio_concurrently.return_value = MOCK_ANALYSIS_RESULT_UNCLASSIFIED

    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")
    request_data = {"drums_path": test_file}

    response = client.post(
        '/api/analyze_drums', json=request_data
    )

    assert response.status_code == 200
    # Expect original features + 'other/unknown', drum_type and 0.0 confidence
    expected_drum_hits = []
    for hit in MOCK_ANALYSIS_RESULT_UNCLASSIFIED["hits"]:
        classified_hit = hit.copy()
        classified_hit['drum_category'] = 'other'
        classified_hit['category_confidence'] = 0.0
        classified_hit['drum_type'] = 'unknown'
        classified_hit['type_confidence'] = 0.0
        classified_hit['qualifier'] = 'no_qualifier'
        classified_hit['qualifier_confidence'] = 0.0

        expected_drum_hits.append(classified_hit)

    expected_response = {
        "hits": expected_drum_hits,
        "tempo": MOCK_ANALYSIS_RESULT_UNCLASSIFIED["tempo"]
    }

    assert response.json == expected_response

    mock_load_audio_from_file.assert_called_once_with(test_file)
    mock_analyze_audio_concurrently.assert_called_once_with(
        mock_y_audio, 22050
    )

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
@patch('musictranslator.drum_analysis_service.app.drum_mla')
def test_analyze_drums_endpoint_empty_audio_data(
    mock_drum_mla,
    mock_analyze_audio_concurrently,
    mock_load_audio_from_file,
    client,
    create_dummy_audio_files
):
    """
    Tests the scenario where load_audio_from_file returns an empty
    audio array.
    """
    # Simulate an empty audio array returned by librosa.load
    mock_load_audio_from_file.return_value = (np.array([], dtype=np.float32), 22050)

    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")
    request_data = {"drums_path": test_file}

    response = client.post('/api/analyze_drums', json=request_data)

    assert response.status_code == 422 # unprocessable entity
    assert "error" in response.json
    assert "No audio data found in the provided file." in response.json['error']

    mock_load_audio_from_file.assert_called_once_with(test_file)
    mock_analyze_audio_concurrently.assert_not_called()
    mock_drum_mla.classify_drum_events.assert_not_called()
