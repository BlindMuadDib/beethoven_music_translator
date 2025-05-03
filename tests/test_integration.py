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
import requests_mock
import musictranslator
from musictranslator.musicprocessing.transcribe import process_transcript

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['kind', 'get', 'clusters'], capture_output=True, text=True)
        if "kind" not in result.stdout:
            raise Exception("KIND cluster is not running. Please run run_integration_test.sh first.")

        # Get NodePort
        # result = subprocess.run(['kubectl', 'get', 'service', 'translator-service', '-o' 'jsonpath="{.spec.ports[0].nodePort}"'], capture_output=True, text=True)
        # cls.nodeport = int(result.stdout.strip('""'))
        # print(f"NodePort: {cls.nodeport}")

        # Wait for pods to get ready with a timeout
        timeout = time.time() + 60
        while time.time() < timeout:
            result = subprocess.run(['kubectl', 'get', 'pods', '-o', 'jsonpath={.items[*].status.containerStatuses[*].ready}"'], capture_output=True, text=True)
            if "true true true" in result.stdout:
                break
            time.sleep(2)
        else:
            raise Exception("Timeout waiting for pods to become ready")

        cls.base_url = "https://localhost"
        cls.host_header = {"Host": "musictranslator.org"}
        cls.ssl_verify = False

        print("SetUpClass completed")

    @classmethod
    def tearDownClass(cls):
        # No need to delete KIND cluster here, it's done in the bash script
        pass

    def setUp(self):
        self.audio_file = open("data/audio/BloodCalcification-NoMore.wav", 'rb')
        self.lyrics_file = open("data/lyrics/BloodCalcification-NoMore.txt", 'rb')

    def tearDown(self):
        self.audio_file.close()
        self.lyrics_file.close()

    def test_translate_success(self):
        target_url = f"{self.base_url}/translate?access_code=''"
        files = {
            'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
            'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
        }
        try:
            response = requests.post(
                target_url,
                files=files,
                headers=self.host_header,
                timeout=1200,
                verify=self.ssl_verify
            )
            response.raise_for_status() # Raise HTTPError for bad responses

            # Parse the JSON response
            response_data = response.json()
            self.assertEqual(response.status_code, 200)

            # Extract words from the lyrics file
            # Ensure all are included in the final mapped_result
            original_lyrics_lines = process_transcript("data/lyrics/BloodCalcification-NoMore.txt")

            self.assertEqual(len(original_lyrics_lines), len(response_data), "Number of lines in original lyrics and mapped result do not match.")

            # Assert the presence and order of words within each line
            for i, original_line in enumerate(original_lyrics_lines):
                if i < len(response_data):
                    mapped_line = response_data[i]
                    mapped_words_in_line = [item['word'].lower().strip(".,!?;:") for item in mapped_line]

                    self.assertEqual(len(original_line), len(mapped_words_in_line),
                                     f"Number of words in line {i+1} does not match.")

                    for j, original_word in enumerate(original_line):
                        if j < len(mapped_words_in_line):
                            self.assertEqual(original_word, mapped_words_in_line[j],
                                             f"Word mismatch in line {i+1}, position {j+1}: "
                                             f"Expected '{original_word}', got '{mapped_words_in_line[j]}'.")
                        else:
                            self.fail(f"Mapped result for line {i+1} is shorter than expected.")

        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")

        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON response: {e}")

    def test_translate_without_access_code(self):
        """Test no access granted to those without code"""
        target_url = f"{self.base_url}/translate"
        files = {
            'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
            'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
        }
        response = requests.post(
            target_url,
            files=files,
            headers=self.host_header,
            timeout=1200,
            verify=self.ssl_verify
        )
        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Access Denied. Please provide a valid access code.")

    # def test_translate_mfa_error(self):
    #     # Mock mfa error response
    #     files = {
    #             'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
    #             'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
    #     }
    #     mock_mfa_error = {"error": "MFA alignment service unavailable"}
    #
    #     with requests_mock.Mocker() as m:
    #         # Mock the /align endpoint to simulate an MFA error
    #         m.post("http://mfa-service:24725/align", json=mock_mfa_error, status_code=500)
    #
    #         # Call the /translate endpoint
    #         response = requests.post(self.flask_url, files=files, timeout=1200)
    #
    #         self.assertEqual(response.status_code, 500)
    #         response_data = response.json()
    #
    #         self.assertIn("error", response_data)
    #         self.assertEqual(response_data["error"], mock_mfa_error["error"])
    #
    # def test_translate_demucs_error(self):
    #     # Mock demucs error
    #     files = {
    #             'audio': ('data/audio/BloodCalcification-NoMore.wav', self.audio_file, 'audio/wav'),
    #             'lyrics': ('data/lyrics/BloodCalcification-NoMore.txt', self.lyrics_file, 'text/plain')
    #     }
    #     mock_demucs_error = {"error": "Demucs split service unavailable"}
    #     with requests_mock.Mocker() as m:
    #         m.post("http://demucs-service:22227/separate", json=mock_demucs_error, status_code=500)
    #
    #         # Ensure /align endpoint is not called by checking history
    #         m.post("http://mfa-service:24725/align", status_code=200)
    #         m.post("http://mfa-service:24725/align", status_code=500)
    #
    #         # Call the /translate endpoint
    #         response = requests.post("http://locahost:30276/translate", files=files, timeout=1200)
    #
    #         self.assertEqual(response.status_code, 500)
    #         response_data = response.json()
    #
    #         self.assertIn("error", response_data)
    #         self.assertEqual(response_data["error"], mock_demucs_error["error"])
    #
    #         # Assert that /align endpoint was not called
    #         history = m.request_history
    #         align_calls = [req for req in history if req.url == "http://mfa-service:24625/align"]
    #         self.assertEqual(len(align_calls), 0, "The /align endpoint should not have been called.")

    def test_main_deployment(self):
        # Test the musictranslator.main Flask app deployment and service
        response = requests.get(
            f"{self.base_url}/translate/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'OK')
        self.assertEqual(response.json().get('message'), 'Music Translator is running')

    def test_align_deployment(self):
        # test the align deployment and service
        response = requests.get(
            f"{self.base_url}/align/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('OK', response.text)

    def test_separator_deployment(self):
        # test the separator deployment and service
        response = requests.get(
            f"{self.base_url}/separate/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('OK', response.text)

    # Add more tests for other scenarios
