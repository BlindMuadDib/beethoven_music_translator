"""
Wrapper for  Kubernetes to run specific codes within a Docker image

ARGS:
    lyrics transcript and Spleeter vocal stem

RETURNS:
    Alignment data in JSON format
"""
import subprocess
import json
import os
import tempfile
import shutil
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/align', methods=['POST'])
def align():
    """Main function of the wrapper"""
    if 'audio' not in request.files or 'lyrics' not in request.files:
        return jsonify({'error': 'Audio or lyrics file missing'}), 400
    audio_file = request.files.get('audio')
    lyrics_file = request.files.get('lyrics')

    temp_dir = tempfile.mkdtemp()
    try:
        audio_path = os.path.join(temp_dir, audio_file.filename)
        lyrics_path = os.path.join(temp_dir, lyrics_file.filename)
        audio_file.save(audio_path)
        lyrics_file.save(lyrics_path)

        # Download the models and dictionaries
        subprocess.run(
            ["mfa", "model", "download", "acoustic", "english_us_arpa"],
            check=True
        )
        subprocess.run(
            ["mfa", "model", "download", "dictionary", "english_us_arpa"],
        check=True
        )

        # Validate the corpus
        validation_result = subprocess.run(
            ["mfa", "validate", "/data/MFA/corpus",
            "english_us_arpa", "english_us_arpa"],
            capture_output=True, text=True, check=True
        )

        if validation_result.returncode != 0:
            return jsonify({'error': f"Corpus validation failed: {validation_result.stderr}"}), 500

        # Perform alignment, set output format to JSON
        alignment_result = subprocess.run(
            ["mfa", "align",
             "--output_format", "json",
             audio_path, lyrics_path,
            "english_us_arpa", "english_us_arpa", "aligned"],
            cwd=temp_dir, capture_output=True, text=True, check=False
        )

        # If alignment fails on intial attempt, increase beam size
        # Solves failed alingment for most songs
        if alignment_result.returncode != 0:
            print("Retry alignment ...")
            retry_result = subprocess.run(
                ["mfa", "align",
                 "--output_format", "json",
                 audio_path, lyrics_path,
                "english_us_arpa", "english_us_arpa", "aligned",
                "--beam", "100", "--retry_beam", "400"],
                cwd=temp_dir, capture_output=True, text=True, check=True
            )

            if retry_result.returncode != 0:
                return jsonify({'error': f"Alignment failed: {retry_result.stderr}"}), 500
            alignment_result = retry_result

        # Parses JSON string data into Python dictionary
        # Then into a JSON response
        try:
            alignment_json = json.loads(alignment_result.stdout)
            return jsonify(alignment_json)
        except json.JSONDecodeError:
            return jsonify({'error': "Failed to decode alignment JSON output."}), 500

    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        return jsonify({'error': error_message}), 500
    except FileNotFoundError as e:
        return jsonify({'error': f"File not found: {e}"}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e: # pylint: disable=broad-except
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=24725)
