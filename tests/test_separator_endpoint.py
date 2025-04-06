import json
import os
import logging
import pytest
import requests
from musictranslator import separator_wrapper

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Assuming INPUT_DIR and OUTPUT_DIR are defined in separator_wrapper.py
INPUT_DIR = separator_wrapper.INPUT_DIR
OUTPUT_DIR = separator_wrapper.OUTPUT_DIR

@pytest.fixture
def real_audio_file():
    """Fixture to provide a real audio file for testing"""
    file_path = "data/audio/BloodCalcification-NoMore.wav" # Use a real audio file
    yield file_path

def test_separate_endpoint_post_integration_with_files(real_audio_file):
    """
    End-to-end test using actual audio data and checking Demucs output files
    """
    url = f"http://localhost:22227/separate"

    data = {"audio_filename": os.path.basename(real_audio_file)}
    headers = {'Content-type': 'application/json'}

    response = requests.post(url, data=json.dumps(data), headers=headers)

    assert response.status_code == 200
    response_json = response.json()

    output_dir = os.path.join(
        OUTPUT_DIR,
        "htdemucs_6s",
        os.path.splitext(os.path.basename(real_audio_file))[0],
    )

    for filename in os.listdir(output_dir):
        if filename.endswith(".wav"):
            expected_file_path = os.path.join(output_dir, filename)
            assert response_json[filename.split(".")[0]] == expected_file_path
            assert os.path.exists(expected_file_path)
            os.remove(expected_file_path)
    os.rmdir(output_dir)

def test_separate_endpoint_post_missing_filename():
    """
    Test /separate endpoint with no filename on the audio file.
    """
    url = f"http://localhost:22227/separate"

    response = requests.post(url, data=json.dumps({}), headers={'Content-Type': 'application/json'})

    assert response.status_code == 400
    assert response.json() == {"error": "Audio filename missing."}

def test_separate_endpoint_post_demucs_error(real_audio_file, monkeypatch):
    """
    Test /separate endpoint when Spleeter returns an error
    """
    url = f"http://localhost:22227/separate"

    data = {"audio_filename": os.path.basename(real_audio_file)}
    headers = {'Content-Type': 'application/json'}

    def mock_run_demucs(audio_file_path):
        raise RuntimeError("Demucs processing error")

    monkeypatch.setattr("musictranslator.separator_wrapper.run_demucs", mock_run_demucs)

    response = requests.post(url, data=json.dumps(data), headers=headers)

    assert response.status_code == 200 # Demucs executes even if there is an error
    response_json = response.json()

    output_dir = os.path.join(
        OUTPUT_DIR,
        "htdemucs_6s",
        os.path.splitext(os.path.basename(real_audio_file))[0],
    )

    for filename in os.listdir(output_dir):
        if filename.endswith(".wav"):
            expected_file_path = os.path.join(output_dir, filename)
            assert response_json[filename.split(".")[0]] == expected_file_path
            assert os.path.exists(expected_file_path)
            os.remove(expected_file_path)
    os.rmdir(output_dir)

def test_separate_endpoint_post_filenotfound():
    """
    Test /separate endpoint when file is not found
    """
    url = f"http://localhost:22227/separate"

    data = {"audio_filename": "nonexistent_file.wav"}
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, data=json.dumps(data), headers=headers)

    assert response.status_code == 404
    assert response.json() == {'error': 'Audio file not found.'}
