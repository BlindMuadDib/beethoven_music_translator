import os
import json
import tempfile
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from musictranslator.mfa_wrapper import app

class TestMFAWrapper(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.test_audio_path = "tests/test_audio.wav"
        self.test_lyrics_path = "tests/test_lyrics.txt"
        self.test_textgrid_path = "tests/test_alignment.TextGrid"

        with open(self.test_audio_path, 'w') as f:
            f.write("test audio")
        with open(self.test_lyrics_path, 'w') as f:
            f.write("test lyrics")
        with open(self.test_textgrid_path, 'w') as f:
            f.write('''File type = "OOTextFile"
Object class = "TextGrid"

xmin = 0
xmax = 1
tiers? <exists>
    size = 1
    item []:
        item [1]:
            class = "IntervalTier"
            name = "words"
            xmin = 0
            xmax = 1
            intervals: size = 2
                intervals [1]:
                    xmin = 0
                    xmax = 0.5
                    text = "hello"
                intervals [2]:
                    xmin = 0.5
                    xmax = 1
                    text = "world"''')

    def tearDown(self):
        if os.path.exists(self.test_audio_path):
            os.remove(self.test_audio_path)
        if os.path.exists(self.test_lyrics_path):
            os.remove(self.test_lyrics_path)
        if os.path.exists(self.test_textgrid_path):
            os.remove(self.test_textgrid_path)

    @patch('subprocess.run')
    def test_align_success(self, mock_subprocess_run):
        # Mock subprocess calls
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        def mock_textgrid_from_file(path):
            mock_tg = MagicMock()
            mock_words_tier = MagicMock()
            mock_words_tier.name = 'words'
            mock_words_tier.intervals = [
                MagicMock(minTime=0, maxTime=0.5, mark='hello'),
                MagicMock(minTime=0.5, maxTime=1, mark='world')
            ]
            mock_tg.getFirst.return_value = mock_words_tier
            return mock_tg

        with patch('textgrid.TextGrid.fromFile', side_effect=mock_textgrid_from_file):
            with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
                response = self.app.post('/align', data={
                    'audio': (audio_file, 'test_audio.wav'),
                    'lyrics': (lyrics_file, 'test_lyrics.txt')
                })
            print(f"Response data: {response.data!r}")
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data.decode('utf-8'))
            self.assertEqual(data, {
                'tier_name': 'words',
                'intervals': [
                    {'xmin': 0, 'xmax': 0.5, 'word': 'hello'},
                    {'xmin': 0.5, 'xmax': 1, 'word': 'world'}
                ]
            })

    def test_align_missing_files(self):
        response = self.app.post('/align', data={})
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'Audio or lyrics file missing'})

    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["mfa", "align", "audio_path", "lyrics_path", "english_us_arpa", "english_us_arpa", "aligned", "--beam", "100", "--retry_beam", "400"],
            stderr=b"Subprocess failed",
        )
        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('Subprocess failed', data['error'])

    @patch('subprocess.run')
    def test_align_validation_error(self,mock_subprocess_run):
        mock_subprocess_run.side_effect =  subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "validate", "/data/MFA/corpus", "english_us_arpa", "english_us_arpa"],
                stderr=b"Validation failed",
        )
        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('Validation failed', data['error'])
