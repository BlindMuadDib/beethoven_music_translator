"""
A Flask endpoint for the volume analysis endpoint.
"""

import os
from flask import Flask, request, jsonify
from .volume_analysis import calculate_rms_for_file

app = Flask(__name__)

@app.route("/api/analyze_rms", methods=["POST"])
def analyze_rms_endpoint():
    """
    Expects a JSON payload: {"audio_paths": {"song": "path1", "bass": "path2", ... } }
    """
    if not request.json or "audio_paths" not in request.json:
        return jsonify({"error": "Malformed request, 'audio_paths' key missing."}), 400

    audio_paths = request.json["audio_paths"]

    response_data = {
        "overall_rms": [],
        "instruments": {}
    }

    # Process the main song file
    if "song" in audio_paths:
        song_path = audio_paths.pop("song")
        # This assumes it's a valid path, change before integration with K8s
        response_data["overall_rms"] = calculate_rms_for_file(song_path)

    # Process instrument stems
    for instrument, path in audio_paths.items():
        rms_values = calculate_rms_for_file(path)
        response_data["instruments"][instrument] = {
            "rms_values": rms_values
        }

    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=39574, debug=True)
