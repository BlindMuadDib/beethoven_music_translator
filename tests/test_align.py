"""
Test file for the mfa_service module
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing import align
from musictranslator.musicprocessing.align import align_lyrics, MFA_SERVICE_URL

class TestAlignLyrics(unittest.TestCase):

    def setUp(self):
        # Create dummy test files
        with open("audio.wav", "wb") as f:
            f.write(b"dummy audio data")
        with open("lyrics.txt", "w") as f:
            f.write("dummy lyrics data")

    def tearDown(self):
        if os.path.exists("audio.wav"):
            os.remove("audio.wav")
        if os.path.exists("lyrics.txt"):
            os.remove("lyrics.txt")

    @patch('musictranslator.musicprocessing.align.requests.post')
    def test_align_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "alignment_file_path"}
        mock_post.return_value = mock_response

        result = align_lyrics("audio.wav", "lyrics.txt")
        self.assertEqual(result, {"data": "alignment_file_path"})
        mock_post.assert_called_once_with(MFA_SERVICE_URL, files={'audio': unittest.mock.ANY, 'lyrics': unittest.mock.ANY}, timeout=10)

    @patch('musictranslator.musicprocessing.align.requests.post')
    def test_align_lyrics_failure_http(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = align_lyrics("audio.wav", "lyrics.txt")
        self.assertEqual(result, {"error": "MFA alignment failed: Internal Server Error"})

    @patch('musictranslator.musicprocessing.align.requests.post')
    def test_align_lyrics_request_exception(self, mock_post):
        # Mock a request error
        mock_post.side_effect = requests.exceptions.RequestException("Request failed")

        result = align_lyrics("audio.wav", "lyrics.txt")

        self.assertEqual(result, {"error": "Error communicating with MFA: {e}"})

    def test_align_lyrics_file_error(self):
        result = align_lyrics("nonexistent_audio.mp3", "nonexistent_lyrics.txt")
        self.assertTrue("Error opening file" in result["error"])

    @patch('musictranslator.musicprocessing.align.requests.post')
    def test_align_lyrics_value_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        result = align_lyrics("audio.wav", "lyrics.txt")
        self.assertTrue("Error parsing TextGrid" in result["error"])

    @patch('requests.post')
    def test_align_lyrics_general_error(self, mock_post):
        mock_post.side_effect = Exception("Unexpected Error")
        result = align_lyrics("audio.wav", "lyrics.txt")
        self.assertTrue("Unexpected error in mfa_service" in result["error"])
