import os
import logging
import concurrent
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import librosa
import soundfile as sf

# Setup basic logging
logger = logging.getLogger(__name__)

# --- Worker Functions ---

def _estimate_tempo_worker(y: np.ndarray, sr: int) -> float:
    """Worker task for tempo estimation."""
    return estimate_tempo(y, sr)

def load_audio_from_file(file_path: str) -> tuple[np.ndarray, int]:
    """
    Loads audio from a given file path.
    Args:
        file_path (str): The path to the audio file.
    Returns:
        tuple[np.ndarray, int]: A tuple containing the audio time series (y) and sampling rate (sr).
    Raises:
        FileNotFoundError: If the file_path does not exist.
        Exception: For other errors during audio loading.
    """
    if not os.path.exists(file_path):
        logger.error("Audio file not found: %s", file_path)
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    try:
        # sr=None preserves the original sr, mono=True converts to mono
        y, sr = librosa.load(file_path, sr=None, mono=True)
        logger.info("Successfully loaded audio from %s. Shape: %s, SR: %s", file_path, y.shape, sr)
        return y, sr
    except Exception as e:
        logger.critical("Error loading audio file %s: %s", file_path, e, exc_info=True)
        raise # Re-raises the exception after logging

def detect_onsets(y: np.ndarray, sr: int) -> list[float]:
    """
    Detects audio onsets (drum hits).
    Args:
        y (np.ndarray): Audio time series.
        sr (int): Sampling rate.
    Returns:
        list[float]: List of onset times in seconds.
    """
    logger.info("Starting onset detection. Audio length: %ss, SR: %s", (len(y)/sr), sr)
    try:
        # Compute onset strength envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        logger.debug("Onset strength envelope computed. Shape: %s, Max value: %s", onset_env.shape, np.max(onset_env))

        if onset_env is None:
            logger.error("onset_env is None after librosa.onset.onset_strength. This is unexpected.")
            return []
        if not isinstance(onset_env, np.ndarray):
            logger.error("onset_env is not a numpy array. Type: %s",
                         type(onset_env))
            return []
        if onset_env.size == 0:
            logger.error("onset_env is an empty numpy array after librosa.onset.onset_strength. No onsets can be detected.")
            return []

        # Detect onsets based on the onset strength envelope
        # Default delta value is 0.7. Decreasing delta will increase
        # sensitivity. A smaller delta means it's easier to detect
        # a "peak" relative to surrounding values.
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            wait=1,
            pre_max=3,
            post_max=3,
            delta=0.1
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        logger.info("Detected %s onsets.", len(onset_times))
        if len(onset_times) == 0:
            logger.warning("No onsets detected. This might indicate the audio is too quiet, lacks transients, or default parameters are too strict.")
        else:
            logger.debug(f"Detected onset times (first 10): {[f'{t:.2f}' for t in onset_times[:10]]}...")
            logger.debug(f"Detected onset times (last 10): {[f'{t:.2f}' for t in onset_times[-10:]] if len(onset_times) > 10 else onset_times}...")
        return onset_times.tolist()
    except Exception as e:
        logger.critical("Error during onset detection: %s", e, exc_info=True)
        return []

