import os
import json
import shutil
import unittest
import uuid
import tempfile
import numpy as np
import soundfile as sf
from unittest.mock import patch, MagicMock, mock_open
from musictranslator.harmonic_service.app import app as harmonic_service_app

# Directory for temporary test audio files specific to this test suite
TEST_ENDPOINT_AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'temp_harmonic_endpoint_audio')
SAMPLE_RATE = 44100 # Standard sample rate

# --- Helper Functions ---

def create_sine_wave_file(filepath, freq, duration=0.5, samplerate=SAMPLE_RATE):
    """Helper to create a sine wave audio file for testing."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * freq * t)
    sf.write(filepath, wave, samplerate)

def create_silent_file(filepath, duration=0.5, samplerate=SAMPLE_RATE):
    """Helper to create a silent audio file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    silent_audio = np.zeros(int(samplerate * duration))
    sf.write(filepath, silent_audio, samplerate)

# --- End Helper Functions ---

class TestHarmonicServiceEndpoint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test client and create test audio files."""
        if harmonic_service_app:
            cls.client = harmonic_service_app.test_client()
        else:
            cls.clent = None
            return

        # Create a temporary directory for test results
        cls.temp_results_dir = tempfile.TemporaryDirectory()

        # Path the RESULTS_BASE_PATH to point to the temp directory
        cls.patcher = patch('musictranslator.harmonic_service.app.RESULTS_BASE_PATH',
                            cls.temp_results_dir.name)
        cls.patcher.start()

        # Create shared test audio files
        os.makedirs(TEST_ENDPOINT_AUDIO_DIR, exist_ok=True)

        # File paths...
        cls.vocals_file = os.path.join(
            TEST_ENDPOINT_AUDIO_DIR,
            'vocals_test.wav'
        )
        cls.bass_file = os.path.join(
            TEST_ENDPOINT_AUDIO_DIR,
            'bass_test.wav'
        )
        cls.guitar_file = os.path.join(
            TEST_ENDPOINT_AUDIO_DIR,
            'guitar_test.wav'
        )
        cls.full_track_file = os.path.join(
            TEST_ENDPOINT_AUDIO_DIR,
            'full_track_test.wav'
        )
        # Create a specific file for the invalid job ID test
        cls.test_invalid_job_id_track_file = os.path.join(
            TEST_ENDPOINT_AUDIO_DIR,
            'fulltracktest.wav')

        # Create audio content...
        create_sine_wave_file(cls.vocals_file,
                              freq=440.0)   # A4 note
        create_sine_wave_file(cls.bass_file,
                              freq=110.0)   # A2 note
        create_sine_wave_file(cls.guitar_file,
                              freq=440.0)   # A4 note
        create_sine_wave_file(cls.full_track_file,
                              freq=220.0)   # A3 note
        # Copy the content for the invalid job id file
        shutil.copyfile(cls.full_track_file,
                        cls.test_invalid_job_id_track_file)

    @classmethod
    def tearDownClass(cls):
        """Clean up test resources after all done."""
        # Stop the patcher
        cls.patcher.stop()
        # Clean up the temporary results directory
        cls.temp_results_dir.cleanup()
        # Clean up the test audio files
        if os.path.exists(TEST_ENDPOINT_AUDIO_DIR):
            shutil.rmtree(TEST_ENDPOINT_AUDIO_DIR)

    def test_empty_request(self):
        """Test sending an empty request body."""
        response = self.client.post('/api/analyze_harmonic', json={})
        self.assertEqual(response.status_code, 400)
        error_data = response.get_json()
        self.assertIn("error", error_data)
        self.assertIn("Request body cannot be empty",
                      error_data['error'])

    def test_health_check(self):
        """Test the /harmonic/health endpoint."""
        response = self.client.get('/harmonic/health')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'OK')
        self.assertIn("Harmonic Analysis service is running",
                      json_data['message'])

    def test_valid_request_returns_202_and_url(self):
        """
        Test that a valid request returns a 202 Accepted status
        and a JSON response with only results_url.
        """
        # Generate a unique job ID to ensure test isolation
        job_id = str(uuid.uuid4())
        # Use a file path that includes the job_id
        full_track_with_job_id = os.path.join(TEST_ENDPOINT_AUDIO_DIR,
                                              f'{job_id}_full_track.wav')
        shutil.copyfile(self.full_track_file,
                        full_track_with_job_id)

        # Create a payload with the new file path
        payload = {
            "full_track_path": full_track_with_job_id,
            "stem_paths": {
                "vocals": self.vocals_file,
                "bass": self.bass_file
            }
        }

        response = self.client.post('/api/analyze_harmonic',
                                    json=payload)

        # Clean up the dummy file
        os.remove(full_track_with_job_id)

        self.assertEqual(response.status_code, 202)
        json_data = response.get_json()
        self.assertIn('results_url', json_data)
        expected_url = f"/api/results/{job_id}_harmonic.json"
        self.assertEqual(json_data["results_url"], expected_url)

    @patch('musictranslator.harmonic_service.app.os.makedirs')
    def test_valid_request_saves_static_metadata_to_disk(self, mock_makedirs):
        """
        Test that a valid request correctly saves the analysis results
        to a JSON file on the mocked disk.
        """
        job_id = str(uuid.uuid4())
        full_track_with_job_id = os.path.join(TEST_ENDPOINT_AUDIO_DIR,
                                              f'{job_id}_full_track.wav')
        shutil.copyfile(self.full_track_file, full_track_with_job_id)

        mock_file_path = os.path.join(self.temp_results_dir.name,
                                      f"{job_id}_harmonic.json")

        # Use MagicMock to simulate the file object
        m = mock_open()
        with patch('musictranslator.harmonic_service.app.open', m):

            payload = {
                "full_track_path": full_track_with_job_id,
                "stem_paths": {
                    "vocals": self.vocals_file
                }
            }
            response = self.client.post('/api/analyze_harmonic',
                                        json=payload)

            # Assert that open was called with the correct path and
            # mode
            m.assert_called_once_with(mock_file_path, 'w')

            # Get the mock file handle
            handle = m()

            # The json.dump function may call write() multiple times,
            # so we join the content from all calls.
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)
            dump_args = json.loads(written_content)

            self.assertIn("job_id", dump_args)
            self.assertEqual(dump_args["job_id"], job_id)

            # Assert that the full_track analysis data was saved
            self.assertIn('full_track_analysis', dump_args)
            self.assertIn('duration',
                          dump_args['full_track_analysis'])

            # Assert that the stem analysis data was saved
            self.assertIn('stem_analyses', dump_args)
            self.assertIn('vocals', dump_args['stem_analyses'])
            self.assertIn('tempo', dump_args['stem_analyses']['vocals'])

            # Assert that the large, time-series data is NOT in this file
            self.assertNotIn('f0_data', dump_args['stem_analyses']['vocals'])

        # Clean up the dummy file
        os.remove(full_track_with_job_id)

    def test_stream_ndjson_endpoint(self):
        """
        Test that the new NDJSON streaming endpoint correctly returns a
        stream of time-sliced JSON objects.
        """
        job_id = str(uuid.uuid4())
        # Use a short sine wave file for this test to speed it up
        temp_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR,
                                 f'{job_id}_test.wav')
        create_sine_wave_file(temp_file, freq=440.0, duration=1.0)

        # The streaming endpoint will receive the path via a query param
        stream_url = f"/api/results/stream/{job_id}_test.ndjson?stem_path={temp_file}"

        response = self.client.get(stream_url)
        os.remove(temp_file)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/x-ndjson')

        # Now, parse the response to ensure it's valid NDJSON
        decoded_data = response.data.decode('utf-8')
        lines = decoded_data.strip().split('\n')
        self.assertTrue(len(lines) > 0)

        for line in lines:
            try:
                data = json.loads(line)
                self.assertIsInstance(data, dict)
                # Check for some expected keys in each slice
                self.assertIn('time', data)
                self.assertIn('f0_data', data)
                self.assertIn('mfccs', data)
            except json.JSONDecodeError:
                self.fail("Response content is not valid NDJSON.")

    def test_missing_full_track_path_returns_error(self):
        """
        Test that a request with a missing full_track_path returns
        and error.
        """
        payload = {
            "stem_paths": {"vocals": self.vocals_file}
        }
        response = self.client.post('/api/analyze_harmonic',
                                    json=payload)
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('error', json_data)
        self.assertIn('full_track_path', json_data['error'])

    def test_missing_stem_paths_returns_error(self):
        """
        Test that a request with missing stem_paths returns an error.
        """
        payload = {
            "full_track_path": self.full_track_file
        }
        response = self.client.post('/api/analyze_harmonic',
                                    json=payload)
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('error', json_data)
        self.assertIn('stem_paths', json_data['error'])

    def test_invalid_job_id_format(self):
        """
        Test that a file path without a job_id returns an error.
        """
        payload = {
            "full_track_path": self.test_invalid_job_id_track_file,
            "stem_paths": {"vocals": self.vocals_file}
        }
        response = self.client.post('/api/analyze_harmonic',
                                    json=payload)
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('error', json_data)
        self.assertIn("Filename must be in the format <job_id>_",
                      json_data['error'])
