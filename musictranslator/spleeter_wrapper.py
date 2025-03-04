from flask import Flask, request, jsonify
import subprocess
import os
import base64

app = Flask(__name__)

@app.route('/split', methods=['POST'])
def split():
    audio_file = request.files['audio']
    if not audio_file:
        return jsonify({'error': 'No audio file provided'}), 400
    audio_file.save("input_audio.wav")
    try:
        subprocess.run([
            'spleeter', 'separate',
            '-p', 'spleeter:4stems-16kHz',
            '-o', '.',
            "input_audio.wav"
        ])
        results = {}
        for stem in ["vocal", "accompaniment", "drums", "bass"]:
            with open(f"input_audio/{stem}.wav", "rb") as f:
                results[stem] = base64.b64encode(f.read()).decode()
            subprocess.run(['rm', 'input_audio'])
            return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.remove("input_audio.wav")

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')
