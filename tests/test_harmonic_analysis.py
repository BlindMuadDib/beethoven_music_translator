"""
This is a test file for the Harmonic analysis functions module
Each separated stem track is individually analyzed dynamically
Result will be a stream of frequencies for each instrument
"""
import unittest
import os
import numpy as np
import soundfile as sf
import librosa
from musictranslator.harmonic_service.analysis_functions import analyze_audio_features

# Define a directory for test audio files, relative to this test script
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'test_audio')
SAMPLE_RATE = 44100 # Standard sample rate

class TestFundFreq(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create neccessary dummy audio files for testing."""
        if not os.path.exists(TEST_AUDIO_DIR):
            os.makedirs(TEST_AUDIO_DIR)

        # 1. Silent audio file (short duration of zeros)
        cls.silent_file = os.path.join(TEST_AUDIO_DIR, 'silent.wav')
        silent_audio = np.zeros(int(0.1 * SAMPLE_RATE)) # 0.1 seconds of silence
        sf.write(cls.silent_file, silent_audio, SAMPLE_RATE)

        # 2. Audio file with a clear A4 sine wave (440 Hz)
        cls.a4_sine_file = os.path.join(TEST_AUDIO_DIR, 'a4_sine.wav')
        cls.known_freq_a4 = 440.0
        DURATION_A4 = 1.0 # 1 second
        t_a4 = np.linspace(0, DURATION_A4, int(SAMPLE_RATE * DURATION_A4), False)
        a4_sine_wave = 0.5 * np.sin(2 * np.pi * cls.known_freq_a4 * t_a4)
        sf.write(cls.a4_sine_file, a4_sine_wave, SAMPLE_RATE)

        # 3. Audio file with a clear C3 sine wave (approx 130.81 Hz)
        cls.c3_sine_file = os.path.join(TEST_AUDIO_DIR, 'c3_sine.wav')
        cls.known_freq_c3 = librosa.note_to_hz('C3')
        DURATION_C3 = 1.0 # 1 second
        t_c3 = np.linspace(0, DURATION_C3, int(SAMPLE_RATE * DURATION_C3), False)
        c3_sine_wave = 0.5 * np.sin(2 * np.pi * cls.known_freq_c3 * t_c3)
        sf.write(cls.c3_sine_file, c3_sine_wave, SAMPLE_RATE)

        # # Assign files for specific instrument tests (can be more varied later)
        # cls.vocals_file_success = cls.a4_sine_file
        # cls.guitar_file_success = cls.a4_sine_file
        # cls.bass_file_success = cls.c3_sine_file
        # # Drums are more complex
        # # Will implement later
        # # cls.drums_file_success = raise NotImplementedError
        # cls.piano_file_success = cls.a4_sine_file
        # cls.other_file_success = cls.a4_sine_file

        # 4. Non-existent file path
        cls.non_existent_file = os.path.join(TEST_AUDIO_DIR, 'non_existent_audio.wav')
        # Ensure it doesn't exist for the test
        if os.path.exists(cls.non_existent_file):
            os.remove(cls.non_existent_file)

        # 5. Corrupted audio file (a text file)
        cls.corrupted_file_dummy = os.path.join(TEST_AUDIO_DIR, 'corrupted_audio.txt')
        with open(cls.corrupted_file_dummy, 'w') as f:
            f.write("This is not a valid audio file content.")

        # 6. Very short audio file (might be too short for analysis)
        cls.very_short_file = os.path.join(TEST_AUDIO_DIR, 'very_short.wav')
        SHORT_DURATION = 0.0001 # 0.0001 seconds, potentially too short
        t_short = np.linspace(0, SHORT_DURATION, int(SAMPLE_RATE * SHORT_DURATION), False)
        short_sine_wave = 0.5 * np.sin(2 * np.pi * cls.known_freq_a4 * t_short)
        sf.write(cls.very_short_file, short_sine_wave, SAMPLE_RATE)

    @classmethod
    def tearDownClass(cls):
        """Clean up dummy audio files and directory after all tests"""
        # List of files created by setUpClass
        files_to_remove = [
            cls.silent_file,
            cls.a4_sine_file,
            cls.c3_sine_file,
            cls.corrupted_file_dummy,
            cls.very_short_file
            # cls.non_existent_file is not created, so no need to remove
        ]
        for f_path in files_to_remove:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError as e:
                    print(f"Error removing file {f_path}: {e}")

        # Remove the test_audio directory if it's empty
        if os.path.exists(TEST_AUDIO_DIR):
            if not os.listdir(TEST_AUDIO_DIR):
                try:
                    os.rmdir(TEST_AUDIO_DIR)
                except OSError as e:
                    print(f"Error removing directory {TEST_AUDIO_DIR}: {e}")
                else:
                    print(f"Warning: {TEST_AUDIO_DIR} not removed because it's not empty.")

    # --- Helper Function ---

    def _assert_successful_analysis(self, result_dict, known_freq=None, tolerance_hz=15.0):
        """
        Helper method to assert that the full analysis result
        dictionary is valid.
        """
        self.assertIsInstance(result_dict, dict)

        # Check top-level keys
        self.assertIn("f0_data", result_dict)
        self.assertIn("spectral_features", result_dict)
        self.assertIn("timbral_features", result_dict)
        self.assertIn("temporal_features", result_dict)

        # Check f0_data structure and values
        f0_data = result_dict["f0_data"]
        self.assertIsInstance(f0_data, dict)
        self.assertIn("times", f0_data)
        self.assertIn("f0_values", f0_data)
        self.assertEqual(
            len(f0_data["times"]), len(f0_data["f0_values"])
        )
        self.assertTrue(
            any(f is not None for f in f0_data["f0_values"]),
            "Expected some voiced frames"
        )

        if known_freq:
            voiced_f0 = [f for f in f0_data["f0_values"] if f is not None]
            self.assertTrue(len(voiced_f0) > 0)
            mean_f0 = np.mean(voiced_f0)
            self.assertAlmostEqual(
                mean_f0, known_freq, delta=tolerance_hz,
                msg=f"Mean F0 ({mean_f0:.2f} Hz) not close to known F0 ({known_freq:.2f} Hz)"
            )

        # Check spectral_features
        spectral_features = result_dict["spectral_features"]
        self.assertIsInstance(spectral_features, dict)
        self.assertIn("spectrogram", spectral_features)
        self.assertIsInstance(spectral_features["spectrogram"], list)
        self.assertTrue(len(spectral_features["spectrogram"]) > 0)
        self.assertIn("rms", spectral_features)
        self.assertIsInstance(spectral_features["rms"], list)

        # Check timbral_features
        timbral_features = result_dict["timbral_features"]
        self.assertIsInstance(timbral_features, dict)
        self.assertIn("mfccs", timbral_features)
        self.assertIsInstance(timbral_features["mfccs"], list)
        self.assertTrue(len(timbral_features["mfccs"]) > 0)
        self.assertIn("chroma_stft", timbral_features)
        self.assertIsInstance(timbral_features["chroma_stft"], list)
        self.assertTrue(len(timbral_features["chroma_stft"]) > 0)

        # Check temporal_features
        temporal_features = result_dict["temporal_features"]
        self.assertIsInstance(temporal_features, dict)
        self.assertIn("onsets", temporal_features)
        self.assertIsInstance(temporal_features["onsets"], list)
        self.assertIn("beats", temporal_features)
        self.assertIsInstance(temporal_features["beats"], list)
        self.assertIn("tempo", temporal_features)
        self.assertIsInstance(temporal_features["tempo"], float)

    # --- "Success" Tests (using sine waves for predictability) ---
    def test_full_analysis_a4_sine_success(self):
        """Test a full analysis on a predictable A4 sine wave."""
        result = analyze_audio_features(self.a4_sine_file)
        self.assertIsNotNone(result)
        self._assert_successful_analysis(
            result, known_freq=self.known_freq_a4
        )

    def test_full_analysis_c3_sine_success(self):
        """Test a successful F0 analysis on a predictable C3 sine wave."""
        result = analyze_audio_features(self.c3_sine_file)
        self.assertIsNotNone(result)
        self._assert_successful_analysis(
            result, known_freq=self.known_freq_c3
        )

    # --- "No Audio" / Specific Condition Tests ---
    def test_fund_freq_silent_audio_returns_none(self):
        """Test that analysis of a silent audio track returns None."""
        response = analyze_audio_features(self.silent_file)
        self.assertIsNone(
            response, "Analysis of silent audio should return None"
        )

    def test_fund_freq_very_short_audio_returns_none(self):
        """Test that analysis of a very short audio track returns None."""
        # This relies on the duration check in analyze_fund_freq
        response = analyze_audio_features(self.very_short_file)
        self.assertIsNone(
            response,
            "Analysis of very short audio should return None due to duration constraints."
        )

    # --- "Error" Condition Tests (File-level errors) ---
    def test_fund_freq_non_existent_file_returns_none(self):
        """Test analysis of a non-existent file returns None"""
        response = analyze_audio_features(self.non_existent_file)
        self.assertIsNone(response, "Analysis of a non-existent file should return None.")

    def test_fund_freq_corrupted_file_returns_none(self):
        """Test analysis of a corrupted/invalid audio file (text file) returns None."""
        response = analyze_audio_features(self.corrupted_file_dummy)
        self.assertIsNone(response, "Analysis of a corrupted file should return None.")

