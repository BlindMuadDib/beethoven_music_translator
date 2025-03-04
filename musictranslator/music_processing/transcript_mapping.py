import json
import os
import string

def process_transcript(transcript_path):
    """Reads and splits the transcript into lines and words"""
    try:
        with open(transcript_path, "r") as file:
            lines = file.readlines()
        transcript_lines = [line.strip().split() for line in lines if line.strip()]
        print(f"process_transcript complete: {transcript_lines}")
        return transcript_lines
    except Exception as e:
        print(f"[ERROR] Error processing transcript: {e}")
        return []

def sync_alignment_json_with_transcript_lines(alignment_data, transcript_lines):
    """Synchronize the alignment JSON with the lines of the transcript"""

    # Remove punctuation from transcript_lines to properly sync
    def remove_punctuation(text):
        translator = str.maketrans('', '', string.punctuation)
        return text.translate(translator)

    # Create a copy of transcript_lines with punctuation removed
    transcript_lines_no_punc = [
        [remove_punctuation(word) for word in line] for line in transcript_lines
    ]

    try:
        synchronized_transcript = []

        word_intervals = tuple(
            {
                "word": interval["word"],
                "xmin": interval["xmin"],
                "xmax": interval["xmax"]
            }
            for interval in alignment_data["intervals"] if interval["word"].strip()
        )

        for line in transcript_lines_no_punc:
            timed_line = []
            for word in line:
                word_lower = word.lower()
                for interval in word_intervals:
                    # Check if the interval is a valid dictionary with the expected keys
                    if isinstance(interval, dict) and "word" in interval:
                        if interval["word"].lower() == word_lower:
                            timed_line.append((interval["xmin"], interval["xmax"], word))
                            break
            synchronized_transcript.append(timed_line)

        print(f"The Alignment dictionary has been synchronized to transcript lines: {synchronized_transcript}")
        return synchronized_transcript

    except Exception as e:
        print(f"[ERROR] Error synchronizing alignment dictionary: {e}")
        return []

def create_synchronized_transcript_json(transcript_path, alignment_json_path, output_json_path):
    """Combines all functions to create a synchronized transcript JSON file"""
    transcript_lines = process_transcript(transcript_path)
    try:
        with open(alignment_json_path, 'r') as f:
            alignment_data = jsn.load(f)
    except Exception as e:
        print(f"[ERROR] Error loading alignment JSON: {e}")
        return False

    synchronized_transcript = sync_alignment_json_with_transcript_lines(alignment_data, transcript_lines)

    try:
        with open(output_json_path, 'w') as f:
            json.dump(synchronized_transcript, f, indent=4)
        return True
    except Exception as e:
        print(f"[ERROR] Error creating synchronized transcript JSON: {e}")
        return False
