"""
Map the alignment data from the .json alignment file to the lyrics transcript line-by-line
"""

import json

def process_transcript(lyrics_path):
    """
    Processes the lyrics file and returns a list of lines,
    Each containing a list of words"""
    try:
        with open(lyrics_path, 'r') as file:
            raw_lines = file.readlines()
            processed_lines = []
            for raw_line in raw_lines:
                # Store the original, stripped line
                original_text = raw_line.strip()
                if not original_text: # Skip empty lines
                    continue
                # Normalize words for matching, but keep original_text separate
                words = [word.lower().strip(".,!?;:") for word in original_text.strip().split()]
                # Filter out empty strings that might result from multiple spaces or stripping
                words = [word for word in words if word]
                # Only add if there are actual words after processing
                if words:
                    processed_lines.append({
                        "original_text": original_text,
                        "word_list": words
                    })
            return processed_lines
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
        print("Warning: No lines processed from lyrics file.")
        return []

    alignment_intervals = alignment_json.get('tiers', {}).get('words', {}).get('entries', [])
    final_mapped_result = []
    interval_index = 0 # Tracks current position in alignment_intervals

    for line_obj in transcript_lines:
        line_text_original = line_obj["original_text"]
        transcript_line_words = line_obj["word_list"]

        current_line_word_data = []
        line_actual_start_time = None
        line_actual_end_time = None

        # use a temporary index for searching within the current line
        temp_interval_search_idx = interval_index

        for word in transcript_line_words:
            if not word:
                continue

            found_match = False

            # Search for the transcript word in the alignment intervals
            # starting from temp_interval_search_idx
            search_lookahead_idx = temp_interval_search_idx
            while search_lookahead_idx < len(alignment_intervals):
                interval = alignment_intervals[search_lookahead_idx]
                aligned_word_text = interval[2].lower().strip(".,!?;:") if len(interval) > 2 else ''

                if aligned_word_text == word:
                    word_start_time = interval[0]
                    word_end_time = interval[1]
                    current_line_word_data.append({
                        'word': interval[2],
                        'start': word_start_time,
                        'end': word_end_time
                    })
                    # Update line start/end times
                    if word_start_time is not None:
                        if line_actual_start_time is None or word_start_time < line_actual_start_time:
                            line_actual_start_time = word_start_time
                    if word_end_time is not None:
                        if line_actual_end_time is None or word_end_time > line_actual_end_time:
                            line_actual_end_time = word_end_time

                    temp_interval_search_idx = search_lookahead_idx + 1 # Move the global index forward
                    found_match = True
                    break # break the inner while loop since  a match for the current word was found

                search_lookahead_idx += 1

            if not found_match:
                current_line_word_data.append({'word': word, 'start': None, 'end': None})

        # After processing all words in the transcript line, update the main interval_index
        # This ensures that for the next line, we start searching from where the current line left off.
        interval_index = temp_interval_search_idx

        if current_line_word_data:
            final_mapped_result.append({
                "line_text": line_text_original,
                "words": current_line_word_data,
                "line_start_time": line_actual_start_time,
                "line_end_time": line_actual_end_time
            })

    return final_mapped_result
