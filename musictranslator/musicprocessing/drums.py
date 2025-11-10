"""
Uses librosa to determine drum hits then processes each onset
To determine
"""
import logging
import requests

logger = logging.getLogger(__name__)

DRUMS_SERVICE_URL = "http://drums-service:25941/api/analyze_drums"

def request_drum_analysis(drums_path):
    """Send a request to the drums analysis service"""
    logger.info(
        "Attemping to reach drums-service at: %s with drums track: %s",
        DRUMS_SERVICE_URL, drums_path
    )
    if not drums_path:
        logger.warning("request_drum_analysis called without a valid drums_path")
        return {"error": "No drums path provided for Drum analysis."}
    try:
        data = {"drums_path": drums_path}
        headers={'Content-Type': 'application/json'}
        response = requests.post(
            DRUMS_SERVICE_URL,
            json=data,
            headers=headers,
            timeout=1200
        )
        response.raise_for_status()

        drums_data = response.json()
        logger.info(
            "Successfully received drums analysis results"
        )
        return drums_data

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if http_err.response else None
        return {
            "error": f"HTTP error occurred calling Drums Service: {http_err} - Response: {http_err.response.text if http_err.response else 'No response text'}",
            "status_code": status_code
        }
    except requests.exceptions.ConnectionError as conn_err:
        return {"error": f"Connection error calling Drums Service: {conn_err}"}
    except requests.exceptions.Timeout as time_err:
        return {"error": f"Timeout calling Drums Service: {time_err}"}
    except requests.exceptions.RequestException as req_err:
        return {"error": f"Request exception calling Drums Service: {req_err}"}
    except ValueError as json_err:
        return {"error": f"Error decoding JSON response from Drums Service: {json_err}"}

