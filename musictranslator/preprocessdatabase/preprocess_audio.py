import os
import subprocess

def preprocess_audio(library_dir, spleeter_dir, file_name):
    """Uses Spleeter by Deezer to isolate vocal track for more accurate alignment"""
    #Licensed under MIT License. Repository: https://github.com/deezer/spleeter

    print("Processing audio with Spleeter")

    #Run Spleeter to separate the vocal track in 16kHz
    spleeter_command = [
        "docker", "run", "--rm", "-v",
        f"{library_dir}:/input",
        f"{spleeter_dir}:/output",
        "researchdeezer/spleeter",
        "separate", "-o", "/output", "-p", "spleeter:4stems-16kHz", "-i", f"/input/{file_name}"
        ]
    subprocess.run(spleeter_command)
    print(f"Processed {file_name} with Spleeter")

    vocal_track_path = os.path.join(spleeter_dir, file_name.split(".")[0], "vocals.wav")
    return vocal_track_path
