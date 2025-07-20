"""
Test suite for musictranslator/musicprocessing/drums.py
"""

import json
import unittest
from unittest.mock import MagicMock, patch
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing import drums
from musictranslator.musicprocessing.drums import request_drum_analysis, DRUMS_SERVICE_URL

class TestDrumsClient(unittest.TestCase):

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_success(self, mock_post):
        """Test a successful post and response"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200

        expected_drums_data = [
            {
                "onset_time": 0.5,
                "duration": 0.1,
                "relative_volume": 0.123,
                "dominant_frequency": 440.0,
                "spectral_centroid": 500.0,
                "spectral_rolloff": 1500.0,
                "spectral_flux": 0.05,
                "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
            },
            {
                "onset_time": 1.2,
                "duration": 0.08,
                "relative_volume": 0.098,
                "dominant_frequency": 220.0,
                "spectral_centroid": 300.0,
                "spectral_rolloff": 1000.0,
                "spectral_flux": 0.03,
                "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
            }
        ]
        mock_response.json.return_value = expected_drums_data
        mock_post.return_value = mock_response

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)
        self.assertEqual(result, expected_drums_data)
        mock_post.assert_called_once_with(
            DRUMS_SERVICE_URL,
            json={"drums_path": drums_path},
            headers={'Content-Type': 'application/json'},
            timeout=500
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_http_failure(self, mock_post):
        """Tests the drums endpoint when there is an http failure"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)

        self.assertIn("error", result)
        self.assertIn("HTTP error occurred calling Drums Service:  - Response: Internal Server Error", result["error"])
        self.assertEqual(result.get("status_code"), 500)
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_request_failure(self, mock_post):
        """Test drums endpoint when the request fails"""
        mock_post.side_effect = requests.exceptions.RequestException("Request failed")

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Request exception calling Drums Service: Request failed")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_connection_error(self, mock_post):
        """Test drums endpoint with connection error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Connection error calling Drums Service: Connection refused")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_timeout_failure(self, mock_post):
        """Test drums endpoint when it times out"""
        mock_post.side_effect = requests.exceptions.Timeout("Timed out")

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Timeout calling Drums Service: Timed out")

    @patch('musictranslator.musicprocessing.drums.requests.post')
    def test_drums_value_error(self, mock_post):
        """Test drums endpoint when it returns invalid JSON"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        json_err = "Invalid JSON received"
        mock_response.json.side_effect = ValueError(json_err, "doc", 0)
        mock_post.return_value = mock_response

        drums_path = "/shared-data/test_job/drums.wav"
        result = request_drum_analysis(drums_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Error decoding JSON response from Drums Service: ('Invalid JSON received', 'doc', 0)")
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    def test_drums_empty_path(self):
        """Test drums endpoint when drums_path is empty"""
        result = request_drum_analysis([])
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No drums path provided for Drum analysis.")

    def test_drums_none_path(self):
        """Test drums endpoint when drums_path is None"""
        result = request_drum_analysis(None)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No drums path provided for Drum analysis.")
