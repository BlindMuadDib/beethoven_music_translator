"""
Tests for spleeter_wrapper.py
Focusing on command generation for 4stems-16kHz
And error handling
"""
import json
import unittest
import subprocess
from flask import Flask
from werkzeug.datastructures import FileStorage
from io import BytesIO
from unittest.mock import patch, MagicMock
from musictranslator import spleeter_wrapper
from musictranslator.spleeter_wrapper import app, separate

class TestSpleeterWrapper(unittest.TestCase):
    """Unittests"""

    def setUp(self):
        """Create a fake directories for the tests"""
        self.app = app.test_client()
        self.app.testing = True

    @patch('musictranslator.spleeter_wrapper.subprocess.run')
    def test_separate_success(self, mock_subprocess_run):
        """Test successful separation"""
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        audio_file = FileStorage(stream=BytesIO(b'audio_data'), filename='audio.wav', content_type='audio/wav')
        response = self.app.post('/separate', data={'audio': audio_file}, content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('vocals_stem_path', data)

    @patch('musictranslator.spleeter_wrapper.subprocess.run')
    def test_separate_failure(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(returncode=1)

        audio_file = FileStorage(stream=BytesIO(b'audio_data'), filename='audio.wav', content_type='audio/wav')
        response = self.app.post('/separate', data={'audio': audio_file}, content_type='multipart/form-data')

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_separate_missing_file(self):
        response = self.app.post('/separate')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_separate_no_selected_file(self):
        response = self.app.post('/separate')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
