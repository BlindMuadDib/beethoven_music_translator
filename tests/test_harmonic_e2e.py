"""
End-to-End test for the harmonic service using Podman.
This test builds the service container, runs it, and then sends a real
API request to a running container to validate its behavior.
"""

import unittest
import shutil
import os
import math
import time
import json
import uuid
import tempfile
import requests
import podman
from podman.errors import APIError, ImageNotFound, NotFound as PodmanNotFound, BuildError as PodmanBuildError
from urllib.parse import quote
from musictranslator.harmonic_service.app import MAX_CPU_WORKERS

# Configuration for the E2E test
HARMONIC_SERVICE_IMAGE_TAG = "harmonic_service:latest"
HARMONIC_SERVICE_CONTAINER_NAME = "harmonic_service_container"
SERVICE_URL = "http://localhost:20006"

# Project root
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)

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
HOST_STEM_DIR = os.path.join(PROJECT_ROOT, "data", "separator_output",
                             "htdemucs_6s",
                             "Depressed-RichardOmelette")
# Host directory for the full track file
HOST_FULL_TRACK_DIR = os.path.join(PROJECT_ROOT, "data", "audio")

# Path where the stems will be mounted inside the container
CONTAINER_STEM_DIR = "/test_audio_stems"
# Path where the full track directory will be mounted inside the container
CONTAINER_FULL_TRACK_DIR = "/test_audio_full_track"
CONTAINER_RESULTS_DIR = "/shared-data/results"

# Stems to be tested (filenames in HOST_STEM_DIR)
STEM_FILES = [
    "bass.wav", "guitar.wav", "piano.wav",
    "other.wav", "vocals.wav"
]
FULL_TRACK_FILENAME = "Depressed-RichardOmelette.wav"
FULL_TRACK_FILE_HOST_PATH = os.path.join(HOST_FULL_TRACK_DIR,
                               FULL_TRACK_FILENAME)

