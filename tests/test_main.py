"""
Unit test for the Flask application main.py
Focuses on API endpoint behavior
"""

import os
import json
import shutil
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, Response
from musictranslator import main

class TestMain(unittest.TestCase):
    """Testing suite"""
    def setUp(self):
        """Sets up a Flask test client and creates a temporary directory"""
        self.app = main.app.test_client()
        self.temp_dir = "test_temp"
        os.makedirs(self.temp_dir, exist_ok=True)
        main.app.config['UPLOAD_FOLDER'] = self.temp_dir

    def tearDown(self):
        """Removes the temporary directory after the tests"""
        shutil.rmtree(self.temp_dir)

    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    @patch('musictranslator.spleeter_wrapper.SpleeterWrapper.separate')
    @patch('musictranslator.mfa_wrapper.align')
    @patch('musictranslator.musictprocessing.map_transcript.create_synchronized_transcript_json')
    def test_translate_success(self, mock_map, mock_align, mock_separate, mock_validate_text, mock_validate_audio):
        """Tests the /translate endpoint with a successful audio and lyrics processing"""
        mock_validate_audio.return_value = True
        mock_validate_text.return_value = True
        mock_separate.return_value = None
        mock_align.return_value = "aligned.TextGrid"
        mock_map.return_value = {"alignment": "data"}

        audio_file = (b'audio_data', 'audio.wav')
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

    self.assertEqual(response.status_code, 200)
    self.assertEqual(json.loads(response.data), {"alignment": "data"})

    mock_validate_audio.assert_called_once()
    mock_validate_text.assert_called_once()
    mock_separate.assert_called_once()
    mock_align.assert_called_once()
    mock_map.assert_called_once()

    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    def test_translate_invalid_audio(self, mock_validate_text, mock_validate_audio):
        """Tests the /translate endpoint returns an error for invalid audio"""
        mock_validate_audio.return_value = False

        audio_file = (b'invalid_audio_data', 'audio.wav')
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {"error": "Invalid audio file."})

    @patch('musictranslator.main.validate_text')
    @patch('musictranslator.main.validate_audio')
    def test_translate_invalid_lyrics(self, mock_validate_text, mock_validate_audio):
        """Tests the /translate endpoint returns an error for invalid lyrics"""
        mock_validate_text.return_value = False

        audio_file = (b'audio_data', 'lyrics.txt')
        lyrics_file = (b'invalid_lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data_, {"error": "Invalid lyrics file."}))

    def test_translate_missing_audio(self):
        """Tests the /translate endpoint when audio file is missing"""
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {"error": "Missing audio file."})

    def test_translate_missing_lyrics(self):
        """Tests the /translate endpoint when lyrics file is missing"""
        audio_file = (b'audio_data', 'audio.wav')

        response = self.app.post('/translate', data={
            'audio': audio_file,
        })

    @patch('musictranslator.spleeter_wrapper.SpleeterWrapper.separate')
    def test_translate_spleeter_failure(self, mock_separate):
        """Tests the /translate endpoint when Spleeter separation fails"""
        mock_separate.side_effect = Exception("Spleeter error")

        audio_file = (b'audio_data', 'audio.wav')
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {"error": "Internal server error."})

    @patch('musictranslator.mfa_wrapper.align')
    def test_translate_mfa_failure(self, mock_align):
        """Tests the /translate endpoint when MFA alignment fails"""
        mock_align.side_effect = Exception("MFA error")

        audio_file = (b'audio_data', 'audio.wav')
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
            })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.load(response.data), {"error": "Internal server error."})

    @patch('musictranslator.musictprocessing.map_transcript.create_synchronized_transcript_json')
    def test_translate_map_failure(self, mock_map):
        """Tests the /translate endpoint when mapping the TextGrid fails"""
        mock_map.side_effect = Exception("Mapping error")

        audio_file = (b'audio_data', 'audio.wav')
        lyrics_file = (b'lyrics_data', 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {"error": "Internal server error."})
