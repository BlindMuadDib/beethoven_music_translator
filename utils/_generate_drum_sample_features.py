"""
A helper function to automate feature analysis on drum samples
Accepts audio.wav files, and generates a file of JSON dictionaries
"""

import os
import sys
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from musictranslator.drum_analysis_service import drum_analysis

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Defines the root directory where the drums samples are located
DRUM_SAMPLES_ROOT_DIR = Path('/home/BlindMuadDib/projects/Music-Translation-for-and-by-Deaf/data_backend/drum_samples/')
OUTPUT_JSON_FILE = 'drum_sample_features.json'

def parse_drum_label(file_name: str) -> dict:
    """
    Parses the file name to determine drum_category, type, and
    qualifier. This logic needs to be robust and adapted to our
    naming conventions.
    """
    file_name_lower = file_name.lower()

    category = "other"
    drum_type = "unknown"
    qualifiers = set()

    # Step 1: Determine Drum Category and Initial Drum Type
    if "hihat" in file_name_lower or "hi-hat" in file_name_lower:
        category = "cymbal"
        drum_type = "hihat"
    elif "crash" in file_name_lower:
        category = "cymbal"
        drum_type = "crash"
    elif "ride" in file_name_lower:
        category = "cymbal"
        drum_type = "ride"
    elif "gong" in file_name_lower:
        category = "cymbal"
        drum_type = "gong"
    elif "cymbal" in file_name_lower:
        category = "cymbal"
        drum_type = "unknown"

    if "bass" in file_name_lower or "kick" in file_name_lower:
        category = "kick"
        drum_type = "bass"

    elif "snare" in file_name_lower:
        category = "snare"
        if "open" in file_name_lower or "off" in file_name_lower:
            drum_type = "open_band"
        elif "close" in file_name_lower or "on" in file_name_lower:
            drum_type = "closed_band"
        else:
            drum_type = "closed_band"

    elif "tom" in file_name_lower:
        category = "tom"
        if ("med" in file_name_lower and "high" in file_name_lower) \
            or ("mid" in file_name_lower and "high" in file_name_lower):
            drum_type = "med_high"
        elif ("med" in file_name_lower and "low" in file_name_lower) \
            or ("mid" in file_name_lower and "low" in file_name_lower):
            drum_type = "med_low"
        elif "mid" in file_name_lower:
            drum_type = "mid"
        elif "low" in file_name_lower or "floor" in file_name_lower:
            drum_type = "low"
        elif "hi" in file_name_lower or "high" in file_name_lower:
            drum_type = "high"
        else: # Default tom type if not specified
            drum_type = "mid"

    elif "cowbell" in file_name_lower:
        category = "other"
        drum_type = "cowbell"

    if drum_type is None:
        drum_type = "unknown"

    if category == "kick" and drum_type == "unknown":
        drum_type = "bass"
    elif category == "snare" and drum_type == "unknown":
        drum_type = "closed_band"
    elif category == "tom" and drum_type == "unknown":
        drum_type = "mid"

    # Step 2: Determine Qualifiers based on Category/Type
    # This allows multiple qualifiers to be found in a list

    if "rim" in file_name_lower:
        qualifiers.add("rimshot")
    if "brush" in file_name_lower:
        qualifiers.add("brush")
    if "chain" in file_name_lower:
        qualifiers.add("chains")
    if "stop" in file_name_lower or "mute" in file_name_lower:
        qualifiers.add("muted")

    elif category == "cymbal":
        # Qualifiers specific to cymbal types
        if drum_type == "hihat":
            # Hihat specific state qualifiers
            if "open" in file_name_lower:
                qualifiers.add("open")
            elif "close" in file_name_lower:
                qualifiers.add("close")
        else:
            if "full" in file_name_lower:
                qualifiers.add("full")
            if "mid" in file_name_lower:
                qualifiers.add("mid")
            if "bell" in file_name_lower:
                qualifiers.add("bell")

    # Step 3: Format the qualifier string
    # If multiple qualifiers are found, join them with an underscore,
    # sorted for consistency. Otherwise, use "no_qualifier"
    final_qualifier = "no_qualifier"
    if qualifiers:
        final_qualifier = "_".join(sorted(list(qualifiers)))

    # Handle cases where 'multiple' is in the filename for samples
    # with multiple hits. This might influence how the sample is used,
    # but not necessarily the category itself.
    is_multiple_hits_sample = "multiple" in file_name_lower or "roll" in file_name_lower or "sequence" in file_name_lower

    return {
        "drum_category": category,
        "drum_type": drum_type,
        "qualifier": final_qualifier,
        "is_multiple_hits_sample": is_multiple_hits_sample
    }

