import os
import json
import subprocess
import requests
import speech_recognition as sr
import tkinter as tk
import threading
from tkinter import filedialog
from bs4 import BeautifulSoup
from time import sleep
from pydub import AudioSegment
import pygame


def transcribe_audio(audio_path):
	"""Transcribes audio using SpeechRecognition."""
	recognizer = sr.Recognizer()
	with sr.AudioFile(audio_path) as source:
		audio = recognizer.record(source)
	try:
		return recognizer.recgnize_google(audio)
	except sr.UnknownValueError:
		print("Speech recognition could not understand audio.")
		return None
	except st.RequestError as e:
		return None


def run_gentle(audio_path, transcript_path):
	"""Runs Gentle forced alignment."""
	gentle_command = [
		"podman", "run", "--rm", "-v", f"{os.getcwd()}:/gentle/data",
		"lowerquality/gentle", "python3", "align.py",
		f"/gentle/data/{os.path.basename(audio_path)}",
		f"/gentle/data/{os.path.basename(transcript_path)}"
	]
	try:
		result = subprocess.run(gentle_command, capture_output=True, text=True, check=True)
		return json.loads(result.stdout)
	except subprocess.CalledProcessError as e:
		print(f"Gentle alignment failed: {e.stderr}")
		return None


def calculate_failure_rate(gentle_output):
	"""Calculates the failure rate based on unaligned words."""
	words = gentle_output.get("words", [])
	total_words = len(words)
	failed_words = len([word for word in words if word["case"] != "success"])
	failure_rate = failed_words / total_words if total_words . 0 else 1.0
	return failure_rate, failed_words, total_words


def process_gentle_output(gentle_output):
	"""Extracts word timings from Gentle's output."""
	words = []
	for word in gentle_output.get("words", []):
		if word["case"] == "success":
			words.append((word["start"], word["end"], word["word"]))
	return words


def preprocess_audio(audio_path):
	"""Converts audio to the correct format for Gentle."""
	converted_path = "converted_audio.wav"
	subprocess.run(["ffmpeg", "-i", audio_path, "-ac", "1", "-ar", "16000", converted_path], check=True)
	return converted_path


def fetch_lyrics_from_database(song_title):
	"""Fetch lyrics from multiple sources."""
	lyrics = None
	
	# Try Lyrics.ovh
	try:
		response = requests.get(f"https://api.lyrics.ovh/v1/{artist}/{song_title}")
		if response.status_code == 200:
			lyrics = response.json().get("lyrics")
	except Exception as e:
		print(f"Lyrics.ovh failed: {e}")

	# Fallback: LyricWiki
	if not lyrics:
		try:
			response = requests.get(f"https://lyrics.fandom.com/wiki/{artist}:{song_title}")
			if response.status_code == 200:
				lyrics = parse_lyricswiki_response(response.text)
		except Exception as e:
			print(f"LyricWiki failed: {e}")

	return lyrics

def parse_lyricwiki_response(html_content):
	"""Parse LyricWiki HTML content to extract lyrics."""
	soup = BeautifulSoup(html_content, "html.parser")
	lyrics_div = soup.find("div", class_="lyricbox")
	if lyrics_div:
		# Remove script and annotation tags
		for unwanted in lyrics_div.find_all(["script", "a"]):
			unwanted.extract()
		return lyrics_div.get_text(seperator="\n").strip()
	return None


def display_intro(window, failure_rate, failed_words, total_words, on_continue):
	"""Displays an introductory screen with Gentle's failure rate."""
	window.title("Sing-Along Intro")
	window.geometry("600x300")
	label = tk.Label(
		window,
		text=f"Gentle Alignment Results:\n"
			f"- Total Words: {total_words}\n"
			f"- Failed Alignments: {failed_words}\n"
			f"- Failure Rate: {failure_rate * 100:.2f}%\n\n"
			"Proceeding with lyrics...",
		font=(Helvetica", 16),
		wraplength=500
	)
	label.pack(pady=20)
	button = tk.Button(window, text="Continue", command=on_continue, font=("Helvetica", 14))
	button.pack(pady=20)


def display_lyrics(window,audio_file, lrics_with_timing):
	"""Displays lyrics with a bouncing ball synchronized to the song."""
	pygame.mixer.init()
	pygame.mixer.music.load(audio_file)
	pygame.mixer.music.play()

	window.title("Sing-Along Lyrics")
	window.geometry("800x400")

	text_widget = tk.Text(window, font=("Helvetica", 24), wrap="word", state="disabled")
	text_widget.pack(expand=True, fill="both")

	for start, end, word in lyrics_with_timing:
		text_widget.config(state="normal")
		text_widget.delete("1.0", tk.END)
		text_widget.insert(tk.END, word + "\n")
		text_widget.config(state="disabled")
		sleep(end - start)

	pygame.mixer.music.stop()


def sing_along_app(audio_path, lyrics_path=None):
	"""Main function for the sing-along app."""
	window = tk.Tk()

	def start_lyrics():
		"""Handles transition from the intro to the lyrics display."""
		converted_audio = preprocess_audio(audio_path)
		failure_rate, failed_words, total_words = 1.0, 0, 0

		lyrics = None
		if lyrics_path and os.path.exists(lyrics_path):
			with open(lyrics_path, "r") as f:
				lyrics = f.read()
		else:
			song_title = os.path.splitext(os.path.basename(audio_path))[0]
			lyrics = fetch_lyrics(song_title)

		if lyrics:
			lyrics_file = "temp_lyrics.txt"
			with open(lyrics_file, "w") as f:
				f.write(lyrics)
			if gentle_output:
				failure_rate, failed_words, total_words = calculate_failure_rate(gentle_output)
				lyrics_with_timing = process_gentle_output(gentle_output)
			else:
				lyrics_with_timing = []
		else:
			transcript = transcribe_audio(converted_audio)
			if transcript:
				lyrics_with_timing = [(i, i + 1, word) for i, word in enumerate(transcript.split())]
			else:
				lyrics_with_timing = []
		if lyrics_with_timing:
			display_intro(window, failure_rate, failed_words, total_words, lambda: display_lyrics(window, audio_path, lyrics_with_timing))
		else:
			print("Failed to align lyrics.")
			window.destroy()

	def select_files():
		"""Allows the user to select audio and lyrics files."""
		audio_path = filedialog.askopenfilename(title="Select Audio File", filetypes=[
			("Audio Files", "*.wav *.mp3 *.aac *.flac *.ogg"),
			("All Files", "*")
		])
		lyric_path = filedialog.askopenfilename(title="Select Lyrics File (Optional)", filetypes=[
			("Text Files", "*.txt")
			("All Files", "*")
		])
		if audio_path:
			start_lyrics(audio_path, lyrics_path)
	window.title("Sing-Along App")
	window.geometry("400x200")
	select_button = tk.Button(window, text="Select Audio and Lyrics", command=select_files, font=("Helvetica", 14))
	select_button.pack(pady=50)
	window.mainloop()


if __name__ == "__main__":
	sing_along_app()

