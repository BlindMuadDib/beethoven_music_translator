"""
Map the alignment data to the lyrics transcript line-by-line
"""

import json
import string

def process_transcript(transcript_path):
    """Reads and splits the transcript into lines and words"""
    try:
        with open(transcript_path, "r", encoding="utf-8") as file:
            lines = file.readlines()
        transcript_lines = [line.strip().split() for line in lines if line.strip()]
        print(f"process_transcript complete: {transcript_lines}")
        return transcript_lines
    except Exception as e: # pylint: disable=broad-except
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
                matched_interval = next(
                    (
                        (interval["xmin"], interval["xmax"], word)
                        for interval in word_intervals
                        if (isinstance(interval, dict) and
                            "word" in interval and
                            interval["word"].lower() == word_lower)
                    ),
                    None,
                )
                if matched_interval:
                    timed_line.append(matched_interval)
            synchronized_transcript.append(timed_line)

        print(
            f"The Alignment dictionary has been synchronized to transcript lines:"
            f"{synchronized_transcript}"
        )
        return synchronized_transcript

    except Exception as e: # pylint: disable=broad-except
        print(f"[ERROR] Error synchronizing alignment dictionary: {e}")
        return []
