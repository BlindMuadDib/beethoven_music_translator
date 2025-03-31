"""
Test map.py
"""
import json
import unittest
from unittest.mock import mock_open, patch

from musictranslator.musicprocessing.map_transcript import (
    process_transcript,
    sync_alignment_json_with_transcript_lines,
)

class TestMap(unittest.TestCase):
    """
    Test suite for the map.py module
    """

    def setUp(self):
        """Set up test environment"""
        self.transcript_content = "Line 1: Hello, world!\nLine 2: Test sentence."
        self.alignment_data = {
            "intervals": [
                {"word": "Hello", "xmin": 0.1, "xmax": 0.5},
                {"word": "world", "xmin": 0.6, "xmax": 1.0},
                {"word": "Test", "xmin": 1.1, "xmax": 1.5},
                {"word": "sentence", "xmin": 1.6, "xmax": 2.0},
            ]
        }

    @patch("builtins.open", new_callable=mock_open, read_data="Line 1: Hello, world!\nLine 2: Test sentence.")
    def test_process_transcript_success(self, mock_file):
        """Test successful processing of a transcript"""
        result = process_transcript("dummy_path.txt")
        self.assertEqual(result, [["Line", "1:", "Hello,", "world!"], ["Line", "2:", "Test", "sentence."]])

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_process_transcript_file_not_found(self, mock_file):
        """Test handling of a file not found error"""
        result = process_transcript("nonexistent_path.txt")
        self.assertEqual(result, [])

    def test_sync_alignment_json_with_transcript_lines(self):
        """Test synchronization of alignment data with transcript lines"""
        transcript_lines = [["Hello", "world"], ["Test", "sentence"]]
        result = sync_alignment_json_with_transcript_lines(self.alignment_data, transcript_lines)
        expected = [[(0.1, 0.5, "Hello"), (0.6, 1.0, "world")], [(1.1, 1.5, "Test"), (1.6, 2.0, "sentence")]]
        self.assertEqual(result, expected)
