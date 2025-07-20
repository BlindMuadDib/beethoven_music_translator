import os
import logging
import sys
from flask import Flask, request, jsonify
from drum_analysis_service import drum_analysis

# --- Flask App Setup ---
app = Flask(__name__)

# --- Logging Setup ---
# Configure logging for the Flask app
# Using Flask's  logger makes it integrate well with Flask's debugging and deployment.
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,
                    format='%(asctime)s = %(name)s - %(levelname)s - %(message)s')
logger = app.logger

@app.route('/api/analyze_drums', methods=['POST'])
def analyze_drums_endpoint():
    """
    Endpoint to analyze drum hits for given audio stem paths.
    Expects JSON: {"drum_path": "/path/to/audio.wav"}
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
            raise

        # 2. Perform concurrent drum analysis
        logger.info("Calling analyze_audio_concurrently...")
        drum_hits = drum_analysis.analyze_audio_concurrently(y, sr)

        if drum_hits:
            logger.info("Successfully analyzed drums. Found %s hits.", len(drum_hits))
        else:
            logger.info("No drum hits returned.")

        return jsonify(drum_hits), 200
        logger.info("Drum analysis complete. Returing results for: %s", drums_path)

    except Exception as e:
        logger.critical("Unhandled error during drum analysis: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error during analysis. Details: " + str(e)}), 500

@app.route('/drums/health', methods=['GET'])
def health_check():
    """Health check endpoint for the Drum Analysis service."""
    logger.info("Health check requested for Drum Analysis service.")
    return jsonify({"status": "OK", "message": "Drum Analysis service is running"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=25941, debug=True)
