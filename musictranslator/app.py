from flask import Flask, request, jsonify
import os
import requests
import json
import base64
import tempfile
import shutil
import magic
import re
import subprocess
from music_processing.spleeter_service import split_audio
from music_processing.mfa_service import align_lyrics
from music_processing.transcript_mapping import create_synchronized_transcript_json

app = Flask(__name__)

# Directory paths
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(DATA_DIR, 'music')
AUDIO_DIR = os.path.join(MUSIC_DIR, 'audio')
LYRICS_DIR = os.path.join(MUSIC_DIR, 'lyrics')
MFA_DIR = os.path.join(MUSIC_DIR, 'MFA')
MFA_CORPUS_DIR = os.path.join(MFA_DIR, 'corpus')
MFA_ALIGNED_DIR = os.path.join(MFA_DIR, 'corpus_aligned')
MFA_OUTPUT_DIR = os.path.join(MFA_DIR, 'output')
SPLEETER_OUTPUT_DIR = os.path.join(MUSIC_DIR, 'spleeter_output')

SPLEETER_SERVICE_URL = "http://spleeter-service:24725/split"
MFA_SERVICE_URL = "http://mfa-service:24725/align"

def validate_audio(filepath):
    try:
        result = subprocess.run(['ffmpeg', '-i', filepath, '-f', 'null', '-'],
                                capture_output=True, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error validating audio: {e}")
        return False

@app.route('/split', methods=['POST'])
def split():
    audio_file = requests.files['audio']
    song_name = request.form.get('song')

    if not audio_file and not song_name:
        return jsonify({'error': 'No audio file or song selected'}), 400

    temp_audio = None

    if audio_file:
        file_type = magic.from_buffer(audio_file.read(2048), mime=True)
        audio_file.seek(0)
        if file_type != 'audio/wav':
            return jsonify({'error': 'Invalid file type'}), 400

        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_file.save(temp_audio.name)

        if not validate_audio(temp_audio.name):
            os.remove(temp_audio.name)
            return jsonify({'error': 'Invalid audio file'}), 400

    else:
        input_audio = os.path.join(AUDIO_DIR, f"{song_name}.wav")
        if not os.path.exists(input_audio):
            return jsonify({'error': 'Song not found in corpus'}), 400
        temp_audio = open(input_audio, 'rb')

    try:
        if temp_audio:
            if audio_file:
                with open(temp_audio.name, 'rb') as audio_file_obj:
                    files = {'audio': audio_file_obj}
                    response =requests.post(SPLEETER_SERVICE_URL, files=files)
                    response.raise_for_status()
                    results = response.json()
                    output_dir = os.path.join(SPLEETER_OUTPUT_DIR, song_name) if song_name else "temp_spleeter_output"
                    os.makedirs(output_dir, exist_ok=True)
                    for stem, data in results.items():
                        with open(os.path.join(output_dir, f"{stem}.wav"), "wb") as f:
                            f.write(base64decode(data))
                    for  stem in results:
                        shutil.copy(os.path.join(temp_dir, f"{stem}.wav"), os.path.join(SPLEETER_OUTPUT_DIR, f"{stem}.wav"))
                    shutil.rmtree(temp_dir)
            else:
                with temp_audio as audio_file_obj:
                    files = {'audio': audio_file_obj}
                    response =requests.post(SPLEETER_SERVICE_URL, files=files)
                    response.raise_for_status()
                    results = response.json()
                    output_dir = os.path.join(SPLEETER_OUTPUT_DIR, song_name) if song_name else "temp_spleeter_output"
                    os.makedirs(output_dir, exist_ok=True)
                    for stem, data in results.items():
                        with open(os.path.join(output_dir, f"{stem}.wav"), "wb") as f:
                            f.write(base64decode(data))
                    for stem in results:
                        shutil.copy(os.path.join(temp_dir, f"{stem}.wav"))
                    shutil.rmtree(temp_dir)
        return jsonify({'message': 'Audio split successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_audio and audio_file:
            os.remove(temp_audio.name) #remove temp file

@app.route('/align', methods=['POST'])
def align():
    audio_file = request.files.get('audio')
    lyrics_file = request.files['lyrics']
    song_name = request.form.get('song')

    if (not audio_file or not lyrics_file) and not song_name:
        return jsonify({'error': 'Audio, lyrics, or song selection missing'}), 400

    temp_audio = None
    temp_lyrics = None

    if audio_file and lyrics_file: # User uploaded files
        audio_file_type = magic.from_buffer(audio_file.read(2048), mime=True)
        audio_file.seek(0)
        lyrics_file_type = magic.from_buffer(lyrics_file.read(2048), mime=True)
        lyrics_file.seek(0)

        if audio_file_type != 'audio/wav' or lyrics_file_type != 'text/plain':
            return jsonify({'error': 'Invalid file type'}), 400

        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_file.save(temp_audio.name)

        if not validate_audio(temp_audio.name):
            os.remove(temp_audio.name)
            return jsonify({'error': 'Invalid audio file'}), 400

        temp_lyrics = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        lyrics_file.save(temp_lyrics.name)
    else: # User selected song from corpus
        input_audio = os.join(AUDIO_DIR, f"{song_name}.wav")
        input_lyrics = os.path.join(LYRICS_DIR, f"{song_name}.txt")
        if not os.path.exists(input_audio) or not os.path.exists(input_lyrics):
            return jsonify({'error': 'Song not found in corpus'}), 404
        temp_audio = open(input_audio, 'rb')
        temp_lyrics = open(input_lyrics, 'rb')

    try:
        files = {'audio': temp_audio, 'lyrics': temp_lyrics}
        response = requests.post(MFA_SERVICE_URL, files=files)
        response.raise_for_status()
        alignment_data = response.json()
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        with open(output_file.name, 'w') as f:
            json.dump(alignment_data, f, indent=4)
        shutil.copy(output_file.name, os.path.join(MFA_OUTPUT_DIR, os.path.basename(output_file.name)))
        return jsonify({'message': 'Lyrics aligned successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if isinstance(temp_audio, tempfile._TemporaryFileWrapper):
            os.remove(temp_aaudio.name)
        else:
            temp_audio.close()
        if isinstance(temp_lyrics, tempfile._TemporaryFileWrapper):
            os.remove(temp_lyrics.name)
        else:
            temp_lyrics.close()
        if 'output_file' in locals():
            os.remove(output_file.name)

@app.route('/translate', methods=['POST'])
def translate():
    song_name = reqest.form.get('song')

    if not song_name:
        return jsonify({'error': 'No song selected'}), 400

    output_file - os.path.join(MFA_OUTPUT_DIR, f"{song_name}.json")

    try:
        with open(output_file, 'r') as f:
            mfa_data = json.load(f)
        return jsonify(mfa_data)
    except FileNotFoundError:
        return jsonify({'error': 'MFA output file not found'}), 400
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid MFA output file format'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/synchronized_transcript', methods=['POST'])
def generate_synchronized_transcript():
    song_name = request.gorm.get('song')

    if not song_name:
        return jsonify({'error': 'No song selected'}), 400

    lyrics_file = os.path.join(LYRICS_DIR, f"{song_name}.txt")
    textgrid_file = os.path.join(MFA_ALIGNED_DIR, f"{song_name}.TextGrid")
    output_json_file = os.path.join(MFA_OUTPUT_DIR, f"{song_name}_synchronized_transcript.json")

    if not os.path.exists(lyrics_file) or not os.path.exists(textgrid_file):
        return jsonify({'error': 'Lyrics or TextGrid file not found'}), 404

    if create_synchronized_transcript_json(lyrics_file, alignment_json_file, output_json_file):
        try:
            with open(output_json_file, 'r') as f:
                transcript_data = json.load(f)
            return jsonify(transcript_data)
        except Exception as e:
            return jsonify({'error': f"Error reading transcript JSON: {e}"}), 500
    else:
        return jsonify({'error': 'Failed to generate synchronized transcript'}), 500

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1')
