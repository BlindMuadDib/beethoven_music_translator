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

        # Default hop_length for librosa.pyin is frame_length // 4.
        # Default frame_length is 2048. So, default hop_length = 512.
        # It's good practice to be explicit if defaults are relied upon or use the actual value.
        # For pyin, the effective hop_length of the output f0 series is determined by its internal processing,
        # often aligning with standard STFT hop lengths (e.g., 512 for sr=22050, or 44100).
        # Let's assume a common hop_length or retrieve if possible, for pyin it's often relateed to frame_length/4
        # The librosa documentation doesn't explicitly state the hop_length of the output F0 series in samples,
        # but it's tied to the frame processing. Typically, for sr=22050, hop_length=512 is common.
        # For sr=44100, a hop_length for pyin might be 1024 or related to its internal windowing.
        # Let's stick to a common default used in STFTs for time conversion, often 512.
        # A more robust way would be to confirm librosa.pyin's effective hop length if it's not standard.
        # For now, using a common STFT hop_length:
        DUMMY_HOP_LENGTH = 512  # This is an assumption; pyin's hop may vary.
                                # The actual time of resolution of pyin is typically around 10-30ms.
                                # The output of pyin has one F0 value per frame.

        # pyin provides f0, voiced flag
        # f0 contains np.nan where the signal is unvoiced
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr)

        # If all f0 values are NaN, it means no fundamental frequency was detected
        # or the entire track was considered unvoiced
        if np.all(np.isnan(f0)):
            # print("Warning: F0 analysis returned all NaN.")
            return None

        # Generate timestamps for each f0 value.
        # The number of frames in f0 corresponds to the number of analysis windows.
        # The times correspond to the center of each analysis frame.
        times = librosa.times_like(f0, sr=sr) # Preferred method of using times_like with f0 array directly

        # Convert NaN to None for JSON compatibility
        f0_list = [float(val) if not np.isnan(val) else None for val in f0]
        times_list = [float(t) for t in times]

        return {"times": times_list, "f0_values": f0_list, "time_interval": (times_list[1] - times_list[0]) if len(times_list) > 1 else 0.01}

    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None
