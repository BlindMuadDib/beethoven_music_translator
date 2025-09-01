"""
This service provides an API for analyzing the harmonic, spectral,
timbral and tempora features of audio stems and/or full tracks.
"""

import os
import json
import logging
import atexit
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, as_completed
from flask import Flask, request, jsonify, Response, stream_with_context
from .analysis_functions import get_static_features, generate_time_sliced_features, analyze_full_track_features

app = Flask(__name__)

# --- Global Configuration & Setup ---
# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = app.logger # Use Flask's logger

MAX_CPU_WORKERS = int(os.environ.get("HARMONIC_CPU_WORKERS", "1"))

RESULTS_BASE_URL = "/api/results"
# The local file path for storing results. This path should
# correspond to the PVC.
RESULTS_BASE_PATH = "/shared-data/results/"

# 1. Create the Process Pool ONCE when the application starts.
# This pool will be reused by all requests to this worker process.
process_pool = ProcessPoolExecutor(max_workers=MAX_CPU_WORKERS)

# 2. Register a shutdown hook.
# This ensures that when the Gunicorn worker process exists, it will
# gracefully shut down the process pool and clean up its child processes.
def shutdown_pool():
    logger.info("Shutting down process pool...")
    process_pool.shutdown(wait=True)
atexit.register(shutdown_pool)

# --- End Global Setup ---

@app.route('/api/analyze_harmonic', methods=['POST'])
def analyze_harmonic_endpoint():
    """Endpoint to analyze audio features for given audio stem paths.
    Expects JSON: {
        "full_track_path": "/path/to/full_track.wav",
        "stem_paths": {"instrument_name": "/path/to/audio.wav", ...}
    }

    Both "full_track_path" and "stem_paths" are required.

    Returns JSON: {
        "results_url": "https://musictranslator.org/api/results/unique-id"
    }
    """
    if not request.is_json:
        logger.warning("Request received is not JSON.")
        return jsonify({"error": "Invalid request: Content-Type must be application/json"}), 415

    data = request.get_json()
    if not data:
        logger.warning("Request JSON body is empty.")
        return jsonify({"error": "Request body cannot be empty"}), 400

    full_track_path = data.get('full_track_path')
    stem_paths = data.get('stem_paths')

    if not full_track_path or not isinstance(full_track_path, str) or not os.path.exists(full_track_path):
        logger.warning("Invalid or missing 'full_track_path': %s.",
                       full_track_path)
        return jsonify({
            "error": "Missing or invalid 'full_track_path'. Must be a valid string path to an existing file."
        }), 400

    if not stem_paths or not isinstance(stem_paths, dict):
        logger.warning("Invalid or empty 'stem_paths': %s",
                       stem_paths)
        return jsonify({
            "error": "Missing or invalid 'stem_paths'. Must be a non-empty dictionary of instrument paths."
        }), 400

    # Extract the job_id from the full_track_path as requested.
    # Assumes filename format is '<job_id>_path/to/full/track.wav'.
    filename = os.path.basename(full_track_path)
    if '_' not in filename:
        logger.error("full_track_path filename does not contain a job_id.")
        return jsonify({
            "error": "Filename must be in the format <job_id>_/path/to/full/track.wav"
        }), 400

    job_id = filename.split('_')[0]

    static_results_url = os.path.join(RESULTS_BASE_URL, f"{job_id}_harmonic.json")

    results_data = {
        "job_id": job_id,
        "results_url": static_results_url,
        "full_track_analysis": None,
        "stem_analyses": {}
    }
    logger.info(
        "Received analysis request for full track: %s and stems: %s",
        full_track_path, list(stem_paths.keys())
    )

    # The tasks for the ProcessPoolExecutor. These tasks must be
    # picklable, so we're passing only string paths.
    tasks = {
        'full_track': full_track_path,
        **{f"stem_{name}": path for name, path in stem_paths.items()}
    }

    try:
        # 3. Use the global `process_pool` instead of creating a new one.
        futures = {
            process_pool.submit(
                analyze_full_track_features, full_track_path
            ): {
                "type": 'full_track',
                "id": "full_track"
            }
        }
        for name, path in stem_paths.items():
            futures[process_pool.submit(
                        get_static_features, path
            )] = {
                "type": "stem",
                "id": name
            }

        # As tasks complete, collect the results
        for future in as_completed(futures):
            task_info = futures[future]
            job_type, identifier = task_info["type"], task_info["id"]

            try:
                analysis_data = future.result()
                if job_type == 'full_track':
                    results_data['full_track_analysis'] = analysis_data
                    logger.info("Successfully analyzed full track.")
                else:
                    results_data['stem_analyses'][identifier] = analysis_data
                    logger.info("Successfully analyzed stem '%s'.",
                                identifier)

            except Exception as e:
                logger.error(
                    "Error during analysis for job type '%s' (id: '%s'): %s",
                    job_type, identifier, e, exc_info=True
                )
                if job_type == 'full_track':
                    results_data['full_track_analysis'] = {"error": str(e)}
                else:
                    results_data['stem_analyses'][identifier] = {"error": str(e)}

        # Save the results to disk
        os.makedirs(RESULTS_BASE_PATH, exist_ok=True)
        output_path = os.path.join(RESULTS_BASE_PATH,
                                   f"{job_id}_harmonic.json")
        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=4)
        logger.info("Successfully saved analysis results to %s",
                    output_path)

        return jsonify({
            "results_url": static_results_url,
            "job_id": job_id
        }), 202

    except concurrent.futures.process.BrokenProcessPool as e:
        logger.critical("CRITICAL: The process pool was broken. Request failed for job_id: %s. %s",
                        job_id, e, exc_info=True)
        return jsonify({
            "error": "A critical error occurred during parallel processing, and the task could not be completed. This is likely due to the service running out of memory. Please try again or contact support if the issue persists."
        }), 500
    except Exception as e:
        logger.error("An unexpected error occurred in the analysis endpoint for job_id: %s. %s",
                     job_id, e, exc_info=True)
        return jsonify({
            "error": "An unexpected server error occurred."
        }), 500

@app.route('/api/harmonic/stream/<job_id>_<stem_name>.ndjson', methods=['GET'])
def stream_results_ndjson(job_id, stem_name):
    """
    Streams time-sliced analysis data in NDJSON format.
    The client must provide the stem path via a query parameter.
    """
    stem_path = request.args.get('stem_path')
    if not stem_path or not os.path.exists(stem_path):
        return jsonify({"error": "Invalid or missing 'stem_path' parameter."}), 400

    logger.info(
        "Initiating streaming for job_id: %s, stem: %s",
        job_id, stem_name
    )

    def generate():
        """Generator function to yield NDJSON lines."""
        for time_slice_data in generate_time_sliced_features(stem_path):
            yield json.dumps(time_slice_data) + "\n"

    response = Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson'
    )
    # This header is crucial for front-end streaming parsers.
    response.headers['X-Content-Type-Options'] = 'nosniff'

    return response

@app.route('/harmonic/health', methods=['GET'])
def health_check():
    """Healh check endpoint for the Harmonic Analysis service."""
    return jsonify({"status": "OK", "message": "Harmonic Analysis service is running"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=20006, debug=True)
