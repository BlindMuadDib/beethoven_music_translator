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
import magic
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from musictranslator.musicprocessing.align import align_lyrics
from musictranslator.musicprocessing.separate import split_audio
from musictranslator.musicprocessing.transcribe import process_transcript, map_transcript

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

@app.route('/', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({"status": "OK", "message": "Music Translator is running"}), 200

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

    audio_file_path = os.path.join('/shared-data/audio', audio_filename)
    lyrics_path = os.path.join('/shared-data/lyrics', lyrics_filename)
    alignment_json_path = None

    try:
        # Save files to the shared volume
        audio_file.save(audio_file_path)
        lyrics_file.save(lyrics_path)

        # Validate the files
        if not validate_audio(audio_file_path):
            os.remove(audio_file_path)
            os.remove(lyrics_path)
            return jsonify({'error': 'Invalid audio file.'}), 400

        if not validate_text(lyrics_path):
            os.remove(audio_file_path)
            os.remove(lyrics_path)
            return jsonify({'error': 'Invalid lyrics file.'}), 400
        app.logger.info("DEBUG - audio and lyrics saved and validated.")
        app.logger.info(f"Audio: {audio_file_path}, Lyrics: {lyrics_path}")

        # Calls the split_audio function
        # from musictranslator.musicprocessing.separate
        separate_result = split_audio(audio_file_path)
        app.logger.info(f"DEBUG - Separate Result: {separate_result}")

        if isinstance(separate_result, dict) and "error" in separate_result:
            app.logger.info("DEBUG - Demucs error detected")
            return jsonify(separate_result), 500

        vocals_stem_path = separate_result.get('vocals')
        app.logger.info(f"DEBUG - Vocals Stem Path: {vocals_stem_path}")
        if not vocals_stem_path:
            app.logger.info("DEBUG - Vocals track not found")
            return jsonify({"error": "Error during audio separation: Vocals track not found."}), 500

        # Call the align_lyrics function from musictranslator.musicprocessing.align
        # Only if the audio separation was successful
        if vocals_stem_path:
            app.logger.info("DEBUG - Proceeding to align_lyrics")
            align_result = align_lyrics(vocals_stem_path, lyrics_path)
            app.logger.info(f"DEBUG - Received align_result: {align_result}")

            if isinstance(align_result, dict) and "error" in align_result:
                app.logger.info("DEBUG - MFA error detected")
                return jsonify(align_result), 500

        # Map the alignment_result to the lyrics transcript with
        # musictranslator.musicprocessing.transcribe
        alignment_json_path = align_result
        app.logger.info(f"DEBUG - alignment json path = {alignment_json_path}")
        mapped_result = map_transcript(alignment_json_path, lyrics_path)
        app.logger.info(f"Mapped result determined: {mapped_result}")

        if not mapped_result:
            return jsonify({"error": "Failed to map alignment to transcript."}), 500

        return jsonify(mapped_result), 200

    except Exception as e: # pylint: disable=broad-exception-caught
        app.logger.info(f"Error during translation: {e}")
        return jsonify({"error": "Internal server error."}), 500

    finally:
        if os.path.exists(audio_file_path):
            try:
                shutil.rmtree(audio_file_path)
            except OSError:
                pass
        if os.path.exists(lyrics_path):
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
    app.run(debug=True, host='0.0.0.0', port=20005)
