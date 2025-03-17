"""
Uses Montreal Forced Aligner (MFA) to perform lyric alignment.
Licensed under MIT License.
Repository: https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner
"""
import requests

MFA_SERVICE_URL = "http://mfa-service:24725/align"

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
            response.raise_for_status()

            textgrid_content = response.text
            return textgrid_content

    except requests.exceptions.RequestException as e:
        return f"[ERROR] Error communicating with MFA service: {e}"
    except OSError as e:
        return f"[ERROR] Error opening file: {e}"
    except ValueError as e:
        return f"[ERROR] Error parsing TextGrid: {e}"
    except Exception as e: # Catch any other errors
        return f"[ERROR] Unexpected error in mfa_service: {e}"
