"""
Client module to request Fundamental Frequency analysis from the F0 microservice
for various audio stems.
Librosa repository: https://github.com/librosa/librosa
Licensed under the ISC License
"""
import logging
import requests

logger = logging.getLogger(__name__)

F0_SERVICE_URL = "http://f0-service:20006/analyze_f0"

def request_f0_analysis(stem_paths: dict):
    """
    Requests Fundamental Frequency (F0) analysis from the F0 service for the provided stems.

    Args:
        stem_paths (dict): A dictionary where keys are instrument names
                           (e.g., 'vocals', 'bass', etc.) and values are
                           the absolute paths to the corresponding audio
                           stem files. This typicallys comes from the
                           `separate_audio` output.

    Returns:
        dict: A dictionary containing the F0 analysis results, where keys
              are instrument names and values are lists of F0 values (or
              None if analysis failed for a stem or no F0 detected).
              Returns a dictionary with an 'error' key if the request to
              the F0 service fails or the service itself indicates an error.
    """
    if not isinstance(stem_paths, dict) or not stem_paths:
        logger.warning("request_f0_analysis called with empty or invalid stem_paths")
        return {"error": "No stem paths provided for F0 analysis."}

    payload_stems = {}
    for instrument, path in stem_paths.items():
        # Standardize instrument name for filtering (optional, but good practice)
        instrument_lower = instrument.lower()
        if instrument_lower == 'drums':
            logger.info("Skipping F0 analysis for 'drums' stem: %s", path)
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
                "Skipping F0 analysis for instrument '%s' due to invalid/missing path ('%s') or irrelevant type.",
                instrument,
                path
            )

    if not payload_stems:
        logger.warning("No valid/relevant stems found to send for F0 analysis after filtering.")
        # Return an empty dict or a specific indicator,
        # an error dict might be too strong
        # if it's acceptable for no F0 analysis to occur.
        # Let's return a dict that can be identified as "no analysis performed"
        return {"info": "No relevant stems were submitted for F0 analysis."}

    data_to_send = {"stem_paths": payload_stems}
    headers = {'Content-Type': 'application/json'}

    logger.info(
        "Sending request to F0 service (%s) for stems: %s",
        F0_SERVICE_URL,
        list(payload_stems.keys())
    )
    logger.debug("Payload for F0 service: %s", data_to_send)

    try:
        response = requests.post(
            F0_SERVICE_URL,
            json=data_to_send,
            headers=headers,
            timeout=1200
        )
        response.raise_for_status()

        f0_results = response.json()
        # The F0 service should directly return a dict like {"vocals": [...], "bass": [...], ... }
        # or an error dict from its own logic e.g. {"error": "some internal issue"}
        logger.info(
            "Successfully received F0 analysis results. Instruments processed: %s",
            list(f0_results.keys()) if isinstance(f0_results, dict) else 'Invalid response format'
        )
        return f0_results

    except requests.exceptions.HTTPError as http_err:
        return {
            "error": f"HTTP error occurred calling F0 service: {http_err} - Response: {http_err.response.text if http_err.response else 'No response text'}"
        }
    except requests.exceptions.ConnectionError as conn_err:
        return {"error": f"Connection error calling F0 service: {conn_err}"}
    except requests.exceptions.Timeout as time_err:
        return {"error": f"Timeout calling F0 service: {time_err}"}
    except requests.exceptions.RequestException as req_err:
        return {"error": f"Request exception calling F0 service: {req_err}"}
    except ValueError as json_err:
        return {"error": f"Error decoding JSON response from F0 service: {json_err}"}
