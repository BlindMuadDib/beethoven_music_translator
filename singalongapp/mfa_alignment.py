import os
import tkinter as tk
import subprocess
import requests
from tkinter import filedialog

def run_montreal_forced_aligner(audio_path, transcript_path):
    """Uses Montreal Forced Aligner (MFA) to perform forced alignment."""
    data_directory = filedialog.askdirectory(title="Select the parent directory for MFA Corpus, Alignments, and Outputs.")
    corpus_directory = filedialog.askdirectory(title="Select the corpus directory (must contain only one transcript per one audio with same names, different extensions).")
    aligned_directory = filedialog.askdirectory(title="Select the directory to save alignments.")

    try:
        print("Downloading models and dictionary for MFA...")
        subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath(data_directory)}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "model", "download", "acoustic", "english_us_arpa",
            "mfa", "model", "download", "dictionary", "english_us_arpa"
        ], check=True)

        print("Validating corpus...")
        Validation_result = subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath(data_directory)}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "validate", f"/data/{os.path.basename(corpus_directory)}",
            "english_us_arpa", "english_us_arpa"
            ], capture_output=True, text=True)

        if validation_result.returncode != 0:
            print(f"[ERROR]Corpus validation failed: {validation_result.stderr}")
            return None

        print("Performing alignment...")
        alignment_result = subprocess.run([
            "docker", "run", "--rm", "-v",
            f"{os.path.abspath(data_directory)}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest",
            "mfa", "align", f"/data/{os.path.basename(corpus_directory)}",
            "english_us_arpa", "english_us_arpa", f"/data/{os.path.basename(aligned_directory)}"
            ], capture_output=True, text=True)

        if alignment_result.returncode != 0:
            print("[WARNING] Alignment failed with default settings. Retrying with increased beam width...")
            retry_result = subprocess.run([
                "docker", "run", "--rm", "-v",
                f"{os.path.abspath(data_directory)}:/data", "docker.io/mmcauliffe/montreal-forced-aligner:latest"
                "mfa", "align", f"/data/{os.path.basename(corpus_directory)}",
                "english_us_arpa", "english_us_arpa", f"/data/{os.path.basename(aligned_directory)}",
                "--beam", "100", "--retry_beam", "400"
                ], capture_output=True, text=True)

            if retry_result.returncode != 0:
                print(f"[ERROR] Alignment failed after retry: {retry_result.stderr}")
                return None

        alignment_path = os.path.join(aligned_directory, filedialog.asksaveasfilename(
            title="Save alignment file", defaultextension=".TextGrid"))
        print(f"[INFO] Alignment output saved to: {alignment_path}")
        return alignment_path

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] MFA subprocess failed: {e}")
        return None

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return None
