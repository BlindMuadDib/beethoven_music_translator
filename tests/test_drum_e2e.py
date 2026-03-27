import os
import shutil
import io
import json
import time
import threading
import pathlib
import requests
import pytest
import numpy as np
import podman
from podman.errors.exceptions import NotFound

# --- Configuration ---
IMAGE_NAME = "drums_endpoint_test"
DOCKERFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "drums-endpoint.Dockerfile")
CONTAINER_PORT = 25941
HOST_PORT = 25941
HEALTH_CHECK_URL = f"http://127.0.0.1:{HOST_PORT}/drums/health"
ANALYZE_DRUMS_URL = f"http://127.0.0.1:{HOST_PORT}/api/analyze_drums"

# Simulate the PVC path inside the container and on the host for E2E testing
# For the test, we'll acreate a temp dir on the host to act as the PVC mount.
PVC_MOUNT_HOST_BASE = pathlib.Path("/tmp/musictranslator_e2e_test_pvc")
CONTAINER_PVC_MOUNT_BASE = "/shared-data"

# Real drum track's relative path within the *simulated* PVC structure
# This mirrors: /shared-data/separator_output/htdemucs_6s/BloodCalcification-NoMore/drums.wav
# So, the host path for the test will be: /tmp/musictranslator_e2e_test_pvc/separator_output/.../drums.wav
# And the container path will be: /shared-data/separator_output/.../drums.wav
REAL_DRUM_TRACK_RELATIVE_PATH = pathlib.Path(
    "separator_output", "htdemucs_6s", "BloodCalcification-NoMore", "drums.wav"
)
REAL_DRUM_TRACK_HOST_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "separator_output", "htdemucs_6s", "BloodCalcification-NoMore", "drums.wav"
)
# This will be the actual path for the file *inside the container* during the test
CONTAINER_DRUM_TRACK_PATH = str(pathlib.Path(CONTAINER_PVC_MOUNT_BASE) / REAL_DRUM_TRACK_RELATIVE_PATH)

# --- Podman Client Fixture ---
@pytest.fixture(scope="module")
def podman_client():
    """Provides a podan client instance."""
    try:
        # Use systemd service for podman if available
        uid = os.getuid()
        client = podman.PodmanClient(base_url=f"unix:///run/user/{uid}/podman/podman.sock")
        client.ping()
        print(f"\nPodman client connected via systemd socket: unix:///run/user/{uid}/podman/podman.sock")
        yield client
    except Exception as e:
        pytest.fail(f"\nCould not connect to podman via systemd socket: {e}")
    finally:
        if 'client' in locals() and client:
            client.close()

# --- Shared Data Setup Fixture ---
@pytest.fixture(scope="module")
def setup_shared_data():
    """
    Creates a temporary directory on the host to simulate the PVC
    mount point and copies the necessary audio file into it,
    mirroring the expected K8s structure.
    """
    PVC_MOUNT_HOST_BASE.mkdir(parents=True, exist_ok=True)

    # Create the target directory inside the simulated PVC mount point
    target_dir_on_host = PVC_MOUNT_HOST_BASE / REAL_DRUM_TRACK_RELATIVE_PATH.parent
    target_dir_on_host.mkdir(parents=True, exist_ok=True)

    # Copy the actual drums.wav file to this simulated PVC location
    target_file_on_host = PVC_MOUNT_HOST_BASE / REAL_DRUM_TRACK_RELATIVE_PATH

    # Ensure the source file actually exists on the host
    if not os.path.exists(REAL_DRUM_TRACK_HOST_SOURCE_PATH):
        pytest.fail(f"Source drum track not found: {REAL_DRUM_TRACK_HOST_SOURCE_PATH}. Please ensure it exists.")

    shutil.copy(REAL_DRUM_TRACK_HOST_SOURCE_PATH, target_file_on_host)
    print(f"Copied test drum track to simulated PVC mount: {target_file_on_host}")

    yield str(PVC_MOUNT_HOST_BASE) # Yield the host path for the PVC mount

    # Teardown: Clean up the temporary directory
    print(f"Cleaning up simulated PVC mount: {PVC_MOUNT_HOST_BASE}")
    shutil.rmtree(PVC_MOUNT_HOST_BASE)


