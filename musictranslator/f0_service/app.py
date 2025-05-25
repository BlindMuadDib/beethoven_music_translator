import os
import logging
import numpy as np
from flask import Flask, request, jsonify
from .fund_freq import analyze_fund_freq

app = Flask(__name__)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = app.logger # Use Flask's logger

@app.route('/analyze_f0', methods=['POST'])
def analyze_f0_endpoint():
    """Endpoint to analyze fundamental frequency for given audio stem paths.
    Expects JSON: {"stem_paths": {"instrument_name": "/path/to/audio.wav", ...}}
    Returns JSON: {"instrument_name": [f0_values_list_or_null], ...}
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
    logger.info(f"Received F0 analysis request for stems: {list(stem_paths.keys())}")

    for instrument, audio_path in stem_paths.items():
        logger.info(f"Analyzing F0 for instrument: {instrument}, path: {audio_path}")
        if not isinstance(audio_path, str) or not os.path.exists(audio_path):
            logger.warning(f"Invalid or non-existent path for {instrument}: {audio_path}")
            results[instrument] = None
            continue

        try:
            # fmin and fmax could be configurable per instrument type in the future
            f0_array = analyze_fund_freq(audio_path)

            if f0_array is None:
                logger.info(f"No F0 data returned for {instrument} (path: {audio_path}).")
                results[instrument] = None
            else:
                # Convert numpy.ndarray to list and handle np.nan for JSON compatiblity
                f0_list = [x if not np.isnan(x) else None for x in f0_array]
                results[instrument] = f0_list
                logger.info(f"Successfully analyzed F0 for {instrument} (path: {audio_path}).")
        except Exception as e:
            logger.error(f"Error during F0 analysis for {instrument} (path: {audio_path}): {e}", exc_info=True)
            results[instrument] = None

    logger.info(f"F0 analysis complete. Returning results for: {list(results.keys())}")
    return jsonify(results), 200

@app.route('/f0/health', methods=['GET'])
def health_check():
    """Healh check endpoint for the F0 service."""
    return jsonify({"status": "OK", "message": "F0 Analysis service is running"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=20006, debug=True)
