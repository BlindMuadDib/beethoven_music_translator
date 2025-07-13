"""
Client module to request Volume analysis from the Volume microservice
for various audio stems and the song before stem separation.
Librosa repository: https://github.com/librosa/librosa
Licensed under the ISC License
"""
import logging
import requests

logger = logging.getLogger(__name__)

VOLUME_SERVICE_URL = "http://rms-service:39574/api/analyze_rms"

def request_volume_analysis(audio_data: dict):
    """
    Requests Volume analysis from the volume microservice
    for the provided audio file and audio stems.
    We are using RMS because it is an accurate measurement of
    volume in electronic media, and gives relative volume.
    Both total relative volume and individual instrument relative
    volume are captured for a more complete picture.

    Args:
        data (dict): A data dictionary whos keys are tracks to be analyzed ('song', 'bass', 'drums', etc.) and values are directory paths to the file on the PVC.

    Returns:
        A data dictionary where keys are "overall_rms" and
        "instruments." Instruments is a nested dictionary with
        keys who's values are a nested dictionary of the "rms_values".
        All "rms_values" are an array, where the first value
        represents the timestamp and the second number represents
        the RMS value at the given timestamp.
        example:
            {
            "overall_rms": [
                [0.00, 0.15],
                [0.02, 0.18],
                [0.04, 0.25],
            ],
            "instruments": {
                "bass": {
                    "rms_values": [
                        [0.00, 0.08],
                        [0.02, 0.09],
                        [0.04, 0.15],
                    ]
                },
                "drums": {
                    "rms_values": [
                        [0.00, 0.12],
                        [0.02, 0.14],
                        [0.04, 0.22],
                    ]
                },
                ...
            }
        }

    """

    if not isinstance(audio_data, dict) or not audio_data:
        logger.warning("requests_volume_analysis called with invalid or no data")
        return {"error": "No audio or stems provided for Volume analysis"}

    payload_data = {}
    for audio_file, path in audio_data.items():
        # Standardized input names
        audio_lower = audio_file.lower()
        # Only include valid paths
        if path and isinstance(path, str) and audio_lower in [
            "song",
            "bass",
            "drums",
            "guitar",
            "other",
            "piano",
            "vocals"
        ]:
            payload_data[audio_file] = path
        else:
            logger.warning(
                "Skipping volume analysis for audio_file '%s' due to invalid/missing path (%s) or irrelevant type.",
                audio_file,
                path
            )

    if not payload_data:
        logger.error("No valid/relevant audio to be sent for volume analysis after filtering")
        return {"error": "No audio was submitted for volume analysis!"}

    data_to_send = {"audio_paths": payload_data}
    headers = {'Content-Type': 'application/json'}

    logger.info(
        "Sending request to Volume Service (%s) for audio %s",
        VOLUME_SERVICE_URL,
        list(payload_data.keys())
    )
    logger.debug("Payload for Volume Service: %s", data_to_send)

    try:
        response = requests.post(
            VOLUME_SERVICE_URL,
            json=data_to_send,
            headers=headers,
            timeout=1200
        )
        response.raise_for_status()

        rms_results = response.json()
        logger.info(
            "Successfully recevied Volume analysis results. Audio processed: %s",
            list(rms_results.keys()) if isinstance(rms_results, dict) else "Invalid response format"
        )
        return rms_results
    except requests.exceptions.HTTPError as http_err:
        return {
            "error": f"HTTP Error occurred while calling Volume service: {http_err} - Response: {http_err.response.text if http_err.response else 'No response text'}"
        }
    except requests.exceptions.ConnectionError as conn_err:
        return {"error": f"Connection error calling Volume service: {conn_err}"}
    except requests.exceptions.Timeout as time_err:
        return {"error": f"Timeout calling Volume service: {time_err}"}
    except requests.exceptions.RequestException as req_err:
        return {"error": f"Request exception calling Volume service: {req_err}"}
    except ValueError as json_err:
        return {"error": f"Error decoding JSON response from Volume service: {json_err}"}
