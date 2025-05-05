"""
This is an end-to-end test suite for /align endpoint
It tests the Flask endpoint
It tests whether the alignment tool correctly accesses the file paths and returns the appropriate JSON response
It also tests error handling
"""
import json
import os
import logging
import time
import pytest
import requests
from podman import PodmanClient

@pytest.fixture(scope="function")
def mfa_flask_container(request):
    try:
        client = PodmanClient(base_url="unix:///run/user/1000/podman/podman.sock")
        image_name = "localhost/blindmuaddib/align-endpoint:latest"
        container_name = "align-test-container"
        port = 24725

        # Build the Dockerfile
        build_context = "./tests"
        build_args = {}
        image, build_logs = client.images.build(
            path=build_context,
            dockerfile="test-align-endpoint.Dockerfile",
            tag=image_name,
            buildargs=build_args,
            rm=True
        )
        if build_logs:
            for log in build_logs:
                try:
                    decoded_log = log.decode('utf-8')
                    if 'stream' in decoded_log:
                        print(decoded_log.strip())
                except UnicodeDecodeError:
                    print(f"Could not decode log: {log}")

        # Check if a container with the same name exists and remove it
        try:
            existing_container = client.containers.get(container_name)
            existing_container.stop()
            existing_container.remove()
            print(f"Removed existing container: {container_name}")
        except Exception:
            pass

        # Define resource limits; adjust to your needs
        mem_limit = '32G'

        # Run the container
        container = client.containers.run(
            image_name,
            ports={f"{port}/tcp": port},
            name=container_name,
            detach=True,
            remove=False,
            mem_limit=mem_limit,
        )
        print(f"Container '{container_name} started with ID: {container.id}, Memory limit: {mem_limit}")

        # Wait for the Flask server to start
        startup_timeout = 10
        start_time = time.time()
        while True:
            try:
                health_check_url = f"http://127.0.0.1:{port}"
                requests.get(health_check_url, timeout=1)
                print("Flask server is reachable")
                break
            except requests.exceptions.ConnectionError:
                if time.time() - start_time > startup_timeout:
                    raise Exception("Timeout waiting for Flask server to start")
                time.sleep(0.5)

        yield f"http://127.0.0.1:{port}"

    finally:
        # Conditional cleanup: Stop and remove the container only after passing that test
        if not hasattr(request.session, "testsfailed") and request.session.testsfailed == 0:
            try:
                container = client.containers.get(container_name)
                container.stop(timeout=5)
                container.remove()
                print(f"Contanier '{container.name}' stopped and removed.")
            except podman.error.exceptions.NotFound:
                print(f"Container '{container_name}' not found, likely already removed")
            except Exception:
                print(f"Error during container cleanup: {e}")
            try:
                client.images.remove(image_name, force=True)
                print(f"Image '{image_name}' remove.")
            except podman.error.exceptions.ImageNotFound:
                print(f"Image '{image_name}' not found, likely already removed")
            except Exception as e:
                print(f"Error during image cleanup: {e}")
        else:
            print(f"Test failed, container '{container_name}' will be left running for inspection.")
        client.close()

def test_align_endpoint(mfa_flask_container):
    endpoint = f"{mfa_flask_container}/align"
    audio_path = "/app/data/separator_output/htdemucs_6s/BloodCalcification-NoMore/vocals.wav"
    lyrics_path = "/app/data/lyrics/BloodCalcification-NoMore.txt"

    payload = {
        "vocal_stem_path": audio_path,
        "lyrics_file_path": lyrics_path,
    }

    response = requests.post(endpoint, json=payload, timeout=1200)

    assert response.status_code == 200
    data = response.json()
    assert "alignment_file_path" in data
    alignment_file_path = data["alignment_file_path"]
    print(f"Alignment file path returned by server: {alignment_file_path}")

def test_align_endpoint_missing_files(mfa_flask_container):
    endpoint = f"{mfa_flask_container}/align"
    payload = {}

    response = requests.post(endpoint, json=payload, timeout=100)

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "vocal_stem_path or lyrics_file_path missing" in data["error"]
