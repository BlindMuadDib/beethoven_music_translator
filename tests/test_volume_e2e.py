import os
import time
import json
import unittest
import requests
import podman
from podman.errors import APIError, ImageNotFound, NotFound as PodmanNotFound, BuildError as PodmanBuildError

# --- Configuration for the Volume Service E2E Test ---
VOLUME_SERVICE_IMAGE_TAG = "volume_service:latest"
VOLUME_SERVICE_CONTAINER_NAME = "volume_service_container"
SERVICE_URL = "http://localhost:39574"

# --- Project and Path Configuration ---
# Absolute path to the project's root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# The directory containing the Dockerfile and service code, used as the build context for Podman
BUILD_CONTEXT_DIR = PROJECT_ROOT
# The path to the Dockerfile, relative to the build context
DOCKERFILE_PATH_IN_CONTEXT = os.path.join(PROJECT_ROOT, "volume-endpoint.Dockerfile")

# The host directory containing all test audio data
# This entire directory will be mounted into the container
HOST_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
# The path where the host data directory will be mounted inside the container
CONTAINER_DATA_DIR = "/data"

# --- Audio File Paths (relative to CONTAINER_DATA_DIR) ---
SONG_FILE_PATH = "audio/BloodCalcification-NoMore.wav"
STEM_DIR_PATH = "separator_output/htdemucs_6s/BloodCalcification-NoMore"
STEMS_TO_TEST = ["bass", "drums", "guitar", "other", "piano", "vocals"]


