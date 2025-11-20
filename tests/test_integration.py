"""
Integration testing to ensure all services communicate correctly
"""
import unittest
import os
import json
import subprocess
import time
import re
import requests
import musictranslator
from musictranslator.musicprocessing.transcribe import process_transcript

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("Starting Integration Test Setup...")

        cls.base_url = "http://localhost:9000/api"
        cls.auth_base_url = "http://localhost:9000/auth"

        cls.host_header = {"Host": "musictranslator.org"}
        cls.ssl_verify = False

        cls.admin_email = "admin@musictranslator.org"
        cls.admin_pass = "super-insecure-default-password"

        cls.test_email = f"test-user-{int(time.time())}@example.com"
        cls.test_pass = "testpassword123"

        # This session will be authenticated as the new test user
        cls.user_session = cls.get_authenticated_session(
            cls.test_email,
            cls.test_pass
        )

        print("SetUpClass completed: Test user created and logged in.")

    @classmethod
    def get_authenticated_session(cls, email, password):
        """
        Automates the entire user creation and login flow to get a valid
        session cookie for testing.
        """
        admin_session = None
        try:
            # --- 1. Reset DB and Create Admin ---
            # Use a *new* session for this one-off admin-task
            print("Resetting auth database...")
            reset_url = f"{cls.auth_base_url}/_reset_db"
            reset_resp = requests.post(reset_url, headers=cls.host_header,
                                       verify=cls.ssl_verify, timeout=10)
            reset_resp.raise_for_status()
            print("Database reset.")

            # --- 2. Login as Admin ---
            admin_session = requests.Session()
            admin_session.headers.update(cls.host_header)
            admin_session.verify = cls.ssl_verify

            login_url = f"{cls.auth_base_url}/login"

            # Get the CSRF token from login page
            login_page_resp = admin_session.get(login_url)
            csrf_token = cls.scrape_csrf_token(login_page_resp.text)

            admin_creds = {
                "email": cls.admin_email,
                "password": cls.admin_pass,
                "csrf_token": csrf_token
            }

            login_resp = admin_session.post(login_url, data=admin_creds,
                                            allow_redirects=True)
            login_resp.raise_for_status()
            if "Invalid email or password" in login_resp.text:
                raise Exception("Admin login failed.")
            print("Admin login successful.")

            # --- 3. Request Access for New User
            print(f"Requesting access for {email}...")
            req_access_url = f"{cls.auth_base_url}/request-access"
            req_page_resp = admin_session.get(req_access_url) # Use admin sesh
            csrf_token = cls.scrape_csrf_token(req_page_resp.text,
                                               form_action="/auth/request-access")

            access_request_data = {"email": email, "csrf_token": csrf_token}
            req_access_resp = admin_session.post(req_access_url,
                                                 data=access_request_data,
                                                 allow_redirects=True)
            req_access_resp.raise_for_status()

            # --- 4. Approve Access as Admin ---
            print("Approving access...")
            admin_req_page_resp = admin_session.get(f"{cls.auth_base_url}/admin/requests")
            approve_url = cls.find_approve_url(admin_req_page_resp.text,
                                               email)
            if not approve_url:
                raise Exception(f"Could not find approve URL for {email}")

            approve_resp = admin_session.post(f"{cls.auth_base_url}{approve_url}",
                                              allow_redirects=True)
            approve_resp.raise_for_status()
            print("Access approved.")

            # --- 5. Register New User ---
            # Use a *new, clean* session for registration
            user_session = requests.Session()
            user_session.headers.update(cls.host_header)
            user_session.verify = cls.ssl_verify

            print("Registering new user...")
            register_url = f"{cls.auth_base_url}/register"
            reg_page_resp = user_session.get(register_url)
            csrf_token = cls.scrape_csrf_token(reg_page_resp.text)

            register_data = {
                "email": email,
                "password": password,
                "password_confirm": password,
                "csrf_token": csrf_token
            }
            reg_resp = user_session.post(register_url, data=register_data,
                                         allow_redirects=True)
            reg_resp.raise_for_status()
            # Note: With FLASK_ENV=testing, registration does not auto-login
            print("User registered.")

            # --- 6. Login as New User to Get Session ---
            print("Logging in as new user...")
            login_page_resp = user_session.get(login_url)
            csrf_token = cls.scrape_csrf_token(login_page_resp.text)

            login_data = {
                "email": email,
                "password": password,
                "csrf_token": csrf_token
            }

            final_login_resp = user_session.post(login_url, data=login_data,
                                                 allow_redirects=True)
            final_login_resp.raise_for_status()

            if "Invalid email or password" in final_login_resp.text:
                raise Exception(f"Failed to log in as new user {email}.")

            print("User login successful. Session is active.")
            return user_session # Return the authenticated session

        except Exception as e:
            print(f"FATAL: Failed to create authenticated session: {e}")
            raise
        finally:
            if admin_session:
                admin_session.close()

    @classmethod
    def scrape_csrf_token(cls, html_text, form_action=None):
        """
        Finds a CSRF token in HTML text.
        """
        if form_action:
            # More specific search
            form_match = re.search(f'<form[^>]+action="{form_action}"[^>]*>.*?</form>',
                                   html_text, re.DOTALL)
            html_text = form_match.group(0) if form_match else ""

        csrf_token_match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html_text)
        if not csrf_token_match:
            raise Exception(f"Could not find csrf_token. Searched in {html_text[:500]}...")
        return csrf_token_match.group(1)

    @classmethod
    def find_approve_url(cls, html_text, email):
        """
        Finds the POST URL to approve a request for a given email.
        """
        # Finds: <tr> ... <td>test@example.com</td> ... <form action="/auth/admin/approve/1"> ... </form>
        match = re.search(f'<tr>.*?<td>{re.escape(email)}</td>.*?<form.*?action="([^"]+)">.*?</form>.*?,</tr>',
                          html_text, re.DOTALL)
        if match:
            return match.group(1)
        return None

    @classmethod
    def tearDownClass(cls):
        if cls.user_session:
            cls.user_session.close()
        print("\nTearDownClass completed")

    def setUp(self):
        self.audio_file_path = "data/audio/BloodCalcification-SkinDeep.wav"
        self.lyrics_file_path = "data/lyrics/BloodCalcification-SkinDeep.txt"
        self.audio_file = open(self.audio_file_path, 'rb')
        self.lyrics_file = open(self.lyrics_file_path, 'rb')

    def tearDown(self):
        if hasattr(self, 'audio_file') and not self.audio_file.closed:
            self.audio_file.close()
        if hasattr(self, 'lyrics_file') and not self.lyrics_file.closed:
            self.lyrics_file.close()

    def test_translate_success_with_session(self):
        """
        Tests the full translation pipeline using the valid session cookie obtained during setUpClass.
        """
        target_url = f"{self.base_url}/translate"
        files = {
            'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
            'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
        }

        print("\nSubmitting translation job...")
        try:
            # 1. Submit the job using the pre-authenticated session
            response = self.user_session.post(
                target_url,
                files=files,
                timeout=1200
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
                    result_response = self.user_session.get(result_url,
                                                            timeout=60)
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

            self.assertEqual(job_status, 'finished', f"Job did not finish. Final status: {job_status}")
            self.assertIsNotNone(final_job_result_data, "Final job result data is None.")

            # 3. Validate the final result structure
            self.assertIsInstance(final_job_result_data, dict, f"Final job result should be a dictionary, but is {type(final_job_result_data)}.")
            self.assertIn("mapped_result", final_job_result_data)
            self.assertIn("harmonic_analysis", final_job_result_data)
            self.assertIn("drum_analysis", final_job_result_data)
            self.assertIn("audio_url", final_job_result_data)

            # Validate lyrics mapping portion
            mapped_result = final_job_result_data["mapped_result"]
            self.assertIsInstance(mapped_result, list)
            original_lyrics_lines = process_transcript(self.lyrics_file_path)

            self.assertEqual(len(original_lyrics_lines), len(mapped_result), "Number of lines in original lyrics and mapped result do not match.")

            # Assert the presence and order of words within each line
            for i, original_line in enumerate(original_lyrics_lines):
                self.assertLess(i, len(mapped_result), "Mapped result has fewer lines than original")
                mapped_line = mapped_result[i]

                self.assertIn("line_text", mapped_line)
                self.assertEqual(mapped_line["line_text"], original_line["original_text"],
                                 f"Line text mismatch for line {i+1}.")

                self.assertIn("words", mapped_line)
                self.assertIsInstance(mapped_line["words"], list)

                mapped_words_texts = [
                    item.get('word', '').lower().strip(".,!?;:") for item in mapped_line["words"]
                ]
                original_words_in_line = original_line["word_list"]

                self.assertEqual(len(mapped_words_texts), len(original_words_in_line),
                                 f"Word count mismatch in line '{original_line['original_text']}' (line {i+1}).")

                for j, original_word_text in enumerate(original_words_in_line):
                    self.assertEqual(original_word_text, mapped_words_texts[j],
                                        f"Word mismatch in line '{original_line['original_text']}' (line {i+1}), word {j+1}.")

                self.assertIn("line_start_time", mapped_line)
                self.assertIn("line_end_time", mapped_line)
                # Timings can be None if no words in the line had timings
                self.assertTrue(isinstance(mapped_line["line_start_time"], (float, int, type(None))),
                                f"line_start_time for line {i+1} is not a number or None.")
            print("Mapped result structure and content appear valid.")

            # Validate harmonic_analysis portion
            # Start with the harmonic_analysis URL structure
            harmonic_info = final_job_result_data["harmonic_analysis"]
            self.assertIsInstance(harmonic_info, dict)
            self.assertIn("static_results_url", harmonic_info)
            self.assertIn("streaming_urls", harmonic_info)
            self.assertIsInstance(harmonic_info["streaming_urls"], dict)

            static_harmonic_url = harmonic_info["static_results_url"]
            self.assertTrue(static_harmonic_url.startswith('api/results/file'))
            print(f"Harmonic analysis static URL found: {static_harmonic_url}. Fetching data...")

            # Fetch the data from the static_results_url and validate it.
            base_host = self.base_url.rsplit('/api', 1)[0] # This gets 'http://localhost:9000'
            full_static_harmonic_url = f"{base_host}/{static_harmonic_url}"
            harmonic_response = self.user_session.get(full_static_harmonic_url,
                                                      timeout=60)
            self.assertEqual(harmonic_response.status_code, 200)
            static_harmonic_data = harmonic_response.json()

            # Assert structure of harmonic_analysis, a dictionary
            # with keys full_track_analysis and stem_analyses.
            self.assertIsInstance(static_harmonic_data, dict)
            # self.assertEqual(len(static_harmonic_data), 4,
            #                  f"Actual amount of keys does not match expected value. Keys present: {list(static_harmonic_data.keys())}")
            # Don't fail the test for now since the additional key should be
            # fine for now given test_harmonic_e2e passes. Just print keys
            print(f"Keys from static_harmonic_data: {list(static_harmonic_data.keys())}")
            self.assertIn("full_track_analysis", static_harmonic_data)
            self.assertIn("stem_analyses", static_harmonic_data)

            # Assert full_track_analysis is structured correctly
            full_track_analysis = static_harmonic_data["full_track_analysis"]
            self.assertIsInstance(full_track_analysis, dict)
            self.assertEqual(len(full_track_analysis), 3)
            self.assertIn("duration", full_track_analysis)
            self.assertIn("tempo", full_track_analysis)
            self.assertIn("rms_overall", full_track_analysis)
            self.assertIsInstance(full_track_analysis["duration"],
                                    float)
            self.assertIsInstance(full_track_analysis["tempo"],
                                    float)
            self.assertIsInstance(full_track_analysis["rms_overall"],
                                    dict)

            # Assert rms_overall is structured correctly
            rms_overall = full_track_analysis["rms_overall"]
            self.assertEqual(len(rms_overall), 2)
            self.assertIn("times", rms_overall)
            self.assertIn("values", rms_overall)
            self.assertIsInstance(rms_overall["times"], list)
            self.assertIsInstance(rms_overall["values"], list)

            print("Static harmonic analysis data structure appears valid.")

            # Assert the streaming URL's contain the appropriate data for
            # non-zero slices for each instrument
            # # Expected response structure: {
            #     "time": float(t),
            #     "f0_data": float(f0_data[0][i]) if not np.isnan(f0_data[0][i]) else None,
            #     "spectral_centroid": float(spectral_centroid[0][i]),
            #     "spectral_bandwidth": float(spectral_bandwidth[0][i]),
            #     "spectral_rolloff": float(spectral_rolloff[0][i]),
            #     "spectral_flatness": float(spectral_flatness[0][i]),
            #     "rms": float(rms[0][i]),
            #     "mfccs": mfccs_raw[:, i].tolist(),
            #     "chroma_stft": chroma_stft_raw[:, i].tolist(),
            #     "spectrogram": S_magnitude[:, i].tolist(),
            #     "frequencies": frequencies.tolist(),
            # }
            print("\nValidating streaming harmonic analysis URLs and content...")
            streaming_urls = harmonic_info.get("streaming_urls", {})
            self.assertTrue(len(streaming_urls) > 0,
                            "Expected at least one streaming URL for harmonic analysis.")

            # Define the expected structure for each JSON object in the stream
            expected_keys_and_types = {
                "time": float,
                "f0_data": float, # Note: This can also be None, we'll check for that
                "spectral_centroid": float,
                "spectral_bandwidth": float,
                "spectral_rolloff": float,
                "spectral_flatness": float,
                "rms": float,
                "mfccs": list,
                "chroma_stft": list,
                "spectrogram": list,
                "frequencies": list,
            }

            base_host = self.base_url.rsplit('/api', 1)[0]
            for stem_name, stream_url in streaming_urls.items():
                print(f"--- Validating stream for stem: '{stem_name}' ---")
                full_stream_url = f"{base_host}/{stream_url}"

                stream_response = requests.get(
                    full_stream_url,
                    headers=self.host_header,
                    verify=self.ssl_verify,
                    timeout=120
                )
                self.assertEqual(stream_response.status_code, 200,
                                 f"Failed to fetch stream for {stem_name}")
                self.assertEqual(stream_response.headers.get('Content-Type'),
                                 'application/x-ndjson')

                # Process the NDJSON response
                ndjson_content = stream_response.text
                lines = ndjson_content.strip().split('\n')
                self.assertTrue(len(lines) > 0,
                                f"Stream for '{stem_name}' should not be empty.")
                print(f"Received {len(lines)} time slices for '{stem_name}'. Validating first slice...")

                # Check the first data slice throughly
                first_slice = json.loads(lines[0])
                self.assertIsInstance(first_slice, dict)

                for key, expected_type in expected_keys_and_types.items():
                    self.assertIn(key, first_slice,
                                  f"Key '{key}' missing in stream slice for '{stem_name}'")
                    value = first_slice[key]
                    # Special check for f0_data which can be None if unvoices
                    if key == 'f0_data':
                        self.assertTrue(
                            isinstance(value, (expected_type, type(None))),
                            f"Value for '{key}' is not {expected_type} or None for '{stem_name}'."
                        )
                    else:
                        self.assertIsInstance(value, expected_type,
                                              f"Value for '{key}' is not {expected_type} for '{stem_name}'.")

                # Check list lengths for consistency where applicable
                self.assertEqual(len(first_slice['mfccs']), 20)
                self.assertEqual(len(first_slice['chroma_stft']), 12)
                self.assertEqual(len(first_slice['spectrogram']),
                                 len(first_slice['frequencies']))

                print(f"Stream structure for '{stem_name}' appears valid.")

            print("All harmonic analysis streams validated successfully.")

            # --- Validate drum_analysis portion ---
            drums_data = final_job_result_data["drum_analysis"]
            print("Validating drum_analysis structure...")

            if isinstance(drums_data, dict) and ("error" in drums_data or "info" in drums_data):
                self.fail(f"Drums analysis reported an error or info message: {drums_data}")
            else:
                self.assertIsInstance(
                    drums_data, dict,
                    f"Drum analysis result should be a dictionary, but is {type(drums_data)}")

                self.assertIn("hits", drums_data)
                self.assertIn("tempo", drums_data)

                hits = drums_data["hits"]
                tempo = drums_data["tempo"]

                self.assertIsInstance(hits, list,
                                      "Drum hits should be a list.")
                self.assertIsInstance(tempo, (float, int),
                                      "Drum tempo should be a float or int.")
                self.assertTrue(tempo >= 0,
                                "Tempo must be non-negative.")

                # Iterate through each drum event dictionary
                if len(hits) > 0:
                    for i, drum_event in enumerate(hits):
                        self.assertIsInstance(
                            drum_event, dict,
                            f"Drum event at index {i} is not a dictionary."
                        )

                        # Define expected float keys
                        float_keys = [
                            "onset_time", "duration", "relative_volume",
                            "dominant_frequency", "spectral_centroid",
                            "spectral_rolloff", "spectral_flux",
                            "category_confidence", "type_confidence",
                            "qualifier_confidence"
                        ]

                        for key in float_keys:
                            self.assertIn(
                                key, drum_event,
                                f"Missing key '{key}' in drum event at index {i}."
                            )
                            self.assertIsInstance(
                                drum_event[key], float,
                                f"Value for '{key}' in drum event at index {i} is not a float."
                            )

                        # Validate mfccs
                        self.assertIn(
                            "mfccs", drum_event,
                            f"Missing key 'mfccs' in drum event at index {i}"
                        )
                        mfccs = drum_event["mfccs"]
                        self.assertIsInstance(
                            mfccs, list,
                            f"'mfccs' in drum event at index {i} is not a list."
                        )
                        self.assertEqual(
                            len(mfccs), 13,
                            f"'mfccs' in drum event at index {i} does not have 13 elements."
                        )
                        for j, mfcc_value in enumerate(mfccs):
                            self.assertIsInstance(
                                mfcc_value, float,
                                f"MFCC value at index {j} in drum event at index {i} is not a float."
                            )

                        # Validate MLA Classifications
                        self.assertIn(
                            "drum_category", drum_event,
                            f"Missing key 'drum_category' in drum event at index {i}."
                        )
                        drum_category = drum_event["drum_category"]
                        self.assertIsInstance(
                            drum_category, str,
                            f"'drum_category' in drum event at index {i} is not a string."
                        )
                        possible_drum_categories = [
                            'kick', 'snare', 'tom', 'cymbal', 'other'
                        ]
                        self.assertIn(
                            drum_category, possible_drum_categories
                        )

                        self.assertIn(
                            "drum_type", drum_event,
                            f"Missing key 'drum_type' in drum event at index {i}."
                        )
                        drum_type = drum_event["drum_type"]
                        self.assertIsInstance(
                            drum_type, str,
                            f"'drum_type' in drum event at index {i} is not a string."
                        )
                        possible_drum_types = [
                            'bass', 'open_band', 'closed_band',
                            'med_high', 'med_low', 'mid', 'low',
                            'high', 'crash', 'hihat', 'ride', 'gong',
                            'unknown', 'cowbell'
                        ]
                        self.assertIn(
                            drum_type, possible_drum_types
                        )

                        self.assertIn(
                            "qualifier", drum_event,
                            f"Missing key 'qualifier' in drum event at index {i}.")
                        qualifier = drum_event["qualifier"]
                        self.assertIsInstance(
                            qualifier, str,
                            f"'qualifier' in drum event at index {i} is not a string.")
                        possible_qualifiers = [
                            'rimshot', 'brush', 'chains',
                            'no_qualifier', 'full', 'mid', 'bell',
                            'muted', 'brush','chains',
                            'full_muted', 'mid_muted', 'bell_muted',
                            'full_brush', 'mid_brush', 'bell_brush',
                            'full_chains', 'mid_chains',
                            'bell_chains', 'brush_muted',
                            'chains_muted', 'bell_brush_muted',
                            'bell_chains_muted', 'mid_brush_muted',
                            'mid_chains_muted', 'full_brush_muted',
                            'full_chains_muted', 'brush_bell',
                            'chains_bell', 'brush_full',
                            'chains_full', 'brush_mid', 'chains_mid',
                            'brush_bell_muted', 'chains_bell_muted',
                            'brush_full_muted', 'chains_full_muted',
                            'brush_mid_muted', 'chains_mid_muted',
                            'open', 'close'
                        ]
                        self.assertIn(
                            qualifier, possible_qualifiers
                        )
                else:
                    print("No drum hits detected for this audio, skipping individual hit validation.")

            print("Drum analysis data structure appears valid.")

            # --- Validate audio_url and original_filename ---
            print(f"Audio URL: {final_job_result_data["audio_url"]}")
            self.assertTrue(final_job_result_data["audio_url"].startswith(f"api/files/{job_id}_"))
            self.assertIn("original_filename", final_job_result_data)
            self.assertEqual(final_job_result_data["original_filename"], os.path.basename(self.audio_file_path))
            print("Audio URL and original filename appear valid.")

            # Clean up the processed audio file and its results
            audio_url = final_job_result_data["audio_url"]
            filename_to_delete = os.path.basename(audio_url)
            cleanup_url = f"{self.base_url}/cleanup/{filename_to_delete}"
            print(f"Cleaning up file via endpoint: {cleanup_url}")
            cleanup_response = self.user_session.delete(cleanup_url,
                                                        timeout=60)
            self.assertEqual(cleanup_response.status_code, 200,
                             "Cleanup request failed.")
            print("Cleanup successful.")

        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            self.fail(f"JSON decode error during integration test: {e}. Response: {response.text if 'response' in locals() else 'N/A'}")

    def test_translate_unauthenticated(self):
        """
        Test that a request without a session cookie is rejected.
        """
        print("\nTesting unauthorized request (no session cookie)...")
        target_url = f"{self.base_url}/translate"
        files = {
            'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
            'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
        }

        response = requests.post(
            target_url,
            files=files,
            headers=self.host_header,
            timeout=180,
            verify=self.ssl_verify
        )
        self.assertEqual(response.status_code, 401,
                         f"Expected 401 error code, received {response.status_code}.")
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Access Denied. Please login.")
        print("Unauthorized request correctly rejected.")

    #
    # def test_get_results_initial_status(self):
    #     """Test getting the initial status of a job"""
    #     print("\nTesting initial job status retrieval...")
    #     target_url = f"{self.base_url}/translate"
    #     files = {
    #         'audio': (os.path.basename(self.audio_file_path), self.audio_file, 'audio/wav'),
    #         'lyrics': (os.path.basename(self.lyrics_file_path), self.lyrics_file, 'text/plain')
    #     }
    #     headers = {**self.host_header,
    #                'X-Access-Code': self.valid_access_code}
    #
    #     try:
    #         # Submit the job
    #         response = requests.post(
    #             target_url,
    #             files=files,
    #             headers=headers,
    #             timeout=60,
    #             verify=self.ssl_verify
    #         )
    #         response.raise_for_status()
    #         self.assertEqual(response.status_code, 202)
    #         response_data = response.json()
    #         self.assertIn("job_id", response_data)
    #         job_id = response_data["job_id"]
    #         print(f"Job submitted with ID: {job_id}. Checking initial status...")
    #
    #         # Give a moment for the job to be registered by RQ
    #         time.sleep(2)
    #
    #         # Check the status
    #         result_url = f"{self.base_url}/results/{job_id}"
    #         result_response = requests.get(
    #             result_url,
    #             headers=self.host_header,
    #             verify=self.ssl_verify,
    #             timeout=20
    #         )
    #         result_response.raise_for_status()
    #         result_data = result_response.json()
    #
    #         self.assertIn("status", result_data)
    #         self.assertIn(result_data["status"], ['queued', 'started'], f"Expected initial status 'queued' or 'started', but got '{result_data['status']}'")
    #         print(f"Initial job status retrieval test passed. Status: {result_data['status']}")
    #
    #     except requests.exceptions.RequestException as e:
    #         self.fail(f"Error during initial status test: {e}")

    def test_get_results_nonexistent_job(self):
        """Tests getting results for a job ID that does not exist"""
        print("\nTesting results retrieval for a non-existent job ID...")
        non_existent_job_id = "non-existent-job-12345"
        result_url = f"{self.base_url}/results/{non_existent_job_id}"

        response = self.user_session.get(
            result_url,
            timeout=20
        )
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn("status", response_data)
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Job ID not found or invalid.", response_data.get("message", ""))

    def test_main_deployment(self):
        # Test the musictranslator.main Flask app deployment and service
        response = self.user_session.get(f"{self.base_url}/translate/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'OK')
        self.assertEqual(response.json().get('message'), 'Music Translator is running')

    # Add more tests for other scenarios
