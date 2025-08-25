"""
This is the module contains functions responsible for finding a wide
range of audio features for the separate instrument stem tracks
"""
import numpy as np
import librosa

def analyze_full_track_features(audio_path, sr=44100):
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

def analyze_audio_features(audio_path, sr=44100):
    """
    Performs a comprehensive analysis of an audio file, extracting a
    variety of features.

    Args:
        audio_path (str): Path to the audio file.
        sr (int): The sample rate to resample the audio to. Using a
        consistent rate simplifies feature extraction and comparison.

    Returns:
        dict or None: A dictionary containing all computed features,
                      or None on failure. All numpy arrays are
                      converted to lists for JSON serialization.
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

        # --- F0 Analysis ---
        # fmin and fmax could be configurable per instrument type in the future
        fmin = librosa.note_to_hz('A1')
        fmax = librosa.note_to_hz('G8')
        f0, voiced_flag, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr)
        times_f0 = librosa.times_like(f0, sr=sr)

        # Replace NaN with None for JSON compatibility
        f0_list = [float(val) if not np.isnan(val) else None for val in f0]

        # --- Spectrogram (Short Term Fourier Transform) ---
        # Compute the STFT
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
        S_magnitude = np.abs(D)

        # Convert magnitude spectrogram to list of lists for JSON
        # serialization
        spectrogram_list = S_magnitude.tolist()

        # Get frequency bins and time bins for the spectrogram
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
        times_stft = librosa.times_like(S_magnitude, sr=sr, hop_length=hop_length)

        # --- Onset Detection ---
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length).tolist()

        # --- Beat/Tempo Tracking ---
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

        # --- Other Spectral and Timbral Features ---
        # ALL of these features are computed using the same STFT frame
        # structure, which makes them naturally time-aligned.
        spectral_centroid = librosa.feature.spectral_centroid(S=S_magnitude, sr=sr).tolist()
        spectral_bandwidth = librosa.feature.spectral_bandwidth(S=S_magnitude, sr=sr).tolist()
        spectral_rolloff = librosa.feature.spectral_rolloff(S=S_magnitude, sr=sr).tolist()
        spectral_flatness = librosa.feature.spectral_flatness(S=S_magnitude).tolist()
        rms = librosa.feature.rms(y=y).tolist()
        mfccs = librosa.feature.mfcc(y=y, sr=sr).tolist()
        chroma_stft = librosa.feature.chroma_stft(y=y, sr=sr).tolist()

        return {
            "f0_data": {
                "times": times_f0.tolist(),
                "f0_values": f0_list,
            },
            "spectral_features": {
                "times": times_stft.tolist(),
                "frequencies": freqs.tolist(),
                "spectrogram": spectrogram_list,
                "rms": rms,
                "spectral_centroid": spectral_centroid[0],
                "spectral_bandwidth": spectral_bandwidth[0],
                "spectral_rolloff": spectral_rolloff[0],
                "spectral_flatness": spectral_flatness[0],
            },
            "timbral_features": {
                "mfccs": mfccs,
                "chroma_stft": chroma_stft,
            },
            "temporal_features": {
                "onsets": onset_times,
                "tempo": float(tempo),
                "beats": beat_times,
            }
        }

    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None
