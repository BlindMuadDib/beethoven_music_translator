import os
import logging
import sys
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import numpy as np
from flask import Flask, request, jsonify
from . import drum_analysis
from . import DrumMLA as drum_mla_module
from .DrumMLA import DrumMLA

MAX_CPU_WORKERS = int(os.environ.get("DRUMS_CPU_WORKERS", "2"))

# --- Flask App Setup ---
app = Flask(__name__)

# --- Logging Setup ---
# Configure logging for the Flask app
# Using Flask's  logger makes it integrate well with Flask's debugging and deployment.
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s = %(name)s - %(levelname)s - %(message)s')
logger = app.logger

# --- Numba Logger Configuration ---
try:
    numba_logger = logging.getLogger('numba')
    numba_logger.setLevel(logging.WARNING)
    numba_core_ssa_logger = logging.getLogger('numba.core.ssa')
    numba_core_ssa_logger.setLevel(logging.WARNING)
    numba_np_ufunc_logger = logging.getLogger('numba.np.ufunc')
    numba_np_ufunc_logger.setLevel(logging.WARNING)
    logger.info("Numba log levels set to WARNING to supress verbose output.")
except Exception as e:
    logger.error(f"Failed to configure Numba loggers: {e}")

DRUM_SAMPLES_FILE = "/app/data_backend/drum_sample_features.json"

# This `drum_mla` global is for the Flask worker itself, not directly
# for the pool's sub-workers. It will be used by
# `analyze_audio_concurrently` and for the API calls *from this Flask
# worker*.
drum_mla = None
SHARED_EXECUTOR = None

# Initializer function for the ProcessPoolExecutor workers
def _init_process_pool_worker(
    raw_known_samples, feature_weights, drum_categories,
    drum_types, drum_qualifiers, feature_ranges
):
    """
    Initializer for each worker in the ProcessPoolExecutor.
    This function sets the global variables within the drum_mla_module
    for the current worker process.
    """
    logger.info("Initializing ProcessPoolExecutor worker...")

    # Set the simple global variables
    drum_mla_module._global_feature_weights = feature_weights
    drum_mla_module._global_drum_categories = drum_categories
    drum_mla_module._global_drum_types = drum_types
    drum_mla_module._global_drum_qualifiers = drum_qualifiers
    drum_mla_module._global_feature_ranges = feature_ranges

    # Use the static method from the DrumMLA class to prepare the
    # complex known_samples dict
    drum_mla_module._global_known_samples = DrumMLA._prepare_known_samples_from_raw(
        raw_known_samples, drum_categories, drum_types, drum_qualifiers, feature_weights
    )

    logger.info("Worker initialization complete.")

# --- DrumMLA Initialization ---

def load_drum_mla():
    """
    Loads drum samples and Initializes DrumMLA. Called once on
    app startup.
    """
    global drum_mla, SHARED_EXECUTOR

    if drum_mla is not None:
        return # Already loaded

    try:
        if not os.path.exists(DRUM_SAMPLES_FILE):
            logger.critical("Drum samples file not found: %s",
                            DRUM_SAMPLES_FILE)
            # Change to run without functionality
            # For now Initializes an empty instance
            drum_mla = DrumMLA()
            raw_known_samples_data = []
            logger.warning("DrumMLA initalized without known samples due to missing file.")
        else:
            with open(DRUM_SAMPLES_FILE, 'r') as f:
                raw_known_samples_data = json.load(f)

            # The main process gets a full instance of DrumMLA
            drum_mla = DrumMLA(known_samples_data=raw_known_samples_data)
            logger.info("DrumMLA initialized with %d total known samples.",
                        len(raw_known_samples_data))

        # Initalize the SHARED_EXECUTOR (ProcessPoolExecutor)
        # Pass DrumMLA's necessary data as arguments to the
        # intializer
        SHARED_EXECUTOR = ProcessPoolExecutor(
            max_workers=MAX_CPU_WORKERS,
            initializer=_init_process_pool_worker,
            initargs=(
                raw_known_samples_data,
                drum_mla.feature_weights,
                drum_mla.drum_categories,
                drum_mla.drum_types,
                drum_mla.drum_qualifiers,
                drum_mla._feature_ranges
            )
        )
        logger.info(
            "Initialized global ProcessPoolExecutor with %s workers.",
            MAX_CPU_WORKERS
        )

    except Exception as e:
        logger.critical(
            "Failed to load drum samples or initalize DrumMLA: %s",
            e, exc_info=True
        )
        # Initialize an empty MLA to prevent startup failure
        drum_mla = DrumMLA()
        SHARED_EXECUTOR = ProcessPoolExecutor(max_workers=1)
        logger.error("DrumMLA and ProcessPoolExecutor initialized as empty/minimal due to prior error.")

# Call this function when the app starts
with app.app_context():
    load_drum_mla()

