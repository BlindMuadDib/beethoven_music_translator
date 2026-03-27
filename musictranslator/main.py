"""
This module implements a Flask web application for audio processing and lyrics alignment

It provides one endpoint for splitting audio files using Demucs,
Another endpoint for aligned lyrics with audio using Montreal Forced Aligner,
and generating synchronized transcripts
After validating audio and lyrics are valid files
"""

import os
import io
import zipfile
import json
import shutil
import subprocess
import logging
import uuid
import threading
import time
import magic
import requests
import redis
import rq
from urllib.parse import urlencode, urlparse
from rq import Queue, get_current_job
from rq.job import Job
from flask import Flask, request, jsonify, g, send_from_directory, make_response, send_file
from werkzeug.utils import secure_filename
from musictranslator.musicprocessing.align import align_lyrics
from musictranslator.musicprocessing.separate import split_audio
from musictranslator.musicprocessing.transcribe import map_transcript
from musictranslator.musicprocessing.harmonic import request_harmonic_analysis
from musictranslator.musicprocessing.drums import request_drum_analysis

app = Flask(__name__)

# Define the directory where uploaded/processed files are stored for serving
SERVE_AUDIO_DIR = '/shared-data/audio'
RESULTS_DIR = '/shared-data/results'

AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth-service')
DATA_VERSION = "0.1.4"

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
            g.redis_conn.ping() # Verify connection
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

