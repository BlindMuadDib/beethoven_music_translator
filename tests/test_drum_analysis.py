import io
import os
import logging
import concurrent
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch, MagicMock
import numpy as np
import pytest
import librosa
import librosa.display
import soundfile as sf

from musictranslator.drum_analysis_service import drum_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# --- Tests for load_audio_from_file ---
@patch('musictranslator.drum_analysis_service.drum_analysis.os.path.exists')
@patch('librosa.load')
def test_load_audio_from_file_success(mock_load, mock_exists):
    mock_exists.return_value = True
    mock_load.return_value = (np.array([1, 2, 3], dtype=np.float32), MOCK_SR)

    y, sr = drum_analysis.load_audio_from_file("dummy.wav")

    mock_exists.assert_called_once_with("dummy.wav")
    mock_load.assert_called_once_with("dummy.wav", sr=None, mono=True)
    assert isinstance(y, np.ndarray)
    assert sr == MOCK_SR

@patch('musictranslator.drum_analysis_service.drum_analysis.os.path.exists')
def test_load_audio_from_file_not_found(mock_exists):
    mock_exists.return_value = False

    with pytest.raises(FileNotFoundError, match="Audio file not found: non_existent.wav"):
        drum_analysis.load_audio_from_file("non_existent.wav")

    mock_exists.assert_called_once_with("non_existent.wav")

@patch('musictranslator.drum_analysis_service.drum_analysis.os.path.exists', return_value=True)
@patch('librosa.load', side_effect=Exception("Corrupt file"))
def test_load_audio_from_file_loading_error(mock_exists, mock_load):
    with pytest.raises(Exception, match="Corrupt file"):
        drum_analysis.load_audio_from_file("corrupt.wav")
    mock_load.assert_called_once_with("corrupt.wav")

# --- Tests for detect_onsets (mocking librosa internals) ---
@patch('librosa.onset.onset_strength')
@patch('librosa.onset.onset_detect')
@patch('librosa.frames_to_time')
def test_detect_onsets_success(
    mock_frames_to_time, mock_onset_detect, mock_onset_strength
):
    y = np.random.rand(MOCK_SR * 5).astype(np.float32) # 5 sec audio
    mock_onset_strength.return_value = np.random.rand(100) # Dummy onset strength
    mock_onset_detect.return_value = np.array([10, 20, 30]) # Dummy onset frames
    mock_frames_to_time.return_value = np.array([0.1, 0.2, 0.3]) # Dummy onset times

    onsets = drum_analysis.detect_onsets(y, MOCK_SR)

    assert onsets == [0.1, 0.2, 0.3]
    mock_onset_strength.assert_called_once_with(y=y, sr=MOCK_SR)
    mock_onset_detect.assert_called_once() # Args are complex, just check if called
    mock_frames_to_time.assert_called_once_with(mock_onset_detect.return_value, sr=MOCK_SR)

@patch('librosa.onset.onset_strength', return_value=np.array([]))
def test_detect_onsets_empty_onset_env(mock_onset_strength):
    y = np.random.rand(MOCK_SR * 5).astype(np.float32)
    onsets = drum_analysis.detect_onsets(y, MOCK_SR)
    assert onsets == []
    mock_onset_strength.assert_called_once()

@patch('librosa.onset.onset_strength', return_value=None)
def test_detect_onsets_none_onset_env(mock_onset_strength):
    y = np.random.rand(MOCK_SR * 5).astype(np.float32)
    onsets = drum_analysis.detect_onsets(y, MOCK_SR)
    assert onsets == []
    mock_onset_strength.assert_called_once()

@patch('librosa.onset.onset_strength')
@patch('librosa.onset.onset_detect', return_value=np.array([]))
@patch('librosa.frames_to_time')
def test_detect_onsets_no_onsets_detected(
    mock_frames_to_time, mock_onset_detect, mock_onset_strength
):
    y = np.random.rand(MOCK_SR * 5).astype(np.float32)
    mock_onset_strength.return_value = np.random.rand(100)
    mock_frames_to_time.return_value = np.array([]) # No onset times

    onsets = drum_analysis.detect_onsets(y, MOCK_SR)
    assert onsets == []
    mock_onset_detect.assert_called_once()

