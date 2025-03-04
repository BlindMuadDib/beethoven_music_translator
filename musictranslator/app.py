from flask import Flask, request, jsonify
from music_processing.transcript_mapping import create_synchronized_transcript_json
import os
import requests

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
        output_dir = os.path.join(SPLEETER_OUTPUT_DIR, song_name) if song_name else "temp_spleeter_output"
        os.makedirs(output_dir, exist_ok=True)
        split_audio(input_audio, os.path.join(output_dir, "vocals.wav"), os.path.join(output_dir, "accompaniment.wav"), os.path.join(output_dir, "drums.wav"), os.path.join(output_dir, "bass.wav"))
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
        output_file = os.path.join(MFA_OUTPUT_DIR, f"{song_name}.json") if song_name else "aligned_output.txt"
        align_lyrics(os.path.join(SPLEETER_OUTPUT_DIR, song_name, "vocals.wav"), input_lyrics, output_file, DATA_DIR, 'MFA', 'output')
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

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1')
