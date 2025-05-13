"""
Tests for separator_wrapper.py
Focusing on Demucs separation and error handling
"""
import os
import unittest
import tempfile
import shlex
import pathlib
from unittest.mock import patch, call
from musictranslator import separator_wrapper

EXPECTED_STEMS = sorted(["bass", "drums", "guitar",  "other", "piano","vocals"])

class TestSeparatorWrapper(unittest.TestCase):
    """Unittests for Demucs wrapper."""

    def setUp(self):
        """Set up test fixtures"""
        # This temp dir will be patched as separator_wrapper.OUTPUT_DIR
        self.temp_output_dir_obj = tempfile.TemporaryDirectory(prefix="sep_wrapper_main_out_")
        self.mock_output_dir_path = self.temp_output_dir_obj.name

        # Temp dir for dummy input audio files
        self.temp_audio_input_dir_obj = tempfile.TemporaryDirectory(prefix="audio_input_")
        self.input_file_name = "test_audio.wav"
        self.input_file_path = os.path.join(self.temp_audio_input_dir_obj.name, self.input_file_name)
        with open(self.input_file_path, "wb") as f:
            f.write(b"dummy audio data for testing")

        # Pre-calculate the expected subdirectory where Demucs stems would be written
        # This is based on: mock_output_dir_path / model_name / audio_file_basename_no_ext
        self.audio_file_basename_no_ext = os.path.splitext(self.input_file_name)[0]
        self.expected_demucs_stems_output_subdir = os.path.join(
            self.mock_output_dir_path, "htdemucs_6s", self.audio_file_basename_no_ext
        )

    def tearDown(self):
        self.temp_audio_input_dir_obj.cleanup()
        self.temp_output_dir_obj.cleanup()

    # --- Helper Function ---

    def _get_expected_demucs_cli_args(self, input_path, output_path_root):
        """Helper to generate the list of args demucs.separate.main expetects."""
        command_str = f'-n htdemucs_6s "{input_path}" -o "{output_path_root}"'
        return shlex.split(command_str)

    # --- Test Cases ---

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('demucs.separate.main')
    def test_run_demucs_success(self, mock_demucs_main, mock_os_makedirs):
        """
        Test successful Demucs run with 6-stem model
        Ensures all 6 stems are correctly identified using isolated mock output dir.
        """

        def simulate_demucs_file_creation(demucs_args_list):
            # The output dir passed to demucs is at index 4
            # For: -n htdemucs_6s "input.wav" -o "output_dir_root"
            # demucs_args_list[4] is "output_dir_root" (which is self.mock_output_dir_path)

            # Demucs itself creates subdirectories: output_dir_root / model_name / audio_file_basename_no_ext

            # Simulate demucs creating the necessary output directory and stem files
            target_dir_to_create = self.expected_demucs_stems_output_subdir

            # Use pathlib to ensure REAL directory creation
            target_dir_pathlib = pathlib.Path(target_dir_to_create)
            print(f"[SIMULATE_FUNC] Attempting to create directory with pathlib: {target_dir_pathlib}")
            try:
                target_dir_pathlib.mkdir(parents=True, exist_ok=True)
                print(f"[SIMULATE_FUNC] os.makedirs call completed for {target_dir_pathlib}")
                if not target_dir_pathlib.exists():
                    # This would be extremely strange for the real os.makedirs
                    print(f"[SIMULATE_FUNC] CRITICAL ERROR: Directory {target_dir_pathlib} DOES NOT EXIST after pathlib.Path!")
                else:
                    print(f"[SIMULATE_FUNC] Directory {target_dir_pathlib} confirmed to exist!")
            except Exception as e_makedirs:
                print(f"[SIMULATE_FUNC] pathlib.Path FAILED with: {e_makedirs}")
                raise

            for stem_name in EXPECTED_STEMS:
                file_to_create = os.path.join(target_dir_to_create, f"{stem_name}.wav")
                print(f"[SIMULATE_FUNC] Attempting to open and write: {file_to_create}")
                try:
                    with open(file_to_create, "wb") as f:
                        f.write(f"mock {stem_name} audio data".encode())
                    print(f"[SIMULATE_FUNC] successfully wrote {file_to_create}")
                except FileNotFoundError as e_fnf_open:
                    print(f"[SIMULATE_FUNC] FAILED to open {file_to_create} (FileNotFoundError).")
                    print(f"[SIMULATE_FUNC] Does its parent directory '{target_dir_pathlib}' exist? {target_dir_pathlib.exists()}")
                    parent_of_target_dir = target_dir_pathlib.parent
                    print(f"[SIMULATE_FUNC] Does the parent's parent '{parent_of_target_dir}' exist? {target_dir_pathlib.exists()}")
                    raise e_fnf_open
                except Exception as e_open:
                    print(f"[SIMULATE_FUNC] FAILED to open/write {file_to_create} with other error: {e_open}")
                    raise e_open

            return None

        mock_demucs_main.side_effect = simulate_demucs_file_creation

        # Patch separator OUTPUT_DIR to use test temp dir
        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            result = separator_wrapper.run_demucs(self.input_file_path)

        # Verify os.makedirs in separator_wrapper was called correctly for the root output dir
        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)

        # Verify demucs.separate.main was called with the correct arguments
        expected_cli_args = self._get_expected_demucs_cli_args(self.input_file_path, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        # Verify the results
        self.assertEqual(len(result), len(EXPECTED_STEMS))
        for stem_name in EXPECTED_STEMS:
            self.assertIn(stem_name, result)
            expected_file_path = os.path.join(self.expected_demucs_stems_output_subdir, f"{stem_name}.wav")
            self.assertEqual(result[stem_name], expected_file_path)
            self.assertTrue(os.path.exists(expected_file_path), f"Mocked stem file{expected_file_path} not found.")

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('demucs.separate.main')
    def test_demucs_runtime_error(self, mock_demucs_main, mock_os_makedirs):
        """Test run_demucs correctly handles RuntimeError from demucs.separate.main."""
        mock_demucs_main.side_effect = RuntimeError("Demucs internal processing error")

        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            with self.assertRaises(RuntimeError) as context:
                separator_wrapper.run_demucs(self.input_file_path)

        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)
        expected_cli_args = self._get_expected_demucs_cli_args(self.input_file_path, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        self.assertEqual(
            str(context.exception),
            "Demucs processing erro: Demucs internal processing error"
        )

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('demucs.separate.main')
    def test_demucs_generic_exception(self, mock_demucs_main, mock_os_makedirs):
        """Test run_demucs correctly handles a generic Exception from demucs.separate.main."""
        mock_demucs_main.side_effect = ValueError("Some other Demucs error")

        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            with self.assertRaises(RuntimeError) as context:
                separator_wrapper.run_demucs(self.input_file_path)

        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)
        expected_cli_args = self._get_expected_demucs_cli_args(self.input_file_path, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        self.assertEqual(
            str(context.exception),
            "An unexpected error occurred: Some other Demucs error"
        )

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('demucs.separate.main')
    def test_demucs_file_not_found(self, mock_demucs_main, mock_os_makedirs):
        """Test run_demucs when demucs.separate.main raises FileNotFoundError (e.g., input file)."""
        error_message = f"No such file or directory: {self.input_file_path}"
        mock_demucs_main.side_effect = FileNotFoundError(error_message)

        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            with self.assertRaises(RuntimeError) as context:
                separator_wrapper.run_demucs(self.input_file_path)

        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)
        expected_cli_args = self._get_expected_demucs_cli_args(self.input_file_path, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        self.assertEqual(
            str(context.exception),
            f"File Not Found: {error_message}"
        )

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('musictranslator.separator_wrapper.os.listdir')
    @patch('demucs.separate.main')
    def test_demucs_missing_file_error_listdir(self, mock_demucs_main, mock_os_listdir, mock_os_makedirs):
        """
        Test run_demucs when os.listdir fails after demucs "completes"
        """
        # Simulate demucs.separate.main running "successfully" (i.e., not raising an error)
        mock_demucs_main.return_value = None

        # os.listdir will be called with self.expected_demucs_stems_output_subdir
        # Simulate os.listdir failing for this path
        listdir_fail_message = f"Simulated error: Cannot list directory '{self.expected_demucs_stems_output_subdir}'"
        mock_os_listdir.side_effect = FileNotFoundError(listdir_fail_message)

        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            with self.assertRaises(RuntimeError) as context:
                separator_wrapper.run_demucs(self.input_file_path)

        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)
        expected_cli_args = self._get_expected_demucs_cli_args(self.input_file_path, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        # Verify os.listdir was called with the expected path (where stems should be)
        mock_os_listdir.assert_called_once_with(self.expected_demucs_stems_output_subdir)

        self.assertEqual(
            str(context.exception),
            f"File Not Found: {listdir_fail_message}"
        )

    @patch('musictranslator.separator_wrapper.os.makedirs')
    @patch('demucs.separate.main')
    def test_demucs_input_file_missing(self, mock_demucs_main, mock_os_makedirs):
        """
        Test run_demucs handles FileNotFoundError from demucs for a non-existent input file.
        """
        non_existent_input_file = os.path.join(self.temp_audio_input_dir_obj.name, "nonexistent_audio.wav")
        # Ensure the file truly doesn't exist for a clean test
        self.assertFalse(os.path.exists(non_existent_input_file))

        # Simulate demucs.separate.main raising FileNotFoundError for this non-existent input
        demucs_error_message = f"Input file not found by Demucs: {non_existent_input_file}"
        mock_demucs_main.side_effect = FileNotFoundError(demucs_error_message)

        with patch('musictranslator.separator_wrapper.OUTPUT_DIR', new=self.mock_output_dir_path):
            with self.assertRaises(RuntimeError) as context:
                separator_wrapper.run_demucs(non_existent_input_file)

        mock_os_makedirs.assert_called_once_with(self.mock_output_dir_path, exist_ok=True)
        expected_cli_args = self._get_expected_demucs_cli_args(non_existent_input_file, self.mock_output_dir_path)
        mock_demucs_main.assert_called_once_with(expected_cli_args)

        self.assertEqual(
            str(context.exception),
            f"File Not Found: {demucs_error_message}"
        )
