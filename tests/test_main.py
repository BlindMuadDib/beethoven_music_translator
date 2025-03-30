"""
Unit test for the Flask application main.py
Focuses on API endpoint behavior
"""

import os
import json
import shutil
import unittest
from unittest.mock import patch, MagicMock, call
from werkzeug.datastructures import FileStorage
from io import BytesIO
from flask import Flask, Response
from musictranslator import main
from musictranslator.main import app

class TestMain(unittest.TestCase):
    """Testing suite"""
    def setUp(self):
        """Sets up a Flask test client and creates a temporary directory"""
        self.app = main.app.test_client()
        self.temp_dir = "test_temp"
        os.makedirs(self.temp_dir, exist_ok=True)
        main.app.config['UPLOAD_FOLDER'] = self.temp_dir

        self.audio_path = os.path.join(self.temp_dir, 'audio.wav')
        self.lyrics_path = os.path.join(self.temp_dir, 'lyrics.txt')

        with open(self.audio_path, 'wb') as audio_file:
            audio_file.write(b'fake audio data')

        with open(self.lyrics_path, 'w') as lyrics_file:
            lyrics_file.write('Sample lyrics')

    def tearDown(self):
        """Removes the temporary directory after the tests"""
        if os.path.exists(self.audio_path):
            os.remove(self.audio_path)
        if os.path.exists(self.lyrics_path):
            os.remove(self.lyrics_path)
        shutil.rmtree(self.temp_dir)

    @patch('musictranslator.musicprocessing.align.align_lyrics')
    @patch('musictranslator.musicprocessing.separate.split_audio')
    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    @patch('musictranslator.main.create_synchronized_transcript_json')
    def test_translate_success(self, mock_create_json, mock_validate_text, mock_validate_audio, mock_split_audio, mock_align_lyrics):
        """Tests the /translate endpoint with a successful audio and lyrics processing"""
        mock_validate_audio.return_value = True
        mock_validate_text.return_value = True
        mock_split_audio.return_value = {'vocals_stem_path': '/path/to/vocals.wav'}
        mock_align_lyrics.return_value = {'tier_name': 'words', 'intervals': [{'xmin': 0.0, 'xmax': 1.0, 'word': 'hello'}]}
        mock_create_json.return_value = {'result': 'success'}

        audio_file = FileStorage(stream=BytesIO(b'audio_data'), filename='audio.wav', content_type='audio/wav')
        lyrics_file = FileStorage(stream=BytesIO(b'lyrics_data'), filename='lyrics.txt', content_type='text/plain')

        response = self.app.post('/translate', data={'audio': audio_file, 'lyrics': lyrics_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {'result': 'success'})

    @patch('musictranslator.musicprocessing.align.align_lyrics')
    @patch('musictranslator.musicprocessing.separate.split_audio')
    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    def test_translate_spleeter_error(self, mock_validate_text, mock_validate_audio, mock_split_audio, mock_align_lyrics):
        mock_validate_audio.return_value = True
        mock_validate_text.return_value = True
        mock_split_audio.return_value = {'error': 'Spleeter Error'}

        audio_file = FileStorage(stream=BytesIO(b'audio_data'), filename='audio.wav', content_type='audio/wav')
        lyrics_file = FileStorage(stream=BytesIO(b'lyrics_data'), filename='lyrics.txt', content_type='multipart/form-data')

        response = self.app.post('/translate', data={'audio': audio_file, 'lyrics': lyrics_file})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'Spleeter Error'})

    @patch('musictranslator.musicprocessing.align.align_lyrics')
    @patch('musictranslator.musicprocessing.separate.split_audio')
    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    def test_translate_mfa_error(self, mock_validate_text, mock_validate_audio, mock_split_audio, mock_align_lyrics):
        mock_validate_audio.return_value = True
        mock_validate_text.return_value = True
        mock_split_audio.return_value = {'vocals_stem_path': '/path/to/vocals.wav'}
        mock_align_lyrics.return_value = {'error': 'MFA Alignment Failed'}

        audio_file = FileStorage(stream=BytesIO(b'audio_data'), filename='audio.wav', content_type='audio/wav')
        lyrics_file = FileStorage(stream=BytesIO(b'lyrics_data'), filename='lyrics.txt', content_type='text/plain')

        response = self.app.post('/translate', data={'audio': audio_file, 'lyrics': lyrics_file})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'MFA Alignment Failed'})

    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    def test_translate_invalid_audio(self, mock_validate_text, mock_validate_audio):
        """Tests the /translate endpoint returns an error for invalid audio"""
        mock_validate_audio.return_value = False

        invalid_audio_path = os.path.join(self.temp_dir, 'invalid_audio.wav')
        with open(invalid_audio_path, 'w') as invalid_audio_file:
            invalid_audio_file.write('This is not audio data.')

        audio_file = (open(invalid_audio_path, 'rb'), 'audio.wav')
        lyrics_file = (open(self.lyrics_path, 'rb'), 'lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {"error": "Invalid audio file."})

        os.remove(invalid_audio_path)

    @patch('musictranslator.main.validate_audio')
    @patch('musictranslator.main.validate_text')
    def test_translate_invalid_lyrics(self, mock_validate_text, mock_validate_audio):
        """Tests the /translate endpoint returns an error for invalid lyrics"""
        mock_validate_text.return_value = False

        invalid_lyrics_path = os.path.join(self.temp_dir, 'invalid_lyrics.txt')
        with open(invalid_lyrics_path, 'w') as invalid_lyrics_file:
            invalid_lyrics_file.write('<html><body>This is not plain text.</body></html>')

        audio_file = (open(self.audio_path, 'rb'), 'audio.wav')
        lyrics_file = (open(invalid_lyrics_path, 'rb'), 'invalid_lyrics.txt')

        response = self.app.post('/translate', data={
            'audio': audio_file,
            'lyrics': lyrics_file
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {"error": "Invalid lyrics file."})

        os.remove(invalid_lyrics_path)

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

    @patch('musictranslator.musicprocessing.map_transcript.create_synchronized_transcript_json')
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
