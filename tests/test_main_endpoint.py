import json
import os
import io
import unittest
import pytest
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import patch, ANY
from musictranslator.main import app

@pytest.fixture
def client():
    """
    Pytest fixture to create a test client for the Flask app
    The ensures we're testing against a clean app context
    """
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client # provide the client to the tests

def load_test_file(filepath):
    """Helper function to load test file data"""
    try:
        with open(filepath, 'rb') as f:
            return io.BytesIO(f.read())
    except FileNotFoundError as e:
        pytest.fail(f"Test file not found: {e}")

def load_json_file(filepath):
    """Helper function to load JSON test data"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError as e:
        pytest.fail(f"JSON test file not found: {e}")
    except json.JSONDecodeError as e:
        pytest.fail(f"Error decoding JSON from {filepath}: {e}")

@patch('musictranslator.main.split_audio')
@patch('musictranslator.main.align_lyrics')
@patch('musictranslator.main.map_transcript')
def test_translate_endpoint_post(mock_map_transcript, mock_align_lyrics, mock_split_audio, client: FlaskClient):
    """
    Test the /translate endpoint with a POST request,
    mocking the internal calls to split_audio and align_lyrics,
    using real test data
    """
    audio_file_path = "data/audio/BloodCalcification-NoMore.wav"
    lyrics_file_path = "data/lyrics/BloodCalcification-NoMore.txt"
    separated_vocals_path = "data/separator_output/htdemucs_6s/BloodCalcification-NoMore/vocals.wav"
    aligned_lyrics_path = "data/aligned/BloodCalcification-NoMore.json"
    expected_mapped_results_path = "data/mapped_results/BloodCalcification-NoMore.json"

    audio_data = load_test_file(audio_file_path)
    lyrics_data = load_test_file(lyrics_file_path)
    expected_mapped_results = load_json_file(expected_mapped_results_path)

    audio_file = (audio_data, os.path.basename(audio_file_path))
    lyrics_file = (lyrics_data, os.path.basename(lyrics_file_path))

    data = {
        'audio': audio_file,
        'lyrics': lyrics_file,
    }

    # Mock the response from split_audio
    mock_split_audio.return_value = {
        'vocals': separated_vocals_path,
        'drums': 'data/separator_output/htdemucs_6s/BloodCalcification-NoMore/drums.wav',
        'bass': 'data/separator_output/htdemucs_6s/BloodCalcification-NoMore/bass.wav',
        'guitar': 'data/separator_output/htdemucs_6s/BloodCalcification-NoMore/guitar.wav',
        'other': 'data/separator_output/htdemucs_6s/BloodCalcification-NoMore/other.wav',
        'piano': 'data/separator_output/htdemucs_6s/BloodCalcification-NoMore/piano.wav'
    }

    # Mock the response from align_lyrics
    mock_align_lyrics.return_value = aligned_lyrics_path

    # Mock the response from map_transcript
    mock_map_transcript.return_value = expected_mapped_results

    response = client.post(
        '/translate',
        data=data,
        content_type='multipart/form-data'
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json == expected_mapped_results

    # Assert the mocked funtions wer called correctly
    mock_split_audio.assert_called_once_with(ANY)
    mock_align_lyrics.assert_called_once_with(separated_vocals_path, ANY)
    mock_map_transcript.assert_called_once_with(aligned_lyrics_path, ANY)

def test_translate_endpoint_missing_audio(client: FlaskClient):
    """
    Test /translate endpoint with missing audio file
    """
    lyrics_file_path = "data/lyrics/BloodCalcification-NoMore.txt"
    lyrics_data = load_test_file(lyrics_file_path)
    lyrics_file = (lyrics_data, os.path.basename(lyrics_file_path))
    data = {'lyrics': lyrics_file}
    response = client.post(
        '/translate',
        data=data,
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing audio file."}

def test_translate_endpoint_missing_lyrics(client: FlaskClient):
    """
    Test /translate endpoint with missing lyrics file
    """
    audio_file_path = "data/audio/BloodCalcification-NoMore.wav"
    audio_data = load_test_file(audio_file_path)
    audio_file = (audio_data, os.path.basename(audio_file_path))
    data = {'audio': audio_file}
    response = client.post(
            '/translate',
            data=data,
            content_type='multipart/form-data'
        )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing lyrics file."}