# --- VALIDATE ACCESS HELPER FUNCTION ---
def is_session_valid(session_cookie):
    """
    Validates a session by forwarding the cookie to the auth service.
    """
    if not session_cookie:
        return False
    try:
        url = f"{AUTH_SERVICE_URL}/internal/validate-session"
        app.logger.info(f"Validating session against: {url}")
        # Forward the user's session cookie to the auth service
        cookies = {'session': session_cookie}
        response = requests.get(url, cookies=cookies, timeout=5)

        if response.status_code == 200:
            data = response.json()
            return data.get("valid", False)

        app.logger.error(f"Auth service returned non-200 status for session validation: {response.status_code}")
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Could not connect to auth service for session validation: {e}")
        return False

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
    harmonic_analysis_result = None
    drum_analysis_result = None
    separate_cleanup_path = None
    job = get_current_job()

    logger = logging.getLogger("rq.worker")
    logger.setLevel(logging.INFO)

    try:
        job_id = job.id if job else str(uuid.uuid4())
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
        drums_stem_path = separate_result.get('drums')

        if not vocals_stem_path or not os.path.exists(vocals_stem_path):
            logger.error("Vocals track not found after separation.")
            raise Exception("Error during audio separation: Vocals track not found.")

        # Determine the common directory for cleanup
        first_stem_path = next(iter(separate_result.values()), None)
        if first_stem_path and isinstance(first_stem_path, str):
            separate_cleanup_path = os.path.dirname(first_stem_path)
        logger.info("Step 1 Complete. Vocals Stem Path: %s. Cleanup path: %s", vocals_stem_path, separate_cleanup_path)

        # --- 2. Concurrent Harmonic, Volume & Drum Analysis and Lyrics Alignment ---
        logger.info("Step 2: Starting concurrent Harmonic, and Percussive instrument analysis, and Lyrics Alignment ...")
        if job:
            job.meta['progress_stage'] = 'stem_processing'
            job.save_meta()

        thread_results_shared = {
            "alignment_json_path": None, "alignment_error": None,
            "harmonic_analysis_urls": None, "harmonic_error": None,
            "drum_analysis_data": None, "drum_error": None,
            "mfa_job_dir": None
        }

        def _align_lyrics_task():
            # Skip alignment if no lyrics were provided (Instrumental)
            if not unique_lyrics_path:
                logger.info("Align-Thread: No lyrics path provided (Instrumental). Skipping alignment.")
                return

            try:
                logger.info("Align-Thread: Starting lyrics alignment for vocals '%s' and lyrics '%s'.", vocals_stem_path, unique_lyrics_path)

                result = align_lyrics(vocals_stem_path, unique_lyrics_path)

                if isinstance(result, dict) and "error" in result:
                    thread_results_shared["alignment_error"] = result["error"]
                    logger.error("Align-Thread: MFA error = %s", result['error'])

                elif not result or 'alignment_file_path' not in result or 'job_dir_path' not in result:
                    err_msg = f"Alignment result path invalid or missing keys: {result}"
                    thread_results_shared['alignment_error'] = err_msg
                    logger.error("Align-Thread: %s", err_msg)

                elif not os.path.exists(result['alignment_file_path']):
                    err_msg = f"Alignment result path invalid or not found: {result}"
                    thread_results_shared["alignment_error"] = err_msg
                    logger.error("Align-Thread: %s", err_msg)

                else:
                    thread_results_shared["alignment_json_path"] = result['alignment_file_path']
                    # Save the cleanup dir
                    thread_results_shared["mfa_job_dir"] = result['job_dir_path']
                    logger.info("Align-Thread: Alignment successful. Path: %s", result['alignment_file_path'])
            except Exception as e:
                logger.error("Align-Thread: Exception - %s", e, exc_info=True)
                thread_results_shared["alignment_error"] = str(e)

        def _harmonic_analysis_task():
            try:
                logger.info(
                    "Harmonic-Thread: Starting Harmonic analysis for stems: %s, full track: %s",
                    list(separate_result.keys()),
                    unique_audio_path
                )
                # Initiate the analysis. This now returns a dict with
                # 'results_url'
                initial_response = request_harmonic_analysis(
                    separate_result,
                    unique_audio_path
                )

                if isinstance(initial_response, dict) and "error" in initial_response:
                    thread_results_shared["harmonic_error"] = initial_response["error"]
                    logger.error(
                        "Harmonic-Thread: Harmonic service error - %s",
                        initial_response["error"]
                    )
                    return

                if isinstance(initial_response, dict) and "info" in initial_response:
                    # Case where no relevant stems were sent
                    thread_results_shared["harmonic_analysis_data"] = initial_response
                    logger.info("Harmonic-Thread: %s", initial_response["info"])
                    return

                static_results_url = initial_response.get("results_url")
                if not static_results_url:
                    err_msg = f"Harmonic service did not return a results_url. Response: {initial_response}"
                    thread_results_shared["harmonic_error"] = err_msg
                    logger.error("Harmonic-Thread: %s",
                                 err_msg)
                    return

                # Poll for the results file on the shared volume
                static_results_filename = os.path.basename(static_results_url)
                # The results are saved in a different subdirectory on the
                # shared volume
                expected_file_path = os.path.join('/shared-data/results',
                                                  static_results_filename)
                logger.info("Harmonic-Thread: Polling for results file at %s",
                            expected_file_path)

                # Poll for up to 20 minutes (1200 seconds)
                file_found = False
                for _ in range(1200):
                    if os.path.exists(expected_file_path):
                        logger.info("Harmonic-Thread: Found results file. Passing file to final results.")
                        file_found = True
                        break
                    time.sleep(1)

                if file_found:
                    streaming_urls = {}
                    try:
                        with open(expected_file_path, 'r') as f:
                            harmonic_data = json.load(f)

                        stem_analyses = harmonic_data.get("stem_analyses", {})
                        for stem_name, stem_path in separate_result.items():
                            # Check if this stem was successfully analyzed (has a non-error entry)
                            if stem_name in stem_analyses and stem_analyses[stem_name] and "error" not in stem_analyses[stem_name]:
                                query_params = urlencode({"stem_path": stem_path})
                                stream_filename = f"{job_id}_{stem_name}.ndjson"
                                streaming_urls[stem_name] = f"api/harmonic/stream/{stream_filename}?{query_params}"
                        logger.info(
                            "Harmonic-Thread: Successfully generated streaming URLs for: %s",
                            list(streaming_urls.keys())
                        )
                    except (json.JSONDecodeError, IOError) as e:
                        logger.error(
                            "Harmonic-Thread: Failed to read or parse static results file %s: %s",
                            expected_file_path, e
                        )
                        # Continue without streaming URLs, but log the problem

                    final_url_static = f"api/results/file/{static_results_filename}"
                    thread_results_shared["harmonic_analysis_urls"] = {
                        "static_results_url": final_url_static,
                        "streaming_urls": streaming_urls
                    }
                    logger.info(
                        "Harmonic-Thread: Harmonic analysis complete. Static URL: %s",
                        final_url_static
                    )
                else:
                    err_msg = f"Timed out waiting for harmonic analysis results file: {expected_file_path}"
                    thread_results_shared["harmonic_error"] = err_msg
                    logger.error("Harmonic-Thread: %s", err_msg)

            except Exception as e:
                logger.error("Harmonic-Thread: Exception - %s",
                             e, exc_info=True)
                thread_results_shared["harmonic_error"] = str(e)

        def _drum_analysis_task():
            # Only run if a drums stem was actually produced by Demucs
            if not drums_stem_path or not os.path.exists(drums_stem_path):
                logger.info("Drum-Thread: No drums stem available for analysis. Skipping.")
                thread_results_shared["drum_analysis_data"] = {"info": "No drums stem available."}
                return
            try:
                logger.info("Drum-Thread: Starting drum analysis for stem: %s", drums_stem_path)
                result = request_drum_analysis(drums_stem_path)
                if isinstance(result, dict) and "error" in result:
                    thread_results_shared["drum_error"] = result["error"]
                    logger.error(f"Drum-Thread: Drum service error - %s", result["error"])
                elif isinstance(result, dict) and "hits" in result:
                    thread_results_shared["drum_analysis_data"] = result
                    logger.info("Drum-Thread: Drum analysis successful")
                else:
                    err_msg = f"Drum analysis returned unexpected data type: {type(result)}"
                    thread_results_shared["drum_error"] = err_msg
                    logger.error("Drum-Thread: %s", err_msg)
            except Exception as e:
                logger.error("Drum-Thread: Exception - %s", e, exc_info=True)
                thread_results_shared["drum_error"] = str(e)

        align_thread = threading.Thread(target=_align_lyrics_task, name="AlignLyricsThread")
        harmonic_thread = threading.Thread(target=_harmonic_analysis_task, name="HarmonicAnalysisThread")
        drums_thread = threading.Thread(target=_drum_analysis_task, name="DrumAnalysisThread")

        # Only start align_thread if there is work to do
        if unique_lyrics_path:
            align_thread.start()
        harmonic_thread.start()
        drums_thread.start()

        # Wait for services to complete
        if unique_lyrics_path:
            align_thread.join()
        harmonic_thread.join()
        drums_thread.join()

        logger.info("Concurrent processing finished. Checking results ...")

        # Process alignment results
        if thread_results_shared["alignment_error"]:
            err_msg = f"Lyrics alignment failed: {thread_results_shared['alignment_error']}"
            logger.error(err_msg)
            raise Exception(err_msg)
        alignment_json_path = thread_results_shared["alignment_json_path"]
        if alignment_json_path:
            logger.info("Step 2.1 (Alignment) Complete. Path: %s",
                        alignment_json_path)
        else:
            logger.info("Step 2.1 (Alignment) Skipped (Instrumental).")

        # Process Harmonic results
        if thread_results_shared["harmonic_error"]:
            logger.warning(f"Harmonic analysis encountered an error: %s. Proceeding without Harmonic data.",
                           thread_results_shared['harmonic_error'])
            harmonic_analysis_result = {
                "error": thread_results_shared["harmonic_error"],
                "info": "Harmonic analysis did not complete successfully."
            }
        else:
            harmonic_analysis_result = thread_results_shared["harmonic_analysis_urls"]
        logger.info("Step 2.2 (Harmonic Analysis) Complete.")

        # Process Drum Results
        if thread_results_shared["drum_error"]:
            logger.warning(
                "Drum analysis encountered an error: %s. Proceeding without drum data.",
                thread_results_shared["drum_error"]
                )
            drum_analysis_result = {
                "error": thread_results_shared["drum_error"],
                "info": "Drum analysis did not complete successfully."
            }
        else:
            drum_analysis_result = thread_results_shared["drum_analysis_data"]
        logger.info("Step 2.4 (Drum Analysis) Complete.")

        # --- 3. Map Transcript and Combine Results ---
        logger.info("Step 3: Mapping transcript and combining results ...")
        if job:
            job.meta['progress_stage'] = 'mapping_transcript'
            job.save_meta()

        if unique_lyrics_path and alignment_json_path:
            mapped_result = map_transcript(alignment_json_path,
                                           unique_lyrics_path)
            logger.info("Mapped result determined: %s", mapped_result)
        else:
            mapped_result = [] # Instrumental tracks have no mapped text
            logger.info("No lyrics to map. Returning empty mapped_result.")

        if mapped_result is None: # Explicitly check for None
            logger.error("Failed to map alignment to transcript.")
            raise Exception("Failed to map alignment to transcript.")

        # Final combined result structure
        final_job_result = {
            "mapped_result": mapped_result,
            "harmonic_analysis": harmonic_analysis_result,
            "drum_analysis": drum_analysis_result if drum_analysis_result else None,
            "audio_url": f"api/files/{unique_audio_filename}",
            "original_filename": original_audio_filename
        }
        logger.info("Background task completed successfully. Final result structure prepared.")

        if job and job.connection:
            cleanup_queue = Queue('cleanup_files', connection=job.connection)

            mfa_job_path = thread_results_shared.get("mfa_job_dir")

            cleanup_queue.enqueue(
                'musictranslator.main.cleanup_files',
                lyrics_path=unique_lyrics_path,
                alignment_path=alignment_json_path,
                separate_path=separate_cleanup_path,
                mfa_job_path=mfa_job_path
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

@app.route('/api/library', methods=['GET'])
def get_library():
    """Returns a list of available Creative Commons songs from predefined metadata."""
    metadata_path = '/shared-data/metadata.json'
    if not os.path.exists(metadata_path):
        app.logger.warning(f"Library metadata not found: {metadata_path}")
        return jsonify([]), 200
        
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            
        cc_songs = [s for s in metadata if s.get('license') == 'Creative Commons']
        cc_songs.sort(key=lambda x: (x.get('artist', '').lower(), x.get('title', '').lower()))
        
        for song in cc_songs:
            prefix = song.get('filename_prefix', '')
            if prefix:
                song['mtr_url'] = f"/api/library/file/{prefix}.mtr"
                song['audio_url'] = f"/api/files/{prefix}.wav"
                
        return jsonify(cc_songs), 200
    except Exception as e:
        app.logger.error(f"Error reading library metadata: {e}")
        return jsonify({"error": "Failed to load library data"}), 500

@app.route('/api/library/file/<filename>', methods=['GET'])
def get_library_file(filename):
    """Serves a translation archive (.mtr) file from the library."""
    translated_dir = '/shared-data/translated'
    return send_from_directory(translated_dir, filename, as_attachment=False)

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
    app.logger.info("DEBUG - Received translation request. Headers: %s, Attempting Redis connection ... ",
                    request.headers)
    # --- Get Queue (which implicitly checks/gets Redis connection) ---
    translation_queue = get_translation_queue()
    if not translation_queue:
        app.logger.error("Translate request failed: Redis queue not available.")
        return jsonify({
            "error": "Translation service temporarily unavailable. Please try again later."
        }), 503

    # --- Access Validation ---
    is_authorized = False
    # Check for a valid session cookie
    session_cookie = request.cookies.get('session')

    app.logger.info("Attempting authorization...")
    if session_cookie:
        app.logger.info("DEBUG - Session cookie found, attempting validation.")
        if is_session_valid(session_cookie):
            is_authorized = True
            app.logger.info("DEBUG - Access granted via session.")

    if not is_authorized:
        app.logger.info("DEBUG - Access denied. Please log in.")

        # Consume the rest of the request's body before returning.
        # This prevents an IncompleteRead error on the client when it's
        # still uploading a large file.
        request.stream.read()

        return jsonify({"error": "Access Denied. Please log in."}), 401

    app.logger.info("Authorization successul. Handling file upload...")

    # --- File Handling & Validation ---
    if 'audio' not in request.files:
        return jsonify({"error": "Missing audio file."}), 400

    audio_file = request.files['audio'] # Audio is required
    lyrics_file = request.files.get('lyrics') # Lyrics are optional

    # Sanitize filenames
    original_audio_filename = secure_filename(audio_file.filename)
    if not original_audio_filename:
        return jsonify({"error": "Invalid audio filename"}), 400

    # Generate unique filenames to prevent conflicts
    job_id = str(uuid.uuid4())
    unique_audio_filename = f"{job_id}_{original_audio_filename}"
    unique_audio_path = os.path.join('/shared-data/audio', unique_audio_filename)

    # Handle optional lyrics
    unique_lyrics_path = None
    unique_lyrics_filename = None
    if lyrics_file:
        original_lyrics_filename = secure_filename(lyrics_file.filename)
        if original_lyrics_filename:
            unique_lyrics_filename = f"{job_id}_{original_lyrics_filename}"
            unique_lyrics_path = os.path.join('/shared-data/lyrics',
                                              unique_lyrics_filename)

    try:
        # Save audio to the shared volume and validate
        audio_file.save(unique_audio_path)
        app.logger.info("Saved audio: %s", unique_audio_path)

        if not validate_audio(unique_audio_path):
            os.remove(unique_audio_path)
            os.remove(unique_lyrics_path)
            return jsonify({'error': 'Invalid audio file.'}), 400

        # Save lyrics to the shared volume if provided, then validate
        if unique_lyrics_path:
            lyrics_file.save(unique_lyrics_path)
            app.logger.info("Saved lyrics: %s", unique_lyrics_path)
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

@app.route('/api/download-mtr/<job_id>', methods=['GET'])
def download_mtr(job_id):
    """
    Generates and serves a .mtr (zip) file containing all translation data
    for a specific job. Bypasses external audio references and packages
    streams locally. Includes 'version' and 'generated_at' metadata.
    """
    app.logger.info("Received request to download .mtr for job_id: %s",
                    job_id)

    # --- Authentication Check ---
    session_cookie = request.cookies.get('session')
    if not session_cookie or not is_session_valid(session_cookie):
        app.logger.warning("Access denied for .mtr download: Invalid session.")
        return jsonify({"error": "Access Denied. Please log in."}), 401

    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            return jsonify({"error": "Database unavailable."}), 503

        job = Job.fetch(job_id, connection=redis_conn)

        if not job.is_finished or not job.result:
            return jsonify({"error": "Job not finished or has no results."}), 404

        original_result = job.result

        # Create an in-memory zip file
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:

            # 1. Prepare modified result.json
            mtr_result = original_result.copy()
            # Explicitly exclude the audio URL (user provides audio locally)
            mtr_result['audio_url'] = None

            # Inject Version and Metadata
            mtr_result['version'] = DATA_VERSION
            mtr_result['generated_at'] = time.time()

            # Log check for core components (DRUM and HARMONIC data)
            # They are carried over by copy(), but verifying here for logging
            # purposes
            if 'drum_analysis' in mtr_result and 'hits' in mtr_result['drum_analysis']:
                app.logger.info("Packing drum_analysis with %s hits",
                                len(mtr_result['drum_analysis']['hits']))

            # Adjust harmonic analysis paths to be relative within the zip
            harmonic_info = mtr_result.get('harmonic_analysis', {})
            harmonic_static_path_in_zip = "harmonic_static.json"

            # Check if static_results_url exists
            static_url = harmonic_info.get('static_results_url')
            static_file_path = None

            if static_url:
                # URL is usually "api/results/file/filename.json"
                # Be robust: check if it's a URL or just a filename
                parsed_url = urlparse(static_url)
                static_filename = os.path.basename(parsed_url.path)
                static_file_path = os.path.join(RESULTS_DIR,
                                                static_filename)
                app.logger.info("Looking for static harmonic file at: %s",
                                static_file_path)
            else:
                # Fallback: Construct filename from job_id
                fallback_filename = f"{job_id}_harmonic.json"
                static_file_path = os.path.join(RESULTS_DIR,
                                                fallback_filename)
                app.logger.warning("No static_results_url found. Trying fallback path: %s",
                                   static_file_path)

            # Verify existence before adding to zip
            if static_file_path and os.path.exists(static_file_path):
                try:
                    with open(static_file_path, 'rb') as f:
                        zf.writestr(harmonic_static_path_in_zip,
                                    f.read())
                    # Update the pointer in result.json
                    harmonic_info['static_results_url'] = harmonic_static_path_in_zip
                except Exception as e:
                    app.logger.error("Error reading static harmonic file: %s",
                                     e)
                    return jsonify({"error": "Failed to read static harmonic data."}), 500
            else:
                app.logger.error("Critical error: Static harmonic file not found at %s", static_file_path)
                # Don't generate a broken zip
                return jsonify({"error": "Harmonic analysis data missing on server."}), 500

            new_streaming_urls = {}

            # 2. Handle Harmonic Data (Static and Streams)
            if 'harmonic_analysis' in original_result and isinstance(original_result['harmonic_analysis'], dict):
                orig_harmonic = original_result['harmonic_analysis']

                # B. Fetch and Add NDJSON Streams
                # Original URLs are like "api/harmonic/stream/{job_id}_{stem}.ndjson?stem_path=..."
                if 'streaming_urls' in orig_harmonic:
                    for stem_name, stream_url, in orig_harmonic['streaming_urls'].items():
                        # Extract the filename from the URL
                        # Expected format: .../{filename}?query_params
                        parsed_url = urlparse(stream_url)
                        stream_filename = os.path.basename(parsed_url.path)

                        # Assume the stream file is generated/stored in
                        # RESULTS_DIR or a subdir. Based on the current
                        # architecture, check RESULTS_DIR first
                        possible_paths = [
                            os.path.join(RESULTS_DIR, stream_filename),
                            os.path.join(RESULTS_DIR, 'streams',
                                         stream_filename)
                        ]

                        stream_data = None
                        for path in possible_paths:
                            if os.path.exists(path):
                                try:
                                    with open(path, 'rb') as f:
                                        stream_data = f.read()
                                    break
                                except Exception:
                                    continue

                        # Update the result.json to point to the internal zip path
                        zip_stream_path = f"streams/{stem_name}.ndjson"
                        new_streaming_urls[stem_name] = zip_stream_path

                        if stream_data:
                            zf.writestr(zip_stream_path, stream_data)
                        else:
                            # Fallback: if file isn't on disk, try to fetch it
                            # from the app itself. This covers cases where the
                            # stream is generated dynamically
                            # Note: This uses 127.0.0.1:20005 assuming the app
                            # calls itself
                            try:
                                app.logger.info("Stream file not found on disk for %s, attempting loopback fetch",
                                                stem_name)
                                # construct loopback URL. stream_url is relative "api/..."
                                loopback_url = f"http://127.0.0.1:20005/{stream_url}"
                                # Pass the session cookie for auth
                                cookies = {'session': session_cookie}
                                resp = requests.get(loopback_url,
                                                    cookies=cookies,
                                                    timeout=10)
                                if resp.status_code == 200:
                                    zf.writestr(zip_stream_path, resp.content)
                                else:
                                    app.logger.warning("Failed to fetch stream %s via loopback: %s",
                                                       stem_name,
                                                       resp.status_code)
                            except Exception as e:
                                app.logger.error("Error fetching stream via loopback: %s",
                                                 e)
                harmonic_info['streaming_urls'] = new_streaming_urls

            # Write the modified result.json
            zf.writestr('result.json', json.dumps(mtr_result, indent=2))

        memory_file.seek(0)

        filename = f"{original_result.get('original_filename', 'translation').split('.')[0]}.mtr"

        return send_file(
            memory_file,
            download_name=filename,
            as_attachment=True,
            mimetype='application/zip'
        )

    except rq.exceptions.NoSuchJobError:
        return jsonify({"error": "Job not found."}), 404
    except Exception as e:
        app.logger.error("Error generating .mtr file: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error generating file."}), 500

