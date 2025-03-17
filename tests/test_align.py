"""
Test file for the mfa_service module
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import requests
import requests_mock

import musictranslator.musicprocessing
from musictranslator.musicprocessing import align
from musictranslator.musicprocessing.align import align_lyrics, MFA_SERVICE_URL

class TESTMFAService(unittest.TestCase):

    def setUp(self):
        self.test_audio_path = "tests/test_audio.wav"
        self.test_lyrics_path = "tests/test_lyrics.txt"
        self.test_textgrid_path = "tests/test_alignment.TextGrid"

        # Create dummy test files
        with open(self.test_audio_path, 'w') as f:
            f.write("test audio")
        with open(self.test_lyrics_path, 'w') as f:
            f.write("test lyrics")
        with open(self.test_textgrid_path, 'w') as f:
            f.write("some sample textgrid data")

    def tearDown(self):
        os.remove(self.test_audio_path)
        os.remove(self.test_lyrics_path)
        os.remove(self.test_textgrid_path)

    def test_align_success(self):
        with requests_mock.Mocker() as m:
            with open(self.test_textgrid_path, 'r') as textgrid_file:
                expected_textgrid = textgrid_file.read()
            m.post(MFA_SERVICE_URL, text=expected_textgrid, status_code=200)

            result = align_lyrics(self.test_audio_path, self.test_lyrics_path)

            self.assertEqual(result, expected_textgrid)


    @patch('requests.post')
    def test_align_lyrics_request_error(self, mock_post):
        # Mock a request error
        mock_post.side_effect = requests.exceptions.RequestException("Test Request Error")

        result = align_lyrics(self.test_audio_path, self.test_lyrics_path)

        self.assertEqual(result, '[ERROR] Error communicating with MFA service: Test Request Error')

    @patch('requests.post')
    def test_align_lyrics_file_error(self, mock_post):
        # Mock an OsError
        result = align_lyrics("nonexistent_audio.wav", self.test_lyrics_path)
        self.assertEqual(result, "[ERROR] Error opening file: [Errno 2] No such file or directory: 'nonexistent_audio.wav'")

    @patch('requests.post')
    def test_align_lyrics_general_error(self, mock_post):
        mock_post.side_effect = Exception("Test General Error")
        result = align_lyrics(self.test_audio_path, self.test_lyrics_path)
        self.assertEqual(result, '[ERROR] Unexpected error in mfa_service: Test General Error')
