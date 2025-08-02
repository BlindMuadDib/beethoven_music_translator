import json
import os
from musictranslator.musicprocessing.transcribe import map_transcript

def create_mapped_result_file(alignment_json_filepath, transcript_filepath, output_json_filepath):
    """
    Runs the map_transcript function and saves its output to a JSON file.
    """
    print(f"Reading alignment data from: {alignment_json_filepath}")
    print(f"Reading lyrics data from: {transcript_filepath}")

    if not os.path.exists(alignment_json_filepath):
        print(f"Error: Alignment JSON file not found at '{alignment_json_filepath}")
        return
    if not os.path.exists(transcript_filepath):
        print(f"Error: Lyrics transcript file not found at '{transcript_filepath}")
        return

    # Call map_transcript
    mapped_data = map_transcript(alignment_json_filepath, transcript_filepath)

    if mapped_data is None:
        print("Error: map_transcript returned None. Check fr errors in the function or input files.")
        return

    if not mapped_data:
        print("Warning: map_transcript returned an empty list. This might be expected if lyrics empty or no alignment.")

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_json_filepath), exist_ok=True)

    # Write the Python object directly to a JSON file
    # json.dump will handle correct JSON formatting (double quotes, etc.)
    try:
        with open(output_json_filepath, 'w', encoding='utf-8') as outfile:
            json.dump(mapped_data, outfile, indent=4) # indent=4 for pretty printing
        print(f"Successfully generated mapped_result: {output_json_filepath}")
    except Exception as e:
        print(f"Error writing JSON to file: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Input files for the "BloodCalcification-SkinDeep" example
    alignment_file = os.path.join(project_root, "data", "aligned", "BloodCalcification-SkinDeep.json")
    lyrics_file = os.path.join(project_root, "data", "lyrics", "BloodCalcification-SkinDeep.txt")

    # This is the file the test will load as the "expected" mapped result
    output_mapped_json_file = os.path.join(project_root, "data", "mapped_results", "BloodCalcification-SkinDeep.json")

    # --- Run the generation ---
    create_mapped_result_file(alignment_file, lyrics_file, output_mapped_json_file)
