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
import logging
import uuid
import magic
import threading
import time
import redis
import rq
from rq import Queue, get_current_job
from rq.job import Job
from flask import Flask, request, jsonify, g, send_from_directory
from werkzeug.utils import secure_filename
from musictranslator.musicprocessing.align import align_lyrics
from musictranslator.musicprocessing.separate import split_audio
from musictranslator.musicprocessing.transcribe import map_transcript
from musictranslator.musicprocessing.F0 import request_f0_analysis

app = Flask(__name__)

# Define the directory where uploaded/processed files are stored for serving
SERVE_AUDIO_DIR = '/shared-data/audio'

# Store valid access codes

VALID_ACCESS_CODES = set([''])

# --- Lazy Redis Connection and Queue  ---

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis-service')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

def get_redis_connection():
    """Gets a Redis connection, storing it in Flask's g object for reuse within a request"""
    # Check if connection already exists in the current request context
    if 'redis_conn' not in g:
        app.logger.info("Creating new Redis connection for this context.")
        try:
            # Add connection timeout
            g.redis_conn = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                socket_connect_timeout=5
            )
            g.redis_conn.ping # Verify connection
        except redis.exceptions.ConnectionError as e:
            app.logger.error("Failed to establish Redis connection in get_redis_connection: %s", e)
            g.redis_conn = None
    return g.redis_conn

def get_translation_queue():
    """Gets the RQ Queue, ensuring Redis connection is attempted."""
    conn = get_redis_connection()
    if conn:
        # RQ Queue might need to be cached differently if 'g' is request-specific
        # For simplicity here, we create it on demand using the available connection
        # Consider caching the Queue instance outside 'g' if perfomance is critical
        # and ensuring the connection is valid when used.
        try:
            queue = Queue("translations", connection=conn)
            return queue
        except Exception as e:
            app.logger.error("Failed to create RQ Queue: %s", e)
            return None

@app.teardown_appcontext
def teardown_redis(exception=None):
    """Closes the Redis connection at the end of the request."""
    conn = g.pop('redis_conn', None)
    if conn is not None:
        app.logger.info("Closing Redis connection for this context.")
        try:
            # Adjust close method based on redis-py version
            if hasattr(conn, 'close'):
                conn.close()
            elif hasattr(conn, 'disconnect'):
                conn.disconnect()
            elif hasattr(conn, 'connection_pool'):
                conn.connection_pool.disconnect()
        except Exception as e:
            app.logger.warning("Error closing Redis connection: %s", e)

# --- End RQ Setup ---

# --- Define the Background Task ---

