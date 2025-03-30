"""
Creates a wrapper Flask endpoint
then executes the Spleeter `separate` command within a Docker container

Args:
    input_file (str): The path to the input audio file
    output_dir (str): The path to the output directory
    stems (str, optional): The Spleeter model to use
        Defaults to 4stems-16kHz

Raises:
    FileNotFoundError: If the input file does not exist
    subprocess.CalledProcessError: If the Spleeter command fails
    ValueError: If input arguments are invalid

This project would not be possible without Spleeter by Deezer
Used under the MIT License
GitHub: https://github.com/deezer/spleeter
"""

import subprocess
import os
import shutil
import tempfile
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

@app.route('/separate', methods=['POST'])
def separate():
    """Separates audio file into stems using Spleeter"""
    if 'audio' not in request.files:
        return jsonify({'error': 'Audio file missing.'}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    if audio_file:
        filename = secure_filename(audio_file.filename)
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, filename)
        output_path = temp_dir

        try:
            audio_file.save(input_path)

            result = subprocess.run(
                [
                    "spleeter", "separate",
                    "-p", "spleeter:4stems-16kHz",
                    "-o", output_path, "-i", input_path
                ],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                return jsonify({'error': f'Spleeter error: {result.stderr}'}), 500

            vocals_stem_path = os.path.join(
                output_path,
                os.path.splitext(filename)[0],
                "vocals.wav"
            )

            return jsonify({'vocals_stem_path': vocals_stem_path}), 200

        except FileNotFoundError as e:
            return jsonify({'error': f'Spleeter error: {e}'}), 500
        finally:
            os.remove(input_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

    return jsonify({'error': 'Invalid file.'}), 400

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True, host='0.0.0.0', port=22227)
