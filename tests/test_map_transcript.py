"""
Test map_transcript.py
A function for musictranslator.main that accepts a lyrics transcript and JSON alignment response
Then outputs a JSON of the transcript with start and end times for each word in a line-by-line format
"""
import json
import tempfile
import os
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
        self.json_alignment = {
            'tier_name': 'words',
            'intervals': [
                {'xmin': 0.1, 'xmax': 0.5, 'word': 'hello'},
                {'xmin': 0.6, 'xmax': 1.0, 'word': 'world'},
                {'xmin': 1.1, 'xmax': 1.5, 'word': 'test'},
                {'xmin': 1.6, 'xmax': 2.0, 'word': 'sentence'}
            ]
        }
        self.transcript_lines = [["hello", "world"], ["test", "sentence"]]

    def tearDown(self):
        # Clean up temporary file
        pass

    @patch("builtins.open", new_callable=mock_open, read_data="Line 1: Hello, world!\nLine 2: Test sentence.")
    def test_process_transcript_success(self, mock_file):
        """Test successful processing of a transcript
        """
        result = process_transcript("dummy_path.txt")
        self.assertEqual(result, [["line", "1:", "hello", "world"], ["line", "2:", "test", "sentence"]])

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_process_transcript_file_not_found(self, mock_file):
        """Test handling of a file not found error"""
        result = process_transcript("nonexistent_path.txt")
        self.assertEqual(result, [])

    def test_sync_alignment_json_with_transcript_lines(self):
        """Test synchronization of alignment data with transcript lines"""
        result = sync_alignment_json_with_transcript_lines(self.json_alignment, self.transcript_lines)
        expected = [[{"word": "hello", "start": 0.1, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0}], [{"word": "test", "start": 1.1, "end": 1.5}, {"word": "sentence", "start": 1.6, "end": 2.0}]]
        self.assertEqual(result, expected)

    def test_sync_alignment_json_with_empty_transcript_lines(self):
        """Test the sync function with empty transcript lines"""
        transcript_lines  = [[], ["test", "sentence"], []]

        result = sync_alignment_json_with_transcript_lines(self.json_alignment, transcript_lines)
        expected = [[{"word": "test", "start": 1.1, "end": 1.5}, {"word": "sentence", "start": 1.6, "end": 2.0}]]
        self.assertEqual(result, expected)

    def test_sync_alignment_json_with_empty_words_intervals(self):
        """Test sync function with empty word intervals in alignment data"""
        json_alignment_with_empty = {
            'tier_name': 'words',
            'intervals': [
                {'xmin': 0.1, 'xmax': 0.5, 'word': 'hello'},
                {'xmin': 0.6, 'xmax': 1.0, 'word': ''},
                {'xmin': 1.1, 'xmax': 1.5, 'word': 'test'},
                {'xmin': 1.6, 'xmax': 2.0, 'word': 'sentence'},
                {'xmin': 2.1, 'xmax': 2.5, 'word': ''}
            ]
        }
        transcript_lines = [["hello", "test", "sentence"]]

        result = sync_alignment_json_with_transcript_lines(json_alignment_with_empty, transcript_lines)
        expected = [[{"word": "hello", "start": 0.1, "end": 0.5}, {"word": "test", "start": 1.1, "end": 1.5}, {"word": "sentence", "start": 1.6, "end": 2.0}]]
        self.assertEqual(result, expected)

    def test_sync_alignment_json_with_punctuation_and_uppercase(self):
        """Test sync function with punctuation and uppercase in transcript lines"""
        transcript_lines = [["Hello,", "World!"], ["TEST", "sentence."]]

        result = sync_alignment_json_with_transcript_lines(self.json_alignment, transcript_lines)
        expected = [[{"word": "hello", "start": 0.1, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0}], [{"word": "test", "start": 1.1, "end": 1.5}, {"word": "sentence", "start": 1.6, "end": 2.0}]]
        self.assertEqual(result, expected)
