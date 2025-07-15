import io
import concurrent.futures
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from musictranslator.drum_analysis_service import drum_analysis

# --- Mock Data for consistency ---
MOCK_SR = 22050 # Sample rate
MOCK_SILENT_AUDIO = np.zeros(MOCK_SR, dtype=np.float32) # 1 second of silence
MOCK_SHORT_AUDIO = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0], dtype=np.float32) # Short decaying sound
MOCK_ONSET_AUDIO_CLEAR_ONSETS = np.concatenate([
    np.zeros(int(0.5 * MOCK_SR), dtype=np.float32), # Silence
    np.linspace(0, 1, int(0.1 * MOCK_SR)), # Attack
    np.zeros(int(0.5 * MOCK_SR), dtype=np.float32), # Silence
    np.linspace(0, 1, int(0.1 * MOCK_SR)), # Attack
    np.zeros(int(0.5 * MOCK_SR), dtype=np.float32) # Silence
]).astype(np.float32)

# --- Tests for detect_onsets (mocking librosa internals) ---
@patch('librosa.onset.onset_strength')
@patch('librosa.onset.onset_detect')
@patch('librosa.frames_to_time')
def test_detect_onsets_single_onset_mocked(
    mock_frames_to_time, mock_onset_detect, mock_onset_strength
):
    mock_onset_strength.return_value = np.array([0.1, 0.8, 0.2]) # Dummy onset strength
    mock_onset_detect.return_value = np.array([1]) # Mocked timed frame index for onset
    mock_frames_to_time.return_value = np.array([0.5]) # Mocked time for onset

    onsets = drum_analysis.detect_onsets(MOCK_SILENT_AUDIO, MOCK_SR)
    assert len(onsets) == 1
    assert onsets[0] == pytest.approx(0.5)

    mock_onset_strength.assert_called_once_with(y=MOCK_SILENT_AUDIO, sr=MOCK_SR)
    mock_onset_detect.assert_called_once_with(onset_env=mock_onset_strength.return_value, sr=MOCK_SR)
    mock_frames_to_time.assert_called_once_with(mock_onset_detect.return_value, sr=MOCK_SR)

@patch('librosa.onset.onset_strength')
@patch('librosa.onset.onset_detect')
@patch('librosa.frames_to_time')
def test_detect_onsets_multiple_onsets_mocked(mock_frames_to_time, mock_onset_detect, mock_onset_strength):
    mock_onset_strength.return_value = np.array([0.1, 0.8, 0.2, 0.9, 0.3])
    mock_onset_detect.return_value = np.array([1, 3])
    mock_frames_to_time.return_value = np.array([0.5, 1.2])

    onsets = drum_analysis.detect_onsets(MOCK_SILENT_AUDIO, MOCK_SR)
    assert len(onsets) == 2
    assert onsets[0] == pytest.approx(0.5)
    assert onsets[1] == pytest.approx(1.2)

@patch('librosa.onset.onset_detect')
def test_detect_onsets_no_onsets_in_silence_mocked(mock_onset_detect):
    mock_onset_detect.return_value = np.array([]) # No onsets detected
    onsets = drum_analysis.detect_onsets(MOCK_SILENT_AUDIO, MOCK_SR)
    assert len(onsets) == 0

