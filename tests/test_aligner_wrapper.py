import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from musictranslator.aligner_wrapper import app

# Define mock paths as constants for clarity and reuse
MOCK_CORPUS_DIR = "/tmp/test_corpus_dir"
MOCK_OUTPUT_DIR = "/tmp/test_output_dir"

class TestMFAWrapper(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        # Push an app context for logging and request context
        self.app_context.push()
        self.client = app.test_client()

        # Create temp files for audio and lyrics
        self.test_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.test_lyrics_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)

        self.test_audio_full_path = self.test_audio_file.name
        self.test_lyrics_full_path = self.test_lyrics_file.name
        self.test_audio_base_name = os.path.splitext(os.path.basename(self.test_audio_full_path))[0]

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

        self.test_audio_file.close()
        self.test_lyrics_file.close()

    def tearDown(self):
        os.remove(self.test_audio_full_path)
        os.remove(self.test_lyrics_full_path)
        # Clean up mock directories if they were created (they shouldn't be)
        if os.path.exists(MOCK_CORPUS_DIR) and MOCK_CORPUS_DIR.startswith("/tmp"):
            shutil.rmtree(MOCK_CORPUS_DIR, ignore_errors=True)
        if os.path.exists(MOCK_OUTPUT_DIR) and MOCK_OUTPUT_DIR.startswith("/tmp"):
            shutil.rmtree(MOCK_OUTPUT_DIR)
        self.app_context.pop()

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.CORPUS_DIR', new=MOCK_CORPUS_DIR)
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR', new=MOCK_OUTPUT_DIR)
    @patch('subprocess.run')
    def test_align_success(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        #Expected paths based on mocked CORPUS_DIR, OUTPUT_DIR and derived base_name
        expected_corpus_audio_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.wav")
        expected_corpus_lyrics_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.txt")
        expected_json_output_path = os.path.join(MOCK_OUTPUT_DIR, f"{self.test_audio_base_name}.json")

        # Mock subprocess.run for successful alignment (first attempt)
        # MFA output (stdout) is not directly used by the app's response, but returncode is critical
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout='', stderr='')
        ]

        response = self.client.post('/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('alignment_file_path', data)
        self.assertEqual(data['alignment_file_path'], expected_json_output_path)

        # Check os.makedirs call
        mock_os_makedirs.assert_any_call(MOCK_CORPUS_DIR, exist_ok=True)
        mock_os_makedirs.assert_any_call(MOCK_OUTPUT_DIR, exist_ok=True)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check shutil.copy calls
        mock_shutil_copy.assert_any_call(self.test_audio_full_path, expected_corpus_audio_path)
        mock_shutil_copy.assert_any_call(self.test_lyrics_full_path, expected_corpus_lyrics_path)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check subprocess.run call
        self.assertEqual(mock_subprocess_run.call_count, 2)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'validate', MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa'],
            capture_output=True, text=True, check=True)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align',
             '--output_format', 'json',
             MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa',
             MOCK_OUTPUT_DIR],
            capture_output=True, text=True, check=False
        )

    def test_align_missing_files(self):
        response = self.client.post('/align', json={})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {'error': 'vocals_stem_path or lyrics_file_path missing'})

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.CORPUS_DIR', new=MOCK_CORPUS_DIR)
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR', new=MOCK_OUTPUT_DIR)
    @patch('subprocess.run')
    def test_align_subprocess_error(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        # Expected paths for copy operations
        expected_corpus_audio_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.wav")
        expected_corpus_lyrics_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.txt")

        # Mock failed first attempt, failed retry
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="Initial alignment failed"),
            MagicMock(returncode=1, stderr="Retry alignment failed")
        ]

        response = self.client.post('/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', data)
        self.assertIn('Alignment failed: Retry alignment failed', data['error'])

        # Check os.makedirs call
        mock_os_makedirs.assert_any_call(MOCK_CORPUS_DIR, exist_ok=True)
        mock_os_makedirs.assert_any_call(MOCK_OUTPUT_DIR, exist_ok=True)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check shutil.copy calls
        mock_shutil_copy.assert_any_call(self.test_audio_full_path, expected_corpus_audio_path)
        mock_shutil_copy.assert_any_call(self.test_lyrics_full_path, expected_corpus_lyrics_path)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check subproce.run calls
        self.assertEqual(mock_subprocess_run.call_count, 3)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'validate', MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa'],
            capture_output=True, text=True, check=True)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align',
             '--output_format', 'json',
             MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa',
             MOCK_OUTPUT_DIR],
            capture_output=True, text=True, check=False
        )
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align',
             '--output_format', 'json',
             MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa',
             MOCK_OUTPUT_DIR,
             '--beam', '100', '--retry_beam', '400'],
            capture_output=True, text=True, check=False
        )

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.CORPUS_DIR', new=MOCK_CORPUS_DIR)
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR', new=MOCK_OUTPUT_DIR)
    @patch('subprocess.run')
    def test_align_retry_success(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        # Expected paths
        expected_corpus_audio_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.wav")
        expected_corpus_lyrics_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.txt")
        expected_json_output_path = os.path.join(MOCK_OUTPUT_DIR, f"{self.test_audio_base_name}.json")

        # Mock failed intitial, successful retry
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="Initial alignment failed", stdout=''),
            MagicMock(returncode=0, stdout='', stderr='')
        ]

        response = self.client.post('/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('alignment_file_path', data)
        self.assertEqual(data['alignment_file_path'], expected_json_output_path)

        # Check os.makedirs call
        mock_os_makedirs.assert_any_call(MOCK_CORPUS_DIR, exist_ok=True)
        mock_os_makedirs.assert_any_call(MOCK_OUTPUT_DIR, exist_ok=True)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check shutil.copy calls
        mock_shutil_copy.assert_any_call(self.test_audio_full_path, expected_corpus_audio_path)
        mock_shutil_copy.assert_any_call(self.test_lyrics_full_path, expected_corpus_lyrics_path)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check subprocess.run calls
        self.assertEqual(mock_subprocess_run.call_count, 3)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'validate', MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa'],
            capture_output=True, text=True, check=True)
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align',
             '--output_format','json',
             MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa',
             MOCK_OUTPUT_DIR],
            capture_output=True, text=True, check=False
        )
        mock_subprocess_run.assert_any_call(
            ['mfa', 'align',
             '--output_format', 'json',
             MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa',
             MOCK_OUTPUT_DIR,
             '--beam', '100', '--retry_beam', '400'],
            capture_output=True, text=True, check=False
        )

    @patch('musictranslator.aligner_wrapper.os.makedirs')
    @patch('musictranslator.aligner_wrapper.shutil.copy')
    @patch('musictranslator.aligner_wrapper.CORPUS_DIR', new=MOCK_CORPUS_DIR)
    @patch('musictranslator.aligner_wrapper.OUTPUT_DIR', new=MOCK_OUTPUT_DIR)
    @patch('subprocess.run')
    def test_corpus_validation_fail(self, mock_subprocess_run, mock_shutil_copy, mock_os_makedirs):
        """Test the aligner when corpus validation fails"""
        # Expected paths for copy operations
        expected_corpus_audio_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.wav")
        expected_corpus_lyrics_path = os.path.join(MOCK_CORPUS_DIR, f"{self.test_audio_base_name}.txt")

        # Mock failed first attempt, failed retry
        mock_subprocess_run.side_effect = MagicMock(returncode=1, stderr="Corpus validation failed", stdout='')

        response = self.client.post('/align', json={
            'vocals_stem_path': self.test_audio_full_path,
            'lyrics_path': self.test_lyrics_full_path
        })
        data = json.loads(response.data.decode('utf-8'))

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', data)
        self.assertIn('Corpus validation failed', data['error'])

        # Check os.makedirs call
        mock_os_makedirs.assert_any_call(MOCK_CORPUS_DIR, exist_ok=True)
        mock_os_makedirs.assert_any_call(MOCK_OUTPUT_DIR, exist_ok=True)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check shutil.copy calls
        mock_shutil_copy.assert_any_call(self.test_audio_full_path, expected_corpus_audio_path)
        mock_shutil_copy.assert_any_call(self.test_lyrics_full_path, expected_corpus_lyrics_path)
        self.assertEqual(mock_shutil_copy.call_count, 2)

        # Check subprocess.run call
        mock_subprocess_run.assert_called_once_with(
            ['mfa', 'validate', MOCK_CORPUS_DIR,
             'english_us_arpa', 'english_us_arpa'],
            capture_output=True, text=True, check=True)

    def test_health_check(self):
        response = self.client.get('/align/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, {"status": "OK"})
