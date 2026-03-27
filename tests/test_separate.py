"""
Test suite for the separate.py module
"""
import os
import unittest
from unittest.mock import patch, mock_open
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing import separate
from musictranslator.musicprocessing.separate import split_audio

class TestSeparate(unittest.TestCase):
    """
    Main function
    """

    @patch('requests.post')
    def test_split_audio_success(self, mock_post):
        """
        Test successful communication with the Spleeter service
        Verifies that the function returns True and makes the correct request
        """
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None # Mock raise for status
        mock_post.return_value.json.return_value = {
            "vocals": "/path/to/test_audio_vocals.wav",
            "drums": "/path/to/test_audio_drums.wav",
            "bass": "/path/to/test_audio_bass.wav",
            "guitar": "/path/to/test_audio_guitar.wav"
        }

        input_file = "test_audio.wav"
        expected_data = {"audio_filename": os.path.basename(input_file)}
        expected_headers = {'Content-Type': 'application/json'}
        expected_response = {
            "vocals": "/path/to/test_audio_vocals.wav",
            "drums": "/path/to/test_audio_drums.wav",
            "bass": "/path/to/test_audio_bass.wav",
            "guitar": "/path/to/test_audio_guitar.wav"
        }

        result = separate.split_audio(input_file)
        self.assertEqual(result, expected_response)
        mock_post.assert_called_once_with(
            separate.SEPARATOR_SERVICE_URL,
            json=expected_data,
            headers=expected_headers,
            timeout=1200
        )

    @patch('requests.post')
    def test_split_audio_request_exception(self, mock_post):
        """
        Test handling of a request exception
        Verifies that the function returns the correct error dictionary
        """
        exception = requests.exceptions.RequestException("Connection error")
        mock_post.side_effect = exception
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertEqual({'error': f'Demucs Error: {exception}'}, result)

    @patch('requests.post')
    def test_split_audio_http_error(self, mock_post):
        """
        Test handling of an HTTP error response
        Verifies that the function returns False
        """
        exception = requests.exceptions.HTTPError("500 Internal Server Error")
        mock_post.side_effect = exception
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertEqual({'error': f'Demucs HTTP Error: {exception}'}, result)

    @patch('requests.post')
    def test_split_audio_general_exception(self, mock_post):
        """
        Test handling of a general exception
        Verifies that the function returns False
        """
        exception = ValueError("Some value error")
        mock_post.side_effect = exception
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertEqual({'error': f'Demucs Error: {exception}'}, result)