def background_translation_task(unique_audio_path, unique_lyrics_path, unique_audio_filename, original_audio_filename):
    """
    This function runs in the background worker.
    It performs audio separation, alignment, and transcription mapping.
    Args:
        unique_audio_path (str): Path to the uniquely named uploaded audio file.
        unique_lyrics_path (str): Path to the uniquely named uploaded lyrics file.
        unique_audio_filename (str): The filename after sanitized with uuid
        original_audio_filename (str): The audio filename the user uploaded
    Returns:
        dict: The final mapped_result JSON.
    Raises:
        Exception: If any step fails, allowing RQ to mark the job as failed.
    """
    alignment_json_path = None
    vocals_stem_path = None
    f0_analysis_result = None
    separate_cleanup_path = None
    job = get_current_job()

    logger = logging.getLogger("rq.worker")
    logger.setLevel(logging.INFO)

    try:
        logger.info(
            "Starting background task for audio: %s, lyrics: %s",
            unique_audio_path,
            unique_lyrics_path,
        )
        if job: job.meta['progress_stage'] = 'starting'; job.save_meta()

        # --- 1. Separate Audio ---
        logger.info("Step 1: Splitting audio ...")
        if job:
            job.meta['progress_stage'] = 'separating_audio'
            job.save_meta()
        separate_result = split_audio(unique_audio_path)
        logger.info("DEBUG - Separate Result: %s", separate_result)

        if isinstance(separate_result, dict) and "error" in separate_result:
            logger.error("Demucs error: %s", separate_result['error'])
            raise Exception(f"Audio separation failed: {separate_result['error']}")

        vocals_stem_path = separate_result.get('vocals')
        if not vocals_stem_path or not os.path.exists(vocals_stem_path):
            logger.error("Vocals track not found after separation.")
            raise Exception("Error during audio separation: Vocals track not found.")

        # Determine the common directory for cleanup
        first_stem_path = next(iter(separate_result.values()), None)
        if first_stem_path and isinstance(first_stem_path, str):
            separate_cleanup_path = os.path.dirname(first_stem_path)
        logger.info("Step 1 Complete. Vocals Stem Path: %s. Cleanup path: %s", vocals_stem_path, separate_cleanup_path)

        # --- 2. Concurrent F0 Analysis and Lyrics Alignment ---
        logger.info("Step 2: Starting concurrent F0 analysis and Lyrics Alignment ...")
        if job:
            job.meta['progress_stage'] = 'stem_processing'
            job.save_meta()

        thread_results_shared = {
            "alignment_json_path": None,
            "f0_analysis_data": None,
            "alignment_error": None,
            "f0_error": None
        }

        def _align_lyrics_task():
            try:
                logger.info("Align-Thread: Starting lyrics alignment for vocals '%s' and lyrics '%s'.", vocals_stem_path, unique_lyrics_path)
                result = align_lyrics(vocals_stem_path, unique_lyrics_path)
                if isinstance(result, dict) and "error" in result:
                    thread_results_shared["alignment_error"] = result["error"]
                    logger.error("Align-Thread: MFA error = %s", result['error'])
                elif not result or (isinstance(result, str) and not os.path.exists(result)):
                    err_msg = f"Alignment result path invalid or not found: {result}"
                    thread_results_shared["alignment_error"] = err_msg
                    logger.error("Align-Thread: %s", err_msg)
                else:
                    thread_results_shared["alignment_json_path"] = result
                    logger.info("Align-Thread: Alignment successful. Path: %s", result)
            except Exception as e:
                logger.error("Align-Thread: Exception - %s", e, exc_info=True)
                thread_results_shared["alignment_error"] = str(e)

        def _f0_analysis_task():
            try:
                logger.info("F0-Thread: Starting F0 analysis for stems: %s", list(separate_result.keys()))
                # `separate_result` is the dict of paths from `split_audio`
                result = request_f0_analysis(separate_result)
                if isinstance(result, dict) and "error" in result:
                    thread_results_shared["f0_error"] = result["error"]
                    logger.error(f"F0-Thread: F0 service error - %s", result["error"])
                elif not isinstance(result, dict):
                    err_msg = f"F0 analysis returned unexpected data type: {type(result)}"
                    thread_results_shared["f0_error"] = err_msg
                    logger.error("F0-Thread: %s", err_msg)
                else:
                    thread_results_shared["f0_analysis_data"] = result
                    logger.info("F0-Thread: F0 analysis successful. Instruments processed: %s", list(result.keys()))
            except Exception as e:
                logger.error("F0-Thread: Exception - %s", e, exc_info=True)
                thread_results_shared["f0_error"] = str(e)

        align_thread = threading.Thread(target=_align_lyrics_task, name="AlignLyricsThread")
        f0_thread = threading.Thread(target=_f0_analysis_task, name="F0AnalysisThread")

        align_thread.start()
        f0_thread.start()

        # Wait for both services to complete
        align_thread.join()
        f0_thread.join()

        logger.info("Concurrent processing finished. Checking results ...")

        # Process alignment results (critical path)
        if thread_results_shared["alignment_error"]:
            err_msg = f"Lyrics alignment failed: {thread_results_shared['alignment_error']}"
            logger.error(err_msg)
            raise Exception(err_msg)
        alignment_json_path = thread_results_shared["alignment_json_path"]
        logger.info("Step 2.1 (Alignment) Complete. Path: %s", alignment_json_path)

        # Process F0 results
        if thread_results_shared["f0_error"]:
            logger.warning(f"F0 analysis encountered an error: %s. Proceeding without F0 data.",
                           thread_results_shared['f0_error'])
            f0_analysis_result = {
                "error": thread_results_shared["f0_error"],
                "info": "F0 analysis did not complete successfully."
            }
        f0_analysis_result = thread_results_shared["f0_analysis_data"]
        logger.info("Step 2.2 (F0 Analysis) Complete.")

        # --- 3. Map Transcript and Combine Results ---
        logger.info("Step 3: Mapping transcript and combining results ...")
        if job:
            job.meta['progress_stage'] = 'mapping_transcript'
            job.save_meta()
        mapped_result = map_transcript(alignment_json_path, unique_lyrics_path)
        logger.info("Mapped result determined: %s", mapped_result)

        if not mapped_result:
            logger.error("Failed to map alignment to transcript.")
            raise Exception("Failed to map alignment to transcript.")

        # Final combined result structure
        final_job_result = {
            "mapped_result": mapped_result,
            "f0_analysis": f0_analysis_result if f0_analysis_result else None,
            "audio_url": f"api/files/{unique_audio_filename}",
            "original_filename": original_audio_filename
        }
        logger.info("Background task completed successfully. Final result structure prepared.")

        if job and job.connection:
            cleanup_queue = Queue('cleanup_files', connection=job.connection)
            cleanup_queue.enqueue(
                'musictranslator.main.cleanup_files',
                lyrics_path=unique_lyrics_path,
                alignment_path=alignment_json_path,
                separate_path=separate_cleanup_path
            )
        else:
            logger.error("Could not get job or Redis connection in background task for cleanup")
        return final_job_result

    except Exception as e:
        logger.error(
            "Error during background task: %s",
            e, exc_info=True
        )
        if job:
            job.meta['failure_reason'] = f"Task failed: {e}"
            job.save_meta()
        raise

