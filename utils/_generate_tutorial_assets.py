import os
import json
import numpy as np
from scipy.io import wavfile
from _generate_tutorial import combine_generated_mock_audio_and_data, SAMPLE_RATE

# Config
default_path = os.path.join(os.path.dirname(__file__), '../data/tutorial')
OUTPUT_DIR = os.getenv('TUTORIAL_OUTPUT_DIR', default_path)
DATA_FILE = os.path.join(OUTPUT_DIR, 'data.json')
AUDIO_FILE = os.path.join(OUTPUT_DIR, 'audio.wav')

class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

def main():
    print(f"Starting generation. Output directory: {OUTPUT_DIR}")

    # 1. Generate Data
    data, audio = combine_generated_mock_audio_and_data()

    # 2. Ensure Output Directory Exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 3. Save Audio (WAV)
    # audio is already float32 (-1.0 to 1.0), which scipy handles correctly
    print(f"Saving audio to {AUDIO_FILE}...")
    wavfile.write(AUDIO_FILE, SAMPLE_RATE, audio)

    # 4. Save Data (JSON)
    print(f"Saving metadata to {DATA_FILE}...")
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, cls=NumpyEncoder)

    print("Generation complete.")

if __name__ == "__main__":
    main()
