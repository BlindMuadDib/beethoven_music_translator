import json
import os
from unittest.mock import patch, MagicMock
import pytest
from musictranslator.drum_analysis_service.app import app

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

MOCK_ANALYSIS_RESULT = [
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
]

# --- Unit Tests for the /api/analyze_drums endpoint ---

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
def test_analyze_drums_success(
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
    mock_load_audio_from_file.return_value = (MagicMock(), 22050)
    mock_analyze_audio_concurrently.return_value = MOCK_ANALYSIS_RESULT

    # Prepare request data
    test_file = os.path.join(TEST_AUDIO_DIR, "drum_track.wav")

    request_data = {
        "drums_path": test_file,
    }

    response = client.post('/api/analyze_drums', json=request_data)

    assert response.status_code == 200
    assert response.json == MOCK_ANALYSIS_RESULT

    # Verify that drum_analysis functions were called correctly
    mock_load_audio_from_file.assert_called_once_with(test_file)
    assert mock_load_audio_from_file.call_count == 1

    # We mocked load_audio_from_file to return a MagicMock for y and a literal for sr
    # So analyze_audio_concurrently should be called with those
    mock_analyze_audio_concurrently.assert_any_call(mock_load_audio_from_file.return_value[0], mock_load_audio_from_file.return_value[1])
    assert mock_analyze_audio_concurrently.call_count == 1

@patch('musictranslator.drum_analysis_service.app.os.path.exists', return_value=False)
@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file')
@patch('musictranslator.drum_analysis_service.drum_analysis.analyze_audio_concurrently')
def test_analyze_drums_endpoint_invalid_path(
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

@patch('musictranslator.drum_analysis_service.drum_analysis.load_audio_from_file', side_effect=Exception("Loading error"))
def test_analyze_drums_endpoint_loading_error(
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
