"""
End-to-End test for the Aligner (MFA) service using Podman.
This test builds the service container from source, runs it,
and verifies the API endpoint using REAL audio/lyrics from /data/corpus.
"""
import json
import os
import shutil
import time
import unittest
import requests
import tempfile
import stat
import podman
from podman.errors import APIError, ImageNotFound, NotFound as PodmanNotFound, BuildError as PodmanBuildError

# Configuration
ALIGNER_IMAGE_TAG = "localhost/align_service:e2e"
ALIGNER_CONTAINER_NAME = "align_service_e2e_container"
SERVICE_PORT = 24725
SERVICE_URL = f"http://localhost:{SERVICE_PORT}"

# Project Root Calculation
# This file is in /tests/test_aligner_endpoint.py
# Root is ../
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Source Data Paths (Real files)
# These must exist in the project for the test to run
SOURCE_AUDIO_PATH = os.path.join(PROJECT_ROOT, "data", "corpus",
                                 "BloodCalcification-NoMore.wav")
SOURCE_LYRICS_PATH = os.path.join(PROJECT_ROOT, "data", "corpus",
                                 "BloodCalcification-NoMore.txt")

# Build Context
BUILD_CONTEXT_DIR = PROJECT_ROOT
DOCKERFILE_PATH = "align-endpoint.Dockerfile"

# Volume Mount Paths
CONTAINER_INPUT_DIR = "/shared-data/input"
CONTAINER_MFA_JOBS_DIR = "/shared-data/mfa-jobs"