# --- Routes ---

@app.route('/api/analyze_drums', methods=['POST'])
def analyze_drums_endpoint():
    """
    Endpoint to analyze drum hits for given audio stem paths.
    Expects JSON: {"drum_path": "/path/to/audio.wav"}
    Returns JSON:
    {
        "hits": [
            { "onset_time": ..., "drum_type": ..., "type_confidence": ..., ...},
            ...
        ],
        "tempo": ...
    }
    """
    if not request.is_json:
        logger.warning("Request received for /api/analyze_drums is not JSON.")
        return jsonify({"error": "Invalid request: Content-Type must be application/json"}), 415

    data = request.get_json()
    if not data or 'drums_path' not in data:
        logger.warning("Request JSON is missing 'drums_path' key for /api/analyze_drums.")
        return jsonify({"error": "Missing 'drums_path' in request body"}), 400

    drums_path = data.get('drums_path')
    if not isinstance(drums_path, str):
        logger.warning("Invalid 'drums_path' type: %s. Must be a string.", type(drums_path))
        return jsonify({"error": "Invalid 'drums_path': must be a string"}), 400

    if not os.path.exists(drums_path):
        logger.warning("Drums path does not exist: %s", drums_path)
        return jsonify({"error": f"Drums path does not exist: {drums_path}"}), 400

    logger.info("Received drum analysis request for path: %s", drums_path)

    try:
        # 1. Load audio from file path
        y, sr = drum_analysis.load_audio_from_file(drums_path)
        logger.info(
            "Before calling detect_onset: y_audio type=%s, shape=%s, sr_audio=%s",
            type(y), y.shape, sr
        )
        if y.size == 0:
            logger.error("Audio series 'y' is empty before onset detection!")
            return jsonify({"error": "No audio data found in the provided file."}), 422

        # 2. Perform concurrent drum analysis
        logger.info("Calling analyze_audio_concurrently...")
        analysis_output = drum_analysis.analyze_audio_concurrently(
            y, sr
        )

        drum_hits_features = analysis_output["hits"]
        overall_tempo_bpm = analysis_output["tempo"]

        # If no drum hits were found, but tempo was, return that structure
        if not drum_hits_features and overall_tempo_bpm is not None:
            logger.info("No drum hits (features) returned, but tempo was estimated.")
            return jsonify({
                "hits": [],
                "tempo": overall_tempo_bpm
            }), 200
        # If no hits AND no tempo
        elif not drum_hits_features:
            logger.info("No drum hits (features) and no tempo returned.")
            return jsonify({
                "hits": [],
                "tempo": 0.0
            }), 200

        # 3. Classify drum hits using DrumMLA
        logger.info("Classifying %d extracted drum hits...",
                    len(drum_hits_features))

        # Ensure drum_mla is initialized. If not, return without
        # classification.
        if drum_mla is None:
            logger.error(
                "DrumMLA not initialized. Cannot classify drum hits."
            )
            # Fallback: return features without classification as
            # 'other/unknown' with 0 confidence, but include tempo
            for hit in drum_hits_features:
                hit['drum_category'] = 'other'
                hit['category_confidence'] = 0.0
                hit['drum_type'] = 'unknown'
                hit['type_confidence'] = 0.0
                hit['qualifier'] = 'no_qualifier'
                hit['qualifier_confidence'] = 0.0
            return jsonify({
                "hits": drum_hits_features,
                "tempo": overall_tempo_bpm
            }), 200

        classified_drum_hits = drum_mla.classify_drum_events(
            drum_hits_features,
            min_category_confidence=0.7,
            min_type_confidence=0.5,
            min_qualifier_confidence=0.5,
            k=5,
            executor=SHARED_EXECUTOR
        )

        logger.info(
            "Drum analysis and classification complete. Found %d classified hits.",
            len(classified_drum_hits))
        return jsonify({
            "hits": classified_drum_hits,
            "tempo": overall_tempo_bpm
        }), 200

    except Exception as e:
        logger.critical("Unhandled error during drum analysis: %s",
                        e, exc_info=True)
        return jsonify(
            {"error": "Internal server error during analysis. Details: " + str(e)}
        ), 500

@app.route('/drums/health', methods=['GET'])
def health_check():
    """Health check endpoint for the Drum Analysis service."""
    logger.info("Health check requested for Drum Analysis service.")
    status = "OK" if drum_mla is not None else "DEGRADED"
    if drum_mla is not None:
        message = "Drum Analysis service is running"
    else:
        message = "Drum Analysis service running, but MLA not initialized"
    return jsonify({"status": status, "message": message}), 200

if __name__ == "__main__":
    # This block is for development only and will NOT run when
    # Gunicorn is used.
    import atexit
    atexit.register(lambda: SHARED_EXECUTOR.shutdown(wait=True))
    app.run(host='0.0.0.0', port=25941, debug=True)
