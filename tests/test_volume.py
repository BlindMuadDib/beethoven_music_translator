"""
Test suite for the volume analysis endpoint
"""

import unittest
from unittest.mock import patch, MagicMock
import requests

import musictranslator.musicprocessing
from musictranslator.musicprocessing.volume import request_volume_analysis, VOLUME_SERVICE_URL

class TestVolumeClient(unittest.TestCase):

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_success(self, mock_post):
        """Test a successful post to the volume client"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        # The expected structure is a JSON dictionary containing an overall RMS array and an RMS array for each instrument
        expected_rms = {
            "overall_rms": [
                [0.00, 0.15],
                [0.02, 0.18],
                [0.04, 0.25],
            ],
            "instruments": {
                "bass": {
                    "rms_values": [
                        [0.00, 0.08],
                        [0.02, 0.09],
                        [0.04, 0.15],
                    ]
                },
                "drums": {
                    "rms_values": [
                        [0.00, 0.12],
                        [0.02, 0.14],
                        [0.04, 0.22],
                    ]
                },
                "guitar": {
                    "rms_values": [
                        [0.00, 0.05],
                        [0.02, 0.10],
                        [0.04, 0.20],
                    ]
                },
                "other": {
                    "rms_values": [
                        [0.00, 0.10],
                        [0.02, 0.22],
                        [0.04, 0.17],
                    ]
                },
                "piano": {
                    "rms_values": [
                        [0.00, 0.07],
                        [0.02, 0.10],
                        [0.04, 0.09],
                    ]
                },
                "vocals": {
                    "rms_values": [
                        [0.00, 0.20],
                        [0.02, 0.18],
                        [0.04, 0.17],
                    ]
                }
            }
        }

        mock_response.json.return_value = expected_rms
        mock_post.return_value = mock_response

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }

        result = request_volume_analysis(data)
        self.assertEqual(result, expected_rms)
        mock_post.assert_called_once_with(
            VOLUME_SERVICE_URL,
            json={
                "data": {
                    "song": "/shared-data/audio/test_song.wav",
                    "vocals": "/shared-data/test_job/stems/vocals.wav",
                    "bass": "/shared-data/test_job/stems/bass.wav",
                    "other": "/shared-data/test_job/stems/other.wav",
                    "drums": "/shared-data/test_job/stems/drums.wav",
                    "guitar": "/shared-data/test_job/stems/guitar.wav",
                    "piano": "/shared-data/test_job/stesms/piano.wav"
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=1200
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_http_failure(self, mock_post):
        """Test an http failure after post request"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        # Configure raise_for_status to raise an HTTP Error for this
        http_error = requests.exceptions.HTTPError(response=mock_response)

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }
        result = request_volume_analysis(data)

        self.assertIn("error", result)
        self.assertIn("HTTP error occurred calling Volume service:  - Response: Internal Server Error", result["error"])
        self.assertEqual(result.get("status_code"), 500)
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_request_failure(self, mock_post):
        """Test a request failure"""
        mock_post.side_effect = requests.exceptions.RequestException("Request failed")

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }
        result = request_volume_analysis(data)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Request exception calling Volume service: Request failed")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_connection_error(self, mock_post):
        """Test a failure to connect to the volume service"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }
        result = request_volume_analysis(data)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Connection error calling Volume service: Connection refused")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_timeout_error(self, mock_post):
        """Test timeout throws the correct error"""
        mock_post.side_effect = requests.exceptions.Timeout("Timed out")

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }
        result = request_volume_analysis(data)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Timeout calling Volume service: Timed Out")
        mock_post.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_value_error(self, mock_post):
        """Test a value error from RMS"""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        json_err_msg = "Invalid JSON received"
        mock_response.json.side_effect = ValueError(json_err_msg, "doc", 0)
        mock_post.return_value = mock_response

        data = {
            "song": "/shared-data/audio/test_song.wav",
            "vocals": "/shared-data/test_job/stems/vocals.wav",
            "bass": "/shared-data/test_job/stems/bass.wav",
            "other": "/shared-data/test_job/stems/other.wav",
            "drums": "/shared-data/test_job/stems/drums.wav",
            "guitar": "/shared-data/test_job/stems/guitar.wav",
            "piano": "/shared-data/test_job/stesms/piano.wav"
        }
        result = request_volume_analysis(data)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Error decoding JSON response from Volume service: ('Invalid JSON received', 'doc', 0)")
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_missing_data(self, mock_post):
        """Test the service gracefully fails when no data is submitted"""
        result = request_volume_analysis({})
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No audio or stems provided for Volume analysis")

    @patch('musictranslator.musicprocessing.volume.requests.post')
    def test_rms_none_data(self, mock_post):
        """Test the service gracefully fails when data is submitted as None"""
        result = request_volume_analysis(None)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No audio or stems provided for Volume analysis")

