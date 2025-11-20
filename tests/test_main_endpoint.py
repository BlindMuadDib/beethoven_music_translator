import json
import os
import io
import uuid
import pytest
import redis
import rq
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import patch, MagicMock, ANY
from musictranslator.main import app

# --- Pytest Fixtures
@pytest.fixture
def client():
    """
    Pytest fixture to create a test client for the Flask app
    """
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client # provide the client to the tests

@pytest.fixture
def mock_uuid_generator():
    """Fixture to mock uuid.uuid4 for predictable job IDs."""
    test_job_id = str(uuid.uuid4())
    with patch('uuid.uuid4', return_value=test_job_id) as mock_uuid:
        yield {'uuid4': mock_uuid, 'test_job_id': test_job_id}

@pytest.fixture
def mock_rq_components(mock_uuid_generator):
    """Fixture to mock RQ components (Redis connection, Queue, Job)."""
    mocks = {
        'redis_conn': MagicMock(spec=redis.Redis),
        'queue': MagicMock(spec=rq.Queue),
        'job': MagicMock(spec=rq.job.Job)
    }
    # Ensure ping on the mock redis connection does not raise an error by default
    mocks['redis_conn'].ping.return_value = True

    # Patch the functions in the main module where they are looked up
    with patch('musictranslator.main.get_redis_connection', return_value=mocks['redis_conn']) as mock_get_conn, \
         patch('musictranslator.main.get_translation_queue', return_value=mocks['queue']) as mock_get_queue, \
         patch('rq.job.Job.fetch', return_value=mocks['job']) as mock_job_fetch:

        mocks['job'].id = mock_uuid_generator['test_job_id'] # Use consistent job ID
        mocks['job'].meta = {} # Initialize meta for progress tracking
        mocks['job'].args = () # Initialize args
        # Ensure enqueue returns the mock job for the /translate endpoint
        mocks['queue'].enqueue.return_value = mocks['job']
        yield {
            **mocks,
            'get_conn': mock_get_conn,
            'get_queue': mock_get_queue,
            'job_fetch': mock_job_fetch
        }

@pytest.fixture
def mock_file_validation():
    """Fixture to mock file validation functions."""
    with patch('musictranslator.main.validate_audio', return_value=True) as mock_va, \
         patch('musictranslator.main.validate_text', return_value=True) as mock_vt:
        yield {'validate_audio': mock_va, 'validate_text': mock_vt}

# --- Helper Functions ---

