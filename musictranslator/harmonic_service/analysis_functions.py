"""
This is the module contains functions responsible for finding a wide
range of audio features for the separate instrument stem tracks
"""
import numpy as np
import librosa

def analyze_full_track_features(audio_path, sr=22050):
    """
    Performs a high-level analysis of a full audio track, primarily
    for duration, tempo and overall volume.

    Args:
        audio_path (str): Path to the audio file.
        sr (int): The sample rate to resample the audio to.

    Returns:
        dict or None: A dictionary containing the computed features,
        or None on failure.
    """
    try:
        y, sr = librosa.load(audio_path, sr=sr)

        n_fft = 2048
        hop_length = 512

        # A simple check for a silent or very short file
        if len(y) < n_fft:
            print(f"Warning: Audio file {audio_path} is too short for analysis")
            return None
        if np.mean(librosa.feature.rms(y=y)[0]) < 1e-6:
            print(f"Warning: Audio file {audio_path} is effectively silent")
            return None

        duration = librosa.get_duration(y=y, sr=sr)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # Calculate RMS as a time-series
        rms_series = librosa.feature.rms(y=y, hop_length=hop_length)
        times_rms = librosa.times_like(rms_series, sr=sr,
                                       hop_length=hop_length)

        return {
            "duration": float(duration),
            "tempo": float(tempo),
            "rms_overall": {
                "times": times_rms.tolist(),
                "values": rms_series[0].tolist()
            }
        }
    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing full track {audio_path}: {e}")
        return None

def generate_time_sliced_features(audio_path, sr=22050):
    """
    Performs a comprehensive analysis of an audio file, extracting a
    variety of features. Generates a sequence of dictionaries, where
    each dictionary contains analysis features for a specific time slice.
    This is a generator function to be used for streaming.

    Args:
        audio_path (str): Path to the audio file.
        sr (int): The sample rate to resample the audio to. Using a
        consistent rate simplifies feature extraction and comparison.

    Returns:
        dict or None: A dictionary containing all computed features,
                      or None on failure, for a single time slice.
    """
    try:
        # Load the audio file once
        y, sr = librosa.load(audio_path, sr=sr)


        # hop_length and n_fft are important parameters for time/
        # frequency resolution
        n_fft = 2048
        hop_length = 512

        # Check to make sure the file is long enough for analysis
        if len(y) < n_fft:
            print(f"Warning: Audio file {audio_path} is too short for analysis.")
            return None

        # Check to make sure the track contains audio. RMS is a good
        # measure of overall energy. Use a very small epsilon to check
        # for an effectively silent file.
        rms_val = np.mean(librosa.feature.rms(y=y)[0])
        if rms_val < 1e-6:
            print(f"Warning: Audio file {audio_path} is effectively silent.")
            return None

        # Pre-compute time-aligned features once
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
        S_magnitude = np.abs(D)
        times_stft = librosa.times_like(S_magnitude, sr=sr, hop_length=hop_length)

        # Use hop_length for features that need a time series
        f0_data = librosa.pyin(
                    y, fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('G8'), sr=sr
                )
        spectral_centroid = librosa.feature.spectral_centroid(
                    S=S_magnitude, sr=sr)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(
                    S=S_magnitude, sr=sr)
        spectral_rolloff = librosa.feature.spectral_rolloff(
                    S=S_magnitude, sr=sr)
        spectral_flatness = librosa.feature.spectral_flatness(
                    S=S_magnitude)
        rms = librosa.feature.rms(y=y)
        frequencies = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Must compute MFCCs and Chroma without transposing them in a return
        mfccs_raw = librosa.feature.mfcc(y=y, sr=sr)
        chroma_stft_raw = librosa.feature.chroma_stft(y=y, sr=sr)


        # Iterate over each time frame and yield a dictionary
        for i, t in enumerate(times_stft):
            yield {
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

    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None

def get_static_features(audio_path, sr=22050):
    """
    Computes static, one-time features like tempo, beats, and onsets.
    """
    try:
        y, sr = librosa.load(audio_path, sr=sr)
        hop_length = 512
        n_fft = 2048

        # A simple check for a silent or very short file
        if len(y) < n_fft:
            print(f"Warning: Audio file {audio_path} is too short for analysis")
            return None
        if np.mean(librosa.feature.rms(y=y)[0]) < 1e-6:
            print(f"Warning: Audio file {audio_path} is effectively silent")
            return None

        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr,
                                                     hop_length=hop_length)
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=hop_length
        ).tolist()
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr,
                                                  hop_length=hop_length)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr,
                                              hop_length=hop_length).tolist()

        return {
            "duration": float(librosa.get_duration(y=y, sr=sr)),
            "tempo": float(tempo),
            "beats": beat_times,
            "onsets": onset_times
        }

    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None

