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
from musictranslator.harmonic_service.analysis_functions import generate_time_sliced_features, analyze_full_track_features, get_static_features

# Define a directory for test audio files, relative to this test script
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'test_audio')
SAMPLE_RATE = 44100 # Standard sample rate

class TestHarmonicAnalysis(unittest.TestCase):

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

    # --- "Success" Tests (using sine waves for predictability) ---

    def test_generate_time_sliced_features(self):
        """
        Test that the generator function yields valid time-sliced data.
        The data is structured: {
                "time": float(t),
                "f0_data": float(f0_data[0][i]) if not np.isnan(f0_data[0][i]) else None,
                "spectral_centroid": float(spectral_centroid[0][i]),
                "spectral_bandwidth": float(spectral_bandwidth[0][i]),
                "spectral_rolloff": float(spectral_rolloff[0][i]),
                "spectral_flatness": float(spectral_flatness[0][i]),
                "rms": float(rms[0][i]),
                "mfccs": mfccs_raw[:, i].tolist(),
                "chroma_stft": chroma_stft_raw[:, i].tolist(),
                "spectrogram": S_magnitude[:, i].tolist(),
                "frequencies": frequencies.tolist(),
            }
        """
        # Use a longer, predictable file for this test
        long_sine_file = os.path.join(TEST_AUDIO_DIR, 'long_a4_sine.wav')
        sf.write(
            long_sine_file,
            librosa.tone(self.known_freq_a4, sr=SAMPLE_RATE, duration=3.0),
            SAMPLE_RATE
        )

        gen = generate_time_sliced_features(long_sine_file)

        # Check the first few and the last few yielded items
        data_points = list(gen)

        self.assertTrue(len(data_points) > 5,
                        f"'len(data_points)' should be 5, but is: {len(data_points)}")

        # Check the first data point
        first_slice = data_points[0]
        self.assertIn("time", first_slice)
        self.assertIsInstance(first_slice["time"], float)
        self.assertIn("f0_data", first_slice)
        self.assertIn("spectral_centroid", first_slice)
        self.assertIn("spectral_bandwidth", first_slice)
        self.assertIn("spectral_rolloff", first_slice)
        self.assertIn("spectral_flatness", first_slice)
        self.assertIn("rms", first_slice)
        self.assertIn("mfccs", first_slice)
        self.assertIn("chroma_stft", first_slice)
        self.assertIn("spectrogram", first_slice)
        self.assertIn("frequencies", first_slice)

        self.assertIsInstance(first_slice["f0_data"], float)
        self.assertIsInstance(first_slice["spectral_centroid"], float)
        self.assertIsInstance(first_slice["spectral_bandwidth"], float)
        self.assertIsInstance(first_slice["spectral_rolloff"], float)
        self.assertIsInstance(first_slice["spectral_flatness"], float)
        self.assertIsInstance(first_slice["rms"], float)
        self.assertIsInstance(first_slice["mfccs"], list)
        self.assertIsInstance(first_slice["chroma_stft"], list)
        self.assertIsInstance(first_slice["spectrogram"], list)
        self.assertIsInstance(first_slice["frequencies"], list)

        # Check the last data point
        last_slice = data_points[-1]
        self.assertIn("time", last_slice)
        self.assertIsInstance(last_slice["time"], float)
        self.assertIn("f0_data", last_slice)
        self.assertIn("spectral_centroid", last_slice)
        self.assertIn("spectral_bandwidth", last_slice)
        self.assertIn("spectral_rolloff", last_slice)
        self.assertIn("spectral_flatness", last_slice)
        self.assertIn("rms", last_slice)
        self.assertIn("mfccs", last_slice)
        self.assertIn("chroma_stft", last_slice)
        self.assertIn("spectrogram", last_slice)
        self.assertIn("frequencies", last_slice)

        self.assertIsInstance(last_slice["f0_data"], float)
        self.assertIsInstance(last_slice["spectral_centroid"], float)
        self.assertIsInstance(last_slice["spectral_bandwidth"], float)
        self.assertIsInstance(last_slice["spectral_rolloff"], float)
        self.assertIsInstance(last_slice["spectral_flatness"], float)
        self.assertIsInstance(last_slice["rms"], float)
        self.assertIsInstance(last_slice["mfccs"], list)
        self.assertIsInstance(last_slice["chroma_stft"], list)
        self.assertIsInstance(last_slice["spectrogram"], list)
        self.assertIsInstance(last_slice["frequencies"], list)

        # Clean up the test file
        os.remove(long_sine_file)

    def test_get_static_features(self):
        """
        Test get_static_features function for returning static,
        one-off features.
        """
        result = get_static_features(self.a4_sine_file)
        self.assertIsInstance(result, dict)
        self.assertIn("duration", result)
        self.assertIsInstance(result["duration"], float)
        self.assertIn("tempo", result)
        self.assertIsInstance(result["tempo"], float)
        self.assertIn("beats", result)
        self.assertIsInstance(result["beats"], list)
        self.assertIn("onsets", result)
        self.assertIsInstance(result["onsets"], list)

    def test_analyze_full_track_features(self):
        """Test the high-level full track analysis."""
        result = analyze_full_track_features(self.a4_sine_file)
        self.assertIsInstance(result, dict)
        self.assertIn("duration", result)
        self.assertIsInstance(result["duration"], float)
        self.assertIn("tempo", result)
        self.assertIsInstance(result["tempo"], float)
        self.assertIn("rms_overall", result)
        self.assertIsInstance(result["rms_overall"]["times"], list)
        self.assertIsInstance(result["rms_overall"]["values"], list)

    # --- "No Audio" / Specific Condition Tests ---
    def test_silent_audio_returns_none(self):
        """Test that analysis of a silent audio track returns None."""
        static_result = get_static_features(self.silent_file)
        self.assertIsNone(static_result,
                          "Analysis of silent audio should return None")

        generator_result = list(generate_time_sliced_features(
            self.silent_file
        ))
        self.assertEqual(len(generator_result), 0,
                         "Generator for silent audio should yield no data")

    def test_very_short_audio_returns_none(self):
        """Test that analysis of a very short audio track returns None."""
        static_result = get_static_features(self.very_short_file)
        self.assertIsNone(static_result,
                          "Analysis of very short audio should return None")

        generator_result = list(generate_time_sliced_features(
            self.very_short_file
        ))
        self.assertEqual(len(generator_result), 0,
                         "Generator for silent audio should yield no data")

    # --- "Error" Condition Tests (File-level errors) ---
    def test_fund_freq_non_existent_file_returns_none(self):
        """Test analysis of a non-existent file returns None"""
        static_result = get_static_features(self.non_existent_file)
        self.assertIsNone(static_result,
                          "Analysis of a non-existent file should return None.")

        generator_result = list(generate_time_sliced_features(
            self.non_existent_file
        ))
        self.assertEqual(len(generator_result), 0,
                         "Generator for corrupted file should yield no data.")

    def test_fund_freq_corrupted_file_returns_none(self):
        """Test analysis of a corrupted/invalid audio file (text file) returns None."""
        static_result = get_static_features(self.corrupted_file_dummy)
        self.assertIsNone(static_result,
                           "Analysis of a corrupted file should return None.")

        generator_result = list(generate_time_sliced_features(
            self.corrupted_file_dummy
        ))
        self.assertEqual(len(generator_result), 0,
                         "Generator for corrupted file should yield no data.")
