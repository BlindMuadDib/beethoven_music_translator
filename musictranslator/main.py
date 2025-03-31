"""
This module implements a Flask web application for audio processing and lyrics alignment

It provides one endpoint for splitting audio files using Spleeter,
aligned lyrics with audio usig Montreal Forced Aligner,
and generating synchronized transcripts
After validating audio and lyrics are valid files
"""

import os
import subprocess
import tempfile
import magic
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from musictranslator.musicprocessing.align import align_lyrics
from musictranslator.musicprocessing.separate import split_audio
from musictranslator.musicprocessing.map_transcript import process_transcript, sync_alignment_json_with_transcript_lines

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

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

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file, \
            tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_lyrics:

            # Save the files with secure names
            audio_path = temp_audio_file.name
            lyrics_path = temp_lyrics.name
            audio_file.save(audio_path)
            lyrics_file.save(lyrics_path)

            # Validate the files
            if not validate_audio(audio_path):
                return jsonify({'error': 'Invalid audio file.'}), 400

            if not validate_text(lyrics_path):
                return jsonify({'error': 'Invalid lyrics file.'}), 400

            # Calls the split_audio function from musictranslator.musicprocessing.separate
            vocals_stem_path = split_audio(audio_path)

            if isinstance(vocals_stem_path, dict) and "error" in vocals_stem_path:
                return jsonify(vocals_stem_path), 500

            # Call the align_lyrics function from musictranslator.musicprocessing.align
            alignment_result = align_lyrics(
                vocals_stem_path['vocals_stem_path'], lyrics_path)

            if isinstance(alignment_result, dict) and "error" in alignment_result:
                return jsonify(alignment_result), 500

            # Map the TextGrid to JSON for front-end simplicity
            transcript_lines = process_transcript(lyrics_path)
            mapped_result = sync_alignment_json_with_transcript_lines(alignment_result, transcript_lines)

            if not mapped_result:
                return jsonify({"error": "Map Error"}), 500

            return jsonify(mapped_result), 200

    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error during translation: {e}")
        return jsonify({"error": "Internal server error."}), 500

    finally:
        try:
            os.remove(audio_path)
            os.remove(lyrics_path)
        except NameError:
            pass
        except OSError:
            pass

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
