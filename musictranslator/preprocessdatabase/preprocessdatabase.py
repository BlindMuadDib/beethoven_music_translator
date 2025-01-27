import os
import shutil
from tkinter import messagebox
from selectfiles.selectfiles import select_library_dir, select_spleeter_dir, select_mfa_corpus_dir, select_alignment_dir
from preprocessdatabase.preprocess_audio import preprocess_audio
from preprocessdatabase.alignment import run_montreal_forced_aligner

def db_translation():
    """Allow user to process entire library at once for faster translation access later"""
    library_dir = select_library_dir()
    spleeter_dir = select_spleeter_dir()
    mfa_corpus_dir = select_mfa_corpus_dir()
    alignment_dir = select_alignment_dir()

    for file_name in os.listdir(library_dir):
        if file_name.endswith(".wav") or file_name.endswith(".mp3"):
            artist, song = os.path.splitext(file_name)[0].split("-")

            # Preprocess audio using the Spleeter Docker image
            preprocess_audio(library_dir, spleeter_dir, file_name)

            # Extract the isolated vocal tracks
            vocal_track_path = os.path.join(spleeter_dir, file_name.split(".")[0], "vocals.wav")
            if os.path.exists(vocal_track_path):
                new_file_name = f"{artist}-{song}.wav"
                new_file_path = os.path.join(mfa_corpus_dir, new_file_name)
                shutil.copy(vocal_track_path, new_file_path)
                print(f"Copied and renamed vocal track to: {new_file_path}")

                # Create TextGrid files using Montreal Forced Aligner
                transcript_path = os.path.join(library_dir, f"{artist}-{song}.txt")
                if os.path.exists(transcript_path):
                    textgrid_path = run_montreal_forced_aligner(new_file_path, transcript_path, alignment_dir)
            else:
                print(f"Vocal track not found for {file_name}")

    messagebox.showinfo("Success", "Library translation processing completed successfully!")

if __name__ == "__main__":
    db_translation()
