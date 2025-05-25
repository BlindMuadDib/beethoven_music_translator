"""
Integration testing to ensure all services communicate correctly
"""
import unittest
import os
import json
import subprocess
import time
import requests
import musictranslator
from musictranslator.musicprocessing.transcribe import process_transcript

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("Starting setUpClass...")
        result = subprocess.run(['kind', 'get', 'clusters'], capture_output=True, text=True)
        if "kind" not in result.stdout:
            raise Exception("KIND cluster is not running. Please run run_integration_test.sh first.")

        # Wait for pods to get ready with a timeout
        timeout = time.time() + 300
        print("Waiting for pods to become ready...")
        while time.time() < timeout:
            # Check readiness of deployments
            main_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/translator-deployment', '--timeout=0s'], capture_output=True).returncode == 0
            worker_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/translator-worker', '--timeout=0s'], capture_output=True).returncode == 0
            align_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/mfa-deployment', '--timeout=0s'], capture_output=True).returncode == 0
            separate_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/demucs-deployment', '--timeout=0s'], capture_output=True).returncode == 0
            f0_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/f0-deployment', '--timeout=0s'], capture_output=True).returncode == 0
            redis_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/redis', '--timeout=0s'], capture_output=True).returncode == 0
            nginx_ready = subprocess.run(['kubectl', 'wait', '--for=condition=available', 'deployment/nginx-deployment', '--timeout=0s'], capture_output=True).returncode == 0
            ingress_ready = subprocess.run(['kubectl', 'wait', '--namespace', 'ingress-nginx', '--for=condition=available', 'deployment/ingress-nginx-controller', '--timeout=0s'], capture_output=True).returncode == 0

            if main_ready and worker_ready and align_ready and separate_ready and redis_ready and nginx_ready and ingress_ready and f0_ready:
                try:
                    print("Checking health endpoints...")
                    main_health = requests.get("https://localhost/translate/health", headers={"Host": "musictranslator.org"}, verify=False, timeout=10)
                    align_health = requests.get("https://localhost/align/health", headers={"Host": "musictranslator.org"}, verify=False, timeout=10)
                    separate_health = requests.get("https://localhost/separate/health", headers={"Host": "musictranslator.org"}, verify=False, timeout=10)
                    f0_health = requests.get("https://localhost/f0/health", headers={"Host": "musictranslator.org"}, verify=False, timeout=10)

                    if main_health.status_code == 200 and align_health.status_code == 200 and separate_health.status_code == 200:
                        print("All health checks passed.")
                        break
                    else:
                        print(f"Health checks failed. Main: {main_health.status_code}, Align: {align_health.status_code}, Separate: {separate_health.status_code}. Retrying...")

                except requests.exceptions.RequestException as e:
                    print(f"Health check request failed: {e}. Retrying...")

            time.sleep(5)
        else:
            subprocess.run(['kubectl', 'get', 'pods'])
            raise Exception("Timeout waiting for pods to become ready")

        cls.base_url = "https://localhost"
        cls.host_header = {"Host": "musictranslator.org"}
        cls.ssl_verify = False

        print("SetUpClass completed")

    @classmethod
    def tearDownClass(cls):
        # No need to delete KIND cluster here, it's done in the bash script
        pass

    def setUp(self):
        self.audio_file_path = "data/audio/BloodCalcification-NoMore.wav"
        self.lyrics_file_path = "data/lyrics/BloodCalcification-NoMore.txt"
        self.audio_file = open(self.audio_file_path, 'rb')
        self.lyrics_file = open(self.lyrics_file_path, 'rb')

    def tearDown(self):
        if hasattr(self, 'audio_file') and not self.audio_file.closed:
            self.audio_file.close()
        if hasattr(self, 'lyrics_file') and not self.lyrics_file.closed:
            self.lyrics_file.close()

    def test_translate_success(self):
        target_url = f"{self.base_url}/translate?access_code="
        files = {
            'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
            'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
        }

        print("\nSubmitting translation job...")
        try:
            # 1. Submit the job
            response = requests.post(
                target_url,
                files=files,
                headers=self.host_header,
                timeout=1200,
                verify=self.ssl_verify
            )
            response.raise_for_status() # Raise HTTPError for bad responses
            self.assertEqual(response.status_code, 202)

            response_data = response.json()
            self.assertIn("job_id", response_data)
            job_id = response_data["job_id"]
            print(f"Job submitted successfully with ID: {job_id}. Polling results...")

            # 2. Poll for results
            result_url = f"{self.base_url}/results/{job_id}"
            polling_timeout_seconds = 1500
            polling_interval_seconds = 20

            start_polling_time = time.time()
            job_status = None
            final_job_result_data = None

            while time.time() - start_polling_time < polling_timeout_seconds:
                time.sleep(polling_interval_seconds)
                try:
                    result_response = requests.get(
                        result_url,
                        headers=self.host_header,
                        verify=self.ssl_verify,
                        timeout=30 # Timeout for polling request
                    )
                    result_response.raise_for_status()
                    result_data = result_response.json()
                    job_status = result_data.get("status")
                    progress_stage = result_data.get("progress_stage", "N/A")
                    print(f"Polling job {job_id}: Status = {job_status}, Stage = {progress_stage}")

                    if job_status == 'finished':
                        self.assertIn("result", result_data)
                        final_job_result_data = result_data["result"]
                        print("Job finished successfully. Validating result...")
                        break # Exit polling loop on success
                    elif job_status == 'failed':
                        self.fail(f"Translation job {job_id} failed. Details: {result_data.get('message', 'No message provided.')}")
                    # Continue polling if status is 'queued' or 'started'

                except requests.exceptions.RequestException as e:
                    print(f"Polling request failed for job {job_id}. Retrying...")
                except json.JSONDecodeError:
                    print(f"Failed to decode JSON from result endpoint for job {job_id}. Retrying...")

            if job_status != 'finished' or final_job_result_data is None:
                self.fail(f"Translation job {job_id} did not complete within the timeout. Final status: {job_status}")

            # 3. Validate the final result structure
            self.assertIsInstance(final_job_result_data, dict, f"Final job result should be a dictionary, but is {type(final_job_result_data)}.")

            # Validate lyrics mapping portion
            self.assertIn("mapped_result", final_job_result_data)
            mapped_result = final_job_result_data["mapped_result"]
            self.assertIsInstance(mapped_result, list)
            original_lyrics_lines = process_transcript(self.lyrics_file_path)

            self.assertEqual(len(original_lyrics_lines), len(mapped_result), "Number of lines in original lyrics and mapped result do not match.")

            # Assert the presence and order of words within each line
            for i, original_line in enumerate(original_lyrics_lines):
                if i < len(mapped_result):
                    mapped_line = mapped_result[i]
                    mapped_words_in_line = [item['word'].lower().strip(".,!?;:") for item in mapped_line]

                    self.assertEqual(len(original_line), len(mapped_words_in_line),
                                     f"Number of words in line {i+1} does not match.")

                    for j, original_word in enumerate(original_line):
                        if j < len(mapped_words_in_line):
                            self.assertEqual(original_word, mapped_words_in_line[j],
                                             f"Word mismatch in line {i+1}, position {j+1}: "
                                             f"Expected '{original_word}', got '{mapped_words_in_line[j]}'.")
                        else:
                            self.fail(f"Mapped result for line {i+1} is shorter than expected.")

            # Validate f0_analysis portion
            self.assertIn("f0_analysis", final_job_result_data)
            f0_data = final_job_result_data["f0_analysis"]

            # Check if F0 analysis reported an error or info message
            if isinstance(f0_data, dict) and ("error" in f0_data or "info" in f0_data):
                print(f"F0 Analysis part of the job reported: {f0_data}")
                # Consider failing the test here if error is present
            else:
                self.assertIsInstance(f0_data, dict)
                self.assertTrue(len(f0_data) > 0)

                expected_stems_for_f0 = ["vocals", "bass", "guitar", "piano", "other"]
                found_f0_stems = 0
                for stem_name, stem_f0_values, in f0_data.items():
                    self.assertIn(stem_name, expected_stems_for_f0)
                    if stem_f0_values is not None:
                        self.assertIsInstance(stem_f0_values, list)
                        if stem_f0_values:
                            self.assertTrue(all(isinstance(val, (int, float)) or val is None for val in stem_f0_values))

                    found_f0_stems +=1
                self.assertTrue(found_f0_stems > 0)
                print("F0 analysis data structure appears valid.")

        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")

    def test_translate_without_access_code(self):
        """Test no access granted to those without code"""
        target_url = f"{self.base_url}/translate"
        files = {
            'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
            'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
        }
        response = requests.post(
            target_url,
            files=files,
            headers=self.host_header,
            timeout=60,
            verify=self.ssl_verify
        )
        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Access Denied. Please provide a valid access code.")

    def test_get_results_initial_status(self):
        """Test getting the initial status of a job"""
        print("\nTesting initial job status retrieval...")
        target_url = f"{self.base_url}/translate?access_code="
        files = {
            'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
            'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
        }

        try:
            # Submit the job
            response = requests.post(
                target_url,
                files=files,
                headers=self.host_header,
                timeout=60,
                verify=self.ssl_verify
            )
            response.raise_for_status()
            self.assertEqual(response.status_code, 202)
            response_data = response.json()
            self.assertIn("job_id", response_data)
            job_id = response_data["job_id"]
            print(f"Job submitted with ID: {job_id}. Checking initial status...")

            # Give a moment for the job to be registered by RQ
            time.sleep(2)

            # Check the status
            result_url = f"{self.base_url}/results/{job_id}"
            result_response = requests.get(
                result_url,
                headers=self.host_header,
                verify=self.ssl_verify,
                timeout=20
            )
            result_response.raise_for_status()
            result_data = result_response.json()

            self.assertIn("status", result_data)
            self.assertIn(result_data["status"], ['queued', 'started'], f"Expected initial status 'queued' or 'started', but got '{result_data['status']}'")
            print(f"Initial job status retrieval test passed. Status: {result_data['status']}")

        except requests.exceptions.RequestException as e:
            self.fail(f"Error during initial status test: {e}")

    def test_get_results_nonexistent_job(self):
        """Tests getting results for a job ID that does not exist"""
        print("\nTesting results retrieval for a non-existent job ID...")
        non_existent_job_id = "non-existent-job-12345"
        result_url = f"{self.base_url}/results/{non_existent_job_id}"

        response = requests.get(
            result_url,
            headers=self.host_header,
            verify=self.ssl_verify,
            timeout=20
        )
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn("status", response_data)
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Job ID not found or invalid.", response_data.get("message", ""))

    def test_main_deployment(self):
        # Test the musictranslator.main Flask app deployment and service
        response = requests.get(
            f"{self.base_url}/translate/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'OK')
        self.assertEqual(response.json().get('message'), 'Music Translator is running')

    def test_align_deployment(self):
        # test the align deployment and service
        response = requests.get(
            f"{self.base_url}/align/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)

    def test_separator_deployment(self):
        # test the separator deployment and service
        response = requests.get(
            f"{self.base_url}/separate/health",
            headers=self.host_header,
            verify=self.ssl_verify
            )
        self.assertEqual(response.status_code, 200)
        # Not exposed so response is index.html

    # Add more tests for other scenarios
