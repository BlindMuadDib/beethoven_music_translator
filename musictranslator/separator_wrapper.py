"""
Creates a Flask endpoint
then utilizes Demucs to separate audio into 6 stems.

Args:
    audio_data (io.BytesIO): The audio data as a byte stream.

Returns:
    dict: A dictionary containing the separated audio streams.

Raises:
    RuntimeError: If there's an error during Demucs processing.

This project would not be possible without Demucs
https://github.com/adefossez/demucs
"""

import os
import shlex
import demucs.separate
from flask import Flask, request, jsonify

app = Flask(__name__)

# PVC input and output paths
INPUT_DIR = "/shared-data/audio"
OUTPUT_DIR = "/shared-data/separator_output"

def run_demucs(audio_file_path):
    """Runs the demucs python library on a given audio file."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        command = f'-n htdemucs_6s "{audio_file_path}" -o "{OUTPUT_DIR}"'
        command_list = shlex.split(command)

        demucs.separate.main(command_list)

        separated_streams = {}
        output_model_dir = os.path.join(
            OUTPUT_DIR,
            "htdemucs_6s",
            os.path.splitext(os.path.basename(audio_file_path))[0],
        )

        for filename in os.listdir(output_model_dir):
            if filename.endswith(".wav"):
                separated_streams[os.path.splitext(filename)[0]] = os.path.join(output_model_dir, filename)

        return separated_streams

    except RuntimeError as e:
        raise RuntimeError(f"Demucs processing erro: {e}")
    except FileNotFoundError as e:
        raise RuntimeError(f"File Not Found: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {e}")

@app.route('/separate', methods=['POST'])
def separate():
    """Creates a Flask endpoint that separates audio file into stems using Demucs."""
    app.logger.info("Separate function called")
    if 'audio_filename' not in request.json:
        return jsonify({'error': 'Audio filename missing.'}), 400

    audio_filename = request.json['audio_filename']
    audio_file_path = os.path.join(INPUT_DIR, audio_filename)

    # Check if the file exists
    if not os.path.exists(audio_file_path):
        return jsonify({'error': 'Audio file not found.'}), 404

    try:
        separated_streams = run_demucs(audio_file_path)
        app.logger.info(f"Separated streams are in {OUTPUT_DIR}")
        return jsonify(separated_streams)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f"An unexpected error occurred: {e}"}), 500

@app.route('/separate/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"}), 200

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(host='0.0.0.0', port=22227)
