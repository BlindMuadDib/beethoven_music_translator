"""
End-to-End test for the harmonic service using Podman.
This test builds the service container, runs it, and then sends a real
API request to a running container to validate its behavior.
"""

import unittest
import os
import time
import json
import tarfile
import io
import requests
import podman
from podman.errors import APIError, ImageNotFound, NotFound as PodmanNotFound, BuildError as PodmanBuildError

# Configuration for the E2E test
HARMONIC_SERVICE_IMAGE_TAG = "harmonic_service:latest"
HARMONIC_SERVICE_CONTAINER_NAME = "harmonic_service_container"

# Project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Path to the directory containing the Dockerfile and the f0_service code
# This will be the build context for Podman
# Dockerfile: PROJECT_ROOT/F0-endpoint.Dockerfile
# Code: musictranslator/f0_service/
# requirements.txt: musictranslator/f0_service/requirements.txt
# The Dockerfile uses `COPY musictranslator/f0_service/requirements.txt .`
# and `COPY musictranslator/f0_service /app/f0_service`
# This means the build context should be PROJECT_ROOT and the Dockerfile
# path needs to be specified relative to that context
BUILD_CONTEXT_DIR = PROJECT_ROOT
DOCKERFILE_PATH_IN_CONTEXT = f"{PROJECT_ROOT}/harmonic-endpoint.Dockerfile"

# Host directory containing the real audio stems for E2E testing
HOST_STEM_DIR = os.path.join(PROJECT_ROOT, "data", "separator_output", "htdemucs_6s", "BloodCalcification-NoMore")
# Path where the stems will be mounted inside the container
CONTAINER_STEM_DIR = "/test_audio_stems"

# Stems to be tested (filenames in HOST_STEM_DIR)
STEM_FILES = ["bass.wav", "guitar.wav", "piano.wav", "other.wav", "vocals.wav"]
SERVICE_URL = "http://localhost:20006"

