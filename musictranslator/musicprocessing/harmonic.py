"""
Client module to request comprehensive analysis of all non-percussion
instruments from the Harmonic microservice
for various audio stems.
Librosa repository: https://github.com/librosa/librosa
Licensed under the ISC License
"""
import logging
import requests

logger = logging.getLogger(__name__)

HARMONIC_SERVICE_URL = "http://harmonic-service:20006/api/analyze_harmonic"

def request_harmonic_analysis(stem_paths: dict, full_track_path: str):
    """
    Requests comprehensive analysis from the Harmonic service for the provided stems.

    Args:
        stem_paths (dict): A dictionary where keys are instrument names
                           (e.g., 'vocals', 'bass', etc.) and values are
                           the absolute paths to the corresponding audio
                           stem files. This typicallys comes from the
                           `separate_audio` output.
        full_track_path (str): The absolute path to the original, full
                               audio file.

    Returns:
        dict: A dictionary containing the harmonic analysis results,
              (or None if analysis failed for a stem or no
              audio detected). Returns a dictionary with an 'error'
              key if the request to  the harmonic service fails or the
              service itself indicates an error.
    """
    if not isinstance(stem_paths, dict) or not stem_paths:
        logger.warning("request_harmonic_analysis called with empty or invalid stem_paths")
        return {"error": "No stem paths provided for Harmonic analysis."}

    if not isinstance(full_track_path, str) or not full_track_path:
        logger.warning("request_harmonic_analysis called with an empty or invalid full_track_path")
        return {
            "error": "No full track path provided for Harmonic analysis."
        }

    payload_stems = {}
    for instrument, path in stem_paths.items():
        # Standardize instrument name for filtering (optional, but good practice)
        instrument_lower = instrument.lower()
        if instrument_lower == 'drums':
            logger.info("Skipping Harmonic analysis for 'drums' stem: %s", path)
            continue
        # Only include relevant stems that have a valid path
        if path and isinstance(path, str) and instrument_lower in [
            'vocals',
            'bass',
            'guitar',
            'piano',
            'other'
        ]:
            # Use original instrument name as key
            payload_stems[instrument] = path
        else:
            logger.warning(
                "Skipping Harmonic analysis for instrument '%s' due to invalid/missing path ('%s') or irrelevant type.",
                instrument,
                path
            )

    if not payload_stems:
        logger.warning("No valid/relevant stems found to send for Harmonic analysis after filtering.")
        # Return an empty dict or a specific indicator,
        # an error dict might be too strong
        # if it's acceptable for no F0 analysis to occur.
        # Let's return a dict that can be identified as "no analysis performed"
        return {"info": "No relevant stems were submitted for Harmonic analysis."}

    data_to_send = {
        "stem_paths": payload_stems,
        "full_track_path": full_track_path
    }
    headers = {'Content-Type': 'application/json'}

    logger.info(
        "Sending request to Harmonic service (%s) for stems: %s",
        HARMONIC_SERVICE_URL,
        list(payload_stems.keys())
    )
    logger.debug("Payload for Harmonic service: %s", data_to_send)

    try:
        response = requests.post(
            HARMONIC_SERVICE_URL,
            json=data_to_send,
            headers=headers,
            timeout=1200
        )
        response.raise_for_status()

        harmonic_results = response.json()
        # The harmonic service should return a dictionary containing the url
        # for the saved results file
        logger.info(
            "Successfully received harmonic analysis results"
        )
        return harmonic_results

    except requests.exceptions.HTTPError as http_err:
        return {
            "error": f"HTTP error occurred calling Harmonic service: {http_err} - Response: {http_err.response.text if http_err.response else 'No response text'}"
        }
    except requests.exceptions.ConnectionError as conn_err:
        return {"error": f"Connection error calling Harmonic service: {conn_err}"}
    except requests.exceptions.Timeout as time_err:
        return {"error": f"Timeout calling Harmonic service: {time_err}"}
    except requests.exceptions.RequestException as req_err:
        return {"error": f"Request exception calling Harmonic service: {req_err}"}
    except ValueError as json_err:
        return {"error": f"Error decoding JSON response from harmonic service: {json_err}"}
