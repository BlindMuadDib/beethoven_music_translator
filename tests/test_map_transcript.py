"""
Test map_transcript.py
A function for musictranslator.main that accepts a lyrics transcript and JSON alignment response
Then outputs a JSON of the transcript with start and end times for each word in a line-by-line format
"""
import json
import tempfile
import os
import tempfile
import unittest
from unittest.mock import mock_open, patch

from musictranslator.musicprocessing.transcribe import (
    process_transcript,
    map_transcript,
)

class TestMap(unittest.TestCase):
    """
    Test suite for the map_transcript.py module
    """

    def setUp(self):
        """Set up test environment"""
        self.dummy_alignment_data = {
            "start": 0,
            "end": 2.5,
            "tiers": {
                "words": {
                    "type": "interval",
                    "entries": [
                        [0.1, 0.5, "hello"],
                        [0.6, 1.0, "world"],
                        [1.1, 1.5, "test"],
                        [1.6, 2.0, "sentence"]
                    ]
                }
            }
        }
        self.json_alignment_content = json.dumps(self.dummy_alignment_data)

        self.transcript_content = "hello world\ntest sentence"
        self.expected_processed_transcript = [["hello", "world"], ["test", "sentence"]]

        self.temp_alignment_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json")
        self.temp_alignment_path = self.temp_alignment_file.name
        json.dump(self.dummy_alignment_data, self.temp_alignment_file)
        self.temp_alignment_file.close()

        self.temp_transcript_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt")
        self.temp_transcript_path = self.temp_transcript_file.name
        self.temp_transcript_file.write(self.transcript_content)
        self.temp_transcript_file.close()

    def tearDown(self):
        # Clean up temporary file
        os.remove(self.temp_alignment_path)
        os.remove(self.temp_transcript_path)

    def test_process_transcript_success(self):
        """Test successful processing of a transcript
        """
        result = process_transcript(self.temp_transcript_path)
        self.assertEqual(result, self.expected_processed_transcript)

    def test_process_transcript_file_not_found(self):
        """Test handling of a file not found error"""
        result = process_transcript("nonexistent_path.txt")
        self.assertEqual(result, [])

    def test_map_transcript(self):
        """Test synchronization of alignment data with transcript lines"""
        result = map_transcript(self.temp_alignment_path, self.temp_transcript_path)
        expected = [[{'word': 'hello', 'start': 0.1, 'end': 0.5}, {
        'word': 'world', 'start': 0.6, 'end': 1.0}], [{'word': 'test', 'start': 1.1, 'end': 1.5}, {'word': 'sentence', 'start': 1.6, 'end': 2.0}]]
        self.assertEqual(result, expected)

    def test_map_transcript_with_missing_words(self):
        """Test the handling of words in the transcript that are missing in the alignment data"""
        missing_words_alignment_data = {
            "start": 0,
            "end": 2.5,
            "tiers": {
                "words": {
                    "type": "interval",
                    "entries": [
                        [0.1, 0.5, "hello"],
                        [1.1, 1.5, "test"],
                        [1.6, 2.0, "sentence"],
                    ]
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json") as tmp_alignment:
            json.dump(missing_words_alignment_data, tmp_alignment)
            tmp_alignment_path = tmp_alignment.name

        transcript_content_missing = "hello different test word sentence"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as tmp_transcript:
            tmp_transcript.write(transcript_content_missing)
            tmp_transcript_path = tmp_transcript.name

        result = map_transcript(tmp_alignment_path, tmp_transcript_path)
        os.remove(tmp_alignment_path)
        os.remove(tmp_transcript_path)
        expected = [[{'word': 'hello', 'start': 0.1, 'end': 0.5}, {'word': 'different', 'start': None, 'end': None}, {'word': 'test', 'start': 1.1, 'end': 1.5}, {'word': 'word', 'start': None, 'end': None}, {'word': 'sentence', 'start': 1.6, 'end': 2.0}]]
        self.assertEqual(result, expected)

    def test_map_transcript_with_empty_words_intervals(self):
        """Test sync function with empty word intervals in alignment data"""
        empty_alignment_data = {
            "start": 0,
            "end": 3.0,
            "tiers": {
                "words": {
                    "type": "interval",
                    "entries": [
                        [0.1, 0.5, "hello"],
                        [0.5, 0.6, ""],
                        [0.6, 1.0, "world"],
                        [1.1, 1.5, "test"],
                        [1.6, 2.0, "sentence"],
                        [2.1, 3.0, ""]
                    ]
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json") as tmp_alignment:
            json.dump(empty_alignment_data, tmp_alignment)
            tmp_alignment_path = tmp_alignment.name

        result = map_transcript(tmp_alignment_path, self.temp_transcript_path)
        expected = [[{'word': 'hello', 'start': 0.1, 'end': 0.5}, {
        'word': 'world', 'start': 0.6, 'end': 1.0}], [{'word': 'test', 'start': 1.1, 'end': 1.5}, {'word': 'sentence', 'start': 1.6, 'end': 2.0}]]
        os.remove(tmp_alignment_path)
        self.assertEqual(result, expected)

    def test_map_transcript_with_punctuation_and_uppercase(self):
        """Test sync function with punctuation and uppercase in transcript lines"""
        upper_transcript_punc = [["Hello,", "World!"], ["TEST", "sentence."]]
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as tmp_transcript:
            tmp_transcript.write('\n'.join([' '.join(line) for line in upper_transcript_punc]))
            tmp_transcript_path = tmp_transcript.name

        result = map_transcript(self.temp_alignment_path, tmp_transcript_path)
        expected = [[{'word': 'hello', 'start': 0.1, 'end': 0.5}, {
        'word': 'world', 'start': 0.6, 'end': 1.0}], [{'word': 'test', 'start': 1.1, 'end': 1.5}, {'word': 'sentence', 'start': 1.6, 'end': 2.0}]]
        os.remove(tmp_transcript_path)
        self.assertEqual(result, expected)

    def test_map_transcript_alignment_file_not_found(self):
        """Test handling of alignment file not found error"""
        result = map_transcript("nonexistent_alinment.json", self.temp_transcript_path)
        self.assertIsNone(result)

    def test_map_transcript_invalid_json(self):
        """Test handling of invalid JSON in the alignment file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json") as tmp_alignment:
            tmp_alignment.write("invalid json")
            tmp_alignment_path = tmp_alignment.name
        result = map_transcript(tmp_alignment_path, self.temp_transcript_path)
        os.remove(tmp_alignment_path)
        self.assertIsNone(result)
