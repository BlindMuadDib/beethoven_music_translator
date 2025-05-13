"""
This is an end-to-end test suite for /align endpoint
It tests the Flask endpoint
It tests whether the alignment tool correctly accesses the file paths and returns the appropriate JSON response
It also tests error handling
"""
import json
import os
import shutil
import time
import pytest
import requests
import tempfile
import stat
import podman
from podman import PodmanClient

@pytest.fixture(scope="function")
def mfa_flask_container(request):
    client = None
    container = None
    image_name = "localhost/blindmuaddib/align-endpoint-test:1"
    container_name = "align-e2e-test-container"
    port = 24725

    host_corpus_dir_temp = None
    host_aligned_dir_temp = None

    try:
        # Create temp directories on the host
        host_corpus_dir_temp = tempfile.mkdtemp(prefix="align_test_corpus_")
        host_aligned_dir_temp = tempfile.mkdtemp(prefix="align_test_aligned_")
        print(f"Created host temp corpus dir: {host_corpus_dir_temp}")
        print(f"Created host temp aligned dir: {host_aligned_dir_temp}")

        # Set permissions to 0o777 (rwxrwxrwx) to all the container user (mfauser)
        # to write into these host-mounted directories.
        permissions = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO # 0o777 in octal

        try:
            print(f"Setting permissions for {host_corpus_dir_temp} to 0o777")
            os.chmod(host_corpus_dir_temp, permissions)
            print(f"Setting permissions for {host_aligned_dir_temp} to 0o777")
            os.chmod(host_aligned_dir_temp, permissions)
            print("Permissions set Successfully.")
        except OSError as chmod_err:
            print(f"Warning: Failed to chmod temporary directories: {chmod_err}")
            raise Exception(f"Failed to set permissions on temp dirs: {chmod_err}") from chmod_err

        volumes = {
            host_corpus_dir_temp: {"bind": "/shared-data/corpus", "mode": "rw"},
            host_aligned_dir_temp: {"bind": "/shared-data/aligned", "mode": "rw"},
        }

        client = PodmanClient(base_url="unix:///run/user/1000/podman/podman.sock")
    #
    #     # Build the Dockerfile
    #     build_context = "./tests/"
    #     print(f"Building image {image_name} from {os.path.abspath(build_context)}/align-endpoint-test.Dockerfile")
    #     image, build_logs_generator = client.images.build(
    #         path=build_context,
    #         dockerfile="align-endpoint-test.Dockerfile",
    #         tag=image_name,
    #         rm=True,
    #         decode=True,
    #         format="docker"
    #     )
    #     print(f"Image build attempt for {image_name} finished.")
    #     if build_logs_generator:
    #         for item_from_generator in build_logs_generator:
    #             log_data_dict = None # This will store the parsed dictionary
    #
    #             if isinstance(item_from_generator, bytes):
    #                 # If bytes, decode and parse as JSON
    #                 try:
    #                     decoded_str = item_from_generator.decode('utf-8')
    #                     log_data_dict = json.loads(decoded_str)
    #                 except UnicodeDecodeError:
    #                     print(f"Build log (bytes, UTF-8 decode error): {item_from_generator!r}")
    #                 except json.JSONDecodeError:
    #                     # If it's not JSON after decoding print as a plain line
    #                     print(f"Build log (bytes, not JSON): {item_from_generator.decode('utf-8', errors='replace').strip()}")
    #                     continue
    #             elif isinstance(item_from_generator, dict):
    #                 # If decode=True worked and it's already a dict
    #                 log_data_dict = item_from_generator
    #             elif isinstance(item_from_generator, str):
    #                 # If decode=True resulted in a string (e.g., library handled JSON error by returning str)
    #                 # Attempt to parse it as JSON, as it might still be a JSON string
    #                 try:
    #                     log_data_dict = json.loads(item_from_generator)
    #                 except json.JSONDecodeError:
    #                     # If it's truly a plain string message
    #                     print(f"Build log (plain string): {item_from_generator.strip()}")
    #                     continue
    #             else:
    #                 print(f"Build log (unknown type {type(item_from_generator)}): {item_from_generator!r}")
    #
    #             if log_data_dict:
    #                 if 'stream' in log_data_dict and log_data_dict.get('stream') is not None:
    #                     stream_content = log_data_dict['stream']
    #                     # Ensure the stream content is a string before stripping
    #                     if isinstance(stream_content, str):
    #                         print(f"Build log: {stream_content.strip()}")
    #                     else:
    #                         print(f"Build log (stream content not string): {stream_content}")
    #                 elif 'errorDetail' in log_data_dict and log_data_dict.get('errorDetail') is not None:
    #                     error_detail = log_data_dict['errorDetail']
    #                     # errorDetail should be a dictionary containing a 'message'
    #                     if isinstance(error_detail, dict):
    #                         print(f"Build Error: {error_detail.get('message', 'Unknown error')}")
    #                     else:
    #                         # If errorDetail is not a dict, print its string representation
    #                         print(f"Build Error (unexpected format): {error_detail}")
    #                 # Check for 'status' for progress updates
    #                 elif 'status' in log_data_dict and log_data_dict.get('status') is not None:
    #                     print(f"Build Status: {log_data_dict['status']}")
    #                     pass
    #
    #     print(f"Successfully built image: {image.id if image else 'Failed'}")

    # Check if a container with the same name exists and remove it
        try:
            existing_container = client.containers.get(container_name)
            if existing_container:
                print(f"Attempting to stop existing container: {container_name}")
                existing_container.stop(timeout=10)
                print(f"Attempting to remove existing container: {container_name}")
                existing_container.remove(force=True)
                print(f"Removed existing container: {container_name}")
        except podman.errors.exceptions.NotFound:
            print(f"No existing container named {container_name} found. Proceeding.")
        except Exception as e:
            print(f"Error managing existing container {container_name}: {e}")

        # Define resource limits; adjust to your needs
        mem_limit = '32G'

        # Run the container
        print(f"Running container {container_name} from image {image_name} with port {port} and mem_limit {mem_limit}")
        print(f"Host corpus dir: {host_corpus_dir_temp} -> /shared-data/corpus")
        print(f"Host aligned dir: {host_aligned_dir_temp} -> /shared-data/aligned")

        container = client.containers.run(
            image_name,
            ports={f"{port}/tcp": port},
            name=container_name,
            detach=True,
            remove=False,
            mem_limit=mem_limit,
            volumes=volumes,
        )
        print(f"Container '{container_name} started with ID: {container.id}, Memory limit: {mem_limit}")

        # Wait for the Flask server to start
        health_check_url = f"http://localhost:{port}/align/health"
        startup_timeout = 60
        start_time = time.time()
        server_ready = False
        print(f"Waiting for Flask server at {health_check_url} (timeout: {startup_timeout}s)")
        while time.time() - start_time < startup_timeout:
            try:
                response = requests.get(health_check_url, timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "OK":
                        print("Flask server is reachable")
                        server_ready = True
                        break
                    else:
                        print(f"Health check status not OK: {data.get('status')}")
                else:
                    print(f"Health check failed with status {response.status_code}")
            except requests.exceptions.ConnectionError:
                print("Flask server not yet responding to connection ...")
            except requests.exceptions.Timeout:
                print(f"Flask server connection timed out during health check ...")
                time.sleep(1)

        if not server_ready:
            # If server didn't start, print container logs for debugging
            print(f"Timeout waiting for Flask server to start. Container logs for {container_name}:")
            try:
                for log_line in container.logs(stream=True):
                    print(log_line.decode('utf-8').strip())
            except Exception as log_exc:
                print(f"Could not retrieve logs: {log_exc}")
            raise Exception("Timeout waiting for Flask server to start. Check container logs.")

        yield f"http://127.0.0.1:{port}"

    finally:
        test_failed = hasattr(request.node, 'rep_call') and request.node.rep_call.failed

        if container:
        #     if test_failed:
        #         print(f"Test failed. Leaving container '{container_name}' (ID: {container.id}) running for inspection.")
        #         print(f"Corpus data on host: {host_corpus_dir_temp}")
        #         print(f"Aligned data on host: {host_aligned_dir_temp}")
        #         print(f"To see logs: podman logs {container_name}")
        #         print(f"To stop: podman stop {container_name} && podman rm {container_name}")
        #     else:
        #         print(f"Test passed or no failure info. Stopping and removing container '{container_name}' ...")
        #         try:
        #             container.stop(timeout=10)
        #             container.remove(force=True)
        #             print(f"Container '{container_name}' stopped and removed.")
        #         except podman.errors.exceptions.NotFound:
        #             print(f"Container '{container_name}' not found during cleanup, likely already removed.")
        #         except Exception as e_cleanup:
        #             print(f"Error during container cleanup: {e_cleanup}")
        # else:
        #     print("Container object not available for cleanup (may have failed to start).")
        #
        # if not test_failed:
        #     # if client and image_name:
        #     #     try:
        #     #         print(f"Removing image '{image_name}'...")
        #     #         client.images.remove(image_name, force=True)
        #     #         print(f"Image '{image_name}' removed.")
        #     #     except podman.errors.exceptions.ImageNotFound:
        #     #         print(f"Image '{image_name}' not found during cleanup.")
        #     #     except Exception as e_img_cleanup:
        #     #         print(f"Error during image cleanup: {e_img_cleanup}")
        #     # Clean up temp host directories
        #     if os.path.exists(host_corpus_dir_temp):
        #         shutil.rmtree(host_corpus_dir_temp)
        #         print(f"Removed host temp corpus dir: {host_corpus_dir_temp}")
        #     if os.path.exists(host_aligned_dir_temp):
        #         shutil.rmtree(host_aligned_dir_temp)
        #         print(f"Remved host temp aligned dir: {host_aligned_dir_temp}")
        # else:
            print(f"Test failed. Host temp dirs kept for inspection:")
            print(f"  Corpus: {host_corpus_dir_temp}")
            print(f"  Aligned: {host_aligned_dir_temp}")


        if client:
            client.close()

def test_align_endpoint(mfa_flask_container):
    endpoint = f"{mfa_flask_container}/align"
    audio_path = "/app/data/separator_output/htdemucs_6s/BloodCalcification-NoMore/vocals.wav"
    lyrics_path = "/app/data/lyrics/BloodCalcification-NoMore.txt"

    # Extract the base name for assert, similiar to the app
    expected_output_base_name = os.path.splitext(os.path.basename(audio_path))[0]

    headers = {'Content-Type': 'application/json'}
    payload = {
        "vocals_stem_path": audio_path,
        "lyrics_path": lyrics_path,
    }

    print(f"Sending POST to {endpoint} with payload: {payload}") # Log payload
    response = requests.post(endpoint, json=payload, headers=headers, timeout=1200)

    # --- Debugging: Print response details regardless of status ---
    print(f"Received status code: {response.status_code}")
    try:
        response_json = response.json()
        print(f"Received JSON response: {response_json}")
    except requests.exceptions.JSONDecodeError:
        print(f"Received non-JSON response text: {response.text}")
    # --- End Debugging ---

    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response body: {response.text}" # Include body in assert message
    data = response.json()
    assert "alignment_file_path" in data
    alignment_file_path = data["alignment_file_path"]
    print(f"Alignment file path returned by server: {alignment_file_path}")

    # Assert the path structure and filename
    assert alignment_file_path.startswith("/shared-data/aligned/"), \
        f"Path should start with /shared-data/aligned/, but got {alignment_file_path}"
    assert alignment_file_path.endswith(f"{expected_output_base_name}.json"), \
        f"Path should end with {expected_output_base_name}.json, but got {alignment_file_path}"

def test_align_endpoint_missing_files(mfa_flask_container):
    endpoint = f"{mfa_flask_container}/align"
    payload = {}

    response = requests.post(endpoint, json=payload, timeout=100)

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "vocals_stem_path or lyrics_file_path missing" in data["error"]
