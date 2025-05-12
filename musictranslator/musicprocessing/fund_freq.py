"""
This is the module responsible for finding the fundamental frequency
For the guitars, vocals, bass, piano and other stem tracks
"""
import numpy as np
import librosa

def analyze_fund_freq(audio_path, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')):
    """
    Analyzes the fundamental frequency (f0) of an audio file.

    Args:
        audio_path (str): Path to the audio file.
        fmin (float): Minimum frequency to search for f0.
        fmax (float): Maximum frequency to search for f0.

    Returns:
        nump.ndarray or None: A time series of fundamental frequencies.
                              Returns None if the audio cannot be loaded,
                              is too short, or if no f0 is detected robustly.
    """
    try:
        # sr=None to preserve original sample rate, which is important for pitch
        # If the file is extremely short or empty, librosa.load might raise an error
        # or return a very short array
        y, sr = librosa.load(audio_path, sr=None)

        if len(y) == 0:
            # This case might be hit if librosa.load returns an empty array for some reason
            # though it often errors out for truly empty/invalid files.
            # print(f"Warning: Audio file {audio_path} loaded as empty.")
            return None

        # For very short audio clips, pyin might bot be effective or might error.
        # librosa.pyin requires minimum duration related to its largest period (1/fmin).
        # A quick check: if duration is less than,
        # say, twice the period of fmin, it might be problematic.
        # For C2 (approx 65 Hz), period is ~0.015s. Let's say we need at least ~0.05s of audio.
        # This threshold might need some adjustment.
        min_duration_for_pyin = 2 / fmin
        if librosa.get_duration(y=y, sr=sr) < min_duration_for_pyin:
            # print(f"Warning: Audio file {audio_path} is too short for reliable F0 estimation.")
            return None

        # pyin provides f0, voiced flag
        # f0 contains np.nan where the signal is unvoiced
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr)

        # If all f0 values are NaN, it means no fundamental frequency was detected
        # or the entire track was considered unvoiced
        if np.all(np.isnan(f0)):
            # print("Warning: F0 analysis returned all NaN.")
            return None

        return f0
    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None
