"""
Test suite for the F0.py module
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing import harmonic
from musictranslator.musicprocessing.harmonic import request_harmonic_analysis, HARMONIC_SERVICE_URL

class TestHarmonicClient(unittest.TestCase):

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_success(self, mock_post):
        """Test successful harmonic request"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        # The harmonic service returns a dict of dictionaries (or None for individual stems)
        expected_harmonic_data = {
            "full_track_analysis": {
                "duration": 0.5,
                "tempo": 136,
                "rms_overall": {
                    "times": [0.1, 0.2, 0.3],
                    "values": [0.88, 0.99, 0.94]
                }
            },
            "stem_analyses": {
                "vocals": {
                    "f0_data": {
                        "times": [0.1, 0.2, 0.3],
                        "f0_values": [440, 660, 880],
                    },
                    "spectral_features": {
                        "times": [0.1, 0.2, 0.3],
                        "frequencies": [880, 1320, 1760],
                        "spectrogram": [1000, 500, 4000],
                        "rms": [0.84, 0.43, 0.91],
                        "spectral_centroid": [1200, 4500, 3000],
                        "spectral_bandwidth": [2000, 800, 1600],
                        "spectral_rolloff": [1600, 3200, 100],
                        "spectral_flatness": [100, 50, 22],
                    },
                    "timbral_features": {
                        "mfccs": [-150, -100, -95, -60, -40, -30, -20, -10, -5, -1, -0.99, -0.60, -0.01],
                        "chroma_stft": [44, 22],
                    },
                    "temporal_features": {
                        "onsets": [0.1],
                        "tempo": 136.0,
                        "beats": [0.1],
                    }
                },
                "bass": {
                    "f0_data": {
                        "times": [0.1, 0.2, 0.3],
                        "f0_values": [None, 80, 100],
                    },
                    "spectral_features": {
                        "times": [0.1, 0.2, 0.3],
                        "frequencies": [None, 220, 300],
                        "spectrogram": [None, 400, 500],
                        "rms": [0.0, 0.5, 0.4],
                        "spectral_centroid": [None, 1200, 2200],
                        "spectral_bandwidth": [None, 500, 1000],
                        "spectral_rolloff": [None, 2200, 4500],
                        "spectral_flatness": [None, 8000, 8000],
                    },
                    "timbral_features": {
                        "mfccs": [-100, -90, -55, -44, -22, -11, -4, -2, -0.98, -0.77, -0.64, -0.2, -0.004],
                        "chroma_stft": [None, 3000, 222],
                    },
                    "temporal_features": {
                        "onsets": [0.2],
                        "tempo": 136.0,
                        "beats": [0.2],
                    }
                },
                "other": None # Example where 'other' might have no F0 data
            }
        }
        mock_response.json.return_value = expected_harmonic_data
        mock_post.return_value = mock_response

        full_track_path = "/shared-data/test_job1/full_track.wav"
        stem_paths = {
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav" # Will be filtered out
        }

        result = request_harmonic_analysis(stem_paths, full_track_path)
        self.assertEqual(result, expected_harmonic_data)
        mock_post.assert_called_once_with(
            HARMONIC_SERVICE_URL,
            json={
                "stem_paths": {
                    "vocals": "/shared-data/test_job/stems/vocals.wav",
                    "bass": "/shared-data/test_job/stems/bass.wav",
                    "other": "/shared-data/test_job/stems/other.wav"
                },
                "full_track_path": full_track_path
            },
            headers={"Content-Type": "application/json"},
            timeout=1200
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_failure_http(self, mock_post):
        """Test a harmonic service http failure"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        # Configure raise_for_status to raise an HTTPError with this response
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(stem_paths, full_track_path)

        self.assertIn("error", result)
        self.assertIn("HTTP error occurred calling Harmonic service:  - Response: Internal Server Error", result["error"])
        self.assertEqual(result.get("status_code"), None) # Returning None
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_failure_request(self, mock_post):
        """Test a harmonic service request failure"""
        mock_post.side_effect = requests.exceptions.RequestException("Request failed")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(stem_paths, full_track_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Request exception calling Harmonic service: Request failed")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_connection_error(self, mock_post):
        """Test a harmonic service connection failure"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(stem_paths, full_track_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Connection error calling Harmonic service: Connection refused")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_failure_timeout(self, mock_post):
        """Test a harmonic service timeout failure"""
        mock_post.side_effect = requests.exceptions.Timeout("Timed Out")

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(stem_paths, full_track_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Timeout calling Harmonic service: Timed Out")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.harmonic.requests.post')
    def test_harmonic_value_error(self, mock_post):
        """Test a harmonic service value error"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        json_err_msg = "Invalid JSON received"
        mock_response.json.side_effect = ValueError(json_err_msg, "doc", 0)
        mock_post.return_value = mock_response

        stem_paths = {"vocals": "/path/to/vocals.wav"}
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(stem_paths, full_track_path)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Error decoding JSON response from harmonic service: ('Invalid JSON received', 'doc', 0)")
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    def test_request_harmonic_analysis_invalid_full_track_path(self):
        """Test calling with an invalid full_track_path"""
        stem_paths = {"vocals": "/path/to/vocals.wav"}
        result_none = request_harmonic_analysis(stem_paths, None)
        self.assertIn("error", result_none)
        self.assertEqual(result_none["error"], "No full track path provided for Harmonic analysis.")

    def test_request_harmonic_analysis_empty_input_stems(self):
        """Test calling with an empty dictionary for stem paths"""
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis({}, full_track_path)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No stem paths provided for Harmonic analysis.")

    def test_request_harmonic_analysis_none_input_stems(self):
        """Test calling with None for stem paths"""
        full_track_path = "/path/to/full/track.wav"
        result = request_harmonic_analysis(None, full_track_path)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No stem paths provided for Harmonic analysis.")

    def test_request_harmonic_analysis_no_relevant_stems_after_filter(self):
        """Test when input stems are all filtered out (e.g., only drums or invalid paths)."""
        stem_paths = {
            "drums": "/shared-data/test_job/stems/drums.wav",
            "another_drums": "/shared-data/test_job/stems/another_drum.wav",
            "invalid_instrument": None
        }
        full_track_path = "/path/to/full/track.wav"
        # request_harmonic_analysis should not call requests.post if payload_stems is empty
        with patch('musictranslator.musicprocessing.harmonic.requests.post') as mock_post_filtered:
            result = request_harmonic_analysis(stem_paths, full_track_path)
            self.assertIn("info", result)
            self.assertEqual(result["info"], "No relevant stems were submitted for Harmonic analysis.")
            mock_post_filtered.assert_not_called()

    def test_request_harmonic_analysis_skips_drums_and_invalid_paths(self):
        """Test that drums are skipped and only valid paths for relevant instruments are sent."""
        stem_paths = {
            "vocals": "/shared-data/vocals.wav",
            "drums": "/shared-data/drums.wav",
            "bass": "/shared-data/bass.wav",
            "guitar": "/shared-data/guitar.wav",
            "piano": None, # Invalid path
            "other": "" # Empty path
        }
        full_track_path = "/shared-data/audio/full_track.wav"
        expected_payload = {
            "stem_paths": {
                "vocals": "/shared-data/vocals.wav",
                "bass": "/shared-data/bass.wav",
                "guitar": "/shared-data/guitar.wav"
                # drums, piano and other should be excluded
            },
            "full_track_path": full_track_path
        }
        # Mock successful response
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"vocals": [], "bass": [], "guitar": []}

        with patch('musictranslator.musicprocessing.harmonic.requests.post', return_value=mock_response) as mock_post:
            request_harmonic_analysis(stem_paths, full_track_path)
            mock_post.assert_called_once_with(
                HARMONIC_SERVICE_URL,
                json=expected_payload,
                headers={"Content-Type": "application/json"},
                timeout=1200
            )
