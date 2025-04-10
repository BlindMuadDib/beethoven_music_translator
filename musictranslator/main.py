"""
This module implements a Flask web application for audio processing and lyrics alignment

It provides one endpoint for splitting audio files using Demucs,
Another endpoint for aligned lyrics with audio using Montreal Forced Aligner,
and generating synchronized transcripts
After validating audio and lyrics are valid files
"""

import os
import shutil
import subprocess
import tempfile
import magic
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from musictranslator.musicprocessing.align import align_lyrics
from musictranslator.musicprocessing.separate import split_audio
from musictranslator.musicprocessing.map_transcript import process_transcript, map_transcript

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Determine the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def validate_audio(file_path):
    """
    Validates an audio file using ffmpeg and magic

    Args:
        filepath (str): The path to the audio file

    Returns:
        bool: True if the audio is valid, False otherwise.
    """
    try:
        magic_type = magic.from_file(file_path, mime=True)
        if not magic_type.startswith("audio/"):
            return False

        subprocess.run(['ffmpeg', '-i', file_path, '-f', 'null', '-'],
                       capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error validating audio: ffmpeg returned non-zero exit code: {e}")
        return False
    except FileNotFoundError as e:
        print(f"Error validating audio: ffmpeg not found: {e}")
        return False
    except magic.MagicException as e:
        print(f"Error validating audio: magic error: {e}")
        return False
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error validating audio: {e}")
        return False

def validate_text(file_path):
    """
    Validates a text file using magic

    Args:
        file_path (str): The path to the text file

    Returns:
        bool: True if the text file is valie, False otherwise
    """
    try:
        file_type = magic.from_file(file_path, mime=True)
        return file_type == 'text/plain'
    except FileNotFoundError as e:
        print(f"Error validating text: File not found: {e}")
        return False
    except magic.MagicException as e:
        print(f"Error validating text: magic error: {e}")
        return False
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error validating text: {e}")
        return False

@app.route('/translate', methods=['POST'])
def translate():
    """
    Handles audio and lyrics translation requests

    Args:
        audio file and lyrics file

    Returns:
        Alignment json of song and lyrics or error
    """
    if 'audio' not in request.files:
        return jsonify({"error": "Missing audio file."}), 400

    if 'lyrics' not in request.files:
        return jsonify({"error": "Missing lyrics file."}), 400

    audio_file = request.files['audio']
    lyrics_file = request.files['lyrics']

    # Sanitize filenames
    audio_filename = secure_filename(audio_file.filename)
    lyrics_filename = secure_filename(lyrics_file.filename)

    if not audio_filename or not lyrics_filename:
        return jsonify({"error": "Invalid filename"}), 400

    temp_audio_dir = None
    temp_lyrics_file = None
    alignment_json_path = None

    try:
        temp_audio_dir = tempfile.mkdtemp()
        temp_audio_path = os.path.join(temp_audio_dir, audio_filename)
        temp_lyrics_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        lyrics_path = temp_lyrics_file.name

        audio_file.save(temp_audio_path)
        lyrics_file.save(lyrics_path)

        # Validate the files
        if not validate_audio(temp_audio_path):
            return jsonify({'error': 'Invalid audio file.'}), 400

        if not validate_text(lyrics_path):
            return jsonify({'error': 'Invalid lyrics file.'}), 400

        # Calls the split_audio function from musictranslator.musicprocessing.separate
        separate_result = split_audio(temp_audio_path)

        if isinstance(separate_result, dict) and "error" in separate_result:
            return jsonify(separate_result), 500

        vocals_stem_path = separate_result.get('vocals')
        if not vocals_stem_path:
            return jsonify({"error": "Error during audio separation: Vocals track not found."}), 500

        # Call the align_lyrics function from musictranslator.musicprocessing.align
        align_result = align_lyrics(
            vocals_stem_path, lyrics_path)

        if isinstance(align_result, dict) and "error" in align_result:
            return jsonify(align_result), 500

        # Map the alignment_result to the lyrics transcript with
        # musictranslator.musicprocessing.map_transcript
        alignment_json_path = align_result
        mapped_result = map_transcript(alignment_json_path, process_transcript(lyrics_path))

        if not mapped_result:
            return jsonify({"error": "Failed to map alignment to transcript."}), 500

        return jsonify(mapped_result), 200

    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error during translation: {e}")
        return jsonify({"error": "Internal server error."}), 500

    finally:
        if temp_audio_dir:
            try:
                shutil.rmtree(temp_audio_dir)
            except OSError:
                pass
        if temp_lyrics_file:
            try:
                os.remove(lyrics_path)
            except OSError:
                pass
        if alignment_json_path and os.path.exists(alignment_json_path):
            try:
                os.remove(alignment_json_path)
            except OSError:
                pass

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(host='0.0.0.0', port=20005, debug=True)
