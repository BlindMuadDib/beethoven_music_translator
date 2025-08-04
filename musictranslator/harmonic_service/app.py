import os
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from flask import Flask, request, jsonify
from .analysis_functions import analyze_audio_features

app = Flask(__name__)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = app.logger # Use Flask's logger

@app.route('/api/analyze_harmonic', methods=['POST'])
def analyze_harmonic_endpoint():
    """Endpoint to analyze audio features for given audio stem paths.
    Expects JSON: {"stem_paths": {"instrument_name": "/path/to/audio.wav", ...}}
    Returns JSON: {"instrument_name": {"f0_values": {...}, "spectral_features": {...}, ... } or null, ...}
    """
    if not request.is_json:
        logger.warning("Request received is not JSON.")
        return jsonify({"error": "Invalid request: Content-Type must be application/json"}), 415

    data = request.get_json()
    if not data or 'stem_paths' not in data:
        logger.warning("Request JSON missing 'stem_paths' key.")
        return jsonify({"error": "Missing 'stem_paths' in request body"}), 400

    stem_paths = data.get('stem_paths')
    if not isinstance(stem_paths, dict):
        logger.warning("'stem_paths' os not a dictionary.")
        return jsonify({"error": "'stem_paths' must be a dictionary"}), 400

    results = {}
    logger.info(f"Received analysis request for stems: {list(stem_paths.keys())}")

    # Use ProcessPoolExecutor to run analyze_audio_features
    # concurrently.
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_to_instrument = {
            executor.submit(analyze_audio_features, path): instrument
            for instrument, path in stem_paths.items()
        }

        # As tasks complete, collect the results
        for future in as_completed(future_to_instrument):
            instrument = future_to_instrument[future]
            try:
                analysis_data = future.result()
                results[instrument] = analysis_data
                if analysis_data:
                    logger.info(
                        "Successfully analyzed %s (path: %s).",
                        instrument, stem_paths[instrument]
                    )
                else:
                    logger.info(
                        "No analysis data returned for %s (path: %s).",
                        instrument, stem_paths[instrument]
                    )
            except Exception as e:
                logger.error(
                    "Error during analysis for %s (path: %s): %s",
                    instrument, stem_paths[instrument],
                    e, exc_info=True
                )
                results[instrument] = None

    logger.info(f"Analysis complete. Returning results for: {list(results.keys())}")
    return jsonify(results), 200

@app.route('/harmonic/health', methods=['GET'])
def health_check():
    """Healh check endpoint for the Harmonic Analysis service."""
    return jsonify({"status": "OK", "message": "Harmonic Analysis service is running"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=20006, debug=True)
