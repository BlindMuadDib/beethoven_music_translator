import numpy as np
import librosa

def calculate_rms_for_file(file_path: str) -> list:
    """
    Loads an audio file and calculates a time-series of its Root Mean Square (RMS) energy.

    Args:
        file_path (str): The path to the audio file.

    Returns:
        A tuple containing (list_of_rms_data, error_message_string)
        list_of_rms_data will contain [timestamp, rms_values] pairs.
        On success, error_message_string will be None.
        On failure, list_of_rms_data will be None.
    """
    try:
        # Load the audio file, sr=None preserves the original sample rate
        y, sr = librosa.load(file_path, sr=None)

        # Calculates RMS energy. This returns a 2D array,
        # we want the first row.
        rms_values = librosa.feature.rms(y=y)[0]

        # Get the timestamps corresponding to each RMS frame
        times = librosa.times_like(rms_values, sr=sr)

        # Combine into the desired [[t1, v1], [t2, v2], ...] format
        # Ensure values are standard Python floats for JSON serialization
        # Add None for the error
        return [[float(t), float(r)] for t, r in zip(times, rms_values)], None

    except Exception as e:
        # Make more robust in refactor
        print(f"Error processing file {file_path}: {e}")
        return None, str(e)
