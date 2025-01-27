import tkinter as tk
from tkinter import filedialog

def select_audio():
    """Select a single audio file to be translated"""
    audio_path = filedialog.askopenfilename(title="Select Audio File", filetypes=[
        ("Audio Files", "*.wav *.mp3 *.aac *.flac *.ogg"),
        ("All Files", "*")
        ])
    return audio_path

def select_transcript():
    """Select the corresponding lyrics of the selected song"""
    transcript_path = filedialog.askopenfilename(title="Select Lyrics File", filetypes=[
        ("Text Files", "*.txt"),
        ("All Files", "*.*")
        ])
    return transcript_path

def select_aligned_transcript():
    """Select an aligned transcript if one has already been made. This allows the user to access their library quicker."""
    aligned_transcript_path = filedialog.askopenfilename(title="Select Lyric Alignment File", filetypes=[
        ("TextGrid Files", "*.TextGrid"),
        ("All Files", "*")
        ])
    return aligned_transcript_path

def select_library_dir():
    """Select a directory for database processing. Allows a user's library to be accessed quicker"""
    library_dir = filedialog.askdirectory(title="Select Directory containing music library files.")
    if not library_dir:
        messagebox.showerror("Error", "No input directory selected.")
        return

def select_spleeter_dir():
    """Select the directory for Spleeter output"""
    spleeter_dir = filedialog.askdirectory(title="Select Directory for Spleeter output")
    if not spleeter_dir:
        messagebox.showerror("Error", "No output directory selected")

def select_mfa_corpus_dir():
    """Select the directory for the MFA corpus for transferring the Spleeter output"""
    mfa_corpus_dir = filedialog.askdirectory(title="Select Directory for the MFA corpus")
    if not mfa_corpus_dir:
        messagebox.showerror("Error", "No MFA Corpus directory selected")

def select_alignment_dir():
    """Select the directory for aligned transcripts"""
    aligned_dir = filedialog.askdirectory(title="Select the directory to save aligned lyrics.")
    if not aligned_dir:
        messagebox.showerror("Error", "No directory selected for aligned lyrics")
