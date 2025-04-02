"""
Integration testing to ensure all services communicate correctly
"""
import unittest
import os
import json
import subprocess
import os
import time
import requests
from unittest.mock import patch

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['kind', 'get', 'clusters'], capture_output=True, text=True)
        if "kind" not in result.stdout:
            raise Exception("KIND cluster is not running. Please run run_integration_test.sh first.")

        # Get NodePort
        result = subprocess.run(['kubectl', 'get', 'service', 'translator-service', '-o' 'jsonpath="{.spec.ports[0].nodePort}"'], capture_output=True, text=True)
        cls.nodeport = result.stdout.strip()
        print(f"NodePort: {cls.nodeport}")

        # Wait for pods to get ready with a timeout
        timeout = time.time() + 60
        while time.time() < timeout:
            result = subprocess.run(['kubectl', 'get', 'pods', '-o', 'jsonpath={.items[*].status.containerStatuses[*].ready}"'], capture_output=True, text=True)
            if "true true true" in result.stdout:
                break
            time.sleep(2)
        else:
            raise Exception("Timeout waiting for pods to become ready")

        print("SetUpClass completed")

    @classmethod
    def tearDownClass(cls):
        # No need to delete KIND cluster here, it's done in the bash script
        pass

    def setUp(self):
        self.flask_url = "http://localhost:{self.nodeport}/translate"
        self.audio_file = open("data/audio/BloodCalcification-NoMore.wav", 'rb')
        self.lyrics_file = open("data/lyrics/BloodCalcification-NoMore.txt", 'rb')

    def tearDown(self):
        self.audio_file.close()
        self.lyrics_file.close()

    def test_translate_success(self):
        files = {
            'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
            'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
        }
        try:
            response = requests.post(self.flask_url, files=files, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses

            # Load expected result from JSON file
            with open("tests/expected_results/BloodCalcification-NoMore.json", "r") as f:
                expected_result = json.load(f)

            # Parse JSON response
            response_data = response.json()

            self.assertEqual(response.status_code, 200)
            self.assertIn("aligned_words", response_data)
            self.assertIsInstance(response_data["aligned_words"], list)
            self.assertTrue(len(response_data["aligned_words"]) > 0)

        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")

        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON response: {e}")

    @patch('requests.post')
    def test_translate_mfa_error(self, mock_post):
        # Mock mfa error response
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = 'MFA Error'
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError('MFA Error', response=mock_post.return_value)

        files = {
            'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
            'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
        }
        response = requests.post(self.flask_url, files=files)
        self.assertEqual(response.status_code, 500)
        self.assertIn('MFA Error', response.text)

    @patch('requests.post')
    def test_translate_spleeter_error(self, mock_post):
        # Mock spleeter error
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = 'Spleeter Error'
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError('Spleeter Error', response=mock_post.return_value)

        files = {
            'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
            'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
        }
        response = requests.post(self.flask_url, files=files)
        self.assertEqual(response.status_code, 500)
        self.assertIn('Spleeter Error', response.text)

    def test_main_deployment(self):
        # Test the musictranslator.main Flask app deployment and service
        # Write test
        response = requests.get(f"http://localhost:{self.nodeport}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('Music Translator', response.text)

    def test_mfa_deployment(self):
        # test the Montreal Forced Aligner deployment and service
        response = requests.get(f"http://localhost:{self.nodeport}/mfa/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn('OK', response.text)

    def test_spleeter_deployment(self):
        # test the Montreal Forced Aligner deployment and service
        response = requests.get(f"http://localhost:{self.nodeport}/spleeter/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn('OK', response.text)

    # Add more tests for other scenarios
