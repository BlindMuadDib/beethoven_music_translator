"""
Tests for spleeter_wrapper.py
"""
import json
import os
import unittest
from flask import Flask
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from musictranslator import spleeter_wrapper

class TestSpleeterWrapper(unittest.TestCase):
    """Test suite"""

    def setUp(self):
        """Set up test environment"""
        self.app = spleeter_wrapper.app.test_client()
        self.app.testing = True
        self.test_audio_path = "test_audio.wav"

        with open(self.test_audio_path, 'wb') as f:
            f.write(b"test_audio_data")

        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        """Tear down test environment"""
        if os.path.exists(self.test_audio_path):
            os.remove(self.test_audio_path)

    @patch('musictranslator.spleeter_wrapper.get_spleeter_pod_name')
    @patch('musictranslator.spleeter_wrapper.execute_command_in_pod')
    def test_split_success(self, mock_execute_command, mock_get_pod_name):
        """Test successful audio splitting."""
        mock_get_pod_name.return_value = "test-pod"
        mock_execute_command.return_value = "output_audio/bass.wav output_audio/drums.wav output_audio/other.wav output_audio/vocals.wav"

        with open(self.test_audio_path, 'rb') as audio_file:
            response = self.app.post('/split', data={'audio': (audio_file, 'test_audio.wav')})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('bass', data)
        self.assertIn('drums', data)
        self.assertIn('other', data)
        self.assertIn('vocals', data)

    @patch('musictranslator.spleeter_wrapper.get_spleeter_pod_name')
    def test_split_no_audio_file(self, mock_get_pod_name):
        """Test handling of no audio file provided"""
        mock_get_pod_name.return_value = "test-pod"
        response = self.app.post('/split', data={})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['error'], 'No audio file provided')

    @patch('musictranslator.spleeter_wrapper.get_spleeter_pod_name')
    def test_split_pod_not_found(self, mock_get_pod_name):
        """Test handling of kubernetes pod error"""
        mock_get_pod_name.return_value = "Error getting pod name: Test Error"
        with open(self.test_audio_path, 'rb') as audio_file:
            response = self.app.post('/split', data={'audio': (audio_file, 'test_audio.wav')})

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn(data['error'], 'Error getting pod name: Test Error')

    @patch('musictranslator.spleeter_wrapper.get_spleeter_pod_name')
    @patch('musictranslator.spleeter_wrapper.get_spleeter_pod_name')
    def test_split_command_error(self, mock_execute_command, mock_get_pod_name):
        """Test handling of file not found error"""
        mock_get_pod_name.return_value = "test-pod"
        mock_execute_command.return_value = "Error executing command: Command Error"
        with open(self.test_audio_path, 'rb') as audio_file:
            response = self.app.post('/split', data={'audio': (audio_file, 'test_audio.wav')})

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn(data['error'], 'Error executing command: Command Error')
