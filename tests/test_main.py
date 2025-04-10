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
        self.test_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.test_lyrics_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        self.test_audio_full_path = self.test_audio_file.name
        self.test_lyrics_full_path = self.test_lyrics_file.name

        # Create a minimal valid WAV file
        with open(self.test_audio_full_path, 'wb') as f:
            # Minimal WAV header (may not be valid for all tools)
            f.write(b'RIFF')
            f.write((36).to_bytes(4, 'little')) # File size - 8
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write((16).to_bytes(4, 'little')) # Format chunk size
            f.write((1).to_bytes(2, 'little')) # Audio format (PCM)
            f.write((1).to_bytes(2, 'little')) # Number of channels
            f.write((1600).to_bytes(4, 'little')) # Sample rate
            f.write((3200).to_bytes(4, 'little')) # Byte rate
            f.write((2).to_bytes(2, 'little')) # Block align
            f.write((16).to_bytes(2, 'little')) # Bits per sample
            f.write(b'data')
            f.write((0).to_bytes(4, 'little')) # Data chunk size


        # Create valid test lyrics
        with open(self.test_lyrics_full_path, 'w') as f:
            f.write('This is a test lyrics file.')

    def tearDown(self):
        """Removes the temporary directory after the tests"""
        os.remove(self.test_audio_full_path)
        os.remove(self.test_lyrics_full_path)
        shutil.rmtree(self.temp_dir)

    def test_translate_missing_audio(self):
        response = self.app.post('/translate', data={'lyrics': (open(self.test_lyrics_full_path, 'rb'), 'test_lyrics.txt')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing audio file.'})

    def test_translate_missing_lyrics(self):
        """Tests the /translate endpoint when lyrics file is missing"""
        response = self.app.post('/translate', data={'audio': (open(self.test_audio_full_path, 'rb'), 'test_audio.wav')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing lyrics file.'})

    def test_translate_invalid_audio(self):
        """Tests the /translate endpoint returns an error for invalid audio"""
        invalid_audio_path = os.path.join(self.temp_dir, 'invalid_audio.txt')
        with open(invalid_audio_path, 'w') as f:
            f.write('Invalid audio file.')

        with open(self.test_lyrics_full_path, 'rb') as lyrics_file, open(invalid_audio_path, 'rb') as audio_file:
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

        with open(self.test_audio_full_path, 'rb') as audio_file, open(invalid_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'invalid_lyrics.bin')
            })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Invalid lyrics file.'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    @patch('musictranslator.main.map_transcript')
    def test_translate_success(self, mock_map_transcript, mock_align_lyrics, mock_split_audio):
        """Tests the /translate endpoint with a successful audio and lyrics processing"""
        mock_split_audio.return_value = {
            'vocals': os.path.join(self.temp_dir, 'vocals.wav'),
            'drums': os.path.join(self.temp_dir, 'drums.wav'),
            'bass': os.path.join(self.temp_dir, 'bass.wav'),
            'guitar': os.path.join(self.temp_dir, 'guitar.wav')}

        # Create a temporary alignment JSON file and mock the return value
        temp_alignment_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temp_alignment_path = temp_alignment_file.name
        temp_alignment_file.write(json.dumps({"tier_name": "words", "intervals": []}).encode('utf-8'))
        temp_alignment_file.close()
        mock_align_lyrics.return_value = temp_alignment_path

        mock_map_transcript.return_value = [{"word": "example", "start": 0.1, "end": 0.5}]


        with open(self.test_audio_full_path, 'rb') as audio_file, open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), [{"word": "example", "start": 0.1, "end": 0.5}])
        mock_split_audio.assert_called_once()
        mock_align_lyrics.assert_called_once()
        mock_map_transcript.assert_called_once()

        # Clean up the temporary alignment file
        if temp_alignment_path and os.path.exists(temp_alignment_path): # Added exists check
            os.remove(temp_alignment_path)

    @patch('musictranslator.main.split_audio')
    def test_translate_separator_error(self, mock_split_audio):
        """Tests the /translate endpoint when the separator service returns an error"""
        mock_split_audio.return_value = {'error': 'Demucs Error'}

        with open(self.test_audio_full_path, 'rb') as audio_file, open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'Demucs Error'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    def test_translate_aligner_error(self, mock_align_lyrics, mock_split_audio):
        """Tests the /translate endpoint when the aligner service returns an error"""
        mock_split_audio.return_value = {
            'vocals': os.path.join(self.temp_dir, 'vocals.wav'),
            'drums': os.path.join(self.temp_dir, 'drums.wav'),
            'bass': os.path.join(self.temp_dir, 'bass.wav'),
            'guitar': os.path.join(self.temp_dir, 'guitar.wav')
        }
        mock_align_lyrics.return_value = {'error': 'Aligner Error'}

        with open(self.test_audio_full_path, 'rb') as audio_file, open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {'error': 'Aligner Error'})

    @patch('musictranslator.main.split_audio')
    @patch('musictranslator.main.align_lyrics')
    @patch('musictranslator.main.map_transcript')
    def test_translate_map_failure(self, mock_map_transcript, mock_align_lyrics, mock_split_audio):
        """Tests the /translate endpoint when transcrpt mapping fails"""
        mock_split_audio.return_value = {
            'vocals': os.path.join(self.temp_dir, 'vocals.wav'),
            'drums': os.path.join(self.temp_dir, 'drums.wav'),
            'bass': os.path.join(self.temp_dir, 'bass.wav'),
            'guitar': os.path.join(self.temp_dir, 'guitar.wav')
        }
        mock_align_lyrics.return_value = os.path.join(self.temp_dir, 'alignment.json')
        mock_map_transcript.return_value = None

        with open(self.test_audio_full_path, 'rb') as audio_file, open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            response = self.app.post('/translate', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {"error": "Failed to map alignment to transcript."})
