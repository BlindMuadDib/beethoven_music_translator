from flask import Flask, request, jsonify
from music_processing.transcript_mapping import create_synchronized_transcript_json
import os
import requests
import base64
import magic
import re
import subprocess

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

@app.route('/split', methods=['POST'])
def split():
    audio_file = requests.files['audio']
    song_name = request.form.get('song')

    if audio_file:
        audio_file.save("input_audio.wav")
        input_audio = "input_audio.wav"
    elif song_name:
        input_audio = os.path.join(AUDIO_DIR, f"{song_name}.wav")
    else:
        return jsonify({'error': 'No audio file provided'}), 400

    try:
        response =requests.post(SPLEETER_SERVICE_URL, files=files)
        response.raise_for_status()
        results = response.json()
        output_dir = os.path.join(SPLEETER_OUTPUT_DIR, song_name) if song_name else "temp_spleeter_output"
        os.makedirs(output_dir, exist_ok=True)
        for stem, data in results.items():
            with open(os.path.join(output_dir, f"{stem}.wav"), "wb") as f:
                f.write(base64decode(data))
        return jsonify({'message': 'Audio split successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if audio_file:
            os.remove("input_audio.wav") #remove temp file

@app.route('/align', methods=['POST'])
def align():
    lyrics_file = request.files['lyrics']
    song_name = request.form.get('song')

    if lyrics_file:
        lyrics_file.save("input_lyrics.txt")
        input_lyrics = "input_lyrics.txt"
    elif song_name:
        input_lyrics = os.path.join(LYRICS_DIR, f"{song_name}.txt")
    else:
        return jsonify({'error': 'No lyrics file provided'}), 400

    try:
        response = requests.pst(MFA_SERVICE_URL, files=files)
        response.raise_for_status()
        alignment_data = response.json()
        output_file = os.path.join(MFA_OUTPUT_DIR, f"{song_name}.json") if song_name else "aligned_output.txt"
        with open(output_file, 'w') as f:
            json.dump(alignment_data, f, indent=4)
        return jsonify({'message': 'Lyrics aligned successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if lyrics_file:
            os.remove("input_lyrics.txt")

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

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    audio_file = request.files['audio']
    artist = request.form.get('artist')
    song = request.form.get('song')

    if not audio_file or not artist or not song:
        return jsonify({'error': 'Missing file or metadata'}), 400

    file_type = magic.from_buffer(audio_file.read(2048), mime=True)
    audio_file.seek(0)

    if file_type != 'audio/wav':
        return jsonify({'error': 'Invalid file type'}), 400

    temp_filepath = "temp_audio.wav"
    audio_file.save(temp_filepath)

    if not validate_audio(temp_filepath):
        os.remove(temp_filepath)
        return jsonify({'error': 'Invalid audio file'}), 400

    filename = f"{artist}_{song}.wav"
    audio_file.save(os.path.join(AUDIO_DIR, filename))
    os.remove(temp_filepath)

    return jsonify({'message': 'Audio uploaded successfully'})

@app.route('/upload_lyrics', methods=['POST'])
def upload_lyrics():
    lyrics_file = request.files['lyrics']
    artist = request.form.get('artist')
    song = request.form.get('song')

    if not lyrics_file or not artist or not song:
        return jsonify({'error': 'Missing file or metadata'}), 400

    file_type = megic.from_buffer(lyrics_file.read(2048), mime=True)
    lyrics_file.seek(0)

    if file_type != 'text/plain':
        return jsonify({'error': 'Invalid file type'}), 400

    lyrics_content = lyrics_file.read().decode('utf-8')

    if not re.match(r'^[a-zA-Z0-9\s\n.,!?]+$', lyrics_content):
        return jsonify({'error': 'Invalid lyrics content'}), 400

    filename = f"{artist}_{song}.txt"
    lyrics_file.save(os.path.join(LYRICS_DIR, filename))

    return jsonify({'message': 'Lyrics uploaded successfully'})

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1')
