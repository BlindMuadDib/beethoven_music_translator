"""
A Flask endpoint for the volume analysis endpoint.
"""

import os
import logging
from flask import Flask, request, jsonify
from .volume_analysis import calculate_rms_for_file

app = Flask(__name__)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = app.logger # Use Flask's logger

@app.route("/api/analyze_rms/health", methods=["GET"])
def health_check():
    """A simple health check endpoint to confirm the service is running."""
    return jsonify({"status": "healthy"}), 200

@app.route("/api/analyze_rms", methods=["POST"])
def analyze_rms_endpoint():
    """
    Expects a JSON payload: {"audio_paths": {"song": "path1", "bass": "path2", ... } }
    """
    if not request.json or "audio_paths" not in request.json:
        logger.warning("Audio_paths key is missing")
        return jsonify({"error": "Malformed request, 'audio_paths' key missing."}), 400

    audio_paths = request.json["audio_paths"]

    response_data = {
        "overall_rms": [],
        "instruments": {},
        "errors": []
    }
    logger.info(f"Received request for Volume Analysis for audio: {
        list(audio_paths.keys())
    }")

    # Process the main song file
    if "song" in audio_paths:
        song_path = audio_paths.pop("song")
        rms_values, error = calculate_rms_for_file(song_path)
        if error:
            logger.warning(f"Error occurred with audio file: {song_path}. Error: {error}")
            response_data["errors"].append(f"File 'song' ({song_path}): {error}")
        # More robust check: only assign if it's a list.
        # Otherwise, default to empty list.
        response_data["overall_rms"] = rms_values if isinstance(rms_values, list) else []

    # Process instrument stems
    for instrument, path in audio_paths.items():
        rms_values, error = calculate_rms_for_file(path)
        if error:
            logger.warning(f"Error occurred for instrument: '{instrument}'. Path: {path}. Error: {error}")
            response_data["errors"].append(f"File '{instrument}' ({path}): {error}")

        response_data["instruments"][instrument] = {
            "rms_values": rms_values if isinstance(rms_values, list) else []
        }

    # If there were no errors, remove the empty errors list for a cleaner response
    if not response_data["errors"]:
        response_data.pop("errors")

    logger.info(f"Volume analysis complete. Returning data for: {
        list(response_data.keys())}")
    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=39574, debug=True)
