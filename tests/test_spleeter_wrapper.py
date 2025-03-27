"""
Tests for spleeter_wrapper.py
Focusing on command generation for 4stems-16kHz
And error handling
"""
import os
import unittest
import subprocess
import shutil
from unittest.mock import patch, call
from musictranslator import spleeter_wrapper
from musictranslator.spleeter_wrapper import SpleeterWrapper

class TestSpleeterWrapper(unittest.TestCase):
    """Unittests"""

    def setUp(self):
        """Create a fake directories for the tests"""
        self.input_dir = "test_input_dir"
        self.output_dir = "test_output_dir"
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self.input_file_name = "input.wav"
        open(os.path.join(self.input_dir, self.input_file_name), 'a').close()

    def tearDown(self):
        """Removes the fake directories after the tests"""
        shutil.rmtree(self.input_dir)
        shutil.rmtree(self.output_dir)

    @patch('subprocess.run')
    def test_separate_4stems_success(self, mock_run):
        """Tests successful command generation"""
        wrapper = SpleeterWrapper()
        wrapper.separate(self.input_dir, self.output_dir, self.input_file_name)

        expected_command = [
            "docker",
            "run",
            "--rm",
            "-v", f"{os.path.abspath(self.input_dir)}:/input",
            "-v", f"{os.path.abspath(self.output_dir)}:/output",
            "researchdeezer/spleeter",
            "separate",
            "-i", f"/input/{self.input_file_name}",
            "-o", "/output",
            "-p", "spleeter:4stems-16kHz"
        ]

        mock_run.assert_called_once_with(expected_command, check=True)

    @patch('subprocess.run')
    def test_separate_invalid_input_dir(self, mock_run):
        """Tests handling of invalid input directory"""
        wrapper = SpleeterWrapper()
        input_dir = "/invalid/input_dir"
        output_dir = "output"
        input_file_name = "input.wav"
        with self.assertRaises(FileNotFoundError):
            wrapper.separate(input_dir, output_dir, input_file_name)

    @patch('subprocess.run')
    def test_separate_invalid_output_dir(self, mock_run):
        """Tests handling of invalid output directory paths"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        output_dir = "/invalid/output"
        input_file_name = "input.wav"
        with self.assertRaises(FileNotFoundError):
            wrapper.separate(input_dir, output_dir, input_file_name)

    @patch('subprocess.run')
    def test_separate_invalid_input_file(self, mock_run):
        """Tests handling of invalid input file paths"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        output_dir = "output"
        input_file_name = "invalid.wav"
        with self.assertRaises(FileNotFoundError):
            wrapper.separate(input_dir, output_dir, input_file_name)

    @patch('subprocess.run')
    def test_separate_subprocess_failure(self, mock_run):
        """Tests handling of subprocess failures during command execution"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        wrapper = SpleeterWrapper()
        output_dir = "output"
        with self.assertRaises(subprocess.CalledProcessError):
            wrapper.separate(self.input_dir, self.output_dir, self.input_file_name)

    @patch('subprocess.run')
    def test_separate_no_input_file_name(self, mock_run):
        """Tests handling of a missing input file argument"""
        wrapper = SpleeterWrapper()
        output_dir = "output"
        input_file_name = "input.wav"
        with self.assertRaises(ValueError):
            wrapper.separate(None, output_dir, input_file_name)

    @patch('subprocess.run')
    def test_separate_no_output_dir(self, mock_run):
        """Tests handling of a missing output directory argument"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        input_file_name = "input.wav"
        with self.assertRaises(ValueError):
            wrapper.separate(input_dir, None, input_file_name)

    @patch('subprocess.run')
    def test_separate_empty_input_dir(self, mock_run):
        """Tests handling of an empty input argument"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        output_dir = "output"
        with self.assertRaises(ValueError):
            wrapper.separate(input_dir, output_dir, "")

    @patch('subprocess.run')
    def test_separate_empty_output(self, mock_run):
        """Tests handling of an empty output argument"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        input_file_name = "input.wav"
        with self.assertRaises(ValueError):
            wrapper.separate(input_dir, "", input_file_name)

    @patch('subprocess.run')
    def test_separate_empty_input_file_name(self, mock_run):
        """Tests handling of an empty file name argument"""
        wrapper = SpleeterWrapper()
        input_dir = "input_dir"
        output_dir = "output"
        with self.assertRaises(ValueError):
            wrapper.separate(input_dir, output_dir, "")

    if __name__ == '__main__':
        unittest.main()
