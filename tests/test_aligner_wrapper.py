import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from musictranslator.aligner_wrapper import app

# Define mock paths as constants for clarity and reuse
MOCK_BASE_DIR = "/tmp/test_mfa_jobs"

class TestMFAWrapper(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        # Push an app context for logging and request context
        self.app_context.push()
        self.client = app.test_client()

        # Create temp dir to hold input files
        self.test_input_dir = tempfile.mkdtemp()

        # Define filenames that satisfy the 'job_id' extraction
        # Must contain '_'
        self.job_id = "job123"
        self.audio_filename = f"{self.job_id}_vocals.wav"
        self.lyrics_filename = f"{self.job_id}_lyrics.txt"

        self.test_audio_full_path = os.path.join(self.test_input_dir,
                                                 self.audio_filename)
        self.test_lyrics_full_path = os.path.join(self.test_input_dir,
                                                  self.lyrics_filename)

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

        with open(self.test_lyrics_full_path, 'w') as f:
            f.write("hello\nworld")

    def tearDown(self):
        # Remove the temp input dir
        if os.path.exists(self.test_input_dir):
            shutil.rmtree(self.test_input_dir)

        # Remove the mock output dir if created
        if os.path.exists(MOCK_BASE_DIR):
            shutil.rmtree(MOCK_BASE_DIR)

        self.app_context.pop()

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.BASE_MFA_DIR', new=MOCK_BASE_DIR)
    @patch('subprocess.run')
    def test_align_success(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        # Calculate expected paths dynamically based on the job_id
        expected_job_dir = os.path.join(MOCK_BASE_DIR, self.job_id)
        expected_corpus_dir = os.path.join(expected_job_dir, "corpus")
        expected_output_dir = os.path.join(expected_job_dir, "aligned")

        # The logic uses split('_')[0] for the base_name
        base_name = self.job_id

        expected_corpus_audio_path = os.path.join(expected_corpus_dir,
                                                  f"{base_name}.wav")
        expected_corpus_lyrics_path = os.path.join(expected_corpus_dir,
                                                   f"{base_name}.txt")
        expected_json_output_path = os.path.join(expected_output_dir,
                                                 f"{base_name}.json")

        # Mock subprocess.run for successful alignment (first attempt)
        # MFA output (stdout) is not directly used by the app's response, but returncode is critical
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout='', stderr='')
        ]

        response = self.client.post('/api/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('alignment_file_path', data)
        self.assertEqual(data['alignment_file_path'], expected_json_output_path)
        self.assertEqual(data['job_dir_path'], expected_job_dir)

        # Check os.makedirs call
        mock_os_makedirs.assert_any_call(expected_corpus_dir, exist_ok=True)
        mock_os_makedirs.assert_any_call(expected_output_dir, exist_ok=True)

        # Check shutil.copy calls
        mock_shutil_copy.assert_any_call(self.test_audio_full_path,
                                         expected_corpus_audio_path)
        mock_shutil_copy.assert_any_call(self.test_lyrics_full_path,
                                         expected_corpus_lyrics_path)

        # Check subprocess.run call
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'validate', '--clean', expected_corpus_dir,
             'english_us_arpa', 'english_us_arpa',
             '--single_speaker'],
            capture_output=True, text=True, check=True)

        mock_subprocess_run.assert_any_call(
            ['mfa', 'align', '--final_clean',
             '--output_format', 'json',
             expected_corpus_dir,
             'english_us_arpa', 'english_us_arpa',
             expected_output_dir,
             '--single_speaker',
             '--beam', '100', '--retry_beam', '400'],
            capture_output=True, text=True, check=False
        )

    def test_align_missing_files(self):
        response = self.client.post('/api/align', json={})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'vocals_stem_path or lyrics_file_path missing'})

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.BASE_MFA_DIR', new=MOCK_BASE_DIR)
    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        # Determine paths
        expected_job_dir = os.path.join(MOCK_BASE_DIR, self.job_id)
        expected_corpus_dir = os.path.join(expected_job_dir, "corpus")
        expected_output_dir = os.path.join(expected_job_dir, "aligned")

        # Mock failed first attempt, failed retry
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="Initial alignment failed"),
            MagicMock(returncode=1, stderr="Retry alignment failed")
        ]

        response = self.client.post('/api/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', data)
        self.assertIn('Alignment failed: Retry alignment failed', data['error'])

        # Check calls were made
        self.assertEqual(mock_subprocess_run.call_count, 3)

        # Verify the retry call arguments
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align', '--final_clean',
             '--output_format', 'json',
             expected_corpus_dir,
             'english_us_arpa', 'english_us_arpa',
             expected_output_dir,
             '--single_speaker',
             '--beam', '500', '--retry_beam', '2000'],
            capture_output=True, text=True, check=False
        )

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.BASE_MFA_DIR', new=MOCK_BASE_DIR)
    @patch('subprocess.run')
    def test_align_retry_success(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        # Expected paths
        expected_job_dir = os.path.join(MOCK_BASE_DIR, self.job_id)
        expected_output_dir = os.path.join(expected_job_dir, "aligned")
        expected_json_output_path = os.path.join(expected_output_dir,
                                                 f"{self.job_id}.json")

        # Mock failed intitial, successful retry
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="Initial alignment failed", stdout=''),
            MagicMock(returncode=0, stdout='', stderr='')
        ]

        response = self.client.post('/api/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('alignment_file_path', data)
        self.assertEqual(data['alignment_file_path'], expected_json_output_path)

        # Check subprocess.run calls
        self.assertEqual(mock_subprocess_run.call_count, 3)

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.BASE_MFA_DIR', new=MOCK_BASE_DIR)
    @patch('subprocess.run')
    def test_corpus_validation_fail(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        """Test the aligner when corpus validation fails"""
        expected_job_dir = os.path.join(MOCK_BASE_DIR, self.job_id)
        expected_corpus_dir = os.path.join(expected_job_dir, "corpus")

        # Mock failed validation
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=1, stderr="Corpus validation failed", stdout='')
        ]

        response = self.client.post('/api/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', data)
        self.assertIn('Corpus validation failed', data['error'])

        # Check subprocess.run call
        mock_subprocess_run.assert_called_once_with(
            ['mfa', 'validate', '--clean', expected_corpus_dir,
             'english_us_arpa', 'english_us_arpa',
             '--single_speaker'],
            capture_output=True, text=True, check=True)

    def test_health_check(self):
        response = self.client.get('/api/align/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {"status": "OK"})
