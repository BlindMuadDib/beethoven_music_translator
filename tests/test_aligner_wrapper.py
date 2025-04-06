import os
import json
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from musictranslator.aligner_wrapper import app, align, CORPUS_DIR, OUTPUT_DIR

class TestMFAWrapper(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.test_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.test_lyrics_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        self.test_audio_full_path = self.test_audio_file.name
        self.test_lyrics_full_path = self.test_lyrics_file.name

        self.test_audio_file.close()
        self.test_lyrics_file.close()

    def tearDown(self):
        os.remove(self.test_audio_full_path)
        os.remove(self.test_lyrics_full_path)

        audio_base_name = os.path.splitext(os.path.basename(self.test_audio_full_path))[0]

        if os.path.exists(os.path.join(CORPUS_DIR, f"{audio_base_name}.wav")):
            os.unlink(os.path.join(CORPUS_DIR, f"{audio_base_name}.wav"))
        if os.path.exists(os.path.join(CORPUS_DIR, f"{audio_base_name}.txt")):
            os.unlink(os.path.join(CORPUS_DIR, f"{audio_base_name}.txt"))

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
        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
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
        # Check that the files were copied
        audio_base_name = os.path.splitext(os.path.basename(self.test_audio_full_path))[0]

        self.assertTrue(os.path.exists(os.path.join(CORPUS_DIR, f"{audio_base_name}.wav")))
        self.assertTrue(os.path.exists(os.path.join(CORPUS_DIR, f"{audio_base_name}.txt")))

    def test_align_missing_files(self):
        response = self.app.post('/align', json={})
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'vocal_stem_path or lyrics_file_path missing'})

    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run):
        # Mock successful model downloads and validation
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            subprocess.CalledProcessError(returncode=1, cmd=["mfa", "align", "--output_format", "json", CORPUS_DIR, "english_us_arpa", "english_us_arpa", OUTPUT_DIR], stderr="Alignment failed"),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "align", "--output_format", "json", CORPUS_DIR, "english_us_arpa", "english_us_arpa", OUTPUT_DIR, "--beam", "100", "--retry_beam", "400"],
                stderr="Alignment failed",
            )
        ]

        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
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
                cmd=["mfa", "validate", CORPUS_DIR, "english_us_arpa", "english_us_arpa"],
                stderr="Validation failed",
            )
        ]

        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
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

        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
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

    @patch('subprocess.run')
    def test_align_json_decode_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=b"invalid json")
        ]

        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
        })

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn("Failed to decode alignment JSON output.", data['error'])
