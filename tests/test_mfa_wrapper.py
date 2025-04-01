import os
import json
import tempfile
import subprocess
import shutil
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from musictranslator.mfa_wrapper import app, align

class TestMFAWrapper(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.temp_dir = tempfile.mkdtemp()
        self.test_audio_path = os.path.join(self.temp_dir, 'test_audio.wav')
        self.test_lyrics_path = os.path.join(self.temp_dir, 'test_lyrics.txt')
        with open(self.test_audio_path, 'wb') as f:
            f.write(b'test audio data')
        with open(self.test_lyrics_path, 'w') as f:
            f.write('test lyric data')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('subprocess.run')
    def test_align_success(self, mock_subprocess_run):
        # Mock successful model downloads, validation and alignment
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=json.dumps({
                'tier_name': 'words',
                'intervals': [
                    {'xmin': 0.0, 'xmax': 1.0, 'word': 'hello'},
                    {'xmin': 1.0, 'xmax': 2.0, 'word': 'world'}
                ]
            }).encode('utf-8'))
        ]

            # Mock alignment to JSON format
        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        expected_data = {
            'tier_name': 'words',
            'intervals': [
                {'xmin': 0.0, 'xmax': 1.0, 'word': 'hello'},
                {'xmin': 1.0, 'xmax': 2.0, 'word': 'world'}
            ]
        }
        self.assertEqual(data, expected_data)

    def test_align_missing_files(self):
        response = self.app.post('/align', data={})
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'Audio or lyrics file missing'})

    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run):
        # Mock successful model downloads and validation
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            subprocess.CalledProcessError(returncode=1, cmd=["mfa", "align", "--output_format", "json", "audio_path", "lyrics_path", "english_us_arpa", "english_us_arpa", "aligned"], stderr="Alignment failed"),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "align", "--output_format", "json", "audio_path", "lyrics_path", "english_us_arpa", "english_us_arpa", "aligned", "--beam", "100", "--retry_beam", "400"],
                stderr="Alignment failed",
            )
        ]

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('Alignment failed', data['error'])

    @patch('subprocess.run')
    def test_align_validation_error(self, mock_subprocess_run):
        # Mock successful model downloads, failed validation
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "validate", "/data/MFA/corpus", "english_us_arpa", "english_us_arpa"],
                stderr="Validation failed",
            )
        ]

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('Validation failed', data['error'])

    @patch('subprocess.run')
    def test_align_retry_success(self, mock_subprocess_run):
        # Mock failed initial, successful retry
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=1),
            MagicMock(returncode=0, stdout=json.dumps({
                'tier_name': 'words',
                'intervals': [
                    {'xmin': 0.0, 'xmax': 1.0, 'word': 'hello'},
                    {'xmin': 1.0, 'xmax': 2.0, 'word': 'world'}
                ]
            }).encode('utf-8'))
        ]

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })


        print("Subprocess Calls:")
        for call in mock_subprocess_run.call_args_list:
            print(call)

        print("Response Status Code:", response.status_code)
        print("Response Data:", response.data)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        expected_data = {
            'tier_name': 'words',
            'intervals': [
                {'xmin': 0.0, 'xmax': 1.0, 'word': 'hello'},
                {'xmin': 1.0, 'xmax': 2.0, 'word': 'world'}
            ]
        }
        self.assertEqual(data, expected_data)

    @patch('subprocess.run')
    def test_align_json_decode_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=b"invalid json")
        ]

        with open(self.test_audio_path, 'rb') as audio_file, open(self.test_lyrics_path, 'rb') as lyrics_file:
            response = self.app.post('/align', data={
                'audio': (audio_file, 'test_audio.wav'),
                'lyrics': (lyrics_file, 'test_lyrics.txt')
            })

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn("Failed to decode alignment JSON output.", data['error'])
