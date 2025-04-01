"""
Map the alignment data to the lyrics transcript line-by-line
"""

import json
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

def sync_alignment_json_with_transcript_lines(alignment_json, transcript_lines):
    """
    Synchronizes alignment data from a TextGrid with transcript lines.


    Args:
        alignment_json (dict): The JSON alignment data
        transcript_lines (list): List of transcript lines

    Returns:
        list: List of aligned data in a line-by-line format
    """
    alignment_intervals = alignment_json.get('intervals', [])
    result = []
    alignment_index = 0

    for line in transcript_lines:
        line_result = []
        for word in line:
            word = word.lower().strip(".,!?")
            if not word:
                continue

            while alignment_index < len(alignment_intervals):
                interval = alignment_intervals[alignment_index]
                if interval['word'] == word:
                    line_result.append({
                        'word': interval['word'],
                        'start': interval['xmin'],
                        'end': interval['xmax']
                    })
                    alignment_index += 1
                    break
                elif interval['word'] == '':
                    alignment_index += 1
                else:
                    alignment_index += 1

        if line_result:
            result.append(line_result)

    return result
