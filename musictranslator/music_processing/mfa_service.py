import requests
import json
import textgrid

MFA_SERVICE_URL = "http://mfa-service:24725/align"

def align_lyrics(audio_file, lyrics_file, output_file):
    """Uses Montreal Forced Aligner (MFA) to perform forced alignment."""
    # Licensed under MIT License. Repository: https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner
    try:
        with open(audio_file, 'rb') as audio_file_obj, optn(lyrics_file, 'rb') as lyrics_file_obj:
            files = {
                'audio': audio_file_obj,
                'lyrics': lyrics_file_obj
            }
            response = requests.post(MFA_SERVICE_URL, files=files)
            response.raise_for_status()

            # The wrapper service returns the TextGrid content as a string
            textgrid_content = response.text

            # Parse the TextGrid content
            tg = textgrid.TextGrid.fromFile(file_path=None, string=textgrid_content)

            words_tier = tg.getFirst('words')
            if not words_tier:
                raise ValueError("The 'words' tier is missing from the TextGrid")

            alignment_data = {
                "tier_name": words_tier.name,
                "intervals": [
                    {
                        "xmin": interval.minTime,
                        "xmax": interval.maxTime,
                        "word": interval.mark
                    } for interval in words_tier.intervals
                ]
            }

            # Write alignment data to JSON file
            with open(output_file, 'w') as f:
                json.dump(alignment_data, f, indent=4)

                return True

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error communicating with MFA service: {e}")
        return False
    except ValueError as e:
        print(f"[ERROR] Error parsing TextGrid: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error in mfa_service: {e}")
        return False
