"""
Test suite for the separate.py module
"""
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

        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertTrue(result)
            mock_post.assert_called_once_with(separate.SPLEETER_SERVICE_URL, files={'audio': mock_post.call_args[1]['files']['audio']}, timeout=10)

    @patch('requests.post')
    def test_split_audio_request_exception(self, mock_post):
        """
        Test handling of a request exception
        Verifies that the function returns False
        """
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertFalse(result)

    @patch('requests.post')
    def test_split_audio_http_error(self, mock_post):
        """
        Test handling of an HTTP error response
        Verifies that the function returns False
        """
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Internal Server Error")
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertFalse(result)

    @patch('requests.post')
    def test_split_audio_general_exception(self, mock_post):
        """
        Test handling of a general exception
        Verifies that the function returns False
        """
        mock_post.side_effect = ValueError("Some value error")
        with patch("builtins.open", mock_open(read_data=b"test_audio_data")):
            result = separate.split_audio("test_audio.wav")
            self.assertFalse(result)