class TestHarmonicServiceE2EPodman(unittest.TestCase):
    podman_client = None
    container = None
    host_results_dir = None

    @classmethod
    def setUpClass(cls):
        """Builds the Podman image and starts the container"""
        if not os.path.exists(HOST_STEM_DIR):
            raise unittest.SkipTest(f"Host stem directory for E2E tests not found: {HOST_STEM_DIR}")
        for stem_file in STEM_FILES:
            if not os.path.exists(os.path.join(HOST_STEM_DIR, stem_file)):
                raise unittest.SkipTest(f"Required stem file not found: {os.path.join(HOST_STEM_DIR, stem_file)}")

        if not os.path.exists(FULL_TRACK_FILE_HOST_PATH):
            raise unittest.SkipTest(
                f"Required full track file not found: {FULL_TRACK_FILE_HOST_PATH}"
            )

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

        # Create a temporary directory on the host to receive the
        # results
        cls.host_results_dir = tempfile.TemporaryDirectory()
        print(f"Results will be written to host directory: {cls.host_results_dir.name}")

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
                environment={"HARMONIC_CPU_WORKERS": "2"},
                volumes={
                    HOST_STEM_DIR: {
                        'bind': CONTAINER_STEM_DIR,
                        'mode': 'ro'
                    },
                    HOST_FULL_TRACK_DIR: {
                        'bind': CONTAINER_FULL_TRACK_DIR,
                        'mode': 'ro'
                    },
                    cls.host_results_dir.name: {
                        'bind': CONTAINER_RESULTS_DIR,
                        'mode': 'rw'
                    }
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
            # Try to print the logs if the test failed before deleting the
            # container
            print(f"--- Logs for container {cls.container.name} ---")
            try:
                logs = cls.container.logs(stdout=True, stderr=True)
                # The logs can be a single byte string or a list of strings
                if isinstance(logs, bytes):
                    print(logs.decode('utf-8', errors='ignore'))
                elif isinstance(logs, list):
                    for log_line in logs:
                        print(log_line.decode('utf-8', errors='ignore').strip())
            except APIError as e:
                print(f"Could not retrieve logs for container {cls.container.name}: {e}")
            print("--- End of logs ---")

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

        if cls.host_results_dir:
            print(f"Cleaning up host results directory: {cls.host_results_dir.name}")
            cls.host_results_dir.cleanup()

    def _assert_stems_analysis_results_valid(self,
                                             instrument_result):
        """
        Helper to check if a single analysis result dict for a stem
        is valid.
        """
        self.assertIsInstance(instrument_result, dict)
        self.assertIn("duration", instrument_result)
        self.assertIn("tempo", instrument_result)
        self.assertIn("beats", instrument_result)
        self.assertIn("onsets", instrument_result)

        self.assertIsInstance(instrument_result['duration'], float)
        self.assertIsInstance(instrument_result['tempo'], float)
        self.assertIsInstance(instrument_result['beats'], list)
        self.assertIsInstance(instrument_result['onsets'], list)
        self.assertTrue(len(instrument_result['beats']) > 0,
                        "Expected at least one beat")

    def _assert_full_track_analysis_results_valid(
        self,
        full_track_analysis_data
    ):
        """
        Helper to ckeck if the full track analysis data structure is
        valid.
        """
        self.assertIsInstance(full_track_analysis_data, dict)
        self.assertIn("duration", full_track_analysis_data)
        self.assertIn("tempo", full_track_analysis_data)
        self.assertIn("rms_overall", full_track_analysis_data)

        self.assertIsInstance(full_track_analysis_data["duration"],
                              float)
        self.assertIsInstance(full_track_analysis_data["tempo"],
                              float)
        self.assertIsInstance(full_track_analysis_data["rms_overall"],
                              dict)

        rms_overall = full_track_analysis_data["rms_overall"]
        self.assertIn("times", rms_overall)
        self.assertIn("values", rms_overall)
        self.assertIsInstance(rms_overall["times"], list)
        self.assertIsInstance(rms_overall["values"], list)
        self.assertTrue(len(rms_overall["times"]) > 0)
        self.assertEqual(len(rms_overall["times"]),
                         len(rms_overall["values"]))

    def _validate_slice_structure(self, slice_data, instrument_name):
        """
        Validates the structure and types of a single time slice from the
        NDJSON stream.
        """
        self.assertIsInstance(slice_data, dict,
                              f"Slice for '{instrument_name}' is not a dict.")

        expected_keys_and_types = {
            "time": float, "f0_data": float, "spectral_centroid": float,
            "spectral_bandwidth": float, "spectral_rolloff": float,
            "spectral_flatness": float, "rms": float, "mfccs": list,
            "chroma_stft": list, "spectrogram": list, "frequencies": list,
        }

        for key, expected_type in expected_keys_and_types.items():
            self.assertIn(key, slice_data,
                          f"Key '{key}' missing in stream slice for '{instrument_name}'")
            value = slice_data[key]
            # f0_data can be None if unvoiced
            if key == 'f0_data':
                self.assertTrue(isinstance(value, (expected_type, type(None))),
                                f"Value for '{key}' is not a {expected_type} or None for '{instrument_name}'")
            else:
                self.assertIsInstance(value, expected_type,
                                      f"Value for '{key}' is not a {expected_type} for '{instrument_name}'")

        # Additional content validation
        self.assertEqual(len(slice_data['mfccs']), 20,
                         f"MFCCs list should have 20 elements for '{instrument_name}'")
        self.assertEqual(len(slice_data['chroma_stft']), 12,
                         f"Chroma should have 12 elements for '{instrument_name}'")
        self.assertEqual(len(slice_data['spectrogram']), len(slice_data['frequencies']),
                         f"Spectrogram and Frequencies lists should have the same length for '{instrument_name}'")

    def test_analyze_all_e2e(self):
        """
        Tests the /api/analyze_harmonic endpoint of the containerized
        service using real audio stems and validates the full feature
        set. Waits for the result file, and validates its contents.
        """
        job_id = str(uuid.uuid4())
        full_track_filename_with_job_id = f"{job_id}_{FULL_TRACK_FILENAME}"

        # Define the source and destination paths on the HOST for
        # the temporary file
        source_track_path = FULL_TRACK_FILE_HOST_PATH
        temp_track_host_path = os.path.join(HOST_FULL_TRACK_DIR,
                                            full_track_filename_with_job_id)

        # This will be the path to the file INSIDE the container
        container_track_path = os.path.join(CONTAINER_FULL_TRACK_DIR,
                                            full_track_filename_with_job_id)

        stem_paths_payload = {}
        for stem_file in STEM_FILES:
            instrument_name = os.path.splitext(stem_file)[0]
            stem_paths_payload[instrument_name] = os.path.join(CONTAINER_STEM_DIR, stem_file)

        full_track_path_payload = os.path.join(
            CONTAINER_FULL_TRACK_DIR,
            full_track_filename_with_job_id
        )

        payload = {
            "full_track_path": container_track_path,
            "stem_paths": stem_paths_payload
        }

        try:
            # Create the temporary copy of the full track with the
            # job_id
            print(f"\nCreating temporary track file: {temp_track_host_path}")
            shutil.copyfile(source_track_path, temp_track_host_path
                            )
            # Send the request to the service
            print(f"Sending E2E request with job_id: {job_id}")
            response = requests.post(
                    f"{SERVICE_URL}/api/analyze_harmonic",
                    json=payload,
                    timeout=1200
            )

            # Check for 202 Accepted and valid URL in resposne
            self.assertEqual(response.status_code, 202, f"Expected 202 Accepted, got {response.status_code}. Response: {response.text}")
            results = response.json()
            self.assertIn("results_url", results)

            # Determine the expected file path on the host
            results_filename = os.path.basename(results["results_url"])
            expected_file_path = os.path.join(self.host_results_dir.name,
                                            results_filename)
            self.assertEqual(results_filename,
                            f"{job_id}_harmonic.json",
                            "Filename in URL should match the job ID.")

            # Wait for the results file to be written by the container
            results_data = None
            for i in range(60):
                if os.path.exists(expected_file_path):
                    print(f"Results file found at: {expected_file_path}")
                    with open(expected_file_path, 'r') as f:
                        results_data = json.load(f)
                    break
                time.sleep(1)

            self.assertIsNotNone(
                results_data,
                f"Test time out waiting for results file: {expected_file_path}"
            )

            # Validate the contents of the JSON file
            self.assertIn("full_track_analysis", results_data)
            self.assertIn("stem_analyses", results_data)
            self.assertIsInstance(results_data["stem_analyses"], dict)

            # Validate the full track analysis
            full_track_analysis_data = results_data["full_track_analysis"]
            self.assertIsNotNone(
                full_track_analysis_data,
                "Expected analysis for the full track but received None"
            )
            self._assert_full_track_analysis_results_valid(
                full_track_analysis_data
            )

            # Validate each stem's analysis
            stem_analyses_data = results_data["stem_analyses"]
            self.assertEqual(len(stem_analyses_data),
                            len(STEM_FILES),
                            "Should have results for all requested stems")
            for instrument, analysis_data in stem_analyses_data.items():
                self.assertIn(instrument, stem_paths_payload.keys(),
                            f"Unexpected instrument '{instrument}' in stem results")
                self.assertTrue(isinstance(
                    analysis_data, (dict, type(None))),
                    f"Analysis data for '{instrument}' should be a dict or None, but was {type(analysis_data)}"
                )

                if analysis_data is not None:
                    print(f"Instument: {instrument} -> SUCCESS (Received dict)")
                    self._assert_stems_analysis_results_valid(analysis_data)
                else:
                    print(f"Instrument: {instrument} -> PASSED (Received None, expected behavior for silent/invalid stems)")

            # --- Validate NDJSON Streaming Endpoints ---
            print("\n--- Starting NDJSON Stream Validation ---")
            for instrument, analysis_data in stem_analyses_data.items():
                print(f"\n--- [{instrument.upper()}] ---")
                if not analysis_data:
                    print(f"Skipping stream validation for '{instrument}' as it had no static analysis data")
                    continue

                # Calculate expected number of frames
                sr, hop_length = 22050, 512
                duration = analysis_data.get("duration", 0)
                expected_frames = math.floor((duration * sr) / hop_length) + 1
                print(f"Audio duration: {duration:.2f}s. Expected approx. {expected_frames} time slices.")

                # Construct the streaming URL
                container_stem_path = stem_paths_payload[instrument]
                encoded_stem_path = quote(container_stem_path)
                stream_url = f"{SERVICE_URL}/api/harmonic/stream/{job_id}_{instrument}.ndjson"
                print(f"Requesting stream from: {stream_url}")

                # Wait for the stream file to exist before requesting it
                expected_stream_file = os.path.join(
                    self.host_results_dir.name,
                    f"{job_id}_{instrument}.ndjson"
                )
                stream_file_found = False
                for _ in range(1200): # Wait up to 20 minutes
                    if os.path.exists(expected_stream_file):
                        stream_file_found = True
                        break
                    time.sleep(10)
                self.assertTrue(stream_file_found,
                                f"Stream file for {instrument} was not created in time.")

                # Fetch and validate the stream
                try:
                    stream_response = requests.get(stream_url, timeout=120,
                                                   stream=True)
                    print(f"Received response with status code: {stream_response.status_code}")
                    self.assertEqual(stream_response.status_code, 200)

                    lines = stream_response.text.strip().split('\n')
                    actual_frames = len(lines)
                    print(f"Received {actual_frames} time slices.")

                    # Assert frame count is within a reasonable tolerance
                    self.assertAlmostEqual(
                        actual_frames, expected_frames, delta=2,
                        msg=f"For '{instrument}', expected ~{expected_frames} frames, but got {actual_frames}"
                    )

                    # Validate the structure of a few slices
                    print("Validating structure of first, middle and last time slices...")
                    self._validate_slice_structure(json.loads(lines[0]),
                                                   instrument)
                    self._validate_slice_structure(
                        json.loads(lines[actual_frames // 2]),
                        instrument
                    )
                    self._validate_slice_structure(json.loads(lines[-1]),
                                                   instrument)
                    print(f"Stream validation for '{instrument}' PASSED!")

                except requests.exceptions.RequestException as e:
                    self.fail(f"Request for '{instrument}' stream failed: {e}")

        finally:
            # Clean up the temporary track and results files
            print("Cleaning up temporary files...")
            if os.path.exists(temp_track_host_path):
                os.remove(temp_track_host_path)
                print(f"Removed temporary track file: {temp_track_host_path}")
            if 'expected_file_path' in locals() and os.path.exists(expected_file_path):
                os.remove(expected_file_path)
                print(f"Cleaned up results file: {expected_file_path}")

if __name__ == '__main__':
    unittest.main()
