import textgrid
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

def create_alignment_dict(alignment_path):
    """Maps the forced alignment tool to the transcript"""
    try:
        tg = textgrid.TextGrid.fromFile(alignment_path)

        # Access the desired tier, "words"
        words_tier = tg.getFirst('words') # Adjust 'words' to match TextGrid
        if not words_tier:
            raise ValueError("The 'words' tier is missing from the TextGrid")

        # Build the alignment dictionary for the 'words' tier
        alignment_dict = {
            "tier_name": words_tier.name,
            "intervals": [
                {
                    "xmin": interval.minTime,
                    "xmax": interval.maxTime,
                    "word": interval.mark
                } for interval in words_tier.intervals
            ]
        }

        # Create a tuple of all intervals containing "words"
        word_intervals = tuple(
            {
                "word": interval["word"],
                "xmin": interval["xmin"],
                "xmax": interval["xmax"]
                }
            for interval in alignment_dict["intervals"] if interval["word"].strip()
        )

        print(f"[DEBUG] Alignment dictionary: {alignment_dict}")
        print(f"[DEBUG] Tuple of word intervals created: {word_intervals}")
        return alignment_dict, word_intervals

    except Exception as e:
        print(f"[ERROR] Error processing TextGrid: {e}")
        return {}


def sync_alignment_dict_with_transcript_lines(word_intervals, transcript_lines):
    """Synchronize the alignment dictionary with the lines of the transcript"""

    # Remove punctuation from transcript_lines to properly sync
    def remove_punctuation(text):
        translator = str.maketrans('', '', ',.!?')
        return text.translate(translator)

    # Create a copy of transcript_lines with punctuation removed
    transcript_lines_no_punc = [
        [remove_punctuation(word) for word in line] for line in transcript_lines
    ]

    try:
        synchronized_transcript = []

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
