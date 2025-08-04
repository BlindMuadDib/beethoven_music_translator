import os
import json
import shutil
import unittest
import numpy as np
import soundfile as sf
from musictranslator.harmonic_service.app import app as harmonic_service_app

# Directory for temporary test audio files specific to this test suite
TEST_ENDPOINT_AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'temp_f0_endpoint_audio')
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

class TestFundFreqServiceEndpoint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test client and create test audio files."""
        if harmonic_service_app:
            cls.client = harmonic_service_app.test_client()
            harmonic_service_app.config['TESTING'] = True
        else:
            raise unittest.SkipTest("Skipping Harmonic service tests: Flask app not loaded.")

        # Create shared test audio files
        cls.vocals_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR, 'vocals_test.wav')
        cls.bass_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR, 'bass_test.wav')
        cls.guitar_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR, 'guitar_test.wav')
        cls.silent_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR, 'silent_test.wav')
        cls.non_existent_file = os.path.join(TEST_ENDPOINT_AUDIO_DIR, 'non_existent_test.wav')

        create_sine_wave_file(cls.vocals_file, freq=440.0)  # A4 note
        create_sine_wave_file(cls.bass_file, freq=110.0)    # A2 note
        create_sine_wave_file(cls.guitar_file, freq=440.0)  # A4 note
        create_silent_file(cls.silent_file)

        # Ensure non_existent_file does not exist for testing that case
        if os.path.exists(cls.non_existent_file):
            os.remove(cls.non_existent_file)

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary test audio directory."""
        if os.path.exists(TEST_ENDPOINT_AUDIO_DIR):
            shutil.rmtree(TEST_ENDPOINT_AUDIO_DIR)

    def test_health_check(self):
        """Test the /harmonic/health endpoint."""
        response = self.client.get('/harmonic/health')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'OK')
        self.assertIn("Harmonic Analysis service is running",
                      json_data['message'])

    def test_analyze_all_success_multiple_stems(self):
        """Test successful F0 analysis for multiple valid stems."""
        payload = {
            "stem_paths": {
                "vocals": self.vocals_file,
                "bass": self.bass_file,
                "guitar": self.guitar_file,
            }
        }
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        results = response.get_json()

        # Check for each instrument and its nested structure
        for instrument in ["vocals", "bass", "guitar"]:
            self.assertIn(instrument, results)
            instrument_result = results[instrument]
            self.assertIsInstance(instrument_result, dict)

            # Check for top-level feature keys
            self.assertIn("f0_data", instrument_result)
            self.assertIn("spectral_features", instrument_result)
            self.assertIn("timbral_features", instrument_result)
            self.assertIn("temporal_features", instrument_result)

            # Check for sub-keys within spectral_features
            spectral_data = instrument_result["spectral_features"]
            self.assertIn("spectrogram", spectral_data)
            self.assertIsInstance(spectral_data["spectrogram"], list)
            self.assertIn("rms", spectral_data)
            self.assertIsInstance(spectral_data["rms"], list)
            self.assertIn("spectral_centroid", spectral_data)
            self.assertIn("spectral_bandwidth", spectral_data)
            self.assertIn("spectral_rolloff", spectral_data)
            self.assertIn("spectral_flatness", spectral_data)

            # Check for sub-keys within timbral_features
            timbral_data = instrument_result["timbral_features"]
            self.assertIn("mfccs", timbral_data)
            self.assertIn("chroma_stft", timbral_data)

            # Check for sub-keys within temporal_features
            temporal_data = instrument_result["temporal_features"]
            self.assertIn("onsets", temporal_data)
            self.assertIsInstance(temporal_data["onsets"], list)
            self.assertIn("beats", temporal_data)
            self.assertIsInstance(temporal_data["beats"], list)
            self.assertIn("tempo", temporal_data)
            self.assertIsInstance(temporal_data["tempo"], float)

    def test_analyze_all_silent_stem(self):
        """Test a stem that is silent (should result in null data)."""
        payload = {"stem_paths": {"vocals": self.silent_file}}
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 200)
        results = response.get_json()
        self.assertIn("vocals", results)
        self.assertIsNone(
            results["vocals"],
            "Analysis for a silent stem should return None"
        )

    def test_analyze_all_non_existent_stem(self):
        """Test a stem path that does not exist."""
        payload = {"stem_paths": {"guitar": self.non_existent_file}}
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 200)
        results = response.get_json()
        self.assertIn("guitar", results)
        self.assertIsNone(results["guitar"], "Analysis for non-existent file should be None")

    def test_analyze_all_empty_stem_paths(self):
        """Test with an empty stem_paths dictionary."""
        payload = {"stem_paths": {}}
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 200)
        results = response.get_json()
        self.assertEqual(results, {})

    def test_analyze_all_missing_stem_paths_key(self):
        """Test request body missing the 'stem_paths' key."""
        payload = {"some_other_key": "value"}
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 400)
        error_data = response.get_json()
        self.assertIn("error", error_data)
        self.assertEqual(error_data["error"], "Missing 'stem_paths' in request body")

    def test_analyze_f0_stem_paths_not_a_dict(self):
        """Test when 'stem_paths' is not a dictionary."""
        payload = {"stem_paths": "not_a_dictionary"}
        response = self.client.post('/api/analyze_harmonic', json=payload)
        self.assertEqual(response.status_code, 400)
        error_data = response.get_json()
        self.assertIn("error", error_data)
        self.assertEqual(error_data["error"], "'stem_paths' must be a dictionary")

    def test_analyze_f0_not_json_request(self):
        """Test sending a request that is not application/json."""
        response = self.client.post('/api/analyze_harmonic', data="this is not json")
        self.assertEqual(response.status_code, 415)
        error_data = response.get_json()
        self.assertIn("error", error_data)
        self.assertEqual(error_data["error"], "Invalid request: Content-Type must be application/json")