# --- Tests for extract_dynamic_segment (mocking librosa internals) ---
@patch('librosa.time_to_samples')
@patch('librosa.feature.rms')
def test_extract_dynamic_segment_decay_detected_mocked(
    mock_rms, mock_samples_to_time
):
    # Simulate RMS decay below threshold
    # RMS values correspond to frames. Assuming hop_length_samples =
    # 0.01 * MOCK_SR, a frame_length of 1024 samples is used for RMS.
    # decay_threshold_db = -20.0 (relative to peak 0.8) -> 09 *
    # 10^(-20/20) = 0.8 * 0.1 = 0.08
    # So, decay should be detected when RMS drops below 0.08
    mock_rms.return_value = np.array([[0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.09, 0.07]]) # Decay at 0.07 (10th frame)

    # Now, let's try calling the function with a dummy audio that is
    # long enough
    long_dummy_audio = np.random.rand(int(MOCK_SR * 2.0)).astype(np.float32) # 2 seconds
    segment = drum_analysis.extract_dynamic_segment(
        long_dummy_audio, MOCK_SR, 0.0,
        max_duration=2.0, decay_threshold_db=-20.0
    )

    # The decay happens at the 10th RMS frame (index 9). Each frame is
    # hop_length_samples. The RMS calculation uses
    # hoplength=int(0.01*sr) and frame_length=1024
    hop_length_samples = int(0.01 * MOCK_SR)
    frame_length_samples = 1024

    # Decay detected at frame index 9 (the 10th frame in the mocked
    # rms array). The end sample is approx the start of that frame +
    # half its length
    expected_end_sample_relative = 9 * hop_length_samples + (frame_length_samples // 2)

    assert len(segment) == pytest.approx(
        expected_end_sample_relative,
        abs=int(frame_length_samples)
    ) # Allowing some sample tolerance (up to a full frame)

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

        assert len(segment) == pytest.approx(
            max_duration * MOCK_SR, abs=100
        ) # Should be capped by max_duration

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

        assert len(segment) == pytest.approx(
            int(0.1 * MOCK_SR), abs=10
        ) # Should be remaining duration

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

# --- Tests for estimate_tempo ---
@patch('librosa.onset.onset_strength')
@patch('librosa.beat.beat_track')
def test_estimate_tempo_success(mock_beat_track, mock_onset_strength):
    y = np.random.rand(MOCK_SR * 10).astype(np.float32) # 10 seconds audio
    mock_onset_strength.return_value = np.random.rand(200) # Dummy onset envelope
    mock_beat_track.return_value = (120.5, np.array([1,2,3])) # Dummy tempo and beats

    tempo = drum_analysis.estimate_tempo(y, MOCK_SR)

    assert tempo == pytest.approx(120.5)
    mock_onset_strength.assert_called_once_with(y=y, sr=MOCK_SR)
    mock_beat_track.assert_called_once_with(
        onset_envelope=mock_onset_strength.return_value,
        sr=MOCK_SR
    )

@patch('librosa.onset.onset_strength', side_effect=Exception("Onset strength error"))
def test_estimate_tempo_onset_strength_error(mock_onset_strength):
    y = np.random.rand(MOCK_SR * 10).astype(np.float32)
    tempo = drum_analysis.estimate_tempo(y, MOCK_SR)
    assert tempo == 0.0
    mock_onset_strength.assert_called_once()

@patch('librosa.beat.beat_track', side_effect=Exception("Beat track error"))
@patch('librosa.onset.onset_strength', return_value=np.random.rand(200))
def test_estimate_tempo_beat_track_error(mock_onset_strength, mock_beat_track):
    y = np.random.rand(MOCK_SR * 10).astype(np.float32)
    tempo = drum_analysis.estimate_tempo(y, MOCK_SR)
    assert tempo == 0.0
    mock_onset_strength.assert_called_once()
    mock_beat_track.assert_called_once()

# --- Tests for analyze_audio_concurrently ---

def test_analyze_audio_concurrently():
    # Dummy audio input for the orchestrator function
    y = np.random.rand(MOCK_SR * 2).astype(np.float32) # 2 seconds of dummy audio

    with patch('musictranslator.drum_analysis_service.drum_analysis.ProcessPoolExecutor') as mock_executor, \
        patch('musictranslator.drum_analysis_service.drum_analysis.detect_onsets') as mock_detect_onsets, \
        patch('concurrent.futures.as_completed') as mock_as_completed:

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

        # Mock for the tempo future
        mock_tempo_future = MagicMock()
        mock_tempo_future.result.return_value = 120.0

        # Create a mock instance for the executor that comes out of the 'with' statement
        # This makes 'with ProcessPoolExecutor() as executor_instance:' yield our mock_executor_instance
        mock_executor_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        mock_executor_instance.submit.return_value = mock_tempo_future

        mock_executor_instance.map.return_value = iter(mock_extracted_features)

        results = drum_analysis.analyze_audio_concurrently(
            y, MOCK_SR
        )

        # Assert the overall structure of the returned dictionary
        assert isinstance(results, dict)
        assert 'hits' in results
        assert 'tempo' in results

        # Assert tempo
        assert results['tempo'] == pytest.approx(120.0)

        # Assert drum hits
        assert len(results['hits']) == len(mock_extracted_features)
        # Assert sorted order by onset_time
        assert [hit['onset_time'] for hit in results['hits']] == sorted(
            [f['onset_time'] for f in mock_extracted_features]
        )

        mock_detect_onsets.assert_called_once_with(y, MOCK_SR)

        # Assert that _estimate_tempo_worker was submitted. We need
        # to check the call to submit that *actually* targets the
        # worker function. The submit method for the tempo is called
        # first.
        assert mock_executor_instance.submit.call_args_list[0].args[0] is drum_analysis._estimate_tempo_worker

        # Assert that _process_single_onset_worker was mapped
        assert mock_executor_instance.map.called
        assert mock_executor_instance.map.call_args[0][0] is drum_analysis._process_single_onset_worker
        # Verify the tasks passed to map are correct (based on
        # detect_onsets return_value)
        expected_tasks = [
            (0.5, 1.0),
            (1.0, 1.5),
            (1.5, None)
        ]
        assert mock_executor_instance.map.call_args[0][1] == expected_tasks

def test_analyze_audio_concurrently_no_onsets():
    y = np.random.rand(MOCK_SR).astype(np.float32)

    with patch('musictranslator.drum_analysis_service.drum_analysis.ProcessPoolExecutor') as mock_executor, \
        patch('musictranslator.drum_analysis_service.drum_analysis.detect_onsets') as mock_detect_onsets:

        mock_detect_onsets.return_value = [] # Simulates no onsets found

        # Mock the executor context manager behavior
        mock_executor_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        mock_tempo_future = MagicMock()
        mock_tempo_future.result.return_value = 90.0

        mock_executor_instance.submit.return_value = mock_tempo_future

        results = drum_analysis.analyze_audio_concurrently(
            y, MOCK_SR
        )

        assert isinstance(results, dict)
        assert 'hits' in results
        assert 'tempo' in results
        assert results['hits'] == []
        assert results['tempo'] == pytest.approx(90.0)

        mock_detect_onsets.assert_called_once_with(y, MOCK_SR)

        # Verify that tempo was submitted
        assert mock_executor_instance.submit.called
        assert mock_executor_instance.submit.call_args[0][0] is drum_analysis._estimate_tempo_worker

        # Verify that map was NOT called for onsets since there are no onsets
        mock_executor_instance.map.assert_not_called()

def test_analyze_audio_concurrently_hit_processing_error_sad_path():
    y = np.random.rand(MOCK_SR * 2).astype(np.float32)

    with patch('musictranslator.drum_analysis_service.drum_analysis.ProcessPoolExecutor') as mock_executor, \
        patch('musictranslator.drum_analysis_service.drum_analysis.detect_onsets') as mock_detect_onsets:

        mock_detect_onsets.return_value = [0.5, 1.2]

        mock_executor_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        # Mock behavior of submit calls: one for tempo, one for hit
        mock_tempo_future = MagicMock()
        mock_tempo_future.result.return_value = 120.0

        # Configure the executor's submit method for tempo
        mock_executor_instance.submit.return_value = mock_tempo_future

        # Configure the executor's map method to raise an exception
        # for all items when its iterator is consumed.
        def error_iterator():
            yield Exception("Processing error 1")
            yield Exception("Processing error 2")

        # We need to make the results from map raise an exception
        # when consumed. We can simulate this by making the generator
        # yield exceptions, or by making the .result() of futures
        # within map raise. Since map returns results directly, we
        # simulate the `_process_single_onset_worker` returning
        # None when an error occurs, as per the `_process_single_onset`
        # which returns None on error
        mock_executor_instance.map.return_value = iter([None, None])

        results = drum_analysis.analyze_audio_concurrently(
            y, MOCK_SR
        )

        assert isinstance(results, dict)
        assert 'hits' in results
        assert 'tempo' in results
        # No hits should be returned if processing fails
        assert results['hits'] == []
        assert results['tempo'] == pytest.approx(120.0)

        mock_detect_onsets.assert_called_once_with(y, MOCK_SR)

        assert mock_executor_instance.submit.call_args_list[0].args[0] is drum_analysis._estimate_tempo_worker

        # Assert that _process_single_onset_worker was mapped
        assert mock_executor_instance.map.called
        assert mock_executor_instance.map.call_args[0][0] is drum_analysis._process_single_onset_worker
        expected_tasks = [
            (0.5, 1.2),
            (1.2, None)
        ]
        assert mock_executor_instance.map.call_args[0][1] == expected_tasks
