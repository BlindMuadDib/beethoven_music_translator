from flask import Flask, request, jsonify
import subprocess
import os

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
        #Move the generated files to the desired output names.
        subprocess.run(['mv', f'input_audio/vocals.wav', "vocals.wav"])
        subprocess.run(['mv', f'input_audio/accompaniment.wav', "accompaniment.wav"])
        subprocess.run(['mv', f'input_audio/drums.wav', "drums.wav"])
        subprocess.run(['mv', f'input_audio/bass.wav', "bass.wav"])
        subprocess.run(['rm', '-rf', 'input_audio']) # remove the folder created by spleeter.

        return jsonify({'message': 'Audio split successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.remove("input_audio.wav")

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')
