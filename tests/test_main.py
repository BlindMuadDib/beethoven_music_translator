"""
Unit test for the Flask application main.py
Focuses on API endpoint behavior
"""

import os
import json
import tempfile
import shutil
import unittest
import uuid
import redis
import rq
from unittest.mock import patch, MagicMock
from musictranslator import main
from musictranslator.main import app

ACCESS_CODE = 'NH009_GBF45_DBV88_NFD'
mock_valid_codes = {ACCESS_CODE}

class TestMain(unittest.TestCase):
    """Testing suite"""
    def setUp(self):
        """Sets up a Flask test client and creates a temporary directory"""
        # Patch valid access codes *before* app context is used heavily
        self.access_patcher = patch('musictranslator.main.VALID_ACCESS_CODES', mock_valid_codes)
        self.access_patcher.start()

        # Patch Redis/RQ components
        self.mock_redis_conn = MagicMock(spec=redis.Redis)
        self.mock_redis_conn.ping.return_value = True

        self.mock_job = MagicMock(spec=rq.job.Job)
        self.mock_queue = MagicMock(spec=rq.Queue)

        # Patch the functions that return connections/queues
        self.patch_get_conn = patch('musictranslator.main.get_redis_connection', return_value=self.mock_redis_conn)
        self.patch_get_queue = patch('musictranslator.main.get_translation_queue', return_value=self.mock_queue)
        self.patch_job_fetch = patch('rq.job.Job.fetch', return_value=self.mock_job)

        # Patch uuid to control job IDs
        self.test_job_id = str(uuid.uuid4())
        self.patch_uuid = patch('uuid.uuid4', return_value=self.test_job_id)

        # Patch file validation to avoid dependency on external tools/libs in most tests
        self.patch_validate_audio = patch('musictranslator.main.validate_audio', return_value=True)
        self.patch_validate_text = patch('musictranslator.main.validate_text', return_value=True)

        # Patch os.remove and shutil.rmtree to avoid errors during cleanup mocking
        self.patch_os_remove = patch('os.remove')
        self.patch_shutil_rmtree = patch('shutil.rmtree')
        # Patch os.path.exists used in cleanup
        self.patch_os_path_exists = patch('os.path.exists', return_value=True)

        self.mock_get_conn = self.patch_get_conn.start()
        self.mock_get_queue = self.patch_get_queue.start()
        self.mock_job_fetch = self.patch_job_fetch.start()
        self.mock_uuid = self.patch_uuid.start()
        self.mock_validate_audio = self.patch_validate_audio.start()
        self.mock_validate_text = self.patch_validate_text.start()
        self.mock_os_remove = self.patch_os_remove.start()
        self.mock_shutil_rmtree = self.patch_shutil_rmtree.start()
        self.mock_os_path_exists = self.patch_os_path_exists.start()

        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        self.temp_dir = tempfile.mkdtemp()

        # Create minimal valid files for tests that need them
        self.test_audio_fd, self.test_audio_full_path = tempfile.mkstemp(suffix=".wav", dir=self.temp_dir)
        self.test_lyrics_fd, self.test_lyrics_full_path = tempfile.mkstemp(suffix=".txt", dir=self.temp_dir)

        # Create a minimal valid WAV file
        with open(self.test_audio_full_path, 'wb') as f:
            # Minimal WAV header (may not be valid for all tools)
            f.write(b'RIFF')
            f.write((36).to_bytes(4, 'little')) # File size - 8
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write((16).to_bytes(4, 'little')) # Format chunk size
            f.write((1).to_bytes(2, 'little')) # Audio format (PCM)
            f.write((1).to_bytes(2, 'little')) # Number of channels
            f.write((16000).to_bytes(4, 'little')) # Sample rate
            f.write((32000).to_bytes(4, 'little')) # Byte rate
            f.write((2).to_bytes(2, 'little')) # Block align
            f.write((16).to_bytes(2, 'little')) # Bits per sample
            f.write(b'data')
            f.write((0).to_bytes(4, 'little')) # Data chunk size

        # Create valid test lyrics
        with open(self.test_lyrics_full_path, 'w') as f:
            f.write('This is a test lyrics file.')

        # Mock the enqueue method to return our mock job
        self.mock_queue.enqueue.return_value = self.mock_job
        # Set the job id on the mock job itself
        self.mock_job.id = self.test_job_id
        self.mock_job.meta = {}
        self.mock_job.args = (
            f'/shared-data/audio/{self.test_job_id}_test_audio.wav',
            f'/shared-data/lyrics/{self.test_job_id}_test_lyrics.txt'
        )
        self.mock_job.kwargs = {}

    def tearDown(self):
        """Stops patchers and removes the temporary directory"""
        # Close file descriptors
        os.close(self.test_audio_fd)
        os.close(self.test_lyrics_fd)

        shutil.rmtree(self.temp_dir) # Clean up temp files

        # Stop all patchers
        self.patch_get_conn.stop()
        self.patch_get_queue.stop()
        self.patch_job_fetch.stop()
        self.patch_uuid.stop()
        self.patch_validate_audio.stop()
        self.patch_validate_text.stop()
        self.patch_os_remove.stop()
        self.patch_shutil_rmtree.stop()
        self.patch_os_path_exists.stop()
        self.access_patcher.stop()
        if self.app_context:
            self.app_context.pop()


    # --- Helper Methods ---
    def _post_translate(self, audio_filename='test_audio.wav', lyrics_filename='test_lyrics.txt', access_code=ACCESS_CODE):
        """Helper to post to the translate endpoint."""
        headers = {}
        if access_code:
            headers['X-Access-Code'] = access_code

        with open(self.test_audio_full_path, 'rb') as audio_file, \
             open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            data = {
                'audio': (audio_file, audio_filename),
                'lyrics': (lyrics_file, lyrics_filename)
            }
            return self.client.post('/translate', data=data, content_type='multipart/form-data', headers=headers)

    def _get_results(self, job_id):
        """Helper to get results from the results endpoint."""
        return self.client.get(f'/results/{job_id}')

    # --- Test Cases ---

    def test_translate_enqueue_success(self):
        """Tests the /translate endpoint successfully enqueues a job."""
        # Reset mocks for specific valdation if needed, otherwise defaults are fine
        self.mock_validate_audio.return_value = True
        self.mock_validate_text.return_value = True

        # Patch save method to avoid actual file saving issues in test environment
        with patch('werkzeug.datastructures.FileStorage.save') as mock_save:
            response = self._post_translate()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(json.loads(response.data), {'job_id': self.test_job_id})
        self.mock_get_queue.assert_called_once() # Ensure queue was requested
        # Check if save was called twice (for audio and lyrics)
        self.assertEqual(mock_save.call_count, 2)
        # Check if enqueue was called with the coorect background task path and args
        self.mock_queue.enqueue.assert_called_once()
        args, kwargs = self.mock_queue.enqueue.call_args
        self.assertEqual(args[0], 'musictranslator.main.background_translation_task')
        # The arguments for the background task itself are in kwargs['args']
        task_actual_args = kwargs.get('args')
        self.assertIsNotNone(task_actual_args, "Keyword argument 'args' for the task not found in enqueue call")
        self.assertIsInstance(task_actual_args, tuple, "'args' for the task should be a tuple")

        expected_audio_path = f'/shared-data/audio/{self.test_job_id}_test_audio.wav'
        expected_lyrics_path = f'/shared-data/lyrics/{self.test_job_id}_test_lyrics.txt'
        expected_task_args = (expected_audio_path, expected_lyrics_path)

        self.assertEqual(task_actual_args, expected_task_args)

        self.assertEqual(kwargs.get('job_id'), self.test_job_id)

    def test_translate_missing_audio(self):
        """Tests /translate with missing audio file"""
        with open(self.test_lyrics_full_path, 'rb') as lyrics_file:
            data = {'lyrics': (lyrics_file, 'test_lyrics.txt')}
            response = self.client.post('/translate', data=data, content_type='multipart/form-data', headers={'X-Access-Code': ACCESS_CODE})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing audio or lyrics file.'})

    def test_translate_missing_lyrics(self):
        """Tests the /translate endpoint when lyrics file is missing"""
        with open(self.test_audio_full_path, 'rb') as audio_file:
            data = {'audio': (audio_file, 'test_audio.wav')}
            response = self.client.post('/translate', data=data, content_type='multipart/form-data', headers={'X-Access-Code': ACCESS_CODE})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Missing audio or lyrics file.'})

    def test_translate_invalid_audio_type(self):
        """Tests /translate with invalid audio file type"""
        # Make validate_audio return False
        self.mock_validate_audio.return_value = False
        self.mock_validate_text.return_value = True

        with patch('werkzeug.datastructures.FileStorage.save'): # Mock save
            response = self._post_translate()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Invalid audio file.'})
        self.mock_validate_audio.assert_called_once()
        self.mock_validate_text.assert_not_called() # Should fail before text validation

    def test_translate_invalid_lyrics_type(self):
        """Tests /translate with invalid lyrics file type (validation fails)."""
        # Make validate_text return False
        self.mock_validate_audio.return_value = True # Ensure audio validation passes
        self.mock_validate_text.return_value = False

        with patch('werkzeug.datastructures.FileStorage.save'): # Mock save
            response = self._post_translate()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data), {'error': 'Invalid lyrics file.'})
        self.mock_validate_audio.assert_called_once()
        self.mock_validate_text.assert_called_once()

    def test_translate_no_access_code(self):
        """Tests /translate without providing an access code."""
        response = self._post_translate(access_code=None)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"error": "Access Denied. Please provide a valid access code."})

    def test_translate_invalid_access_code(self):
        """Tests /translate with an invalid access code."""
        response = self._post_translate(access_code="WRONG_CODE")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"error": "Access Denied. Please provide a valid access code."})

    def test_translate_redis_queue_unavailable(self):
        """Tests /translate when Redis queue cannot be obtained."""
        self.mock_get_queue.return_value = None # Simulate failure to get queue

        with patch('werkzeug.datastructures.FileStorage.save'):
            response = self._post_translate()

        self.assertEqual(response.status_code, 503)
        self.assertIn("Translation service temporarily unavailable", json.loads(response.data)['error'])

    # --- /results Endpoint Tests ---

    def test_get_results_success(self):
        """Tests getting results for a successfully finished job."""
        expected_result = [{"word": "example", "start": 0.1, "end": 0.5}]
        self.mock_job.is_finished = True
        self.mock_job.is_failed = False
        self.mock_job.result = expected_result

        response = self._get_results(self.test_job_id)

        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        self.assertEqual(json.loads(response.data), {"status": "finished", "result": expected_result})
        self.mock_job_fetch.assert_called_once_with(self.test_job_id, connection=self.mock_redis_conn)

    def test_get_results_failed(self):
        """Tests getting results for a failed job."""
        error_message = "Simulated processing error"
        self.mock_job.is_finished = False # Or True, depending on how RQ sets flags on failure
        self.mock_job.is_failed = True
        self.mock_job.exc_info = error_message

        response = self._get_results(self.test_job_id)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.data), {"status": "failed", "message": error_message})
        self.mock_job_fetch.assert_called_once_with(self.test_job_id, connection=self.mock_redis_conn)

    def test_get_result_pending(self):
        """Tests getting results for a job that is still pending (queued/started)."""
        self.mock_job.is_finished = False
        self.mock_job.is_failed = False
        self.mock_job.get_status.return_value = 'started' # Or 'queued'

        response = self._get_results(self.test_job_id)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(json.loads(response.data), {"status": "started"})
        self.mock_job_fetch.assert_called_once_with(self.test_job_id, connection=self.mock_redis_conn)
        self.mock_job.get_status.assert_called_once()

    def test_get_results_nonexistent_job(self):
        """Tests getting results for a job ID that doesn't exist."""
        self.mock_job_fetch.side_effect = rq.exceptions.NoSuchJobError("Job not found")

        response = self._get_results("nonexistent_job_id")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data), {
            "status": "error",
            "message": "Job ID not found or invalid."
        })
        self.mock_job_fetch.assert_called_once_with("nonexistent_job_id", connection=self.mock_redis_conn)

    def test_get_redis_connection_error_on_fetch(self):
        """Tests /results when Redis connection fails during Job.fetch."""
        self.mock_job_fetch.side_effect = redis.exceptions.ConnectionError("Cannot connect to Redis")

        response = self._get_results(self.test_job_id)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.data), {
            "status": "error",
            "message": "Error communicating with Redis."
        })

    def test_health_check_success(self):
        """Tests the health check endpoint when Redis is available."""
        # Ensure the mock connection doesn't raise an error on ping
        self.mock_redis_conn.ping.side_effect = None

        response = self.client.get('/translate/health')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'OK')
        self.assertEqual(data['redis_health_check'], 'connected')
        self.mock_get_conn.assert_called() # Check if connection was attempted
        self.mock_redis_conn.ping.assert_called_once() # Check ping was attempted

    def test_health_check_redis_failure(self):
        """Tests the health check endpoint when Redis connection fails."""
        # Simulate connection error on ping
        self.mock_redis_conn.ping.side_effect = redis.exceptions.ConnectionError("Ping failed")

        response = self.client.get('/translate/health')

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'Error')
        self.assertEqual(data['redis_health_check'], 'disconnected (live test)')
        self.mock_redis_conn.ping.assert_called_once()

    def test_health_check_redis_connection_get_failure(self):
        """Tests health check when getting the Redis connection itself fails."""
        # Override the setUp mock for this specific test
        self.mock_get_conn.stop() # Stop the default successful mock
        patch_get_conn_fail = patch('musictranslator.main.get_redis_connection', return_value=None)
        mock_get_conn_fail = patch_get_conn_fail.start()

        response = self.client.get('/translate/health')

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'Error')
        self.assertEqual(data['redis_health_check'], 'disconnected (live test)')
        mock_get_conn_fail.assert_called()
        self.mock_redis_conn.ping.assert_not_called() # Ping shouldn't be called if connection failed'

        patch_get_conn_fail.stop() # Clean up this test's specific patch
        self.mock_get_conn.start() # Restart the default mock for other tests

if __name__ == '__main__':
    unittest.main()
