import os
from musictranslator.selectfiles.selectfiles import select_audio, select_transcript, select_aligned_transcript, select_spleeter_dir, select_library_dir, select_alignment_dir
from .maptranscript import process_transcript, create_alignment_dict, sync_alignment_dict_with_transcript_lines
from .displaylyrics import display_lyrics
from musictranslator.preprocessdatabase.preprocess_audio import preprocess_audio
from musictranslator.preprocessdatabase.alignment import run_montreal_forced_aligner

def singalongapp():
    """Main Function of the lyric tracking display"""
    # Ask user for files and directories
    audio_path = select_audio()
    transcript_path = select_transcript()
    alignment_path = select_aligned_transcript()

    # Process transcript function is called preemptively for both use cases
    processed_transcript = process_transcript(transcript_path)

    if alignment_path:
        # Allows user to access pretranslated library instead of computing before each song, every time
        alignment_dict, word_intervals = create_alignment_dict(alignment_path)
        if alignment_dict:
            synchronized_transcript = sync_alignment_dict_with_transcript_lines(word_intervals, processed_transcript)
            display_lyrics(audio_path, synchronized_transcript)

    else:
        # Allow user to translate a song that is not in their pretranslated database for immediate use. INEFFICIENT!
        # preprocess audio with Spleeter
        spleeter_dir = select_spleeter_dir()
        library_dir, file_name = os.path.split(audio_path)
        spleeter_dir = os.path.join(library_dir, "processed")
        os.makedirs(spleeter_dir, exist_ok=True)
        vocal_track_path = preprocess_audio(audio_path, spleeter_dir, file_name)

        # Select corpus alignment directory
        alignment_dir = select_alignment_dir()

        # Run Montreal Forced Aligner
        alignment_path = run_montreal_forced_aligner(vocal_track_path, transcript_path, corpus_alignment_dir)
        alignment_dict, word_intervals = create_alignment_dict(alignment_path)
        if alignment_dict:
            synchronized_transcript = sync_alignment_dict_with_transcript_lines(word_intervals, processed_transcript)
            display_lyrics(audio_path, synchronized_transcript)

if __name__ == "__main__":
    singalongapp()
