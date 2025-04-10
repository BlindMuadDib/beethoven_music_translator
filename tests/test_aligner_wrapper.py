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
        self.temp_corpus_dir = tempfile.mkdtemp()
        self.temp_output_dir = tempfile.mkdtemp()

        self.test_audio_base_name = os.path.splitext(os.path.basename(self.test_audio_full_path))[0]

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

        with open(self.test_lyrics_full_path, 'w') as f:
            f.write("hello\nworld")
        shutil.copyfile(self.test_lyrics_full_path, os.path.join(self.temp_corpus_dir, f"{self.test_audio_base_name}.txt"))

        self.test_audio_file.close()
        self.test_lyrics_file.close()

    def tearDown(self):
        os.remove(self.test_audio_full_path)
        os.remove(self.test_lyrics_full_path)
        shutil.rmtree(self.temp_corpus_dir)
        shutil.rmtree(self.temp_output_dir)

    @patch('musictranslator.aligner_wrapper.CORPUS_DIR')
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR')
    @patch('subprocess.run')
    def test_align_success(self, mock_subprocess_run, mock_output_dir, mock_corpus_dir):
        # Mock successful model downloads, validation and alignment
        mock_corpus_dir.return_value = self.temp_corpus_dir
        mock_output_dir.return_value = self.temp_output_dir
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=b'{}')
        ]

        # Mock alignment to JSON format
        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('alignment_file_path', data)
        self.assertTrue(data['alignment_file_path'].endswith(".json"))

    @patch('musictranslator.aligner_wrapper.CORPUS_DIR')
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR')
    def test_align_missing_files(self, mock_output_dir, mock_corpus_dir):
        mock_corpus_dir.return_value = self.temp_corpus_dir
        mock_output_dir.return_value = self.temp_output_dir
        response = self.app.post('/align', json={})
        print(f"Response data: {response.data!r}")
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'vocal_stem_path or lyrics_file_path missing'})

    @patch('musictranslator.aligner_wrapper.CORPUS_DIR')
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR')
    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run, mock_output_dir, mock_corpus_dir):
        mock_corpus_dir.return_value = self.temp_corpus_dir
        mock_output_dir.return_value = self.temp_output_dir
        # Mock successful model downloads and validation
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            subprocess.CalledProcessError(returncode=1, cmd=["mfa", "align", "--output_format", "json", self.temp_corpus_dir, "english_us_arpa", "english_us_arpa", self.temp_output_dir], stderr="Alignment failed"),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "align", "--output_format", "json", self.temp_corpus_dir, "english_us_arpa", "english_us_arpa", self.temp_output_dir, "--beam", "100", "--retry_beam", "400"],
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

    @patch('musictranslator.aligner_wrapper.CORPUS_DIR')
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR')
    @patch('subprocess.run')
    def test_align_validation_error(self, mock_subprocess_run, mock_output_dir, mock_corpus_dir):
        # Mock successful model downloads, failed validation
        mock_corpus_dir.return_value = self.temp_corpus_dir
        mock_output_dir.return_value = self.temp_output_dir
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["mfa", "validate", self.temp_corpus_dir, "english_us_arpa", "english_us_arpa"],
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

    @patch('musictranslator.aligner_wrapper.CORPUS_DIR')
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR')
    @patch('subprocess.run')
    def test_align_retry_success(self, mock_subprocess_run, mock_output_dir, mock_corpus_dir):
        # Mock failed initial, successful retry
        mock_corpus_dir.return_value = self.temp_corpus_dir
        mock_output_dir.return_value = self.temp_output_dir
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=1),
            MagicMock(returncode=0, stdout=b'{}')
        ]

        response = self.app.post('/align', json={
            'vocal_stem_path': self.test_audio_full_path,
            'lyrics_file_path': self.test_lyrics_full_path
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('alignment_file_path', data)
        self.assertTrue(data['alignment_file_path'].endswith(".json"))
