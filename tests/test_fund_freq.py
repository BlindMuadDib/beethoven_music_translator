"""
This is a test file for the fundamental frequency analysis module
Each separated stem track is individually analyzed dynamically
Result will be a stream of frequencies for each instrument
"""
import unittest
import os
import numpy as np
import soundfile as sf
import librosa
from musictranslator.f0_service.fund_freq import analyze_fund_freq

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

        # Assign files for specific instrument tests (can be more varied later)
        cls.vocals_file_success = cls.a4_sine_file
        cls.guitar_file_success = cls.a4_sine_file
        cls.bass_file_success = cls.c3_sine_file
        # Drums are more complex
        # Will implement later
        # cls.drums_file_success = raise NotImplementedError
        cls.piano_file_success = cls.a4_sine_file
        cls.other_file_success = cls.a4_sine_file

        # 4. Non-existent file path
        cls.non_existent_file = os.path.join(TEST_AUDIO_DIR, 'non_existent_audio.wav')
        # Ensure it doesn't exist for the test
        if os.path.exists(cls.non_existent_file):
            os.remove(cls.non_existent_file)

        # 5. Corrupted audio file (a text file)
        cls.corrupted_file_dummy = os.path.join(TEST_AUDIO_DIR, 'corrupted_audio.txt')
        with open(cls.corrupted_file_dummy, 'w') as f:
            f.write("This is not a valid audio file content.")

        # 6. Very short audio file (might be too short for pyin)
        cls.very_short_file = os.path.join(TEST_AUDIO_DIR, 'very_short.wav')
        SHORT_DURATION = 0.01 # 0.01 seconds, potentially too short
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

    def _assert_successful_f0(self, audio_file, known_freq, tolerance_hz=15.0, min_voiced_ratio=0.3):
        """Helper method to assert successful F0 detection."""
        f0_result = analyze_fund_freq(audio_file)
        self.assertIsNotNone(f0_result, f"analyze_fund_freq returned None for {f0_result}")

        # Filter out NaNs (unvoiced frames)
        voiced_f0 = f0_result[~np.isnan(f0_result)]

        # Check if there are any voiced frames at all
        self.assertTrue(len(voiced_f0) > 0, f"No voiced framed detected in {audio_file}. F0 raw: {f0_result}")

        # Check if a sufficient proportion of frames are voiced
        self.assertTrue(len(voiced_f0) / len(f0_result) >= min_voiced_ratio,
                        f"Less than {min_voiced_ratio*100:.1f}% of frames were voices for {audio_file}. "
                        f"Voiced frames: {len(voiced_f0)}, Total frames: {len(f0_result)}")

        # Check if the mean of detected frequencies is close to the known frequency
        mean_f0 = np.mean(voiced_f0)
        self.assertAlmostEqual(mean_f0, known_freq, delta=tolerance_hz,
                               msg=(f"Mean F0 ({mean_f0:.2f} Hz) not close to known F0 ({known_freq:.2f} Hz) "
                                    f"with delta {tolerance_hz} for {audio_file}. Voiced F0s: {voiced_f0[:10]}..."))

    # --- "No Audio" / Specific Condition Tests ---
    def test_fund_freq_silent_audio_returns_none(self):
        """Test that analysis of a silent audio track returns None."""
        response = analyze_fund_freq(self.silent_file)
        self.assertIsNone(response, "Analysis of silent audio should return None")

    def test_fund_freq_very_short_audio_returns_none(self):
        """Test that analysis of a very short audio track returns None."""
        # This relies on the duration check in analyze_fund_freq
        response = analyze_fund_freq(self.very_short_file)
        self.assertIsNone(response, "Analysis of very short audio should return None due to duration constraints.")

    # --- "Success" Tests (using sine waves for predictability) ---
    def test_fund_freq_vocals_success(self):
        """Test a successful F0 analysis on 'vocals' (A4 sine)."""
        self._assert_successful_f0(self.vocals_file_success, self.known_freq_a4)

    def test_fund_freq_guitar_success(self):
        """Test a successful F0 analysis on 'guitar' (A4 sine)."""
        self._assert_successful_f0(self.guitar_file_success, self.known_freq_a4)

    def test_fund_freq_bass_success(self):
        """Test a successful F0 analysis on 'bass' (C3 sine)."""
        self._assert_successful_f0(self.bass_file_success, self.known_freq_c3)

    def test_fund_freq_piano_success(self):
        """Test a successful F0 analysis on 'piano' (A4 sine)."""
        self._assert_successful_f0(self.piano_file_success, self.known_freq_a4)

    def test_fund_freq_other_success(self):
        """Test a successful F0 analysis on 'other' (A4 sine)."""
        self._assert_successful_f0(self.other_file_success, self.known_freq_a4)

    # --- "Error" Condition Tests (File-level errors) ---
    def test_fund_freq_non_existent_file_returns_none(self):
        """Test analysis of a non-existent file returns None"""
        response = analyze_fund_freq(self.non_existent_file)
        self.assertIsNone(response, "Analysis of a non-existent file should return None.")

    def test_fund_freq_corrupted_file_returns_none(self):
        """Test analysis of a corrupted/invalid audio file (text file) returns None."""
        response = analyze_fund_freq(self.corrupted_file_dummy)
        self.assertIsNone(response, "Analysis of a corrupted file should return None.")