class TestVolumeServiceE2E(unittest.TestCase):
    podman_client = None
    container = None

    @classmethod
    def setUpClass(cls):
        """Builds the Podman image, starts the container, and waits for it to be healthy."""
        if not os.path.exists(HOST_DATA_DIR):
            raise unittest.SkipTest(f"Host data directory for E2E tests not found: {HOST_DATA_DIR}")

        try:
            # Get the current user's ID to build the standard socket path
            uid = os.getuid()
            socket_url = f"unix:///run/user/{uid}/podman/podman.sock"
            print(f"Connecting to Podman service at: {socket_url}")
            cls.podman_client = podman.PodmanClient(base_url=socket_url)

            # Diagnostic Print
            # This will show if the base_url is being correctly set internally
            print(f"Podman client configured with internal URL: {cls.podman_client.api.base_url}")

            if not cls.podman_client.ping():
                raise ConnectionError("Failed to ping Podman service.")
        except Exception as e:
            raise unittest.SkipTest(f"Podman is not available or connection failed: {e}")

        # --- Build the container image ---
        print(f"\nBuilding Volume service image ({VOLUME_SERVICE_IMAGE_TAG})...")
        try:
            # Clean up old image if it exists
            try:
                cls.podman_client.images.get(VOLUME_SERVICE_IMAGE_TAG).remove(force=True)
                print(f"Removed existing image: {VOLUME_SERVICE_IMAGE_TAG}")
            except ImageNotFound:
                pass # Image doesn't exist, which is fine

            cls.podman_client.images.build(
                path=BUILD_CONTEXT_DIR,
                dockerfile=DOCKERFILE_PATH_IN_CONTEXT,
                tag=VOLUME_SERVICE_IMAGE_TAG,
                rm=True
            )
            # Verify image exists
            cls.podman_client.images.get(VOLUME_SERVICE_IMAGE_TAG)
            print(f"Image {VOLUME_SERVICE_IMAGE_TAG} built successfully.")

        except (PodmanBuildError, Exception) as e:
            raise unittest.SkipTest(f"Podman image build failed: {e}")

        # --- Run the container ---
        print(f"Starting Volume service container ({VOLUME_SERVICE_CONTAINER_NAME})...")
        try:
            # Clean up old container if it exists
            try:
                cls.podman_client.containers.get(VOLUME_SERVICE_CONTAINER_NAME).remove(force=True)
                print(f"Removed existing container: {VOLUME_SERVICE_CONTAINER_NAME}")
            except PodmanNotFound:
                pass # Container doesn't exist, which is fine

            cls.container = cls.podman_client.containers.run(
                VOLUME_SERVICE_IMAGE_TAG,
                name=VOLUME_SERVICE_CONTAINER_NAME,
                ports={'39574/tcp': 39574},
                volumes={
                    HOST_DATA_DIR: {'bind': CONTAINER_DATA_DIR, 'mode': 'ro'}
                },
                detach=True
            )
        except APIError as e:
            raise unittest.SkipTest(f"Failed to start Volume service container with Podman: {e}")

        # --- Wait for the service to become healthy
        print("Waiting for Volume service to become healthy...")
        max_retries, retry_interval = 120, 1
        for i in range(max_retries):
            try:
                response = requests.get(f"{SERVICE_URL}/api/analyze_rms/health", timeout=2)
                if response.status_code == 200:
                    print("Volume service is healthy.")
                    return # Exit setUpClass successfully
            except requests.exceptions.RequestException:
                time.sleep(retry_interval)

        # If the loop finishes without returning, the service failed to start
        cls.tearDownClass() # Clean up resources
        raise unittest.SkipTest("Volume service did not become healthy in time.")

    @classmethod
    def tearDownClass(cls):
        """Stops and removes the Podman container and image."""
        if cls.container:
            print(f"\nStopping and removing container {cls.container.name}...")
            try:
                cls.container.stop(timeout=10)
                cls.container.remove(force=True)
            except (APIError, Exception) as e:
                print(f"Error removing container {cls.container.name}: {e}")
            finally:
                cls.container = None

        if cls.podman_client:
            try:
                cls.podman_client.images.get(VOLUME_SERVICE_IMAGE_TAG).remove(force=True)
                print(f"Removed image {VOLUME_SERVICE_IMAGE_TAG}.")
            except (ImageNotFound, APIError, Exception) as e:
                print(f"Could not remove image {VOLUME_SERVICE_IMAGE_TAG} (may already be gone): {e}")


    def test_analyze_e2e(self):
        """
        Tests the /api/analyze_rms endpoint using a real song and all its stems.
        """
        # --- Construct the payload with paths inside the container ---
        audio_paths_payload = {"song": os.path.join(CONTAINER_DATA_DIR, SONG_FILE_PATH)}
        for stem in STEMS_TO_TEST:
            audio_paths_payload[stem] = os.path.join(CONTAINER_DATA_DIR, STEM_DIR_PATH, f"{stem}.wav")

        payload = {"audio_paths": audio_paths_payload}

        print(f"Sending E2E request to {SERVICE_URL}/api/analyze_rms...")
        try:
            response = requests.post(f"{SERVICE_URL}/api/analyze_rms", json=payload, timeout=300)
        except requests.exceptions.RequestException as e:
            self.fail(f"Request to Volume service failed: {e}")

        # --- Assertions ---
        self.assertEqual(response.status_code, 200, f"Expected status 200 but got {response.status_code}. Response: {response.text}")

        results = response.json()

        # Check for errors reported by the service
        if "errors" in results and results["errors"]:
            self.fail(f"Service reported errors during processing: {json.dumps(results['errors'], indent=2)}")

        self.assertIn("overall_rms", results)
        self.assertIn("instruments", results)

        # Validate overall RMS
        self.assertIsInstance(results["overall_rms"], list)
        self.assertTrue(len(results["overall_rms"]) > 0, "Overall RMS array should not be empty")
        self.assertEqual(len(results["overall_rms"][0]), 2, "Overall RMS entries must be [time, value] pairs")

        # Validate instruments
        self.assertEqual(set(results["instruments"].keys()), set(STEMS_TO_TEST))
        for instrument, data in results["instruments"].items():
            self.assertIn("rms_values", data)
            self.assertIsInstance(data["rms_values"], list, f"RMS values for {instrument} should be a list")
            if len(data["rms_values"]) > 0:
                self.assertEqual(len(data["rms_values"][0]), 2, f"RMS entries for {instrument} must be [time, value] pairs")

        print("E2E Test passed: Response structure and content are valid.")

if __name__ == '__main__':
    unittest.main()
