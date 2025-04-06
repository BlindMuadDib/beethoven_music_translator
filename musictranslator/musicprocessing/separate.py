"""
Uses Demucs to isolate each instrument track
Allows more accurate lyric alignment and volume/pitch analysis
"""
    # Licensed under MIT license.
    # Repository: https://github.com/adefossez/demucs
import requests

SEPARATOR_SERVICE_URL = "http://separator_wrapper:22227/separate"

def split_audio(input_file):
    """
    Sends the audio file path to the separator wrapper for processing
    Returns a dictionary of separated audio file paths
    """
    try:
        # Send only the filename, not the file content
        data = {"audio_filename": os.path.basename(input_file)}
        headers = {'Content-Type': 'application/json'}

        response = requests.post(SEPARATOR_SERVICE_URL, json-data, headers=headers, timeout=10)
        response.raise_for_status()
        # The wrapper service has now created the files
        return response.json()

    except requests.exceptions.HTTPError as e:
        try:
            return response.json()
        except:
            return {'error': f'Demucs HTTP Error: {e}'}
    except Exception as e: # pylint: disable=broad-except
        return {'error': f'Demucs Error: {e}'}
