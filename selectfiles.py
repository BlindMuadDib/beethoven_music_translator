import tkinter as tk
from tkinter import filedialog

def select_audio():
    audio_path = filedialog.askopenfilename(title="Select Audio File", filetypes=[
        ("Audio Files", "*.wav *.mp3 *.aac *.flac *.ogg"),
        ("All Files", "*")
        ])
    return audio_path

def select_transcript():
    transcript_path = filedialog.askopenfilename(title="Select Lyrics File", filetypes=[
        ("Text Files", "*.txt"),
        ("All Files", "*.*")
        ])
    return transcript_path

def select_aligned_transcript():
    aligned_transcript_path = filedialog.askopenfilename(title="Select Lyric Alignment File", filetypes=[
        ("TextGrid Files", "*.TextGrid"),
        ("All Files", "*")
        ])
    return aligned_transcript_path