# --- End Background Task Definition ---

def validate_access():
    """Validate access based on an access code"""
    access_code = request.args.get('access_code') or request.headers.get('X-Access-Code')
    app.logger.info("DEBUG - Attempting access with code: '%s", access_code)
    app.logger.info("DEBUG - Valid access codes: %s", VALID_ACCESS_CODES)
    if access_code and access_code in VALID_ACCESS_CODES:
        app.logger.info("DEBUG - Access granted.")
        return True
    app.logger.info("DEBUG - Access denied.")
    return False

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
        app.logger.error("Error validating audio: ffmpeg returned non-zero exit code: %s", e)
        return False
    except FileNotFoundError as e:
        app.logger.error("Error validating audio: ffmpeg not found: %s", e)
        return False
    except magic.MagicException as e:
        app.logger.error("Error validating audio: magic error: %s,", e)
        return False
    except Exception as e: # pylint: disable=broad-exception-caught
        app.logger.error("Error validating audio: %s", e)
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
        app.logger.error("Error validating text: File not found: %s", e)
        return False
    except magic.MagicException as e:
        app.logger.error("Error validating text: magic error: %s", e)
        return False
    except Exception as e: # pylint: disable=broad-exception-caught
        app.logger.error("Error validating text: %s", e)
        return False

@app.route('/api/translate/health', methods=['GET'])
def health_check():
    """Health check endpoint using live test"""
    conn = get_redis_connection() # This attempts connection
    redis_live_ok = False
    if conn:
        try:
            conn.ping() # Ping the connection obtained/created by get_redis_connection
            redis_live_ok = True
        except redis.exceptions.ConnectionError:
            redis_live_ok = False # Connection obtained but ping failed
        # Note: teardown_redis will handle closing

    status_code = 200 if redis_live_ok else 503
    return jsonify({
        "status": "OK" if redis_live_ok else "Error",
        "message": "Music Translator is running",
        "redis_health_check": "connected" if redis_live_ok else "disconnected (live test)"
    }), status_code