# --- Tests for extract_dynamic_segment (mocking librosa internals) ---
@patch('librosa.feature.rms')
@patch('librosa.time_to_samples')
@patch('librosa.samples_to_time')
def test_extract_dynamic_segment_full_decay_mocked(
    mock_samples_to_time, mocked_time_to_samples, mock_rms
):
    # Setup mocks
    mocked_time_to_samples.return_value = 0 # Onset at sample 0
    mock_samples_to_time.side_effect = lambda samples, sr: samples / sr # Simple conversion

    """
        Simulates RMS decay: starts high, then goes below threshold
        The actual length of segment matters for how many frames RMS will have
        Let's say a 1-second segment. With hop_length_samples=220, frame_length=1024,
        it would have about 1000/220 = 4-5 frames.
        If using fixed hop and frame, the number of frames will be around
        (len(segment) - frame_length) / hop_length + 1
        For a 1-second segment (22050 samples), with hop=220, frame=1024:
        (22050 - 1024)/220 + 1 = 96 frames
        Mocking rms for the *segment* that `extract_dynamic_segment` will create.
        This requires careful thought about the inner workings of `extract_dynamic_segment`
        The segment length is controlled by decay logic, so we need to mock RMS behavior for that loop

        Simulating a decay: RMS starts above threshold, then drops below.
        The `extract_dynamic_segment` internally calls librosa.features.rms on `segment_y`.
        Let's create a dummy RMS array that will cause it to stop after a certain point.
        Assuming MOCK_SHORT_AUDIO is the 'y' input.
        MOCK_SHORT_AUDIO has 10 samples. if sr=10, then 1 second.
    """
    test_y = np.array([1.0, 0.8, 0.6, 0.4, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005], dtype=np.float32)
    test_sr = 10 # Very low SP for simple sample counting

    # Mock RMS for the segment. `extract_dynamic_segment` will extract `test_y[start_sample:]`.
    # `librosa.feature.rms` will be called on this.
    # Let's say our decay_threshold_db=-20dB relative to pear (1.0) means 0.1 linear.
    # So when RMS drops below 0.1, it should stop.
    mock_rms.return_value = np.array([[0.8, 0.6, 0.4, 0.2, 0.15, 0.08, 0.05]]) # RMS values over time frames

    onset_time = 0.0
    """
        Expected segment should go up to the point where RMS drops below 0.1 (i.e., at 0.08)
        The hop length in extract_dynamic_segment is 0.01 * sr = 0.1 samples for sr=10.
        RMS frames: [0.8 (f0), 0.6, (f1), 0.4 (f2), 0.2 (f3), 0.15 (f4), 0.08 (f5)]
        Decay happens at frame 5. So segment should contain frames 0-5.
        It adds half frame_length. frame_length 1024 / hop 22050 = ~0.046s.
        For test_sr=10, frame_length=1024/22050*10 = 0.46 samples.
        Hop=0.01*10 = 0.1 samples.
        This is getting complicated due to sample-level precision and mock setup for RMS frames.

        Let's simplify the mock logic for extract_dynamic_segment:
        Instead of mocking `librosa.feature.rms` to simulate decay,
        which is very intricate because it depends on input segment length,
        we can simplify to ensure the logic flows:
        We want to test that if RMS *would* decay, it correctly finds the end.
        A more robust unit test might test the decay logic directly given mock RMS values,
        rather than mocking the RMS function itself.

        For this test, let's use a simplified approach to confirm it cuts off.
        We'll assert the length of the returned segmenet is as expected given its internal logic.
        This is still a bit integration-testy, but harder to perfectly mock out.

        Simulating a signal that decays, where we want to test that the *end_sample* is calculated correctly.
        `y` is long, `onset_time` is 0.0. `max_duration` is 2.0. `decay_threshold_db` is -20.0.
        We want to confirm that if RMS hits threshold, it stops *before* max duration.

        Mocking `librosa.feature.rms` to return a specific decay pattern
        We know `extract_dynamic_segment` sets `hop_length_samples = int(0.01 * sr)`
        And `rms_segment = librosa.feature.rms(y=segment_y, frame_length=1024, hop_length=hop_length_samples)[0]`
        Let's say we have an audio with 2 seconds. sr=22050. hop=220.
        A 2-sec audio has 2+22050 = 44100 samples.
        RMS frames: (44100 - 1024) / 220 + 1 approx 196 frames.

        Simulating RMS dropping below threshold after ~0.5 seconds (about 50 frames)
        A dummy RMS array for the purpose of the test
        (peak_rms is 1.0, threshold -20dB means 0.1 linear)
    """
    mock_rms.return_value = np.array([[0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.09, 0.08]]) # Decay at 0.09 (9th frame)

    # Now, let's try calling the function with a dummy audio that is long enough
    long_dummy_audio = np.random.rand(int(MOCK_SR * 2.0)).astype(np.float32) # 2 seconds
    segment = drum_analysis.extract_dynamic_segment(
        long_dummy_audio, MOCK_SR, 0.0,
        max_duration=2.0, decay_threshold_db=-20.0
    )

    # The decay happens at the 9th RMS frame. Each frame is hop_length_samples.
    # (9 * int(0.01 * MOCK_SR) + 1024 // 2) samples
    expected_end_sample_approx = (9 * int(0.01 * MOCK_SR)) + (1024 // 2)
    expected_duration_approx = expected_end_sample_approx / MOCK_SR

    assert len(segment) == pytest.approx(expected_end_sample_approx, abs=100) # Allowing some sample tolerance

def test_extract_dynamic_segment_long_sustain_capped_by_max_duration_mocked():
    # Simulate RMS that never drops below threshold (e.g., constant high energy)
    with patch('librosa.feature.rms') as mock_rms, \
         patch('librosa.time_to_samples') as mocked_time_to_samples:
        mocked_time_to_samples.return_value = 0
        mock_rms.return_value = np.array([[0.8] * 200]) # RMS always high

        max_duration = 1.0
        # A dummy audio longer than max_duration
        long_dummy_audio = np.random.rand(int(MOCK_SR * 2.0)).astype(np.float32)
        segment = drum_analysis.extract_dynamic_segment(
            long_dummy_audio, MOCK_SR, 0.0,
            max_duration=max_duration, decay_threshold_db=-20.0
        )

        assert len(segment) == pytest.approx(max_duration * MOCK_SR, abs=100) # Should be capped by max_duration

def test_extract_dynamic_segment_onset_at_end_of_audio_mocked():
    with patch('librosa.feature.rms') as mock_rms, \
         patch('librosa.time_to_samples') as mock_time_to_samples:
        mock_time_to_samples.return_value = int(0.4 * MOCK_SR) # Onset at 0.4s
        mock_rms.return_value = np.array([[0.5, 0.4]]) # Dummy RMS

        # Short dummy audio, onset at 0.4s, so only 0.1s left
        short_dummy_audio = np.random.rand(int(0.5 * MOCK_SR)).astype(np.float32)
        onset_time = 0.4
        max_duration = 0.5
        segment = drum_analysis.extract_dynamic_segment(
            short_dummy_audio, MOCK_SR,
            onset_time, max_duration=max_duration
        )

        assert len(segment) == pytest.approx(int(0.1 * MOCK_SR), abs=10) # Should be remaining duration

def test_extract_dynamic_segment_no_segment_y():
    with patch('librosa.feature.rms') as mock_rms, \
         patch('librosa.time_to_samples') as mocked_time_to_samples:
        mocked_time_to_samples.return_value = int(1.0 * MOCK_SR) # Onset beyond audio length

        short_dummy_audio = np.random.rand(int(0.5 * MOCK_SR)).astype(np.float32)
        onset_time = 1.0
        segment = drum_analysis.extract_dynamic_segment(short_dummy_audio, MOCK_SR, onset_time, max_duration=0.5)
        assert len(segment) == 0

# --- Tests for extract_features_from_segment (mocking librosa calls for isolation) ---
@patch('librosa.feature.rms')
@patch('librosa.feature.spectral_centroid')
@patch('librosa.feature.spectral_rolloff')
@patch('librosa.onset.onset_strength') # For spectral flux
@patch('librosa.feature.mfcc')
@patch('librosa.pyin') # For F0
def test_extract_features_from_segment(
    mock_pyin, mock_mfcc, mock_onset_strength,
    mock_rolloff, mock_centroid, mock_rms
):
    # Dummy segment length
    segment = np.random.rand(int(0.1 * MOCK_SR)).astype(np.float32) # 0.1 seconds segment

    # Configure mocks to return predictable values
    mock_rms.return_value = np.array([[0.123]])
    mock_centroid.return_value = np.array([[500]])
    mock_rolloff.return_value = np.array([[1500]])
    mock_onset_strength.return_value = np.array([[0.05]])
    mock_mfcc.return_value = np.array([[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130]]).T
    mock_pyin.return_value = (np.array([440, 0, 440]), np.array([]), np.array([])) # F0 values with some zeros

    features = drum_analysis.extract_features_from_segment(segment, MOCK_SR)

    assert features['relative_volume'] == pytest.approx(0.123)
    assert features['dominant_frequency'] == pytest.approx(440.0) # Should average non-zero F0s
    assert features['spectral_centroid'] == pytest.approx(500.0)
    assert features['spectral_rolloff'] == pytest.approx(1500.0)
    assert features['spectral_flux'] == pytest.approx(0.05)
    assert len(features['mfccs']) == 13
    assert features['mfccs'][0] == pytest.approx(10.0)
    assert features['duration'] == pytest.approx(0.1)

    mock_rms.assert_called_once()
    mock_centroid.assert_called_once()
    mock_rolloff.assert_called_once()
    mock_onset_strength.assert_called_once()
    mock_mfcc.assert_called_once()
    mock_pyin.assert_called_once()

def test_extract_features_from_segment_empty_segment():
    sr = 22050
    segment = np.array([], dtype=np.float32)
    features = drum_analysis.extract_features_from_segment(segment, sr)

    # All features should be 0 or empty for an empty segment
    assert features['relative_volume'] == 0.0
    assert features['dominant_frequency'] == 0.0
    assert features['spectral_centroid'] == 0.0
    assert features['spectral_rolloff'] == 0.0
    assert features['spectral_flux'] == 0.0
    assert features['mfccs'] == [0.0] * 13
    assert features['duration'] == 0.0

# --- Tests for analyze_audio_concurrently ---
@patch('musictranslator.drum_analysis_service.drum_analysis.ThreadPoolExecutor')
@patch('musictranslator.drum_analysis_service.drum_analysis.detect_onsets')
@patch('concurrent.futures.as_completed')
def test_analyze_audio_concurrently(
    mock_as_completed,
    mock_detect_onsets,
    mock_executor
):
    # Dummy audio input for the orchestrator function
    y = np.random.rand(MOCK_SR * 2).astype(np.float32) # 2 seconds of dummy audio

    # Mock onsets returned by detect onsets
    mock_detect_onsets.return_value = [0.5, 1.0, 1.5] # Three onsets

    # Mock feature extraction (return dummy feature dicts)
    # The order of results from as_completed might not be the same as input order,
    # so ensure the test can handle that. Our analyze_audio_concurrently sorts them.
    mock_extracted_features = [
        {'onset_time': 0.5, 'relative_volume': 0.1, 'dominant_frequency': 100, 'duration': 0.1},
        {'onset_time': 1.0, 'relative_volume': 0.2, 'dominant_frequency': 200, 'duration': 0.1},
        {'onset_time': 1.5, 'relative_volume': 0.3, 'dominant_frequency': 300, 'duration': 0.1}
    ]

    # Setup the submit and as_completed
    mock_future1 = MagicMock()
    mock_future2 = MagicMock()
    mock_future3 = MagicMock()

    # The _process_single_onset function will be executed.
    # It's return value is the dict.
    # The submit method should return a future whose .result() mnethod
    # returns that dict.
    mock_future1.result.return_value = mock_extracted_features[0]
    mock_future2.result.return_value = mock_extracted_features[1]
    mock_future3.result.return_value = mock_extracted_features[2]

    # Create a mock instance for the executor that comes out of the 'with' statement
    # This makes 'with ThreadPoolExecutor() as executor_instance:' yield our mock_executor_instance
    mock_executor_instance = MagicMock()
    mock_executor.return_value.__enter__.return_value = mock_executor_instance

    # as_completed yields futures. The key of futures dict stores onset_time
    mock_executor_instance.submit.side_effect = [
        mock_future1, mock_future2, mock_future3
    ]
    # Simulate as_completed yielding them possibly out of order
    mock_as_completed.return_value = [
        mock_future3, mock_future1, mock_future2
    ]

    results = drum_analysis.analyze_audio_concurrently(y, MOCK_SR)

    assert len(results) == 3
    # Assert sorted order by onset_time
    assert results[0]['onset_time'] == pytest.approx(0.5)
    assert results[1]['onset_time'] == pytest.approx(1.0)
    assert results[2]['onset_time'] == pytest.approx(1.5)

    mock_detect_onsets.assert_called_once_with(y, MOCK_SR)

    # Verify that _process_single_onset was called for each onset
    mock_executor_instance.submit.assert_any_call(
        drum_analysis._process_single_onset, y, MOCK_SR, 0.5, 1.0
    )
    mock_executor_instance.submit.assert_any_call(
        drum_analysis._process_single_onset, y, MOCK_SR, 1.0, 1.5
    )
    mock_executor_instance.submit.assert_any_call(
        drum_analysis._process_single_onset, y, MOCK_SR, 1.5, None
    )

    expected_futures_arg = {mock_future1, mock_future2, mock_future3}
    actual_futures_arg = set(mock_as_completed.call_args[0][0])
    assert actual_futures_arg == expected_futures_arg
    assert mock_as_completed.call_count == 1

@patch('musictranslator.drum_analysis_service.drum_analysis.detect_onsets')
def test_analyze_audio_concurrently_no_onsets(mock_detect_onsets):
    y = np.random.rand(MOCK_SR).astype(np.float32)
    mock_detect_onsets.return_value = [] # Simulates no onsets found

    results = drum_analysis.analyze_audio_concurrently(y, MOCK_SR)
    assert len(results) == 0
    mock_detect_onsets.assert_called_once_with(y, MOCK_SR)
