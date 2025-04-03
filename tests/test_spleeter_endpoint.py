import io
import os
import shutil
import tempfile
import pytest
import musictranslator
from musictranslator import spleeter_wrapper
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import patch
from musictranslator.spleeter_wrapper import app

@pytest.fixture
def client():
    """
    Pytest fixture to create a test client for the Flask app
    """
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_separate_endpoint_post_integration_with_files(client: FlaskClient, tmp_path):
    """
    Integration test using actual audio data and checking Spleeter output files
    """
    audio_file_path = "data/audio/BloodCalcification-NoMore.wav"
    with open(audio_file_path, 'rb') as audio_file_obj:
        audio_data = audio_file_obj.read()
    audio_file = (io.BytesIO(audio_data), 'BloodCalcification-NoMore.wav')

    data = {
        'audio': audio_file,
    }

    # Use a temporary directory for Spleeter output
    temp_output_dir = tmp_path / "spleeter_output"
    temp_output_dir.mkdir()
    response = client.post(
            '/separate',
            data=data,
            content_type='multipart/form-data'
        )

    assert response.status_code == 200
    response_json = response.get_json()
    assert "vocals_stem_path" in response_json
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    expected_vocals_path = os.path.join(project_root, "data", "spleeter_output", "BloodCalcification-NoMore", "vocals.wav")
    assert expected_vocals_path in response_json["vocals_stem_path"]

    # Ensure the correct files were created
    expected_output_dir = os.path.join(project_root, "data", "spleeter_output", "BloodCalcification-NoMore")
    expected_files = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]

    for filename in expected_files:
        expected_file_path = os.path.join(expected_output_dir, filename)
        assert os.path.exists(expected_file_path)

def test_separate_endpoint_post_missing_audio(client: FlaskClient):
    """
    Test /separate endpoint with a missing audio file
    """
    response = client.post(
        '/separate',
        data={},
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Audio file missing."}

def test_separate_endpoint_post_no_filename(client: FlaskClient):
    """
    Test /separate endpoint with no filename on the audio file.
    """
    audio_data = b"dummy audio data"
    audio_file = (io.BytesIO(audio_data), '')

    data = {
        'audio': audio_file,
    }

    response = client.post(
        '/separate',
        data=data,
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "No selected file."}

def test_separate_endpoint_post_spleeter_error(client: FlaskClient):
    """
    Test /separate endpoint when Spleeter returns an error
    """
    audio_file_path = "data/audio/BloodCalcification-NoMore.wav"
    with open(audio_file_path, 'rb') as audio_file_obj:
        audio_data = audio_file_obj.read()
    audio_file = (io.BytesIO(audio_data), 'BloodCalcification-NoMore.wav')

    data = {
        'audio': audio_file,
    }

    with patch('musictranslator.spleeter_wrapper.run_spleeter_docker') as mock_run_spleeter_docker, \
         patch('os.path.join') as mock_os_path_join, \
         patch('os.path.exists') as mock_os_path_exists:

        mock_run_spleeter_docker.return_value = (1, "", "Spleeter error message")
        mock_os_path_join.side_effect = lambda *args: "/".join(args)
        mock_os_path_exists.return_value = True

        # Mock the FileStorage object to have a proper filename and mimetype
        class MockFileStorage(io.BytesIO):
            filename = 'BloodCalcification-NoMore.wav'
            mimetype = 'audio/wav'

        data['audio'] = (MockFileStorage(audio_data), 'BloodCalcification-NoMore.wav')

        response = client.post(
            '/separate',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 500
        assert response.get_json() == {"error": "Spleeter error: Spleeter error message"}

def test_separate_endpoint_post_filenotfound(client:FlaskClient):
    """
    Test /separate endpoint when file is not found
    """
    audio_file_path = ""

    data = {
        'audio':audio_file_path,
    }

    with patch('musictranslator.spleeter_wrapper.run_spleeter_docker') as mock_run_spleeter_docker:
        mock_run_spleeter_docker.return_value = (1, "", "file not found")

        response = client.post(
            '/separate',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Audio file missing.'}
