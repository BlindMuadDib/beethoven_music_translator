import pytest
import os
import sys
import requests
import json
import time
from bs4 import BeautifulSoup
import podman
from podman.errors.exceptions import NotFound

# --- Configuration ---
IMAGE_NAME = "auth_server_test_image"
CONTAINER_NAME = "auth_server_e2e_container"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, PROJECT_ROOT)

DOCKERFILE_PATH = os.path.join(PROJECT_ROOT, "auth_server.Dockerfile")
CONTAINER_PORT = 45769
HOST_PORT = 45769
BASE_URL = f"http://127.0.0.1:{HOST_PORT}"

# --- Podman Client Fixture ---
@pytest.fixture(scope="session")
def podman_client():
    """Provides a podan client instance."""
    try:
        client = podman.PodmanClient()
        if not client.ping():
            raise Exception("Cannot connect to Podman. Is the service running?")
        yield client
    finally:
        # Final cleanup after all tests are done
        print("\nFinal cleanup...")
        try:
            client = podman.PodmanClient()
            container = client.containers.get(CONTAINER_NAME)
            print(f"Force removing container {CONTAINER_NAME}...")
            container.remove(force=True)
        except NotFound:
            pass # It's already gone, which is fine
        try:
            client = podman.PodmanClient()
            image = client.images.get(IMAGE_NAME)
            print(f"Force removing image {IMAGE_NAME}...")
            image.remove(force=True)
        except NotFound:
            pass # It's already gone
        client.close()

@pytest.fixture(scope="session")
def build_and_run_container(podman_client):
    """
    Fixture to build the container image and run a container.
    The container is yielded for tests to use, and automatically removed
    afterward.
    """
    # Print with flush=True so it prints immediately
    print(f"Building container image from context: {PROJECT_ROOT}",
          flush=True)
    try:
        image, _ = podman_client.images.build(
            path=PROJECT_ROOT,
            dockerfile=DOCKERFILE_PATH,
            tag=IMAGE_NAME,
            nocache=True,
            rm=True
        )
        print(f"Image built: {image.id}")
    except Exception as e:
        pytest.fail(f"Image build failed: {e}", pytrace=False)

    print("Starting container...")
    # Force 1 worker to prevent SQLite locking during tests
    test_command = ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:45769", "app:create_app()"]

    container = podman_client.containers.run(
        image=IMAGE_NAME,
        name=CONTAINER_NAME,
        detach=True,
        ports={f'{CONTAINER_PORT}/tcp': HOST_PORT},
        # Set environment variable to enable testing endpoints
        environment={"FLASK_ENV": "testing"},
        command=test_command
    )

    # Wait for the service to become responsive.
    timeout = 60
    start_time = time.time()

    while True:
        try:
            response = requests.get(BASE_URL + '/internal/healthz', timeout=2)
            if response.status_code == 200:
                print("Container is responsive!")
                break
        except requests.exceptions.RequestException:
            pass

        if time.time() - start_time > timeout:
            logs = "Could not retrieve container logs."
            try:
                logs = "".join(log.decode("utf-8") for log in container.logs(stream=False, stdout=True, stderr=True))
            except Exception as log_e:
                logs += f"\nError retrieving logs: {log_e}"
            finally:
                try:
                    print("Attempting to stop container...")
                    container.stop()
                except requests.exceptions.JSONDecodeError:
                    print("Ignoring JSONDecodeError on container stop (likely already stopped).")
                except Exception as stop_e:
                    print(f"An error occurred during container stop: {stop_e}")

                try:
                    container.remove()
                except Exception as remove_e:
                    print(f"An error occurred during container removal: {removal_e}")

            pytest.fail(
                f"Container failed to become responsive within {timeout}s. LOGS:\n---\n{logs}\n---",
                pytrace=False
            )
        time.sleep(1)

    print(f"Initializing database tables via /_reset_db...")
    try:
        requests.post(f"{BASE_URL}/_reset_db", timeout=5)
    except Exception as e:
        print(f"Warning: Failed to auto-initialize DB: {e}")

    yield BASE_URL

    print("\nStopping and removing container...")
    try:
        container.stop()
        container.remove()
    except Exception:
        pass
    print("Container removed.")

# --- Shared Data Setup Fixture ---
@pytest.fixture(scope="function")
def setup_database(build_and_run_container):
    """
    Sets up a clean database state before each test.
    This fixture depends on `build_and_run_container` to ensure the container
    is running.
    """
    url = build_and_run_container
    # This calls the custom testing endpoint for clearing the database for
    # testing
    try:
        response = requests.post(f"{url}/_reset_db", timeout=5)
        assert response.status_code == 200
    except requests.exceptions.ReadTimeout:
        pytest.fail("Database reset timed out - likely a SQLite lock")
    yield
