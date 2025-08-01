import os
import pytest
import numpy as np
from scipy.io.wavfile import write
from musictranslator.volume_service.volume_analysis import calculate_rms_for_file

@pytest.fixture
def sine_wave_file(tmp_path):
    """
    A pytest fixture to create a temporary WAV file of a 1-second sine wave.
    This file is automatically cleaned up by pytest after the test runs.
    """
    sample_rate = 22050 # Hz
    duration = 1.0 # seconds
    frequency = 440.0 # Hz (contemporary A4 pitch)
    amplitude = 0.8 # Amplitude for the sine wave

    # Generate time axis
    t = np.linspace(0., duration, int(sample_rate * duration), endpoint=False)
    # Generate sine wave
    audio_data = amplitude * np.sin(2. * np.pi * frequency * t)

    # Path to the temporary file
    file_path = tmp_path / "test_sine.wav"

    # Write as a 32-bit float WAV file, as librosa prefers floats.
    # We need to scale it for scipy's write function if it were integer,
    # but for float it's fine.
    write(file_path, sample_rate, audio_data.astype(np.float32))

    # The expected RMS of a sine wave is Amplitude / sqrt(2)
    expected_rms = amplitude / np.sqrt(2)

    return str(file_path), expected_rms

def test_calculate_rms_for_file(sine_wave_file):
    """
    Tests the core RMS calculation logic with a known signal.
    """
    file_path, expected_rms = sine_wave_file

    # This function call is what we are testing
    result = calculate_rms_for_file(file_path)

    # 1. Check the structure is what we are testing
    assert isinstance(result, list), "Output should be a list"
    assert len(result) > 0, "Output list should not be empty"
    assert isinstance(result[0], list), "Each item in the list should be a sublist"
    assert len(result[0]) == 2, "Each sublist should contain [timestamp, rms_value]"

    # 2. Check the data types
    assert isinstance(result[0][0], float), "Timestamp should be a float"
    assert isinstance(result[0][1], float), "RMS value should be a float"

    # 3. Check the calculated values
    # We check the RMS values from the middle of the signal to avoid edge effects
    # of the analysis windows at the beginning and end.
    rms_values = [item[1] for item in result]
    middle_rms_values = rms_values[len(rms_values)//4 : -len(rms_values)//4]

    for rms_value in middle_rms_values:
        # pytest.approx allows for small floating point inaccuracies
        assert rms_value == pytest.approx(expected_rms, abs=1e-3)
