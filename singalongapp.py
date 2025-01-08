from singalongapp.selectfiles import select_audio, select_transcript, select_aligned_transcript
from singalongapp.mfa_alignment import run_montreal_forced_aligner
from singalongapp.maptranscript import process_transcript, create_alignment_dict, sync_alignment_dict_with_transcript_lines
from singalongapp.displaylyrics import display_lyrics

def singalongapp():
    audio_path = select_audio()
    transcript_path = select_transcript()
    alignment_path = select_aligned_transcript()

    processed_transcript = process_transcript(transcript_path)

    if alignment_path:
        alignment_dict, word_intervals = create_alignment_dict(alignment_path)
        if alignment_dict:
            synchronized_transcript = sync_alignment_dict_with_transcript_lines(word_intervals, processed_transcript)
            display_lyrics(audio_path, synchronized_transcript)
    else:
        alignment_path = run_montreal_forced_aligner(audio_path, transcript_path)
        alignment_dict, word_intervals = create_alignment_dict(alignment_path)
        if alignment_dict:
            synchronized_transcript = sync_alignment_dict_with_transcript_lines(word_intervals, processed_transcript)
            display_lyrics(audio_path, synchronized_transcript)

if __name__ == '__main__':
    singalongapp()