# --- Container Fixture ---
@pytest.fixture(scope="module")
def drum_analysis_container(podman_client, setup_shared_data):
    """
    Builds the Docker image, runs the container, and yields the container object.
    Ensures container is stopped and removed after tests.
    """
    container = None
    log_buffer = io.StringIO() # Buffer to store captured logs
    log_thread = None

    # Flag to signal the log reader to stop
    stop_log_thread = threading.Event()

    # Thread to continuously read logs
    def read_container_logs(container_obj, buffer, stop_event):
        print("\n[Log Reader] Starting log reader thread...")
        try:
            # stream=True is crucial here to get live updates
            # follow=True will keep streaming until container stops or connection breaks
            for line in container_obj.logs(stream=True, follow=True):
                if stop_event.is_set():
                    print("[Log Reader] Stop event received, exiting.")
                    break
                try:
                    decoded_line = line.decode('utf-8').strip()
                    buffer.write(decoded_line + "\n")
                    print(f"[CONTAINER LOG] {decoded_line}")
                except UnicodeDecodeError:
                    buffer.write(f"[Log Decode Error] Could not decode: {line}\n")
                    print(f"[CONTAINER LOG - Decode Error] Could not decode: {line}")
        except Exception as e:
            print(f"\n[Log Reader] Log reading stopped due to error: {e}")
        print("[Log Reader] Log reader thread finished.")

    try:
        print(f"\nBuilding Docker image: {IMAGE_NAME}")
        # Build the image. Set path to PROJECT_ROOT
        image, _ = podman_client.images.build(
            path=os.path.dirname(os.path.dirname(__file__)),
            dockerfile=DOCKERFILE_PATH,
            tag=IMAGE_NAME,
            rm=True # Remove intermediate containers
        )
        print(f"Image '{image.tags[0]}' built successfully")

        # Define the volume mount: host path -> container path
        # podman-py expects volumes as a dictionary mapping host_path: {'bind': container_path, 'mode': 'rw'}
        volumes = {setup_shared_data: {'bind': CONTAINER_PVC_MOUNT_BASE, 'mode': 'rw'}}

        print(f"Running container '{IMAGE_NAME}' on port {HOST_PORT}..")
        # Add security_opt=["seccomp=unconfined"] to match K8s deployment
        # This prevents ConnectionResetError caused by seccomp filtering syscalls
        container = podman_client.containers.run(
            image=IMAGE_NAME,
            ports={f"{CONTAINER_PORT}/tcp": HOST_PORT},
            detach=True,
            name=f"test-{IMAGE_NAME}-{int(time.time())}",
            remove=True, # Ensure removal on exit/stop
            volumes=volumes, # Mount the shared data volume
            mem_limit='32G',
            security_opt=["seccomp=unconfined"]
        )
        print(f"Container '{container.name}' started. ID: {container.id}")

        # Start the log reading thread
        log_thread = threading.Thread(
            target=read_container_logs,
            args=(
                container,
                log_buffer,
                stop_log_thread
            ),
            daemon=True
        )
        log_thread.start()

        # Give the container a moment to start and the log reader to attach
        time.sleep(2)

        # Wait for the service to be healthy
        max_retries = 60
        service_healthy = False
        for i in range(max_retries):
            try:
                print(f"Attempt {i+1}/{max_retries}: Checking health at {HEALTH_CHECK_URL}...")
                response = requests.get(HEALTH_CHECK_URL, timeout=5)
                if response.status_code == 200 and response.json().get("status") == "OK":
                    print("Service is healthy!")
                    service_healthy = True
                    break
            except requests.exceptions.ConnectionError as e:
                print(f"ConnectionError: {e}")
                pass # Connection not yet established
            except requests.exceptions.Timeout:
                print("Health check timed out.")
            time.sleep(2)
            # Check if container is still running if connection fails
            try:
                container.reload()
                if container.status != 'running':
                    print(f"Container exited prematurely with status: {container.status}. Checking logs...")
                    # Print logs immediately if container exited
                    print(f"\n--- Container '{container.name}' Logs (Container Exited) ---")
                    print(log_buffer.getvalue())
                    pytest.fail(f"Drum analysis service container exited prematurely. Status: {container.status}")
            except NotFound:
                print(f"Container '{container.name}' not found during health check, it likely crashed and removed itself.")
                print(f"\n--- Container '{container.name}' Logs (Container Crashed and Removed) ---")
                print(log_buffer.getvalue())
                pytest.fail(f"Drum analysis service container crashed and was removed before becoming healthy.")
                time.sleep

        if not service_healthy:
            # If loop finishes without service becoming healthy, print logs and fail
            print(f"\n--- Container '{container.name}' Logs (Health Check Failed) ---")
            print(log_buffer.getvalue())
            pytest.fail(f"Drum analysis service did not become healthy within {max_retries*2} seconds.")

        print(f"Audio file will be accessed directly from mounted volume at: {CONTAINER_DRUM_TRACK_PATH}")

        yield container # Yield the running container to the test to use

    except Exception as e:
        print(f"An error occurred during container setup: {e}")
        print(f"\n--- Container '{container.name if container else 'N/A'}' Logs (Setup Error) ---")
        if log_buffer:
            print(log_buffer.getvalue())
        pytest.fail(f"Failed to set up container for E2E test: {e}")
    finally:
        # Signal the log thread to stop and wait for it
        if log_thread and log_thread.is_alive():
            print("[Log Reader] Signaling log thread to stop...")
            stop_log_thread.set()
            log_thread.join(timeout=5) # Give it a moment to finish

        print(f"--- Container '{container.name}' Final Logs ---")
        # Print all captured logs from the buffer
        captured_logs = log_buffer.getvalue()
        if captured_logs:
            print(captured_logs)
        else:
            print("No logs were captured by the streaming thread.")

        if container:
            try:
                container.reload()
                if container.status == 'running':
                    print(f"Stopping and removing container '{container.name}' (ID: {container.id})...")
                    container.stop(timeout=5)
                    print("Container stopped and removed")

                try:
                    container.reload()
                    if container.status == 'exited':
                        print("Removing container...")
                        container.remove()
                except NotFound:
                    print("Container was automatically removed after stopping.")

            except NotFound:
                print("Container already removed.")
            except Exception as e:
                print(f"Error during container cleanup: {e}")
        else:
            print("No container object to clean up.")

        log_buffer.close()
        print("-------------------------------------------")


