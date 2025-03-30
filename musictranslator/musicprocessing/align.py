"""
Uses Montreal Forced Aligner (MFA) to perform lyric alignment.
Licensed under MIT License.
Repository: https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner
"""
import requests

MFA_SERVICE_URL = "http://mfa_wrapper:24725/align"

def align_lyrics(audio_file, lyrics_file):
    """
    Temporarily open the file with kubernetes cluster for docker image alignment

    Return:
        Expected to return a TextGrid file of the alignment data
    """
    try:
        with open(audio_file, 'rb') as audio_file_obj, open(lyrics_file, 'rb') as lyrics_file_obj:
            files = {
                'audio': audio_file_obj,
                'lyrics': lyrics_file_obj
            }
            response = requests.post(MFA_SERVICE_URL, files=files, timeout=10)

        if response.status_code == 200:
            return response.json()
        return {"error": f"MFA alignment failed: {response.text}"}

    except requests.exceptions.RequestException as e:
        return {"error": "Error communicating with MFA: {e}"}
    except OSError as e:
        return {"error": "Error opening file: {e}"}
    except ValueError as e:
        return {"error": "Error parsing TextGrid: {e}"}
    except Exception as e: # Catch any other errors
        return {"error": "Unexpected error in mfa_service: {e}"}