@app.route('/api/translate', methods=['POST'])
def translate():
    """
    Handles audio and lyrics translation requests
    Enqueues a background job for processing
    Args:
        audio file and lyrics file
    Returns:
        Alignment json of song and lyrics with f0 analysis for each stem or error
    """
    app.logger.info("DEBUG - Received translation request. Attempting Redis connection ... ")
    # --- Get Queue (which implicitly checks/gets Redis connection) ---
    translation_queue = get_translation_queue()
    if not translation_queue:
        app.logger.error("Translate request failed: Redis queue not available.")
        return jsonify({
            "error": "Translation service temporarily unavailable. Please try again later."
        }), 503

    # --- Access Validation ---
    access_code = request.args.get('access_code') or request.headers.get('X-Access-Code')
    app.logger.info("DEBUG - Attempting access with code: '%s'", access_code)
    if not access_code or access_code not in VALID_ACCESS_CODES:
        app.logger.info("DEBUG - Access denied.")
        return jsonify({"error": "Access Denied. Please provide a valid access code."}), 401
    app.logger.info("DEBUG - Access granted")

    # --- File Handling & Validation ---
    if 'audio' not in request.files or 'lyrics' not in request.files:
        return jsonify({"error": "Missing audio or lyrics file."}), 400

    audio_file = request.files['audio']
    lyrics_file = request.files['lyrics']

    # Sanitize filenames
    original_audio_filename = secure_filename(audio_file.filename)
    original_lyrics_filename = secure_filename(lyrics_file.filename)

    if not original_audio_filename or not original_lyrics_filename:
        return jsonify({"error": "Invalid filename"}), 400

    # Generate unique filenames to prevent conflicts
    job_id = str(uuid.uuid4())
    unique_audio_filename = f"{job_id}_{original_audio_filename}"
    unique_lyrics_filename = f"{job_id}_{original_lyrics_filename}"

    unique_audio_path = os.path.join('/shared-data/audio', unique_audio_filename)
    unique_lyrics_path = os.path.join('/shared-data/lyrics', unique_lyrics_filename)

    try:
        # Save files to the shared volume
        audio_file.save(unique_audio_path)
        lyrics_file.save(unique_lyrics_path)
        app.logger.info("Saved files: %s, %s", unique_audio_path, unique_lyrics_path)

        # Validate the files
        if not validate_audio(unique_audio_path):
            os.remove(unique_audio_path)
            os.remove(unique_lyrics_path)
            return jsonify({'error': 'Invalid audio file.'}), 400

        if not validate_text(unique_lyrics_path):
            os.remove(unique_audio_path)
            os.remove(unique_lyrics_path)
            return jsonify({'error': 'Invalid lyrics file.'}), 400
        app.logger.info("DEBUG - audio and lyrics saved and validated.")
        app.logger.info("Audio: %s, Lyrics: %s", unique_audio_path, unique_lyrics_path)

        # --- Enqueue Background Job ---
        try:
            job = translation_queue.enqueue(
                'musictranslator.main.background_translation_task',
                args=(unique_audio_path, unique_lyrics_path, unique_audio_filename, original_audio_filename),
                job_id=job_id,
                job_timeout=5000
            )
            app.logger.info("Enqueued job %s", job.id)

            # --- Return Job ID to CLient ---
            return jsonify({"job_id": job.id}), 202
        except Exception as e:
            app.logger.error("Error during job enqueue (type %s): %s", type(e).__name__, e, exc_info=True)
            return jsonify({"error": "Internal server error processing request"}), 503
    except Exception as e:
        app.logger.error("Error during file validation or saving: %s", e)
        if unique_audio_path and os.path.exists(unique_audio_path):
            os.remove(unique_audio_path)
        if unique_lyrics_path and os.path.exists(unique_lyrics_path):
            os.remove(unique_lyrics_path)
        return jsonify({"error": "Internal server error processing request."}), 500