class TestFundFreqServiceE2EPodman(unittest.TestCase):
    podman_client = None
    container = None

    @classmethod
    def setUpClass(cls):
        """Builds the Podman image and starts the container"""
        if not os.path.exists(HOST_STEM_DIR):
            raise unittest.SkipTest(f"Host stem directory for E2E tests not found: {HOST_STEM_DIR}")
        for stem_file in STEM_FILES:
            if not os.path.exists(os.path.join(HOST_STEM_DIR, stem_file)):
                raise unittest.SkipTest(f"Required stem file not found: {os.path.join(HOST_STEM_DIR, stem_file)}")

        try:
            # Connect to the Podman service
            # Default is typically 'unix:///run/user/{uid}/podman/podman.sock'
            # Adjust URI if your Podman socket is elsewhere
            cls.podman_client = podman.PodmanClient()
            if not cls.podman_client.ping():
                raise ConnectionError("Failed to ping Podman service.")
        except Exception as e:
            raise unittest.SkipTest(f"Podman is not available, not configured, or connection failed: {e}")

        print(f"\nBuilding Harmonic service Podman image ({HARMONIC_SERVICE_IMAGE_TAG}) from context {BUILD_CONTEXT_DIR} using Dockerfile {DOCKERFILE_PATH_IN_CONTEXT} ... ")
        try:
            # Ensure the image doesn't exist from a previous failed run to avoid issues
            try:
                existing_image = cls.podman_client.images.get(HARMONIC_SERVICE_IMAGE_TAG)
                if existing_image:
                    print(f"Removing existing image: {HARMONIC_SERVICE_IMAGE_TAG}")
                    existing_image.remove(force=True)
                    print("Image removed successfully.")
            except ImageNotFound:
                pass

            # The podman-py build method expects a path to a tarball or a directory containing a Dockerfile
            # It can also take a `fileobj` which is a tarball
            # For simplicity with context, we'll use the path to the build context directory
            # The `dockerfile` parameter is relative to this `path`
            print("Attempting to build image ... ")
            cls.podman_client.images.build(
                path=BUILD_CONTEXT_DIR,
                dockerfile=DOCKERFILE_PATH_IN_CONTEXT,
                tag=HARMONIC_SERVICE_IMAGE_TAG,
                rm=True
            )
            # for log_chunk in logs: # Print build logs
            #     if 'stream' in log_chunk:
            #         print(log_chunk['stream'].strip())
            #     elif 'errorDetail' in log_chunk:
            #         print(f"Build Error: {log_chunk['errorDetail']['message']}")
            #         raise PodmanBuildError(log_chunk['errorDetail']['message'], build_log=logs)

            # Verify image was built
            cls.podman_client.images.get(HARMONIC_SERVICE_IMAGE_TAG)
            print(f"Image {HARMONIC_SERVICE_IMAGE_TAG} built successfully")

        except PodmanBuildError as e:
            print("Podman image build failed!")
            raise unittest.SkipTest(f"Podman image build failed: {e}")
        except Exception as e:
            print(f"Podman image build failed! {e}")
            raise unittest.SkipTest(f"An unexpected error occurred during Podman image build: {e}")

        print(f"Starting Harmonic service container ({HARMONIC_SERVICE_CONTAINER_NAME}) ... ")
        # Define resource limits; adjust to your needs
        mem_limit = '32G'
        try:
            # Ensure no container with the same name is already running
            try:
                existing_container = cls.podman_client.containers.get(HARMONIC_SERVICE_CONTAINER_NAME)
                if existing_container:
                    print(f"Removing existing container: {HARMONIC_SERVICE_CONTAINER_NAME}")
                    existing_container.remove(force=True)
            except PodmanNotFound:
                pass

            cls.container = cls.podman_client.containers.run(
                HARMONIC_SERVICE_IMAGE_TAG,
                name=HARMONIC_SERVICE_CONTAINER_NAME,
                ports={'20006/tcp': 20006},
                volumes={
                    HOST_STEM_DIR: {'bind': CONTAINER_STEM_DIR, 'mode': 'ro'}
                },
                detach=True,
                auto_remove=False, # Podman's --rm equivalent
                mem_limit=mem_limit
            )
        except APIError as e:
            raise unittest.SkipTest(f"Failed to start harmonic service container with Podman: {e}")

        # Wait for the service to be ready
        print("Waiting for harmonic service to start ...")
        max_retries = 30
        retry_interval = 1
        for i in range(max_retries):
            try:
                response = requests.get(f"{SERVICE_URL}/harmonic/health", timeout=2)
                if response.status_code == 200:
                    print("Harmonic service is healthy.")
                    return
            except requests.exceptions.ConnectionError:
                time.sleep(retry_interval)
            except requests.exceptions.ReadTimeout:
                print("Health check request timed out, retrying ...")
                time.sleep(retry_interval)

            if i == max_retries - 1:
                cls.tearDownClass()
                raise unittest.SkipTest("Harmonic service (Podman) did not become healthy in time.")

    @classmethod
    def tearDownClass(cls):
        """Stops and removes the Podman container and optionally the image."""
        if cls.container:
            print(*f"Stopping container {cls.container.name} ... ")
            try:
                cls.container.stop(timeout=10)
                print(f"Removing container {cls.container.name} ... ")
                cls.container.remove(force=True)
            except APIError as e:
                print(f"Error stopping/removing container {cls.container.name}: {e}")
            except Exception as e:
                print(f"An unexpected error during container cleanup for {cls.container.name}: {e}")
            finally:
                cls.container = None

        # Optionally, remove the image if it's only for testing and was creating by this test
        if cls.podman_client:
            try:
                # Check if the image tag used by the test exists before trying to remove
                img_to_remove = cls.podman_client.images.get(HARMONIC_SERVICE_IMAGE_TAG)
                if img_to_remove:
                    print(f"Removing image {HARMONIC_SERVICE_IMAGE_TAG} ... ")
                    img_to_remove.remove(force=True)
            except ImageNotFound:
                print(f"Image {HARMONIC_SERVICE_IMAGE_TAG} not found for removal, or already removed.")
            except APIError as e:
                print(f"Error removing image {HARMONIC_SERVICE_IMAGE_TAG}: {e}")
            except Exception as e:
                print(f"An unexpected error during image cleanup for {HARMONIC_SERVICE_IMAGE_TAG}: {e}")

    def test_analyze_all_e2e_real_stems(self):
        """
        Tests the /api/analyze_harmonic endpoint of the containerized
        service using real audio stems and validates the full feature
        set.
        """
        stem_paths_payload = {}
        for stem_file in STEM_FILES:
            instrument_name = os.path.splitext(stem_file)[0]
            stem_paths_payload[instrument_name] = os.path.join(CONTAINER_STEM_DIR, stem_file)

        payload = {"stem_paths": stem_paths_payload}

        print(f"Sending E2E request to {SERVICE_URL}/api/analyze_harmonic with payload: {json.dumps(payload, indent=2)}")
        try:
            # Using a session for potential keep-alive and connection pooling
            with requests.Session() as session:
                response = session.post(
                    f"{SERVICE_URL}/api/analyze_harmonic",
                    json=payload,
                    timeout=1200
                )
        except requests.exceptions.RequestException as e:
            self.fail(f"Request to F0 service failed: {e}")

        self.assertEqual(response.status_code, 200, f"Response content: {response.text}")
        results = response.json()

        self.assertEqual(len(results), len(STEM_FILES), "Should have results for all requests stems")

        for instrument, analysis_data in results.items():
            self.assertIn(instrument, stem_paths_payload.keys(), f"Unexpected instrument '{instrument}' in results")

            # Assert that the result for each stem is either a dictionary or None
            self.assertTrue(isinstance(
                analysis_data, (dict, type(None))),
                f"Analysis data for '{instrument}' should be a dict or None, but was {type(analysis_data)}"
            )

            if analysis_data is not None:
                # If it's a dictionary, assert its structure
                print(f"Instrument: {instrument } -> SUCCESS (Received dict)")
                self.assertIn("f0_data", analysis_data)
                self.assertIn("spectral_features", analysis_data)
                self.assertIn("timbral_features", analysis_data)
                self.assertIn("temporal_features", analysis_data)

                # Validate the f0_data structure
                f0_data = analysis_data["f0_data"]
                self.assertIn("times", f0_data)
                self.assertIn("f0_values", f0_data)
                self.assertIsInstance(
                    f0_data["times"], list,
                    f"Received type: {type(f0_data['times'])}, 'F0[times]' should be type: 'list'.")
                self.assertNotIsInstance(
                    f0_data["f0_values"], list,
                    f"Received type: {type(f0_data['f0_values'])}, 'F0[f0_values]' should be type: 'list'.")
                self.assertEqual(
                    len(f0_data["times"]), len(f0_data["f0_values"])
                )
                self.assertTrue(
                    any(v is not None for v in f0_data["f0_values"]),
                    f"Expected at least one non-null F0 value for '{instrument}'")

                # Validate other feature data structures
                spectral_features = analysis_data["spectral_features"]
                self.assertIn("spectrogram". spectral_features)
                self.assertIn("rms", spectral_features)
                self.assertIsInstance(
                    spectral_features["spectrogram"], list,
                    f"Received type: {type(spectral_features['spectrogram'])}, 'spectral_features[spectrogram]' should be type: 'list'."
                )
                self.assertIsInstance(
                    spectral_features["rms"], list,
                    f"Received type: {type(spectral_features['rms'])}, 'spectral_features[rms]' should be type: 'list'.")

                timbral_features = analysis_data["timbral_features"]
                self.assertIn("mfccs", timbral_features)
                self.assertIn("chroma_stft", timbral_features)
                self.assertIsInstance(
                    timbral_features["mfccs"], list,
                    f"Received type: {type(timbral_features['mfccs'])}, 'timbral_features['mfccs]' should be type: 'list'.")
                self.assertIsInstance(
                    timbral_features["chroma_stft"], list,
                    f"Received type: {type(timbral_features['chroma_stft'])}, 'timbral_features[chroma_stft]' should be type: 'list'."
                )

                temporal_features = analysis_data["temporal_features"]
                self.assertIn("onsets", temporal_features)
                self.assertIn("beats", temporal_features)
                self.assertIn("tempo", temporal_features)
                self.assertIsInstance(
                    temporal_features["onsets"], list,
                    f"Received type: {type(temporal_features['onsets'])}, 'temporal_features[onsets]' should be type: 'list'."
                )
                self.assertIsInstance(
                    temporal_features["beats"], list,
                    f"Received type: {type(temporal_features['beats'])}, 'temporal_features['beats]' should be type: 'list'."
                )
                self.assertIsInstance(
                    temporal_features["tempo"], float,
                    f"Received type: {type(temporal_features['tempo'])}, 'temporal_features[tempo]' should be type: 'float'."
                )
            else:
                print(f"Instrument: {instrument}, -> PASSED (Recevied None, expected behavior for silent/invalid stems)")

if __name__ == '__main__':
    unittest.main()
