import pytest
from unittest.mock import patch
from musictranslator.volume_service.app import app

@pytest.fixture
def client():
    """A test client for the app."""
    return app.test_client()

@patch('musictranslator.volume_service.app.calculate_rms_for_file')
def test_analyze_rms_endpoint_success(mock_calculate_rms, client):
    """Test the /api/analyze_rms endpoint for successful case."""
    # We mock the logic function because we already unit-tested it.
    # Here, we only test that the API layer calls it correctly.
    mock_calculate_rms.return_value = [[0.0, 0.5], [0.1, 0.6]]

    payload = {
        "audio_paths": {
            "song": "/path/to/song.wav",
            "bass": "/path/to/bass.wav",
            "drums": "/path/to/drums.wav",
            "guitar": "/path/to/guitar.wav",
            "other": "/path/to/other.wav",
            "piano": "/path/to/piano.wav",
            "vocals": "/path/to/vocals.wav"
        }
    }
    response = client.post("/api/analyze_rms", json=payload)

    # Assertions
    assert response.status_code == 200
    data = response.get_json()

    assert "overall_rms" in data
    assert "instruments" in data

    assert "bass" in data["instruments"]
    assert "drums" in data["instruments"]
    assert "guitar" in data["instruments"]
    assert "other" in data["instruments"]
    assert "piano" in data["instruments"]
    assert "vocals" in data["instruments"]

    assert data["overall_rms"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["bass"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["drums"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["guitar"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["other"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["piano"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]
    assert data["instruments"]["vocals"]["rms_values"] == [[0.0, 0.5], [0.1, 0.6]]

    # Check that our logic was called for each file
    assert mock_calculate_rms.call_count == 7

def test_analyze_rms_endpoint_bad_request(client):
    """Test the endpoint returns 400 if payload is missing or malformed."""
    response = client.post("/api/analyze_rms", json={"wrong_key": "value"})
    assert response.status_code == 400
