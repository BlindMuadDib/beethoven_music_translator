import os
import shutil
import io
import json
import time
import threading
import time
import pathlib
import requests
import pytest
import podman
from podman.errors.exceptions import NotFound

# --- Configuration ---
IMAGE_NAME = "drums_endpoint_test"
DOCKERFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "drums-endpoint.Dockerfile")
CONTAINER_PORT = 25941
HOST_PORT = 25941
HEALTH_CHECK_URL = f"http://localhost:{HOST_PORT}/drums/health"
ANALYZE_DRUMS_URL = f"http://localhost:{HOST_PORT}/api/analyze_drums"

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

    # Thread to continuously read logs
    def read_container_logs(container_obj, buffer):
        print("\n[Log Reader] Starting log reader thread...")
        try:
            # stream=True is crucial here to get live updates
            # follow=True will keep streaming until container stops or connection breaks
            for line in container_obj.logs(stream=True, follow=True):
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
        container = podman_client.containers.run(
            image=IMAGE_NAME,
            ports={f"{CONTAINER_PORT}/tcp": HOST_PORT},
            detach=True,
            name=f"test-{IMAGE_NAME}-{int(time.time())}",
            remove=True, # Ensure removal on exit/stop
            volumes=volumes, # Mount the shared data volume
            mem_limit='32G'
        )
        print(f"Container '{container.name}' started. ID: {container.id}")

        # Start the log reading thread
        log_thread = threading.Thread(
            target=read_container_logs,
            args=(
                container,
                log_buffer
            ),
            daemon=True
        )
        log_thread.start()

        # Give the container a moment to start and the log reader to attach
        time.sleep(2)

        # Wait for the service to be healthy
        max_retries = 60
        for i in range(max_retries):
            try:
                print(f"Attempt {i+1}/{max_retries}: Checking health at {HEALTH_CHECK_URL}...")
                response = requests.get(HEALTH_CHECK_URL, timeout=5)
                if response.status_code == 200 and response.json().get("status") == "OK":
                    print("Service is healthy!")
                    break
            except requests.exceptions.ConnectionError as e:
                print(f"ConnectionError: {e}")
                pass # Connection not yet established
            except requests.exceptions.Timeout:
                print("Health check timed out.")
            time.sleep(2)
        else:
            pytest.fail(f"Drum analysis service did not become healthy within {max_retries*2} seconds.")

        print(f"Audio file will be accessed directly from mounted volume at: {CONTAINER_DRUM_TRACK_PATH}")

        yield container # Yield the running container to the test to use

    except podman.errors.ImageNotFound:
        pytest.fail(f"Docker image '{IMAGE_NAME}' not found. Please build it first.")
    except Exception as e:
        print(f"An error occurred during container setup: {e}")
        pytest.fail(f"Failed to set up container for E2E test: {e}")
    finally:
        print(f"--- Container '{container.name}' Final Logs ---")
        time.sleep(1)
        if container:
            print(f"Stopping and removing container '{container.name}' (ID: {container.id})...")
            container.stop(timeout=5)
            container.remove()
            print("Container stopped and removed")

        # Print all captured logs from the buffer
        captured_logs = log_buffer.getvalue()
        if captured_logs:
            print(captured_logs)
        else:
            print("No logs were captured by the streaming thread.")

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
    response = requests.post(ANALYZE_DRUMS_URL, json=request_data, timeout=600)

    print(f"Received response status code: {response.status_code}")
    # Debugging code:
    try:
        response_json = response.json()
        print(f"Received response JSON: {json.dumps(response_json, indent=2)}")
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response. Response text: {response.text}")
        response_json = {}

    assert response.status_code == 200
    assert isinstance(response_json, list)
    assert len(response_json) > 0, "Expected drum hits, but got an empty list."

    # Basic structural validation of a drum hit
    if response_json:
        first_hit = response_json[0]
        assert "onset_time" in first_hit
        assert "duration" in first_hit
        assert "relative_volume" in first_hit
        assert "dominant_frequency" in first_hit
        # Potentially add more specific assertions here, e.g., value ranges
        assert isinstance(first_hit['onset_time'], (float, int))
        assert first_hit['onset_time'] >= 0

    print("E2E test successful: Drum analysis returned valid results.")