def _get_project_root():
    """Get's the project root directory from the current test file's location."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_test_file(filepath):
    """Helper function to load test file data"""
    # Construct path relative to the test file's directory if it's not absolute
    if not os.path.isabs(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir) # Get parent of 'tests' directory
        filepath = os.path.join(project_root, filepath)

    try:
        with open(filepath, 'rb') as f:
            return io.BytesIO(f.read())
    except FileNotFoundError as e:
        pytest.fail(f"Test file not found: {filepath}. Original error: {e}")

def load_json_file(filepath):
    """Helper function to load JSON test data"""
    if not os.path.isabs(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir) # Get parent of 'tests' directory
        filepath = os.path.join(project_root, filepath)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError as e:
        pytest.fail(f"JSON test file not found: {filepath}. Original error: {e}")
    except json.JSONDecodeError as e:
        pytest.fail(f"Error decoding JSON from {filepath}: {e}")

# --- Test Cases ---

def test_translate_endpoint_post_success(
    client: FlaskClient,
    mock_rq_components: dict,
    mock_file_validation: dict,
    mock_uuid_generator: dict
):
    """
    Test the /translate and /results endpoints
    for a successful async translation
    """
    # --- Mock the call to the auth service ---
    with patch('musictranslator.main.is_session_valid',
               return_value=True) as mock_session_valid:

        audio_file_path = "data/audio/BloodCalcification-SkinDeep.wav"
        lyrics_file_path = "data/lyrics/BloodCalcification-SkinDeep.txt"
        # Update the mapped_result before running test with the new structure
        expected_mapped_results_path = "data/mapped_results/BloodCalcification-SkinDeep.json"

        audio_data = load_test_file(audio_file_path)
        lyrics_data = load_test_file(lyrics_file_path)
        expected_mapped_results = load_json_file(expected_mapped_results_path)

        mock_drum_analysis_data = {
            "hits": [
                {
                    "onset_time": 0.5,
                    "duration": 0.1,
                    "relative_volume": 0.123,
                    "dominant_frequency": 440.0,
                    "spectral_centroid": 500.0,
                    "spectral_rolloff": 1500.0,
                    "spectral_flux": 0.05,
                    "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                    "drum_category": "snare",
                    "category_confidence": 0.94,
                    "drum_type": "open_band",
                    "type_confidence": 0.95,
                    "qualifier": "rimshot",
                    "qualifier_confidence": 0.99
                },
                {
                    "onset_time": 1.2,
                    "duration": 0.08,
                    "relative_volume": 0.098,
                    "dominant_frequency": 220.0,
                    "spectral_centroid": 300.0,
                    "spectral_rolloff": 1000.0,
                    "spectral_flux": 0.03,
                    "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                    "drum_category": "kick",
                    "category_confidence": 0.99,
                    "drum_type": "bass",
                    "type_confidence": 0.98,
                    "qualifier": "no_qualifier",
                    "qualifier_confidence": 1.0
                }
            ],
            "tempo": 180.0
        }

        data = {
            'audio': (audio_data, os.path.basename(audio_file_path)),
            'lyrics': (lyrics_data, os.path.basename(lyrics_file_path)),
        }

        # --- Phase 1: Test /translate endpoint (Job Enqueueing) ---
        # Mock werkzeug's save to prevent actual file writes during this part of the test
        # The files should be saved to the unique paths for the background worker
        with patch('werkzeug.datastructures.FileStorage.save') as mock_file_save:
            # Set the session cookie on the client
            client.set_cookie('session', 'a-valid-session-cookie')
            response_translate = client.post(
                '/api/translate',
                data=data,
                content_type='multipart/form-data'
            )

        assert response_translate.status_code == 202, f"Response data: {response_translate.data.decode()}"
        # Assert session validation was called
        mock_session_valid.assert_called_once_with('a-valid-session-cookie')

        response_translate_json = response_translate.get_json()
        enqueued_job_id = response_translate_json['job_id']
        assert enqueued_job_id == mock_uuid_generator['test_job_id'] # Check our mocked UUID was used

        # Assert file validation mocks were called
        mock_file_validation['validate_audio'].assert_called_once()
        mock_file_validation['validate_text'].assert_called_once()
        # Assert that FileStorage.save was called for audio and lyrics
        assert mock_file_save.call_count == 2

        # Construct expected unique paths (these are passed to the background task)
        expected_unique_audio_path = f"/shared-data/audio/{enqueued_job_id}_{os.path.basename(audio_file_path)}"
        expected_unique_lyrics_path = f"/shared-data/lyrics/{enqueued_job_id}_{os.path.basename(lyrics_file_path)}"

        expected_audio_url = f"api/files/{enqueued_job_id}_{os.path.basename(audio_file_path)}"
        expected_harmonic_urls = {
            "static_results_url": f"api/results/file/{enqueued_job_id}_harmonic.json",
            "streaming_urls": {
                "vocals": f"api/results/stream/{enqueued_job_id}_vocals.ndjson?stem_path=...",
                "bass": f"api/results/stream/{enqueued_job_id}_bass.ndjson?stem_path=..."
            }
        }

        expected_final_result = {
            "mapped_result": expected_mapped_results,
            "harmonic_analysis": expected_harmonic_urls,
            "drum_analysis": mock_drum_analysis_data,
            "audio_url": expected_audio_url,
            "original_filename": "BloodCalcification-SkinDeep.wav"
        }

        # Check how save was called (order might vary, check both calls)
        saved_paths = [call_args[0][0] for call_args in mock_file_save.call_args_list]
        assert expected_unique_audio_path in saved_paths
        assert expected_unique_lyrics_path in saved_paths

        # Assert RQ enqueue was called correctly
        mock_rq_components['get_queue'].assert_called_once()
        mock_rq_components['queue'].enqueue.assert_called_once()
        pos_args_enqueue, kw_args_enqueue = mock_rq_components['queue'].enqueue.call_args
        assert pos_args_enqueue[0] == 'musictranslator.main.background_translation_task'
        # Check arguments passed to the background task
        expected_task_args = (
            expected_unique_audio_path,
            expected_unique_lyrics_path,
            f"{enqueued_job_id}_{os.path.basename(audio_file_path)}",
            os.path.basename(audio_file_path)
        )
        assert kw_args_enqueue.get('args') == expected_task_args
        assert kw_args_enqueue.get('job_id') == enqueued_job_id

        # --- Phase 2: Test /results/<job_id> endpoint (successful Job Completion) ---
        mock_job = mock_rq_components['job']
        mock_job.is_finished = True
        mock_job.is_failed = False
        mock_job.result = expected_final_result

        response_results = client.get(f'/api/results/{enqueued_job_id}')

    assert response_results.status_code == 200, f"Response data: {response_results.data.decode()}"
    response_results_json = response_results.get_json()
    assert response_results_json["status"] == "finished"
    response_results_json["result"]["harmonic_analysis"]["streaming_urls"] = ANY
    expected_final_result["harmonic_analysis"]["streaming_urls"] = ANY
    assert response_results_json["result"] == expected_final_result

    mock_rq_components['job_fetch'].assert_called_once_with(enqueued_job_id, connection=mock_rq_components['redis_conn'])

def test_translate_endpoint_unauthenticated(client: FlaskClient,
                                            mock_rq_components):
    """
    Test /translate endpoint with a no session cookie.
    """
    # No patch for is_session_valid, or patch it to return False
    with patch('musictranslator.main.is_session_valid', return_value=False) as mock_session_valid:
        audio_file_path = "data/audio/BloodCalcification-SkinDeep.wav"
        lyrics_file_path = "data/lyrics/BloodCalcification-SkinDeep.txt"
        audio_data = load_test_file(audio_file_path)
        lyrics_data = load_test_file(lyrics_file_path)

        data = {
            'audio': (audio_data, os.path.basename(audio_file_path)),
            'lyrics': (lyrics_data, os.path.basename(lyrics_file_path))
        }

        response = client.post(
            '/api/translate',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 401
        assert response.get_json() == {"error": "Access Denied. Please log in."}
        # Ensure no job was enqueued
        mock_rq_components['queue'].enqueue.assert_not_called()

def test_serve_results_file_success(client: FlaskClient):
    """
    Test the serve results endpoint for serving result files successfully.
    """
    with patch('musictranslator.main.send_from_directory') as mock_send:
        mock_send.return_value = "file content"
        response = client.get('/api/results/file/some_results_file.json')
        assert response.status_code == 200
        assert response.data == b"file content"
        mock_send.assert_called_once_with('/shared-data/results',
                                          'some_results_file.json',
                                          as_attachment=False)

def test_serve_results_file_not_found(client: FlaskClient):
    """
    Test the new results file endpoint when the file is not found.
    """
    with patch('musictranslator.main.send_from_directory',
               side_effect=FileNotFoundError) as mock_send:
        response = client.get('/api/results/file/not_found.json')
        assert response.status_code == 404
        assert response.get_json() == {"error": "File not found"}

def test_get_results_success_harmonic_error(
    client: FlaskClient,
    mock_rq_components: dict,
    mock_uuid_generator: dict
):
    """Tests /results when F0 analysis part of the job reported an error."""
    job_id = mock_uuid_generator['test_job_id']
    mock_job = mock_rq_components['job']

    expected_mapped_results = [{
            'line_text': 'example line',
            'words': [
                {'text': 'example', 'start': 0.1, 'end': 0.5},
                {'text': 'line', 'start': 0.6, 'end': 1.0}
            ],
            'line_start_time': 0.1,
            'line_end_time': 1.0
        }]
    harmonic_error_report = {
        "error": "Harmonic service timeout during processing.",
        "info": "Harmonic analysis did not complete successfully."
    }
    expected_final_result_with_harmonic_error = {
        "mapped_result": expected_mapped_results,
        "harmonic_analysis": harmonic_error_report,
        "drum_analysis": [],
        "audio_url": "/files/some_audio.wav",
        "original_filename": "audio.wav"
    }

    mock_job.id = job_id # Ensure fetched job ID matches
    mock_job.is_finished = True
    mock_job.is_failed = False
    mock_job.result = expected_final_result_with_harmonic_error

    response_results = client.get(f'/api/results/{job_id}')
    assert response_results.status_code == 200
    response_results_json = response_results.get_json()
    assert response_results_json == {"status": "finished", "result": expected_final_result_with_harmonic_error}
    mock_rq_components['job_fetch'].assert_called_once_with(job_id, connection=mock_rq_components['redis_conn'])

def test_get_results_pending_with_progress(
    client: FlaskClient,
    mock_rq_components: dict,
    mock_uuid_generator: dict
):
    """Tests /results endpoint for a pending job with a progress_stage in meta."""
    job_id = mock_uuid_generator['test_job_id']

    mock_job = mock_rq_components['job']
    mock_job.id = job_id # Ensure the fetched job ID matches
    mock_job.is_finished = False
    mock_job.is_failed = False
    mock_job.get_status.return_value = 'started'
    mock_job.meta = {'progress_stage': 'stem_processing'}

    response = client.get(f'/api/results/{job_id}')
    assert response.status_code == 202
    expected_response_data = {
        "status": "started",
        "progress_stage": "stem_processing"
    }
    assert response.get_json() == expected_response_data
    mock_rq_components['job_fetch'].assert_called_once_with(job_id, connection=mock_rq_components['redis_conn'])
    mock_job.get_status.assert_called_once()

def test_translate_endpoint_missing_audio(client: FlaskClient, mock_rq_components):
    """
    Test /translate endpoint with missing audio file
    """
    with patch('musictranslator.main.is_session_valid', return_value=True):
        lyrics_file_path = "data/lyrics/BloodCalcification-SkinDeep.txt"
        lyrics_data = load_test_file(lyrics_file_path)
        data = {'lyrics': (lyrics_data, os.path.basename(lyrics_file_path))}

        client.set_cookie('session', 'a-valid-session-cookie')
        response = client.post(
            '/api/translate',
            data=data,
            content_type='multipart/form-data'
        )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing audio or lyrics file."}
    mock_rq_components['get_queue'].assert_called_once() # Should still try to get queue

def test_translate_endpoint_missing_lyrics(client: FlaskClient, mock_rq_components):
    """
    Test /translate endpoint with missing lyrics file
    """
    with patch('musictranslator.main.is_session_valid', return_value=True):
        audio_file_path = "data/audio/BloodCalcification-SkinDeep.wav"
        audio_data = load_test_file(audio_file_path)
        data = {'audio': (audio_data, os.path.basename(audio_file_path))}

        client.set_cookie('session', 'a-valid-session-cookie')
        response = client.post(
                '/api/translate',
                data=data,
                content_type='multipart/form-data'
            )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing audio or lyrics file."}
    mock_rq_components['get_queue'].assert_called_once() # Should still try to get queue
