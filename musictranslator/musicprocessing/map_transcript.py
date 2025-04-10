"""
Map the alignment data from the .json alignment file to the lyrics transcript line-by-line
"""

import json
import os
import re

def process_transcript(lyrics_path):
    """
    Processes the lyrics file and returns a list of lines,
    Each containing a list of words"""
    try:
        with open(lyrics_path, 'r') as file:
            lines = file.readlines()
            result = []
            for line in lines:
                words = [word.lower().strip(".,!?") for word in line.strip().split()]
                if words:
                    result.append(words)
            return result
    except FileNotFoundError:
        print(f"Error: Lyrics file not found at {lyrics_path}")
        return []

def map_transcript(alignment_json_path, lyrics_path):
    """
    Maps the alignment data from the .json alignment file
    to the transcript line-by-line.

    Args:
        alignment_json_path (str): The file path to the .json alignment output from /align
        lyrics_path (str): The file path to the lyrics transcript

    Returns:
        list: List of aligned data in a line-by-line format, or None if an error occurs.
    """
    try:
        with open(alignment_json_path, 'r') as f:
            alignment_json = json.load(f)
    except FileNotFoundError:
        print(f"Error: Alignment JSON file not found at {alignment_json_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {alignment_json_path}")
        return None

    transcript_lines = process_transcript(lyrics_path)
    if not transcript_lines:
        return []

    alignment_intervals = alignment_json.get('tiers', {}).get('words', {}).get('entries', [])
    result = []
    alignment_index = 0
    interval_index = 0

    for line in transcript_lines:
        line_result = []
        for word in line:
            word = word.lower().strip(".,!?")
            if not word:
                continue

            found_match = False
            start_index = interval_index # Keep track of where to start searching

            while start_index < len(alignment_intervals):
                interval = alignment_intervals[start_index]
                interval_word = interval[2].lower().strip(".,!?") if len(interval) > 2 else ''

                if interval_word == word:
                    line_result.append({
                        'word': interval[2],
                        'start': interval[0],
                        'end': interval[1]
                    })
                    interval_index = start_index + 1 # Move the global index forward
                    found_match = True
                    break
                elif interval_word == '':
                    start_index += 1
                else:
                    start_index += 1
                    break

            if not found_match:
                line_result.append({'word': word, 'start': None, 'end': None})

        if line_result:
            result.append(line_result)

    return result