@app.route('/api/files/<path:unique_audio_filename>')
def serve_audio_file(unique_audio_filename):
    """Serves a file from the SERVE_AUDIO_DIR."""
    app.logger.info(f"Attempting to serve file: {unique_audio_filename} from {SERVE_AUDIO_DIR}")
    try:
        return send_from_directory(SERVE_AUDIO_DIR, unique_audio_filename, as_attachment=False)
    except FileNotFoundError:
        app.logger.error(f"Audio file not found: {unique_audio_filename} in {SERVE_AUDIO_DIR}")
        return jsonify({"error": "Audio file not found"}), 404
    except Exception as e:
        app.logger.error(f"Error serving audio file {unique_audio_filename}: {e}")
        return jsonify({"error": "Error serving audio file"}), 500

@app.route('/api/results/file/<path:filename>')
def serve_results_file(filename):
    """
    Serves a results file {e.g., harmonic analysis JSON} from the results
    directory.
    """
    results_dir = '/shared-data/results'
    app.logger.info("Attempting to serve results file: %s from %s",
                    filename, results_dir)
    try:
        # Use send_from_directory for security and proper header handling
        return send_from_directory(results_dir, filename,
                                    as_attachment=False)
    except FileNotFoundError:
        app.logger.error("Results file not found: %s in %s",
                         filename, results_dir)
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        app.logger.error("Error serving results file %s: %s",
                         filename, e)
        return jsonify({"error": "Error serving file"}), 500


