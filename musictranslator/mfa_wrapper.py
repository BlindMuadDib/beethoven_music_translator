from flask import Flask, request, jsonify
import subprocess
import os
import tempfile
impot shutil

app = Flask(__name__)

@app.route('/align', methods=['POST'])
def align():
    audio_file = request.files['audio']
    lyrics_file = request.files['lyrics']
    if not audio_file or not lyrics_file:
        return jsonify({'error': 'Audio or lyrics file missing'}), 400

    temp_dir = tempfile.mkdtemp()
    try:
        audio_path = os.path.join(temp_dir, os.path.basename(audio_file.filename))
        lyrics_path = os.path.join(temp_dir, os.path.basename(lyrics_file.filename))
        audio_file.save(audio_path)
        lyrics_file.save(lyrics_path)

        # Download the models and dictionaries
        subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath('./music')}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "model", "download", "acoustic", "english_us_arpa",
            "mfa", "model", "download", "dictionary", "english_us_arpa"
        ])

        # Validate the corpus
        Validation_result = subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath('./music')}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "validate", f"/data/MFA/corpus",
            "english_us_arpa", "english_us_arpa"
            ], capture_output=True, text=True)

        if validation_result.returncode != 0:
            return jsonify({f"[ERROR]Corpus validation failed: {validation_result.stderr}"})

        # Perform alignment
        alignment_result = subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath('./music')}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "align", f"/data/MFA/corpus}",
            "english_us_arpa", "english_us_arpa", f"/data/MFA/output"
            ], capture_output=True, text=True)

        # If alignment fails on intial attempt, increase beam size
        # Solves failed alingment for most songs
        if alignment_result.returncode != 0:
            retry_result = subprocess.run([
                "docker", "run", "--rm", "-v",
                f"{os.path.abspath('./music')}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest"
                "mfa", "align", f"/data/MFA/corpus}",
                "english_us_arpa", "english_us_arpa", f"/data/MFA/output",
                "--beam", "100", "--retry_beam", "400"
                ], capture_output=True, text=True)

            if retry_result.returncode != 0:
                return jsonify({'error': f"Alignmnet failed: {retry_result.stderr}"}), 500

        return jsonify({'message': 'Alignment successful'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        shutil.rmtree(temp_dir)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')