def generate_features_for_samples(samples_dir: Path, executor: ThreadPoolExecutor) -> list[dict]:
    """
    Iterates through drum sample files, extracts features,
    and returns a list of feature dictionaries.
    Handles both single and multiple hits with a sample file.
    """
    all_sample_features = []
    supported_extensions = ['.wav', '.flac', '.mp3', '.ogg']

    logger.info("Scanning for drum samples in: %s", samples_dir)

    for root, _, files, in os.walk(samples_dir):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() in supported_extensions:
                logger.info("Processing sample: %s", file_name)
                try:
                    label_info = parse_drum_label(file_name)
                    drum_category = label_info["drum_category"]
                    drum_type = label_info["drum_type"]
                    qualifier = label_info["qualifier"]
                    is_multiple_hits_sample = label_info["is_multiple_hits_sample"]

                    y, sr = drum_analysis.load_audio_from_file((str(file_path)))

                    if y.size == 0:
                        logger.warning(f"Audio file {file_name} is empty, skipping.")
                        continue

                    # If the sample is explicitly marked as having
                    # multiple hits OR if we want run onset detect
                    # on all samples just in case
                    # setting True will always run onset detection
                    if is_multiple_hits_sample or True:
                        # Use concurrent analysis to find all hits
                        full_audio_analysis_result = drum_analysis.analyze_audio_concurrently(y, sr, executor)
                        detected_hits = full_audio_analysis_result["hits"]


                        if not detected_hits:
                            logger.warning("No hits detected in sample %s, even though it might contain one. Adding as a single segment for features.", file_name)
                            # Fallback: if no onsets, treat the whole
                            # sample as one segment. This might happen
                            # for very soft hits or sustained sounds
                            # where onset is ambiguous
                            features = drum_analysis.extract_features_from_segment(y, sr)
                            features["sample_name"] = file_name
                            features["drum_category"] = drum_category
                            features["drum_type"] = drum_type
                            features["qualifier"] = qualifier
                            features["original_sample_file"] = file_name
                            features["onset_in_sample"] = 0.0
                            all_sample_features.append(features)
                        else:
                            for hit_data in detected_hits:
                                hit_data["sample_name"] = file_name
                                hit_data["drum_category"] = drum_category
                                hit_data["drum_type"] = drum_type
                                hit_data["qualifier"] = qualifier
                                hit_data["original_sample_file"] = file_name
                                # Rename onset_time to onset_in_sample to avoid confusion later
                                hit_data["onset_in_sample"] = hit_data.pop("onset_time")
                                all_sample_features.append(hit_data)
                    else:
                        # For truly single-hit samples (if you don't
                        # want to run onset_detect on them)
                        features = drum_analysis.extract_dynamic_segment(y, sr)
                        features["sample_name"] = file_name
                        features["drum_category"] = drum_category
                        features["drum_type"] = drum_type
                        features["qualifier"] = qualifier
                        features["original_sample_file"] = file_name
                        features["onset_in_sample"] = 0.0
                        all_sample_features.append(features)

                except FileNotFoundError as e:
                    logger.error(
                        "File not found: %s. Skipping. Error: {%s}",
                        file_path, e
                    )
                except Exception as e:
                    logger.error("Error processing %s: %s",
                                 file_path, e)
            else:
                logger.debug("Skipping unsupported file type: %s",
                             file_path)

    logger.info(
        "Finished processing. Extracted features for %s samples",
        len(all_sample_features))
    return all_sample_features

if __name__ == "__main__":
    if not DRUM_SAMPLES_ROOT_DIR.exists():
        logger.error(
            "DRUM_SAMPLES_ROOT_DIR '%s' does not exist. Please update the path.",
            DRUM_SAMPLES_ROOT_DIR
        )
        sys.exit(1)

    if not DRUM_SAMPLES_ROOT_DIR.is_dir():
        logger.error(
            "DRUM_SAMPLES_ROOT_DIR '%s' is not a directory. Please update the path.",
            DRUM_SAMPLES_ROOT_DIR
        )
        sys.exit(1)

# Create a ThreadPoolExecutor here and pass it to the function
# Max workers can be set to number of CPU cores for optimal performance
with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
    sample_features = generate_features_for_samples(
        DRUM_SAMPLES_ROOT_DIR, executor
    )

    # Save to JSON file
    # Save one level up from sample root, or adjust as needed
    output_path = DRUM_SAMPLES_ROOT_DIR.parent / OUTPUT_JSON_FILE
    try:
        with open(output_path, 'w') as f:
            json.dump(sample_features, f, indent=4)
        logger.info(
            "Successfully saved drum sample features to: %s",
            output_path
        )
    except Exception as e:
        logger.critical(
            "Error saving features to JSON: %s",
            e, exc_info=True
        )