@app.route('/api/results/<job_id>', methods=['GET'])
def get_results(job_id):
    """Check the job status"""
    app.logger.info("Received request for results for job_id: %s", job_id)
    try:
        redis_conn = get_redis_connection()
        if not redis_conn: # Check if connection itself failed
            app.logger.error("Redis connection unavailable in get_results for job %s.", job_id)
            return jsonify({
                "status": "error",
                "message": "Error communicating with Redis."
            }), 503

        job = Job.fetch(job_id, connection=redis_conn)

        if job.is_finished:
            result = job.result
            app.logger.info("Job %s finished. Result: %s", job_id, result)
            if isinstance(result, dict):
                return jsonify({"status": "finished", "result": result}), 200
            app.logger.error("Job %s finished with unexpected result format: %s", job_id, result)
            # If result is not a list, it might be an error object from the task
            # Consider how to handle this - perhaps return 500 if it's not the expected list
            # For now, let's assume if it's not a list, it's an issue
            return jsonify({
                "status": "failed",
                "message": "Job finished with unexpected result type."
            }), 500

        elif job.is_failed:
            app.logger.error("Job %s failed: %s", job_id, job.exc_info)
            return jsonify({"status": "failed", "message": str(job.exc_info)}), 500
        else:
            response_data = {"status": job.get_status()}
            if job.meta and 'progress_stage' in job.meta:
                response_data['progress_stage'] = job.meta['progress_stage']
            return jsonify(response_data), 202

    except rq.exceptions.NoSuchJobError:
        app.logger.warning("Job ID %s not found in Redis.", job_id)
        return jsonify({
            "status": "error",
            "message": "Job ID not found or invalid."
        }), 404
    except redis.exceptions.ConnectionError as e:
        app.logger.error(
            "Redis connection error in get_result for job %s: %s",
            job_id, e
        )
        return jsonify({
            "status": "error",
            "message": "Error communicating with Redis."
        }), 503
    except Exception as e:
        app.logger.error(
            "Unexpected error fetching or processing job %s: %s",
            job_id, e
        )
        return jsonify({
            "status": "error",
            "message": "Internal server error checking job status."
        }), 500

@app.route('/api/files/<path:unique_audio_filename>')
def serve_file(unique_audio_filename):
    """Serves a file from the SERVE_AUDIO_DIR."""
    app.logger.info(f"Attempting to serve file: {unique_audio_filename} from {SERVE_AUDIO_DIR}")
    try:
        return send_from_directory(SERVE_AUDIO_DIR, unique_audio_filename, as_attachment=False)
    except FileNotFoundError:
        app.logger.error(f"File not found: {unique_audio_filename} in {SERVE_AUDIO_DIR}")
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        app.logger.error(f"Error serving file {unique_audio_filename}: {e}")
        return jsonify({"error": "Error serving file"}), 500

@app.route('/api/cleanup/<string:filename>', methods=['DELETE'])
def delete_audio_file(filename):
    """
    Securely deletes a single processed audio file from the shared volume.
    """
    # Security: Sanitize the filename to prevent directory traversal attacks.
    # secure_filename ensures the path is flat and safe.
    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename:
        return jsonify({"error": "Invalid filename provided"}), 400

    file_path = os.path.join('/shared-data/audio', safe_filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            app.logger.info(f"Client-triggered cleanup: Deleted {file_path}")
            return jsonify({"message": f"Successfully deleted {safe_filename}"}), 200
        except OSError as e:
            app.logger.error({f"Error deleting file {file_path}: {e}"})
            return jsonify({"error": "Failed to delete file on server"}), 500
    else:
        # It's okay if the file is already gone, return success.
        app.logger.warning(f"Client requested cleanup for non-existent file: {file_path}")
        return jsonify({"message": "File not found, but request is considered complete"}), 200

def cleanup_files(lyrics_path, alignment_path, separate_path):
    """Cleanup files after final result is determined and sent to frontend"""
    app.logger.info(
        "Cleaning up files: lyrics - %s, alignment - %s, stems - %s",
        lyrics_path,
        alignment_path, separate_path
    )
    if lyrics_path and os.path.exists(lyrics_path):
        os.remove(lyrics_path)
        app.logger.info("Deleted: %s", lyrics_path)
    if alignment_path and os.path.exists(alignment_path):
        os.remove(alignment_path)
        app.logger.info("Deleted: %s", alignment_path)
    if separate_path and os.path.exists(separate_path):
        shutil.rmtree(separate_path)
        app.logger.info(f"Deleted: %s", separate_path)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=20005, debug=True)
