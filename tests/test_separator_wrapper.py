"""
Tests for separator_wrapper.py
Focusing on Demucs separation and error handling
"""
import io
import os
import unittest
import tempfile
import demucs.separate
from unittest.mock import patch, MagicMock
from musictranslator import separator_wrapper
from musictranslator.separator_wrapper import OUTPUT_DIR

class TestSeparatorWrapper(unittest.TestCase):
    """Unittests for Demucs wrapper."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_dir = os.path.join(self.temp_dir.name, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        self.input_file_name = "test_audio.wav"
        self.input_file_path = os.path.join(self.audio_dir, self.input_file_name)
        with open(self.input_file_path, 'wb') as f:
            f.write(b"test audio data")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('demucs.separate.main')
    def test_demucs_success_guitar(self, mock_demucs_main):
        """
        Test successful Demucs run with 6-stem model
        Piano and other models are not desired at this point
        """
        mock_demucs_main.return_value = None

        def mock_demucs_function(args):
            output_model_dir = os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0])
            os.makedirs(output_model_dir, exist_ok=True)

            for source in ["vocals", "drums", "bass", "guitar"]:
                with open(os.path.join(output_model_dir, f"{source}.wav"), "wb") as f:
                    f.write(f"{source} data".encode())

        mock_demucs_main.side_effect = mock_demucs_function

        result = separator_wrapper.run_demucs(self.input_file_path)

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 4)
        self.assertIn("vocals", result)
        self.assertIn("drums", result)
        self.assertIn("bass", result)
        self.assertIn("guitar", result)
        self.assertEqual(result["vocals"], os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0], "vocals.wav"))
        self.assertEqual(result["drums"], os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0], "drums.wav"))
        self.assertEqual(result["bass"], os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0], "bass.wav"))
        self.assertEqual(result["guitar"], os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0], "guitar.wav"))

    @patch('demucs.separate.main')
    def test_demucs_failure(self, mock_demucs_main):
        """Test Demucs failure"""
        mock_demucs_main.side_effect = Exception("Demucs processing error")

        with self.assertRaises(RuntimeError) as context:
            separator_wrapper.run_demucs(self.input_file_path)

        self.assertEqual(str(context.exception), "An unexpected error occurred: Demucs processing error")

    @patch('demucs.separate.main')
    def test_demucs_runtime_error(self, mock_demucs_main):
        mock_demucs_main.side_effect = RuntimeError("Demucs Error")

        with self.assertRaises(RuntimeError) as context:
            separator_wrapper.run_demucs(self.input_file_path)

    @patch('demucs.separate.main')
    def test_file_open_error(self, mock_demucs_main):
        mock_demucs_main.side_effect = None

        def mock_demucs_function(args):
            output_model_dir = os.path.join(OUTPUT_DIR, "htdemucs_6s", os.path.splitext(self.input_file_name)[0])
            os.makedirs(output_model_dir, exist_ok=True)

            for source in ["vocals", "drums", "bass", "guitar"]:
                with open(os.path.join(output_model_dir, f"{source}.wav"), "wb") as f:
                    f.write(f"{source} data".encode())

            mock_demucs_main.side_effect = mock_demucs_function
            with patch('os.path.expanduser', return_value = temp_dir):
                with patch('builtins.open', side_effect=OSError("File Open Error")):
                    with self.assertRaises(RuntimeError) as context:
                        separator_wrapper.run_demucs(self.input_file_path)
                    self.assertEqual(str(context.exception), "Demucs processing erro: File Open Error")

    def test_demucs_missing_file_error(self):
        with self.assertRaises(RuntimeError) as context:
            separator_wrapper.run_demucs("nonexistent_file.wav")

        self.assertIn("File Not Found", str(context.exception))