# --- E2E Test Cases ---
def test_e2e_drum_analysis_success(drum_analysis_container):
    """
    Performs an end-to-end test of the drum analysis service.
    """
    print("\n--- Running E2E Test: test_e2e_drum_analysis_success ---")

    assert drum_analysis_container is not None, "Container was not successfully set up."

    request_data = {
        "drums_path": CONTAINER_DRUM_TRACK_PATH # Use path INSIDE the container
    }

    print(f"Sending POST request to {ANALYZE_DRUMS_URL} with path: {CONTAINER_DRUM_TRACK_PATH}")
    response = requests.post(ANALYZE_DRUMS_URL, json=request_data, timeout=1200)

    print(f"Received response status code: {response.status_code}")
    # Debugging code:
    try:
        response_json = response.json()
        print(f"Received response JSON: {json.dumps(response_json, indent=2)}")
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response. Response text: {response.text}")
        response_json = {}

    assert response.status_code == 200
    assert isinstance(response_json, dict)

    # Basic structural validation of response
    if response_json:
        drum_data = response_json
        assert "tempo" in drum_data
        assert "hits" in drum_data
        assert isinstance(drum_data['hits'], list)

        # Save list of hits for validation
        hits = drum_data["hits"]
        assert len(hits) > 0, "No drum hits were detected in the audio file."

        # Iterate over each hit to validate its structure and types
        for hit in hits:
            assert isinstance(hit, dict)
            assert "onset_time" in hit
            assert "duration" in hit
            assert "relative_volume" in hit
            assert "dominant_frequency" in hit
            assert "spectral_centroid" in hit
            assert "spectral_rolloff" in hit
            assert "spectral_flux" in hit
            assert "mfccs" in hit
            assert "drum_category" in hit
            assert "category_confidence" in hit
            assert "drum_type" in hit
            assert "type_confidence" in hit
            assert "qualifier" in hit
            assert "qualifier_confidence" in hit

            # Validate types and ranges for each key in the hit dict
            assert isinstance(hit['onset_time'], (float, int))
            assert hit['onset_time'] >= 0

            assert isinstance(hit['duration'], (float, int))
            assert hit['duration'] > 0

            assert isinstance(hit['relative_volume'], (float, int))
            assert hit['relative_volume'] >= 0

            assert isinstance(hit['dominant_frequency'], (float, int))
            assert hit['dominant_frequency'] >= 0

            assert isinstance(hit["spectral_centroid"], (float, int))
            assert hit["spectral_centroid"]

            assert isinstance(hit["spectral_flux"], (float, int))
            assert hit["spectral_flux"] >= 0

            assert isinstance(hit["spectral_rolloff"], (float, int))
            assert hit["spectral_rolloff"] >= 0

            assert isinstance(hit["mfccs"], list)
            assert len(hit['mfccs']) > 0

            assert isinstance(hit['drum_category'], str)
            assert hit['drum_category'] in [
                'kick', 'snare', 'tom', 'cymbal', 'other'
            ]
            assert isinstance(hit['category_confidence'], (float, int))
            assert 0.0 <= hit['category_confidence'] <= 1

            assert isinstance(hit['drum_type'], str)
            assert hit['drum_type'] in [
                'bass',
                'open_band', 'closed_band',
                'med_high', 'med_low', 'mid', 'low', 'high',
                'crash', 'hihat', 'ride', 'gong',
                'cowbell', 'unknown'
            ]
            assert isinstance(hit['type_confidence'], (float, int))
            assert 0.0 <= hit['type_confidence'] <= 1

            assert isinstance(hit['qualifier'], str)
            assert hit['qualifier'] in [
                'rimshot', 'brush', 'chains', 'no_qualifier',
                'full', 'mid', 'bell', 'muted',
                'brush', 'chains',
                'full_muted', 'mid_muted', 'bell_muted',
                'full_brush', 'mid_brush', 'bell_brush',
                'full_chains', 'mid_chains', 'bell_chains',
                'brush_muted', 'chains_muted',
                'bell_brush_muted', 'bell_chains_muted',
                'mid_brush_muted', 'mid_chains_muted',
                'full_brush_muted', 'full_chains_muted',
                'open', 'close', 'muted', 'brush', 'chains',
                'open_muted', 'close_muted',
                'open_brush', 'open_chains',
                'close_brush', 'close_chains',
                'brush_muted', 'chains_muted',
                'open_brush_muted', 'close_brush_muted',
                'brush_open', 'brush_close',
                'chains_open', 'chains_close',
                'brush_muted_open', 'brush_muted_close',
                'chains_muted_open', 'brush_muted_close'
                'no_qualifier'
            ]
            assert isinstance(hit['qualifier_confidence'], (float, int))
            assert 0.0 <= hit['qualifier_confidence'] <= 1

        # Validate tempo type
        assert isinstance(drum_data['tempo'], (float, int))
        assert drum_data['tempo'] >= 0

    print("E2E test successful: Drum analysis returned valid results.")
