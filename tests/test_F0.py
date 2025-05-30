"""
Test suite for the F0.py module
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing import F0
from musictranslator.musicprocessing.F0 import request_f0_analysis, F0_SERVICE_URL

class TestF0Client(unittest.TestCase):

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_success(self, mock_post):
        """Test successful F0 request"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        # The F0 service returns a dict of lists (or None for individual stems)
        expected_f0_data = {
            "vocals": {
                "times": [0.0, 0.01, 0.02],
                "f0_values": [220.0, 220.5, None], #np.nan becomes None in JSON
                "time_interval": 0.01
            },
            "bass": {
                "times": [0.0, 0.01],
                "f0_values": [110.0, 110.1],
                "time_interval": 0.01
            },
            "other": None # Example where 'other' might have no F0 data
        }
        mock_response.json.return_value = expected_f0_data
        mock_post.return_value = mock_response

        stem_paths = {
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav" # Will be filtered out
        }

        result = request_f0_analysis(stem_paths)
        self.assertEqual(result, expected_f0_data)
        mock_post.assert_called_once_with(
            F0_SERVICE_URL,
            json={
                "stem_paths": {
                    "vocals": "/shared-data/test_job/stems/vocals.wav",
                    "bass": "/shared-data/test_job/stems/bass.wav",
                    "other": "/shared-data/test_job/stems/other.wav"
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=1200
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_failure_http(self, mock_post):
        """Test a f0 service http failure"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        # Configure raise_for_status to raise an HTTPError with this response
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result = request_f0_analysis(stem_paths)

        self.assertIn("error", result)
        self.assertIn("HTTP error occurred calling F0 service:  - Response: Internal Server Error", result["error"])
        self.assertEqual(result.get("status_code"), None) # Returning None
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_failure_request(self, mock_post):
        """Test a f0 service request failure"""
        mock_post.side_effect = requests.exceptions.RequestException("Request failed")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result = request_f0_analysis(stem_paths)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Request exception calling F0 service: Request failed")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_connection_error(self, mock_post):
        """Test a f0 service connection failure"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result = request_f0_analysis(stem_paths)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Connection error calling F0 service: Connection refused")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_failure_timeout(self, mock_post):
        """Test a f0 service timeout failure"""
        mock_post.side_effect = requests.exceptions.Timeout("Timed Out")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result = request_f0_analysis(stem_paths)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Timeout calling F0 service: Timed Out")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.F0.requests.post')
    def test_f0_value_error(self, mock_post):
        """Test a f0 service value error"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        json_err_msg = "Invalid JSON received"
        mock_response.json.side_effect = ValueError(json_err_msg, "doc", 0)
        mock_post.return_value = mock_response

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result = request_f0_analysis(stem_paths)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Error decoding JSON response from F0 service: ('Invalid JSON received', 'doc', 0)")
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    def test_request_f0_analysis_empty_input_stems(self):
        """Test calling with an empty dictionary for stem paths"""
        result = request_f0_analysis({})
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No stem paths provided for F0 analysis.")

    def test_request_f0_analysis_none_input_stems(self):
        """Test calling with None for stem paths"""
        result = request_f0_analysis(None)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No stem paths provided for F0 analysis.")

    def test_request_f0_analysis_no_relevant_stems_after_filter(self):
        """Test when input stems are all filtered out (e.g., only drums or invalid paths)."""
        stem_paths = {
            "drums": "/shared-data/test_job/stems/drums.wav",
            "another_drums": "/shared-data/test_job/stems/another_drum.wav",
            "invalid_instrument": None
        }
        # request_f0_analysis should not call requests.post if payload_stems is empty
        with patch('musictranslator.musicprocessing.F0.requests.post') as mock_post_filtered:
            result = request_f0_analysis(stem_paths)
            self.assertIn("info", result)
            self.assertEqual(result["info"], "No relevant stems were submitted for F0 analysis.")
            mock_post_filtered.assert_not_called()

    def test_request_f0_analysis_skips_drums_and_invalid_paths(self):
        """Test that drums are skipped and only valid paths for relevant instruments are sent."""
        stem_paths = {
            "vocals": "/shared-data/vocals.wav",
            "drums": "/shared-data/drums.wav",
            "bass": "/shared-data/bass.wav",
            "guitar": "/shared-data/guitar.wav",
            "piano": None, # Invalid path
            "other": "" # Empty path
        }
        expected_payload = {
            "stem_paths": {
                "vocals": "/shared-data/vocals.wav",
                "bass": "/shared-data/bass.wav",
                "guitar": "/shared-data/guitar.wav"
                # drums, piano and other should be excluded
            }
        }
        # Mock successful response
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"vocals": [], "bass": [], "guitar": []}

        with patch('musictranslator.musicprocessing.F0.requests.post', return_value=mock_response) as mock_post:
            request_f0_analysis(stem_paths)
            mock_post.assert_called_once_with(
                F0_SERVICE_URL,
                json=expected_payload,
                headers={"Content-Type": "application/json"},
                timeout=1200
            )
