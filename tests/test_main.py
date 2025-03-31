"""
Unit test for the Flask application main.py
Focuses on API endpoint behavior
"""

import os
import json
import tempfile
import subprocess
import shutil
import unittest
from unittest.mock import patch
from musictranslator import main
from musictranslator.main import app

class TestMain(unittest.TestCase):
    """Testing suite"""
    def setUp(self):
        """Sets up a Flask test client and creates a temporary directory"""
        self.app = app.test_client()
        self.temp_dir = tempfile.mkdtemp()
        self.test_audio_path = os.path.join(self.temp_dir, 'test_audio.wav')
        self.test_lyrics_path = os.path.join(self.temp_dir, 'test_lyrics.txt')

        # Copy the static test_audio file to the temporary directory
        shutil.copyfile('tests/test_data/test_audio.wav', self.test_audio_path)

        # Create valid test lyrics using echo
        with open(self.test_lyrics_path, 'w') as f:
            f.write('This is a test lyrics file.')

    def tearDown(self):
        """Removes the temporary directory after the tests"""
        shutil.rmtree(self.temp_dir)

    def test_translate_missing_audio(self):
        response = self.app.post('/translate', data={'lyrics': (open(self.test_lyrics_path, 'rb'), 'test_lyrics.txt')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing audio file.'})

    def test_translate_missing_lyrics(self):
        """Tests the /translate endpoint when lyrics file is missing"""
        response = self.app.post('/translate', data={'audio': (open(self.test_audio_path, 'rb'), 'test_audio.wav')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing lyrics file.'})

    def test_translate_invalid_audio(self):
        """Tests the /translate endpoint returns an error for invalid audio"""
        invalid_audio_path = os.path.join(self.temp_dir, 'invalid_audio.txt')
        with open(invalid_audio_path, 'w') as f:
            f.write('Invalid audio file.')

        with open(self.test_lyrics_path, 'rb') as lyrics_file, open(invalid_audio_path, 'rb') as audio_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'invalid_audio.txt'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Invalid audio file.'})

    def test_translate_invalid_lyrics(self):
        """Tests the /translate endpoint returns an error for invalid lyrics"""
        invalid_lyrics_path = os.path.join(self.temp_dir, 'invalid_lyrics.bin')
        with open(invalid_lyrics_path, 'wb') as f:
            f.write(b'\x00\x01\x02\x03')

        with open(self.test_audio_path, 'rb') as audio_file, open(invalid_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'invalid_lyrics.bin')
            })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Invalid lyrics file.'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    @patch('musictranslator.main.sync_alignment_json_with_transcript_lines')
    def test_translate_success(self, mock_sync_alignment, mock_align_lyrics, mock_split_audio):
        """Tests the /translate endpoint with a successful audio and lyrics processing"""
        mock_split_audio.return_value = {'vocals_stem_path': '/path/to/vocals.wav'}
        mock_align_lyrics.return_value = {'tier_name': 'words', 'intervals': []}
        mock_sync_alignment.return_value = {"mapped": "result"}

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {"mapped": "result"})

    @patch('musictranslator.main.split_audio')
    def test_translate_spleeter_error(self, mock_split_audio):
        mock_split_audio.return_value = {'error': 'Spleeter Error'}

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'Spleeter Error'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    def test_translate_mfa_error(self, mock_align_lyrics, mock_split_audio):
        mock_split_audio.return_value = {'vocals_stem_path': '/path/to/vocals.wav'}
        mock_align_lyrics.return_value = {'error': 'MFA Alignment Failed'}

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'MFA Alignment Failed'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    @patch('musictranslator.main.sync_alignment_json_with_transcript_lines')
    def test_translate_map_failure(self, mock_sync_alignment, mock_align_lyrics, mock_split_audio):
        """Tests the /translate endpoint when mapping the TextGrid fails"""
        mock_split_audio.return_value = {"vocals_stem_path": "/path/to/vocals.wav"}
        mock_align_lyrics.return_value = {"tier_name": "words", "intervals": []}
        mock_sync_alignment.side_effect = subprocess.CalledProcessError(1, ['some_command'])

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {"error": "Internal server error."})