def extract_dynamic_segment(
    y: np.ndarray, sr: int, current_onset_time: float,
    next_onset_time: float = None,
    max_duration: float = 5.0,
    decay_threshold_db: float = -30.0
) -> np.ndarray:
    """
    Extracts an audio segment from an onset until its decay, or up to max_duration.
    Args:
        y (np.ndarray): Full audio time series.
        sr (int): Sampling rate.
        current_onset_time (float): The detected onset time in seconds.
        next_onset_time (float): The time of he next detected onset in seconds, or None.
        max_duration (float): Maximum duration for the segment in seconds.
        decay_threshold_db (float): RMS energy decay threshold in dB relative to peak.
    Returns:
        np.ndarray: The extracted audio segment.
    """
    onset_sample = librosa.time_to_samples(current_onset_time, sr=sr)
    start_sample = max(0, int(onset_sample))

    end_sample_by_max_duration = min(len(y), start_sample + int(max_duration * sr))

    # Determine the "hard" limit for this segment (next hit or max duration)
    # If next_onset_time is provided, we stop there to avoid bleeding into the next hit
    if next_onset_time:
        next_onset_sample = librosa.time_to_samples(next_onset_time, sr=sr)
        end_sample_by_next_onset = min(len(y), int(next_onset_sample))
        hard_end_limit = min(end_sample_by_max_duration,
                             end_sample_by_next_onset)
    else:
        hard_end_limit = end_sample_by_max_duration

    # Extract an initial chunk to analyze for decay, up to the determined end candidate
    segment_for_decay_analysis = y[start_sample:hard_end_limit]

    if len(segment_for_decay_analysis) == 0:
        logger.debug("Segment for decay analysis is empty at onset %ss.", current_onset_time)
        return np.array([], dtype=np.float32)

    # Calculate RMS energy for the entire signal for normalization
    # rms_full = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    # global_peak_rms = np.max(rms_full) if len(rms_full) > 0 else 1e-6

    # Calculate RMS for the segment starting from onset
    # Using a fixed hop length for monitoring
    hop_length_samples = int(0.01 * sr) # 10 ms hop for envelope tracking
    # Compute RMS for the segment
    rms_segment = librosa.feature.rms(
        y=segment_for_decay_analysis,
        frame_length=1024,
        hop_length=hop_length_samples
    )[0]

    if len(rms_segment) == 0:
        logger.debug("RMS segment is empty for onset %ss.", current_onset_time)
        return np.array([], dtype=np.float32)

    peak_rms_segment = np.max(rms_segment)
    if peak_rms_segment < 1e-7: # Avoid division by zero for silent segments
        logger.debug(f"Onset at {current_onset_time:.2f}s has near-silent peak RMS. Using max_duration.")
        return segment_for_decay_analysis

    # Convert decay threshold from dB to linear scale
    linear_decay_thresh = peak_rms_segment * (10**(decay_threshold_db / 20.0))

    # Find where it drops below threshold
    decay_frames = np.where(rms_segment < linear_decay_thresh)[0]

    if len(decay_frames) > 0:
        # First frame below threshold
        decay_idx = decay_frames[0]
        decay_sample_rel = decay_idx * hop_length_samples + 512
        final_end_sample = min(hard_end_limit, start_sample + decay_sample_rel)
    else:
        final_end_sample = hard_end_limit

    return y[start_sample:final_end_sample]

def extract_features_from_segment(segment: np.ndarray, sr: int) -> dict:
    """
    Extracts various audio features from a given segment.
    Args:
        segment (np.ndarray): Audio segment to analyze.
        sr (int): Sampling rate.
    Returns:
        dict: Dictionary of extracted features.
    """
    if len(segment) == 0:
        logger.warning("Attempted to extract features from an empty segment.")
        # Returns default values for an empty segment
        return {
            "relative_volume": 0.0,
            "dominant_frequency": 0.0,
            "spectral_centroid": 0.0,
            "spectral_rolloff": 0.0,
            "spectral_flux": 0.0,
            "mfccs": [0.0] * 13, # Default 13 MFCCs
            "duration": 0.0
        }

    # RMS Energy (Volume)
    rms = librosa.feature.rms(y=segment).mean()

    # Spectral Centroid
    cent = librosa.feature.spectral_centroid(y=segment, sr=sr)
    spectral_centroid = np.mean(cent)

    # Spectral Rolloff (85th percentile by default)
    rolloff = librosa.feature.spectral_rolloff(y=segment, sr=sr)
    spectral_rolloff = np.mean(rolloff)

    # Domininat Frequency
    # Use FFT to find the frequency bin with the highest manitidue.
    # This is O(N log N) compared to pyin's O(N^2).
    # Apply a Hanning window to reduce spectral leakage
    windowed_segment = segment * np.hanning(len(segment))
    # rfft is faster for real-valued inputs (audio)
    fft_spectrum = np.fft.rfft(windowed_segment)
    fft_frequencies = np.fft.rfftfreq(len(segment), 1/sr)
    # Find peak magnitude
    peak_idx = np.argmax(np.abs(fft_spectrum))
    dominant_frequency = float(fft_frequencies[peak_idx])

    # Spectral Flux (computed over the segment, not just onset)
    # This is a measure of how quickly the spectral content is changing.
    onset_env = librosa.onset.onset_strength(y=segment, sr=sr, aggregate=np.mean)
    spectral_flux = np.mean(onset_env) if len(onset_env) > 0 else 0.0

    # MFCCs - Mel-Frequency Cepstral Coefficients
    # These describe the shape of the spectral envelope, useful for timbre.
    # `n_mfcc=13` is a common choice, excluding c0 (energy) if desired, but including for now.
    mfccs = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=13)
    mean_mfccs = np.mean(mfccs, axis=1).tolist() # Average each coefficient over the segment

    # Duration of the analyzed segment
    duration = len(segment) / sr

    features = {
        "relative_volume": float(rms),
        "dominant_frequency": dominant_frequency,
        "spectral_centroid": float(spectral_centroid),
        "spectral_rolloff": float(spectral_rolloff),
        "spectral_flux": float(spectral_flux),
        "mfccs": mean_mfccs,
        "duration": float(duration)
    }
    logger.debug(f"Extracted features for segment (len={len(segment)/sr:.2f}s): {features}")
    return features

