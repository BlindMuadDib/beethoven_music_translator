"""
Uses Montreal Forced Aligner (MFA) to perform lyric alignment.
Licensed under MIT License.
Repository: https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner
"""
import requests
import logging

logger = logging.getLogger(__name__)

MFA_SERVICE_URL = "http://mfa-service:24725/api/align"

def align_lyrics(vocals_stem_path, lyrics_path):
    """
    Temporarily open the file with kubernetes cluster for docker image alignment

    Return:
        Expected to return a TextGrid file of the alignment data
    """
    logger.info(f"Attempting to contact MFA at: {MFA_SERVICE_URL} with vocals: {vocals_stem_path} and lyrics: {lyrics_path}")
    try:
        data = {"vocals_stem_path": vocals_stem_path, "lyrics_path": lyrics_path}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(MFA_SERVICE_URL, json=data, headers=headers, timeout=1200)
        response.raise_for_status()

        if response.status_code == 200:
            alignment_data = response.json()
            if 'alignment_file_path' in alignment_data:
                return alignment_data['alignment_file_path']
            else:
                return {"error": "MFA successful response missing 'alignment_file_path'"}
        return {"error": f"MFA alignment failed: {response.text}"}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with MFA: {e}")
        return {"error": "Error communicating with MFA: {e}"}
    except OSError as e:
        return {"error": "Error opening file: {e}"}
    except ValueError as e:
        return {"error": "Error parsing TextGrid: {e}"}
    except Exception as e: # Catch any other errors
        return {"error": "Unexpected error in mfa_service: {e}"}
