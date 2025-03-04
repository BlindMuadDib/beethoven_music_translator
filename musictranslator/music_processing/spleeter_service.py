import requests
import json

SPLEETER_SERVICE_URL = "http://spleeter-service:24725/split"

def split_audio(input_file, vocals_output, accompaniment_output, drums_output, bass_output):
    """Uses Spleeter by Deezer to isolate each instrument track for processing of lyric alignment and volume/pitch analysis"""
    # Licensed under MIT license. Repository: https://github.com/deezer/spleeter
    try:
        with open(input_file, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(SPLEETER_SERVICE_URL, files=files)
            response.raise_for_status()
            # The wrapper service has now created the files
            return True

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error communicating with Spleeter service: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error in spleeter_service: {e}")
        return False