def estimate_tempo(y: np.ndarray, sr: int) -> float:
    """
    Estimates the overall tempo (BPM) of the audio track.
    Ars:
        y (np.ndarray): Full audio time series.
        sr (int): Sampling rate.
    Returns:
        float: Estimated tempo in beats per minute (BPM).
               Returns 0.0 if tempo cannot be reliably estimated.
    """
    logger.info("Starting tempo estimation.")
    try:
        # Compute onset strength envelope for tempo estimation
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Estimate the tempo from the onset strength envelope
        tempo, _ = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr
        )

        # tempo is typically a float (e.g., 120.0). Convert to float
        estimated_tempo = float(tempo)
        logger.info("Estimated tempo: %.2f BPM", estimated_tempo)
        return estimated_tempo
    except Exception as e:
        logger.critical("Error during tempo estimation: %s",
                        e, exc_info=True)
        return 0.0

def analyze_audio_concurrently(
    y: np.ndarray, sr: int, executor=None
) -> dict:
    """
    Analyzes audio using an injected executor or creating a local one.
    Args:
        y (np.ndarray): Full audio time series.
        sr (int): Sampling rate.
    Returns:
        dict: A dictionary container 'hits' and 'tempo'.
    """
    logger.info("Starting audio analysis.")

    # Detect onsets first (fast, running in main process)
    onset_times = detect_onsets(y, sr)

    # Helper to run analysis
    def run_with_executor(exec_instance):
        # 1. Submit Tempo
        # We pass 'y' directly. If using ProcessPool, this pickles 'y' once.
        # This is acceptable for a single tempo task.
        tempo_future = exec_instance.submit(_estimate_tempo_worker, y, sr)

        if not onset_times:
            return {"hits": [], "tempo": tempo_future.result()}

        # 2. Extract Segments (Main Process)
        # Slicing numpy arrays is efficient (views/shallow copies where possible).
        # We prepare the arguments for the workers here.
        segments_and_times = []
        for i in range(len(onset_times)):
            current_time = onset_times[i]
            next_time = onset_times[i+1] if i + 1 < len(onset_times) else None

            # Slice audio
            seg = extract_dynamic_segment(y, sr, current_time, next_time)
            segments_and_times.append((seg, current_time))

        # 3. Submit Feature Extraction Tasks
        # We submit the SMALL segment arrays. This is much faster to pickle/
        # transfer than sharing the whole 'y' via globals or managers.
        hit_futures = {
            exec_instance.submit(extract_features_from_segment, seg, sr): onset_time
            for seg, onset_time in segments_and_times
        }

        # 4. Collect Results
        hits = []
        for future in as_completed(hit_futures):
            onset_time = hit_futures[future]
            try:
                features = future.result()
                if features:
                    features['onset_time'] = float(onset_time)
                    hits.append(features)
            except Exception as e:
                logger.error("Error processing hit at %s: %s",
                             onset_time, e)

        hits.sort(key=lambda x: x['onset_time'])
        return {"hits": hits, "tempo": tempo_future.result()}

    if executor:
        return run_with_executor(executor)
    else:
        # Fallback for local testing if no executor provided
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as local_exec:
            return run_with_executor(local_exec)