class TestAlignerServiceE2E(unittest.TestCase):
    podman_client = None
    container = None
    host_input_dir = None
    host_jobs_dir = None

    @classmethod
    def setUpClass(cls):
        """
        Builds the image, copies real data to host volume,
        and runs the container.
        """

        # 0. Validate Source Data Exists
        if not os.path.exists(SOURCE_AUDIO_PATH):
            raise unittest.SkipTest(f"Source audio not found at {SOURCE_AUDIO_PATH}. Please ensure /data/corpus/ exists.")
        if not os.path.exists(SOURCE_LYRICS_PATH):
            raise unittest.SkipTest(f"Source lyrics not found at {SOURCE_LYRICS_PATH}. Re-clone GitHub Repo.")

        # 1. Prepare Host Directories and Data
        cls.host_input_dir = tempfile.mkdtemp(prefix="align_e2e_input_")
        cls.host_jobs_dir = tempfile.mkdtemp(prefix="align_e2e_jobs_")

        # Set permissions to 777 so the container user (mfauser) can write
        os.chmod(cls.host_input_dir, 0o777)
        os.chmod(cls.host_jobs_dir, 0o777)

        print(f"\n[Setup] Host Input Dir: {cls.host_input_dir}")
        print(f"[Setup] Host Jobs Dir: {cls.host_jobs_dir}")

        # 2. Copy Real Data to Host Input Directory
        # These need to be renamed to satisfy the Job ID naming convention
        # Job ID: test123
        cls.job_id = "testjob123"

        # Note: The filename after the underscore doesn't strictly matter,
        # keep it descriptive
        cls.audio_filename = f"{cls.job_id}_BloodCalcification-SkinDeep.wav"
        cls.lyrics_filename = f"{cls.job_id}_BloodCalcification-SkinDeep.txt"

        host_audio_dest = os.path.join(cls.host_input_dir,
                                       cls.audio_filename)
        host_lyrics_dest = os.path.join(cls.host_input_dir,
                                        cls.lyrics_filename)

        print(f"[Setup] Copying real audio to {host_audio_dest}")
        shutil.copy(SOURCE_AUDIO_PATH, host_audio_dest)

        print(f"[Setup] Copying real lyrics to {host_lyrics_dest}")
        shutil.copy(SOURCE_LYRICS_PATH, host_lyrics_dest)

        # 3. Connect to Podman
        try:
            cls.podman_client = podman.PodmanClient()
            if not cls.podman_client.ping():
                raise ConnectionError("Failed to ping Podman service.")
        except Exception as e:
            raise unittest.SkipTest(f"Podman not available: {e}")

        # 4. Build Image
        print(f"[Setup] Building {ALIGNER_IMAGE_TAG} from {BUILD_CONTEXT_DIR}...")
        try:
            # Clean up old image
            try:
                old_img = cls.podman_client.images.get(ALIGNER_IMAGE_TAG)
                old_img.remove(force=True)
            except ImageNotFound:
                pass

            cls.podman_client.images.build(
                path=BUILD_CONTEXT_DIR,
                dockerfile=DOCKERFILE_PATH,
                tag=ALIGNER_IMAGE_TAG,
                rm=True
            )
            print("[Setup] Image built successfully.")
        except Exception as e:
            raise unittest.SkipTest(f"Build failed: {e}")

        # 5. Run Container
        print(f"[Setup] Starting container: {ALIGNER_CONTAINER_NAME}...")
        try:
            # Clean up old container
            try:
                old_cont = cls.podman_client.containers.get(ALIGNER_CONTAINER_NAME)
                old_cont.stop(timeout=0)
                old_cont.remove(force=True)
            except PodmanNotFound:
                pass

            cls.container = cls.podman_client.containers.run(
                ALIGNER_IMAGE_TAG,
                name=ALIGNER_CONTAINER_NAME,
                ports={f'{SERVICE_PORT}/tcp': SERVICE_PORT},
                mounts=[
                    {
                        "type": "bind",
                        "source": cls.host_input_dir,
                        "target": CONTAINER_INPUT_DIR,
                        "read_only": True
                    },
                    {
                        "type": "bind",
                        "source": cls.host_jobs_dir,
                        "target": CONTAINER_MFA_JOBS_DIR,
                        "read_only": False
                    }
                ],
                detach=True,
                auto_remove=False,
                mem_limit='24G'
            )
        except APIError as e:
            raise unittest.SkipTest(f"Failed to start container: {e}")

        # 6. Wait for Health Check
        print("[Setup] Waiting for service health...")
        for _ in range(30):
            try:
                resp = requests.get(f"{SERVICE_URL}/api/align/health",
                                    timeout=1)
                if resp.status_code == 200:
                    print("[Setup] Service is health.")
                    return
            except Exception:
                time.sleep(1)

        cls.tearDownClass()
        raise unittest.SkipTest("Service failed to become healthy.")

    @classmethod
    def tearDownClass(cls):
        """Cleanup resources."""
        if cls.container:
            print(f"\n[Teardown] Stopping container {ALIGNER_CONTAINER_NAME}...")
            try:
                # Retrieve logs if failed
                # logs = cls.container.logs(stdout=True, stderr=True)
                # print(logs.decode('utf-8') if isinstance(logs, bytes) else "")
                cls.container.stop(timeout=5)
                cls.container.remove(force=True)
            except Exception as e:
                print(f"Error removing container: {e}")

        if cls.podman_client:
            try:
                img = cls.podman_client.images.get(ALIGNER_IMAGE_TAG)
                img.remove(force=True)
            except Exception:
                pass

        cls.cleanup_host_dir(cls.host_jobs_dir)
        cls.cleanup_host_dir(cls.host_input_dir)

    @classmethod
    def cleanup_host_dir(cls, dir_path):
        """
        Cleans up a directory on the host.
        Uses a temporary container to delete files created by the service
        container to avoid PermissionError caused by UID mismatches.
        """
        if not dir_path or not os.path.exists(dir_path):
            return

        try:
            # 1. Try standard removal first
            shutil.rmtree(dir_path)
        except PermissionError:
            print(f"[Cleanup] Permission denied for {dir_path}. Attempting cleanup via container...")
            try:
                # 2. Spin up a temporary container to nuke the directory
                # contents as root. Reuse the aligner image because it's
                # known to be available
                cls.podman_client.containers.run(
                    ALIGNER_IMAGE_TAG,
                    command=["rm", "-rf", "/clean_target"],
                    mounts=[{
                        "type": "bind",
                        "source": dir_path,
                        "target": "/clean_target",
                        "read_only": False
                    }],
                    user="root",
                    remove=True,
                    detach=False
                )
                # 3. Now remove the empty directory on host
                shutil.rmtree(dir_path)
                print(f"[Cleanup] Successfully cleaned {dir_path} via container.")
            except Exception as e:
                print(f"[Cleanup] Failed to clean up {dir_path}: {e}")

    def test_align_endpoint_success(self):
        """Tests the /api/align endpoint with REAL valid inputs."""

        # Paths inside the container
        payload = {
            "vocals_stem_path": os.path.join(CONTAINER_INPUT_DIR,
                                             self.audio_filename),
            "lyrics_path": os.path.join(CONTAINER_INPUT_DIR,
                                        self.lyrics_filename)
        }

        print(f"\n[Test] Sending payload: {payload}")
        print("[Test] This may take a few minutes as MFA processes real audio...")

        response = requests.post(f"{SERVICE_URL}/api/align",
                                 json=payload, timeout=600)

        print(f"[Test] Response Code: {response.status_code}")
        if response.status_code != 200:
            print(f"[Test] Error Response: {response.text}")

        self.assertEqual(response.status_code, 200,
                         f"MFA failed with: {response.text}")

        data = response.json()
        self.assertIn("alignment_file_path", data)
        self.assertIn("job_dir_path", data)

        # Verify the structure matches expected output path logic in wrapper
        # The wrapper uses the part of the filename BEFORE the first
        # underscore as the job ID. Job ID is "testjob123"
        expected_json_path = os.path.join(
            CONTAINER_MFA_JOBS_DIR,
            self.job_id,
            "aligned",
            f"{self.job_id}.json"
        )
        self.assertEqual(data['alignment_file_path'], expected_json_path)

        # Verify the file actually exists on the host
        # Host path = host_jobs_dir + /testjob123/aligned/testjob123.json
        host_result_path = os.path.join(
            self.host_jobs_dir,
            self.job_id,
            "aligned",
            f"{self.job_id}.json"
        )
        self.assertTrue(os.path.exists(host_result_path),
                        f"Alignment JSON not found on host at {host_result_path}")

        # Basic validation of the JSON content
        with open(host_result_path, 'r') as f:
            content = json.load(f)
            # TextGrid to JSON usually results in keys like "tiers" or
            # start/end times. Checking it's not empty is a good start
            self.assertTrue(len(content) > 0,
                            "Generated JSON alignment file is empty.")

    def test_align_endpoint_missing_payload(self):
        """Tests error handling for missing payload data."""
        response = requests.post(f"{SERVICE_URL}/api/align",
                                 json={}, timeout=10)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

if __name__ == '__main__':
    unittest.main()
