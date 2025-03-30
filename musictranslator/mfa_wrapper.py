"""
Wrapper for official Docker image for Kubernetes to run specific codes
"""
import subprocess
import os
import tempfile
import shutil
import textgrid
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

        # Perform alignment
        alignment_result = subprocess.run(
            ["mfa", "align", audio_path, lyrics_path,
            "english_us_arpa", "english_us_arpa", "aligned"],
            cwd=temp_dir, capture_output=True, text=True, check=False
        )

        # If alignment fails on intial attempt, increase beam size
        # Solves failed alingment for most songs
        if alignment_result.returncode != 0:
            retry_result = subprocess.run(
                ["mfa", "align", audio_path, lyrics_path,
                "english_us_arpa", "english_us_arpa", "aligned",
                "--beam", "100", "--retry_beam", "400"],
                cwd=temp_dir, capture_output=True, text=True, check=True
            )

            if retry_result.returncode != 0:
                return jsonify({'error': f"Alignment failed: {retry_result.stderr}"}), 500
            retry_result = alignment_result

        textgrid_path = os.path.join(temp_dir, 'aligned', 'aligned.TextGrid')
        tg = textgrid.TextGrid.fromFile(textgrid_path)
        words_tier = tg.getFirst('words')
        if not words_tier:
            return jsonify({"error": "The 'words' tier is missing from the TextGrid"}), 500

        alignment_data = {
            "tier_name": words_tier.name,
            "intervals": [
                {
                    "xmin": interval.minTime,
                    "xmax": interval.maxTime,
                    "word": interval.mark
                }
                for interval in words_tier.intervals
            ]
        }
        return jsonify(alignment_data), 200

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
