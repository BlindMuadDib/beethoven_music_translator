import os
import logging
import concurrent
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import librosa
import librosa.display
import soundfile as sf

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        raise FileNotFoundError("Audio file not found: %s", file_path)

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
            wait=5,
            pre_max=3,
            post_max=3,
            delta=.1
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
    max_duration: float = 3.0,
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

    # Determine potential end sample based on next onset or max duration
    end_sample_by_next_onset = len(y)
    if next_onset_time is not None:
        end_sample_by_next_onset = min(len(y), librosa.time_to_samples(next_onset_time, sr=sr))

    end_sample_by_max_duration = min(len(y), start_sample + int(max_duration * sr))

    # Initialize end_sample based on the earliest of the three constraints
    # (actual end of audio, end_sample_by_next_onset, end_sample_by_max_duration)
    current_segment_end_candidate = min(len(y), end_sample_by_next_onset, end_sample_by_max_duration)

    # If the current onset is at or beyond the end of the audio, or leads to an empty segment, return empty
    if current_segment_end_candidate <= start_sample:
        logger.debug(f"Onset at {current_onset_time:.2f}s leads to an empty or invalid segment candidate.")
        return np.array([], dtype=np.float32)

    # Extract an initial chunk to analyze for decay, up to the determined end candidate
    segment_for_decay_analysis = y[start_sample:current_segment_end_candidate]

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
        end_sample = min(len(y), start_sample + int(max_duration * sr))
        return y[start_sample:end_sample]

    # Convert decay threshold from dB to linear scale
    linear_decay_threshold = peak_rms_segment * (10**(decay_threshold_db / 20.0))

    decay_end_sample_relative = len(segment_for_decay_analysis)
    for i in range(len(rms_segment)):
        if rms_segment[i] < linear_decay_threshold:
            # Found decay point, convert frame index to sample index relative to start_sample
            # Add half frame length to center
            decay_end_sample_relative = i * hop_length_samples + (1024 // 2)
            logger.debug(f"Onset at {current_onset_time:.2f}s decayed at approx {librosa.samples_to_time(start_sample + decay_end_sample_relative, sr=sr):.2f}s.")
            break

    # The actual end sample is the minimum of (decay_end, next_onset_time, max_duration)
    final_end_sample = min(
        # This already incorporates next_onset_time and max_duration
        current_segment_end_candidate,
        # This is the decay point
        start_sample + decay_end_sample_relative
    )

    # Ensure final segment is not empty
    if final_end_sample <= start_sample:
        logger.debug("Final end sample %s is not greater than start sample %s.", final_end_sample, start_sample)

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

    # F0 (Pitch) - using pyin for robustness,
    # but still with caution for drums
    # fmin and fmax define the range for pitch detection.
    # C1-C5 (32.7Hz = 523.25Hz) is a reasonable range for drums.
    # Lower bound might be needed for very large drums.
    f0, _, _ = librosa.pyin(
        y=segment, sr=sr,
        fmin=librosa.note_to_hz('A1'),
        fmax=librosa.note_to_hz('G8'),
        frame_length=2048, hop_length=512
    )
    # Take the mean of non-zero F0 values. If all are zero/unpitched, return 0.
    f0_mean = np.mean(f0[f0 > 0]) if np.any(f0 > 0) else 0.0

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
        "dominant_frequency": float(f0_mean), # Represents the perceived pitch
        "spectral_centroid": float(spectral_centroid),
        "spectral_rolloff": float(spectral_rolloff),
        "spectral_flux": float(spectral_flux),
        "mfccs": mean_mfccs,
        "duration": float(duration)
    }
    logger.debug(f"Extracted features for segment (len={len(segment)/sr:.2f}s): {features}")
    return features

def analyze_audio_concurrently(y: np.ndarray, sr: int) -> list[dict]:
    """
    Orchestrates the drum analysis: detects onsets and extracts features concurrently.
    Args:
        y (np.ndarray): Full audio time series.
        sr (int): Sampling rate.
    Returns:
        list[dict]: A list of dictionaries, each representing a detected drum hit with its features.
    """
    onset_times = detect_onsets(y, sr)
    if not onset_times:
        logger.info("No onsets detected in the audio.")
        return []

    analysis_results = []

    # Prepare arguments for each concurrent task
    tasks = []
    for i, current_onset_time in enumerate(onset_times):
        next_onset_time = onset_times[i+1] if i + 1 < len(onset_times) else None
        tasks.append((current_onset_time, next_onset_time))

    # Use ThreadPoolExecutor for concurrent feature extraction
    # The default number of workers (often CPU count * 5) is usually good for I/O-bound
    # or mixed tasks like this where C-extensions release the GIL.
    with ThreadPoolExecutor() as executor:
        futures = {}
        for current_onset_time, next_onset_time in tasks:
            # Submit feature extraction for this segment to the thread pool
            future = executor.submit(
                _process_single_onset,
                y, sr, current_onset_time, next_onset_time
            )
            futures[future] = current_onset_time # Map future back to its onset time

        for future in concurrent.futures.as_completed(futures):
            onset_time = futures[future]
            try:
                result_data = future.result()
                # Add onset time to the features dict for the final output
                if result_data: # Only add if the segment wasn't empty
                    analysis_results.append(result_data)
            except Exception as exc:
                logger.critical(
                    f'Onset at {onset_time:.2f}s generated an exception: {exc}',
                    exc_info=True
                    )

    # Sort results by onset time for consistent output
    analysis_results.sort(key=lambda x: x['onset_time'])
    logger.info("Completed analysis of %s drum hits.", len(analysis_results))
    return analysis_results

# --- Helper Function ---
def _process_single_onset(
    y: np.ndarray,
    sr: int,
    current_onset_time: float,
    next_onset_time: float
) -> dict | None:
    """Helper function for concurrent execution."""
    try:
        segment = extract_dynamic_segment(y, sr, current_onset_time, next_onset_time)
        if len(segment) == 0:
            logger.debug(f"Skipping analysis for empty segment at onset {current_onset_time:.2f}s")
            return None
        features = extract_features_from_segment(segment, sr)
        features['onset_time'] = float(current_onset_time)
        return features
    except Exception as e:
        logger.critical(f"Error processing single onset at {current_onset_time:.2f}s: {e}", exc_info=True)
        return None
