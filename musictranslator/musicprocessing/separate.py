"""
Uses Spleeter by Deezer to isolate each instrument track
Allows more accurate lyric alignment and volume/pitch analysis
"""
    # Licensed under MIT license.
    # Repository: https://github.com/deezer/spleeter
import requests

SPLEETER_SERVICE_URL = "http://spleeter-service:22227/split"

def split_audio(input_file):
    """ Temporarily opens the audio for Kubernetes """
    try:
        with open(input_file, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(SPLEETER_SERVICE_URL, files=files, timeout=10)
            response.raise_for_status()
            # The wrapper service has now created the files
            return True

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error communicating with Spleeter service: {e}")
        return False
    except Exception as e: # pylint: disable=broad-except
        print(f"[ERROR] Unexpected error in spleeter_service: {e}")
        return False