@app.route('/api/cleanup/<string:filename>', methods=['DELETE'])
def delete_audio_file(filename):
    """
    Securely deletes a single processed audio file and its corresponding
    harmonic analysis results from the shared volume.
    """
    # Security: Sanitize the filename to prevent directory traversal attacks.
    # secure_filename ensures the path is flat and safe.
    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename:
        return jsonify({"error": "Invalid filename provided"}), 400

    # --- Delete Harmonic Analysis Results ---
    # The job_id is the part of the filename before the first underscore
    if '_' in safe_filename:
        job_id = safe_filename.split('_')[0]
        harmonic_results_filename = f"{job_id}_harmonic.json"
        harmonic_results_path = os.path.join('/shared-data/results',
                                             harmonic_results_filename)

        if os.path.exists(harmonic_results_path):
            try:
                os.remove(harmonic_results_path)
                app.logger.info("Client-triggered cleanup: Deleted harmonic results %s",
                                harmonic_results_path)
            except OSError as e:
                # Log the error but don't fail the request, as the main audio
                # file might still be deletable
                app.logger.error("Error deleting harmonic results file %s: %s",
                                 harmonic_results_path, e)

    # --- Delete Main Audio File ---
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

def cleanup_files(lyrics_path, alignment_path, separate_path, mfa_job_path=None):
    """Cleanup files after final result is determined and sent to frontend"""
    app.logger.info(
        "Cleaning up files: lyrics - %s, alignment - %s, stems - %s, mfa_job - %s",
        lyrics_path,
        alignment_path, separate_path, mfa_job_path
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
    if mfa_job_path and os.path.exists(mfa_job_path):
        shutil.rmtree(mfa_job_path)
        app.logger.info(f"Deleted MFA job directory: %s", mfa_job_path)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=20005, debug=True)
