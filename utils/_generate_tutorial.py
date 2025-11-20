"""
This is a utility function to automate the creation of data and audio for a
tutorial video of the Music Translator for and by Deaf for end-users.
It will be processed by the front-end JS app to create consistent visual
elements, with descriptions to be added manually after creation front-end
processing.
"""
import numpy as np
from scipy.signal import chirp, sawtooth, butter, lfilter

# --- Configuration for the Mock Data ---
SAMPLE_RATE = 44100
# A common frame rate is ~43 frames/second (22050 / 512 = 43.066)
# Correcting the sample rate used in the front-end js file utils.js
# This should be 22050, not 44100
ANALYSIS_SAMPLE_RATE = 22050
HOP_LENGTH = 512
FRAME_RATE = ANALYSIS_SAMPLE_RATE / HOP_LENGTH

def _create_time_array(duration_seconds):
    """
    Helper to create a time array for audio signal generation
    """
    return np.linspace(0., duration_seconds,
                       int(duration_seconds * SAMPLE_RATE), endpoint=False)

def _create_frame_data(time, constant_values=None):
    """
    Helper to create a single frame of mock data with default values.
    """
    if constant_values is None:
        constant_values = {}

    defaults = {
        "f0_data": 100.0,
        "spectral_centroid": 1000.0,
        "spectral_rolloff": 2000.0,
        "spectral_flatness": 0.5,
        "spectral_bandwidth": 1500.0,
        "rms": 0.8,
        "spectrogram": [0.1] * 8, # Simplified
        "frequencies": [100, 200, 300, 400, 500, 600, 700, 800], # Simplified
        "mfccs": [1.0] * 20,
        "chroma_stft": [0.0] * 12
    }
    frame = {"time": time, **defaults}
    frame.update(constant_values)
    return frame

def _create_hit_data(onset_time, constant_values=None):
    """
    Helper to create a single drum hit dictionary with default values.
    """
    if constant_values is None:
        constant_values = {}

    defaults = {
        "onset_time": onset_time,
        "duration": 0.2,
        "relative_volume": 0.8,
        "drum_category": "snare",
        "drum_type": "open_band",
        "qualifier": "no_qualifier",
        "dominant_frequency": 800.0,
        "spectral_centroid": 1200.0,
        "spectral_rolloff": 2500.0,
        "spectral_flux": 0.6
    }
    hit = {**defaults}
    hit.update(constant_values)
    return hit

def _create_filtered_noise_audio(duration_seconds, start_cutoff, end_cutoff):
    """
    Helper to generate audio for spectral ramps.
    """
    t = _create_time_array(duration_seconds)
    noise = np.random.normal(0, 0.5, len(t))
    audio = np.zeros_like(noise)

    num_segments = 100
    segment_len = len(t) // num_segments
    cutoff_freqs = np.linspace(start_cutoff, end_cutoff, num_segments)

    for i in range(num_segments):
        start, end = i * segment_len, (i + 1) * segment_len
        nyquist = 0.5 * SAMPLE_RATE
        # Prevent cutoff from exceeding Nyquist
        normalized_cutoff = min(cutoff_freqs[i] / nyquist, 0.999)
        b, a = butter(4, normalized_cutoff, btype='low')
        audio[start:end] = lfilter(b, a, noise[start:end])

    return audio

def _offset_data(data, time_offset):
    """
    Recursively offsets all time-related keys in a data structure.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if k in ['time', 'onset_time', 'line_start_time', 'line_end_time', 'start', 'end']:
                new_dict[k] = v + time_offset if v is not None else v
            elif k in ['times', 'beats', 'onsets'] and isinstance(v, list):
                new_dict[k] = [t + time_offset for t in v]
            else:
                new_dict[k] = _offset_data(v, time_offset)
        return new_dict
    elif isinstance(data, list):
        return [_offset_data(item, time_offset) for item in data]
    else:
        return data

def generate_harmonic_pitch_ramp_data_and_audio(duration_seconds=10):
    """
    Generates time-series data where the main pitch ramps up and a
    corresponding audio segment.
    """
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE

    # Define pitch range (e.g., C4 to C6 and back down)
    min_freq = 261.63   # C4
    max_freq = 1046.50  # C6

    data = []

    # Generate the rising and falling frequencies for the data frames
    midpoint = total_frames // 2
    rising_freqs = np.linspace(min_freq, max_freq, num=midpoint)
    falling_freqs = np.linspace(max_freq, min_freq,
                                num=total_frames - midpoint)
    frequencies = np.concatenate([rising_freqs, falling_freqs])

    for i in range(total_frames):
        time = round(i * time_per_frame, 3)
        frame_data = _create_frame_data(time)
        # Use 'frequencies' to simulate main pitch, as HarmonicVisualizer uses
        # this
        frame_data["frequencies"] = [frequencies[i]]
        frame_data["spectrogram"] = [1.0] # Single strong frequency
        frame_data["f0_data"] = frequencies[i]
        data.append(frame_data)

    # --- Generating Corresponding Audio ---
    # Create a time array for the audio signal
    t = _create_time_array(duration_seconds)

    # Create a chirp that goes up and down.
    # This can be done by concatenating two separate chirps
    t_half = np.linspace(0., duration_seconds / 2,
                         int((duration_seconds / 2) * SAMPLE_RATE),
                         endpoint=False)

    # Generate a wave that sweeps from min_freq to max_freq (logarithmic is more musical)
    wave_up = chirp(t_half, f0=min_freq, f1=max_freq, t1=duration_seconds/2,
                   method='logarithmic')
    # Generate a wave that sweeps from max_freq down to min_freq
    wave_down = chirp(t_half, f0=max_freq, f1=min_freq, t1=duration_seconds/2,
                      method='logarithmic')

    # Combine the two halves
    audio = np.concatenate([wave_up, wave_down])

    # Normalize audio to prevent clipping
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_volume_ramp_data_and_audio(duration_seconds=10):
    """
    Generates time-series data where the volume starts at 0 and rises to 1,
    with a corresponding audio segment.
    """
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE
    data = []

    midpoint = total_frames // 2
    rising_rms = np.linspace(0.0, 0.9, num=midpoint)
    falling_rms = np.linspace(0.9, 0.0, num=total_frames-midpoint)
    rms_values = np.concatenate([rising_rms, falling_rms])

    for i in range(total_frames):
        time = round(i * time_per_frame, 3)
        frame_data = _create_frame_data(time, {"f0_data": 440.0})
        frame_data["rms"] = rms_values[i]
        data.append(frame_data)

    # Audio Generation
    t = _create_time_array(duration_seconds)
    tone = np.sin(2 * np.pi * 440 * t) # A4 note

    # Create a volume envelope that matches the RMS ramp
    envelope_rising = np.linspace(0, 1, len(t) // 2)
    envelope_falling = np.linspace(1, 0, len(t) - len(t) // 2)
    envelope = np.concatenate([envelope_rising, envelope_falling])

    audio = tone * envelope * 0.8
    return data, audio.astype(np.float32)

def generate_overall_volume_ramp_data_and_audio(duration_seconds=10):
    """
    Generates data and audio simulating multiple tracks to show overall volume.
    """
    # For this function, the data format is different, matching
    # `full_track_analysis.rms_overall`
    total_frames = int(duration_seconds * FRAME_RATE)
    times = np.linspace(0, duration_seconds, total_frames)

    midpoint = total_frames // 2
    rising_rms = np.linspace(0.0, 0.9, num=midpoint)
    falling_rms = np.linspace(0.9, 0.0, num=total_frames - midpoint)
    values = np.concatenate([rising_rms, falling_rms])

    data = {"times": times.tolist(), "values": values.tolist()}

    # Audio: Create 3 sine waves and fade them in and out sequentially
    t = _create_time_array(duration_seconds)
    tone1 = np.sin(2 * np.pi * 261.63 * t) # C4
    tone2 = np.sin(2 * np.pi * 329.63 * t) # E4
    tone3 = np.sin(2 * np.pi * 392.00 * t) # G4

    # Create envelopes to fade tones
    envelope_full = np.concatenate([np.linspace(0, 1, len(t)//2),
                                    np.linspace(1, 0, len(t) - len(t)//2)])
    envelope_mid = np.concatenate([np.zeros(len(t)//4),
                                   np.linspace(0, 1, len(t)//4),
                                   np.linspace(1, 0, len(t)//4),
                                   np.zeros(len(t) - 3*(len(t)//4))])
    envelope_late = np.concatenate([np.zeros(len(t)//2),
                                    np.linspace(0, 1, len(t)//4),
                                    np.zeros(len(t)//4)])

    # Combine tones
    audio = (tone1 * envelope_full + tone2 * envelope_mid + tone3 * envelope_late) / 3.0
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_tempos_data_and_audio(duration_seconds=15):
    """
    Generates three segments with slow, medium, and fast tempos.
    """
    segment_duration = duration_seconds / 3
    tempos = [60, 120, 180]
    all_data = []
    all_audio = np.array([], dtype=np.float32)

    current_time_offset = 0.0

    for tempo in tempos:
        total_frames = int(segment_duration * FRAME_RATE)
        time_per_frame = 1 / FRAME_RATE

        for i in range(total_frames):
            time = round(current_time_offset + (i * time_per_frame), 3)
            frame_data = _create_frame_data(time)
            # The vizualizer uses tempo from `stem_analyses.temporal_features.tempo`
            # For simplicity, return a structure that can be combined later
            frame_data["tempo"] = tempo
            all_data.append(frame_data)

        # Audio: Metronome clicks
        t = _create_time_array(segment_duration)
        audio_segment = np.zeros_like(t)
        beats_per_second = tempo / 60
        interval = int(SAMPLE_RATE / beats_per_second)
        for i in range(0, len(audio_segment), interval):
            click_duration = int(SAMPLE_RATE * 0.02)
            audio_segment[i : i + click_duration] = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.02, click_duration)) * 0.8

        all_audio = np.concatenate([all_audio, audio_segment])
        current_time_offset += segment_duration

    # This data would be split into stem_analyses later, but we provide a
    # flat list for testing.
    return all_data, all_audio.astype(np.float32)

def generate_harmonic_beats_and_onsets_data_and_audio(duration_seconds=10):
    """
    Generates a track with steady onsets and beats.
    """
    tempo = 120
    beats_per_second = tempo / 60
    time_per_beat = 1 / beats_per_second

    beats = np.arange(0, duration_seconds, time_per_beat).tolist()
    # Place onsets on the off-beats
    onsets = (np.arange(0, duration_seconds, time_per_beat) + time_per_beat / 2).tolist()

    # Data is not frame-based for this, but static features.
    # Return it in a format that can be placed in `temporal_features`
    data = {"beats": beats, "onsets": onsets, "tempo": tempo}

    # Audio
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    # Beat sound (low tone)
    for beat_time in beats:
        start_index = int(beat_time * SAMPLE_RATE)
        click_duration = int(SAMPLE_RATE * 0.05)
        end_index = start_index + click_duration
        if end_index < len(audio):
            audio[start_index:end_index] = np.sin(2 * np.pi * 500 * np.linspace(0, 0.05, click_duration)) * 0.7

    # Onset sound (high tone)
    for onset_time in onsets:
        start_index = int(onset_time * SAMPLE_RATE)
        click_duration = int(SAMPLE_RATE * 0.05)
        end_index = start_index + click_duration
        if end_index < len(audio):
            audio[start_index:end_index] = np.sin(2 * np.pi * 1200 * np.linspace(0, 0.05, click_duration)) * 0.7

    return data, audio.astype(np.float32)

# def generate_harmonic_f0_data_and_audio(duration_seconds=10):
# This function is redundant given the method for generate_harmonic_pitch_ramp_data_and_audio

def generate_harmonic_spectral_centroid_data_and_audio(duration_seconds=10):
    """Generates a ramp for spectral centroid."""
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE
    data = []

    midpoint = total_frames // 2
    rising = np.linspace(500, 8000, num=midpoint)
    falling = np.linspace(8000, 500, num=total_frames - midpoint)
    values = np.concatenate([rising, falling])

    for i in range(total_frames):
        time = round(i * time_per_frame, 3)
        frame_data = _create_frame_data(time)
        frame_data["spectral_centroid"] = values[i]
        data.append(frame_data)

    audio_up = _create_filtered_noise_audio(duration_seconds/2, 500, 8000)
    audio_down = _create_filtered_noise_audio(duration_seconds/2, 8000, 500)
    audio = np.concatenate([audio_up, audio_down])
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_spectral_rolloff_data_and_audio(duration_seconds=10):
    """
    Generates a ramp for spectral rolloff.
    """
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE
    data = []

    midpoint = total_frames // 2
    rising = np.linspace(1000, 10000, num=midpoint)
    falling = np.linspace(10000, 1000, num=total_frames - midpoint)
    values = np.concatenate([rising, falling])

    for i in range(total_frames):
        time = round(i * time_per_frame, 3)
        frame_data = _create_frame_data(time)
        frame_data["spectral_rolloff"] = values[i]
        data.append(frame_data)

    audio_up = _create_filtered_noise_audio(duration_seconds/2, 1000, 10000)
    audio_down = _create_filtered_noise_audio(duration_seconds/2, 10000, 1000)
    audio = np.concatenate([audio_up, audio_down])
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_spectral_flatness_data_and_audio(duration_seconds=10):
    """
    Ramps spectral flatness from low (tonal) to high (noisy) and back.
    """
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE
    data = []

    midpoint = total_frames // 2
    rising_flatness = np.linspace(0.0, 1.0, num=midpoint)
    falling_flatness = np.linspace(1.0, 0.0, num=total_frames - midpoint)
    flatness_values = np.concatenate([rising_flatness, falling_flatness])

    for i in range(total_frames):
        time = round(i * time_per_frame, 3)
        frame_data = _create_frame_data(time)
        frame_data["spectral_flatness"] = flatness_values[i]
        data.append(frame_data)

    # Audio: Morph from sine wave to white noise and back
    t = _create_time_array(duration_seconds)
    tone = np.sin(2 * np.pi * 440 * t)
    noise = np.random.uniform(-1, 1, len(t))

    envelope = np.concatenate([np.linspace(0, 1, len(t)//2),
                               np.linspace(1, 0, len(t)-len(t)//2)])

    audio = (noise * envelope) + (tone * (1 - envelope))
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_mfccs_data_and_audio(duration_seconds=12):
    """
    Generates three segments with distinct MFCCs.
    """
    segment_duration = duration_seconds / 3
    all_data = []
    all_audio = np.array([], dtype=np.float32)
    current_time_offset = 0.0

    mfcc_presets = [
        np.linspace(10, -5, 20).tolist(),       # Smoothly decreasing
        (np.sin(np.arange(20)) * 15).tolist(),  # Wavy
        np.array([-20, 20] * 10).tolist()       # Jagged alternating
    ]

    # Generate 3 distinct audio types
    t_segment = _create_time_array(segment_duration)
    audio_segments = [
        np.sin(2 * np.pi * 150 * t_segment), # Low sine
        sawtooth(2 * np.pi * 440 * t_segment), # Mid sawtooth
        np.random.uniform(-1, 1, len(t_segment)) # White noise
    ]

    for i, mfccs in enumerate(mfcc_presets):
        total_frames = int(segment_duration * FRAME_RATE)
        time_per_frame = 1 / FRAME_RATE
        for j in range(total_frames):
            time = round(current_time_offset + (j * time_per_frame), 3)
            frame_data = _create_frame_data(time, {"mfccs": mfccs})
            all_data.append(frame_data)

        audio = audio_segments[i] * 0.7
        all_audio = np.concatenate([all_audio, audio])
        current_time_offset += segment_duration

    return all_data, all_audio.astype(np.float32)

def generate_chroma_stft_data_and_audio(duration_seconds=16):
    """
    Generates a scale, then some chords, for chroma_stft visualization.
    """
    notes_duration = 12 # 1 second per note
    chords_duration = 4 # 2 sec per chord
    notes_per_second = 1

    # --- Part 1: Scale ---
    all_data = []
    all_audio = np.array([], dtype=np.float32)
    current_time = 0.0

    for note_index in range(12): # C4 to B4
        freq = 261.63 * (2**(note_index/12)) # C4 is 261.63 Hz

        t_note = _create_time_array(1.0)
        audio_note = np.sin(2 * np.pi * freq * t_note) * 0.7
        all_audio = np.concatenate([all_audio, audio_note])

        total_frames_note = int(1.0 * FRAME_RATE)
        time_per_frame = 1 / FRAME_RATE
        for i in range(total_frames_note):
            time = round(current_time + (i * time_per_frame), 3)
            frame_data = _create_frame_data(time)
            frame_data["chroma_stft"][note_index] = 1.0
            all_data.append(frame_data)
        current_time += 1.0

    # --- Part 2: Chords ---
    chords = [
        [0, 4, 7], # C Major
        [5, 9, 0], # F Major (F, A, C)
    ]
    for chord in chords:
        t_chord = _create_time_array(2.0)
        audio_chord = np.zeros_like(t_chord)
        for note_index in chord:
            freq = 261.63 * (2**(note_index/12))
            audio_chord += np.sin(2 * np.pi * freq * t_chord)

        audio_chord = (audio_chord / len(chord)) * 0.7
        all_audio = np.concatenate([all_audio, audio_chord])

        total_frames_chord = int(2.0 * FRAME_RATE)
        time_per_frame = 1 / FRAME_RATE
        for i in range(total_frames_chord):
            time = round(current_time + (i * time_per_frame), 3)
            frame_data = _create_frame_data(time)
            for note_index in chord:
                frame_data["chroma_stft"][note_index] = 1.0
            all_data.append(frame_data)
        current_time += 2.0

    return all_data, all_audio.astype(np.float32)

def generate_drums_onsets_and_tempo_data_and_audio(duration_seconds=15):
    """
    Generates drum hits for slow, medium, and fast tempos.
    """
    segment_duration = duration_seconds / 3
    tempos = [60, 120, 180]
    data = []
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)
    current_time_offset = 0.0

    for tempo in tempos:
        beats_per_second = tempo / 60
        time_per_beat = 1 / beats_per_second

        num_beats = int(segment_duration * beats_per_second)
        for i in range(num_beats):
            onset_time = current_time_offset + (i * time_per_beat)
            data.append(_create_hit_data(onset_time))

            # Add audio click
            start_idx = int(onset_time * SAMPLE_RATE)
            click_len = int(0.05 * SAMPLE_RATE)
            if start_idx + click_len < len(audio):
                audio[start_idx : start_idx + click_len] = np.random.uniform(-1, 1, click_len) * 0.5

        current_time_offset += segment_duration

    return data, audio.astype(np.float32)

def generate_drums_duration_data_and_audio(duration_seconds=5):
    """
    Generates a short hit and a long hit.
    """
    data = [
        {
            "onset_time": 1.0,
            "duration": 0.1,
            "drum_category": "snare",
            "relative_volume": 0.8
        },
        {
            "onset_time": 3.0,
            "duration": 1.5,
            "drum_category": "cymbal",
            "relative_volume": 0.8
        },
    ]
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    # Short hit (snare-like noise burst with fast decay)
    start_idx_1 = int(1.0 * SAMPLE_RATE)
    len_1 = int(0.1 * SAMPLE_RATE)
    noise_1 = np.random.uniform(-1, 1, len_1)
    decay_1 = np.linspace(1, 0, len_1)**2
    audio[start_idx_1 : start_idx_1 + len_1] = noise_1 * decay_1 * 0.8

    # Long hit (cymbal with slow decay)
    start_idx_2 = int(3.0 * SAMPLE_RATE)
    len_2 = int(1.5 * SAMPLE_RATE)
    # Cymbal sound is more complex: mix of sawtooth waves
    cymbal_sound = np.zeros(len_2)
    for freq in [200, 550, 900, 1300]:
        cymbal_sound += sawtooth(2 * np.pi * freq * np.linspace(0, 1.5, len_2))
    cymbal_sound /= 4.0
    decay_2 = np.linspace(1, 0, len_2)**0.5
    audio[start_idx_2 : start_idx_2 + len_2] = cymbal_sound * decay_2 * 0.8

    return data, audio.astype(np.float32)

def generate_drums_volume_data_and_audio(duration_seconds=10):
    """
    Generates a series of drum hits with ramping volume.
    """
    num_hits = 20
    times = np.linspace(1, duration_seconds - 1, num_hits)

    midpoint = num_hits // 2
    rising = np.linspace(0.1, 1.0, num=midpoint)
    falling = np.linspace(1.0, 0.1, num=num_hits - midpoint)
    volumes = np.concatenate([rising, falling])
    
    data = [_create_hit_data(times[i], {"relative_volume": volumes[i]}) for i in range(num_hits)]
    
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)
    
    for hit in data:
        start_idx = int(hit['onset_time'] * SAMPLE_RATE)
        click_len = int(hit['duration'] * SAMPLE_RATE)
        if start_idx + click_len < len(audio):
            click = np.random.uniform(-1, 1, click_len) * (np.linspace(1,0,click_len)**2)
            audio[start_idx : start_idx + click_len] = click * hit['relative_volume'] * 0.7

    return data, audio.astype(np.float32)

def generate_drums_frequency_ramp_data_and_audio(duration_seconds=10):
    """
    Generates drum hits with ramping frequency features.
    """
    num_hits = 20
    times = np.linspace(1, duration_seconds - 1, num_hits)

    midpoint = num_hits // 2
    rising = np.linspace(200, 5000, num=midpoint)
    falling = np.linspace(5000, 200, num=num_hits - midpoint)
    freqs = np.concatenate([rising, falling])

    data = []
    for i in range(num_hits):
        data.append(_create_hit_data(times[i], {
            "dominant_frequency": freqs[i],
            "spectral_centroid": freqs[i] * 1.5 # Keep them related
        }))

    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    for i, hit in enumerate(data):
        start_idx = int(hit['onset_time'] * SAMPLE_RATE)
        hit_len = int(hit['duration'] * SAMPLE_RATE)
        if start_idx + hit_len < len(audio):
            hit_t = np.linspace(0, hit['duration'], hit_len)
            # Short chirp for each hit
            f0 = freqs[i]
            f1 = f0 + 200 # slight upward chirp
            audio_hit = chirp(hit_t, f0=f0, f1=f1, t1=hit['duration'], method='linear')
            audio[start_idx : start_idx + hit_len] = audio_hit * 0.7

    return data, audio.astype(np.float32)

# def generate_drums_spectral_centroid_data_and_audio(duration_seconds=10):
# This function is included in the above frequency test since the two values are
# so closely related

def organize_drums_MLA_data_and_audio(duration_seconds=20):
    """
    Generates a sequence of different drum hits to showcase all permutations/
    combinations of the MLA classification
    """
    hits = [
        {
            "category": "kick",
            "type": "bass",
            "qualifier": "no_qualifier",
            "sound": "low_thud"
        },
        {
            "category": "snare",
            "type": "open_band",
            "qualifier": "no_qualifier",
            "sound": "noise_burst"
        },
        {
            "category": "snare",
            "type": "open_band",
            "qualifier": "rimshot",
            "sound": "sharp_click"
        },
        {
            "category": "cymbal",
            "type": "hihat",
            "qualifier": "close",
            "sound": "short_tiss"
        },
        {
            "category": "cymbal",
            "type": "hihat",
            "qualifier": "open",
            "sound": "long_tiss"
        },
        {
            "category": "tom",
            "type": "low",
            "qualifier": "no_qualifier",
            "sound": "mid_thud"
        },
        {
            "category": "cymbal",
            "type": "crash",
            "qualifier": "full",
            "sound": "crash_noise"
        },
    ]

    data = []
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    time_step = duration_seconds / (len(hits) + 1)

    for i, hit in enumerate(hits):
        onset_time = (i + 1) * time_step
        data.append({
            "onset_time": onset_time,
            "duration": 0.5,
            "drum_category": hit["category"],
            "drum_type": hit["type"],
            "qualifier": hit["qualifier"],
            "relative_volume": 0.8
        })

        # Generate audio for the hit
        start_idx = int(onset_time * SAMPLE_RATE)
        sound_len = int(0.5 * SAMPLE_RATE)

        sound_wave = np.zeros(sound_len)
        if hit["sound"] == "low_thud":
            thud_t = np.linspace(0, 0.5, sound_len)
            sound_wave = np.sin(2 * np.pi * 60 * thud_t) * (np.linspace(1, 0, sound_len)**3)
        elif hit["sound"] == "noise_burst":
            sound_wave = np.random.uniform(-1, 1, sound_len) * (np.linspace(1, 0, sound_len)**2)
        elif hit["sound"] == "sharp_click":
            sound_wave[:int(0.05*SAMPLE_RATE)] = np.random.uniform(-1, 1, int(0.05*SAMPLE_RATE))
        elif hit["sound"] == "short_tiss":
            sound_wave = np.random.uniform(-1, 1, sound_len) * (np.linspace(1, 0, sound_len)**4)
            # High-pass filter effect by mixing
            sound_wave = sound_wave - np.convolve(sound_wave, np.ones(10)/10, 'same')
        elif hit["sound"] == "long_tiss":
            sound_wave = np.random.uniform(-1, 1, sound_len) * (np.linspace(1, 0, sound_len)**0.5)
            sound_wave = sound_wave - np.convolve(sound_wave, np.ones(10)/10, 'same')
        elif hit["sound"] == "mid_thud":
            thud_t = np.linspace(0, 0.5, sound_len)
            sound_wave = np.sin(2 * np.pi * 150 * thud_t) * (np.linspace(1, 0, sound_len)**2)
        elif hit["sound"] == "crash_noise":
            sound_wave = np.random.uniform(-1, 1, sound_len) * (np.linspace(1, 0, sound_len)**0.3)

        audio[start_idx : start_idx + sound_len] = sound_wave * 0.8

    return data, audio.astype(np.float32)

def generate_lyric_data_and_audio(duration_seconds=10):
    """
    Generates simple lyric data and a corresponding synth melody as vocal data
    """
    lyric_data = [
        {
            "line_text": "This is the first line",
            "line_start_time": 1.0, "line_end_time": 3.5,
            "words": [
                {"word": "This", "start": 1.0, "end": 1.2},
                {"word": "is", "start": 1.3, "end": 1.5},
                {"word": "the", "start": 1.6, "end": 1.8},
                {"word": "first", "start": 2.2, "end": 2.7},
                {"word": "line", "start": 2.9, "end": 3.5},
            ]
        },
        {
            "line_text": "And this is the second",
            "line_start_time": 5.0, "line_end_time": 7.8,
            "words": [
                {"word": "And", "start": 5.0, "end": 5.2},
                {"word": "this", "start": 5.3, "end": 5.6},
                {"word": "is", "start": 5.7, "end": 6.0},
                {"word": "the", "start": 6.1, "end": 6.4},
                {"word": "second", "start": 6.8, "end": 7.8},
            ]
        }
    ]

    # Audio: Simple synth melody matchin word timings and pitches
    t_full = _create_time_array(duration_seconds)
    audio = np.zeros_like(t_full)

    # Pitches for words (in Hz)
    pitches = [261, 293, 261, 329, 293, 349, 392, 249, 440, 392]

    word_list = [word for line in lyric_data for word in line['words']]

    for i, word in enumerate(word_list):
        start_idx = int(word['start'] * SAMPLE_RATE)
        end_idx = int(word['end'] * SAMPLE_RATE)
        duration_samples = end_idx - start_idx

        if duration_samples > 0:
            word_t = np.linspace(0, (duration_samples-1)/SAMPLE_RATE, duration_samples)
            # Sawtooth wave for synth sound
            word_audio = sawtooth(2 * np.pi * pitches[i] * word_t)
            # Simple ADSR envelope
            attack_len = int(0.05 * duration_samples)
            decay_len = int(0.1 * duration_samples)
            sustain_level = 0.7
            envelope = np.concatenate([
                np.linspace(0, 1, attack_len),
                np.linspace(1, sustain_level, decay_len),
                np.full(duration_samples - attack_len - decay_len, sustain_level)
            ])
            audio[start_idx:end_idx] = word_audio * envelope * 0.6

    # Harmonic data is also needed to provide context
    harmonic_data = []
    total_frames = int(duration_seconds * FRAME_RATE)
    time_per_frame = 1 / FRAME_RATE
    current_word_index = 0
    for i in range(total_frames):
        time = i * time_per_frame
        frame_data = _create_frame_data(time, {"f0_data": 0, "rms": 0})

        # Find active word
        active_word = None
        for word in word_list:
            if time >= word['start'] and time < word['end']:
                active_word = word
                break

        if active_word:
            word_idx = word_list.index(active_word)
            frame_data['f0_data'] = pitches[word_idx]
            frame_data['rms'] = 0.6

        harmonic_data.append(frame_data)

    return {"lyrics": lyric_data, "harmonic": harmonic_data}, audio.astype(np.float32)

def combine_generated_mock_audio_and_data():
    """
    Combines all generated clips into a single data object and audio stream.
    """
    # List of functions to call
    generators = [
        generate_harmonic_pitch_ramp_data_and_audio,
        generate_harmonic_volume_ramp_data_and_audio,
        generate_overall_volume_ramp_data_and_audio,
        generate_harmonic_tempos_data_and_audio,
        generate_harmonic_beats_and_onsets_data_and_audio,
        generate_harmonic_spectral_centroid_data_and_audio,
        generate_harmonic_spectral_rolloff_data_and_audio,
        generate_harmonic_spectral_flatness_data_and_audio,
        generate_harmonic_mfccs_data_and_audio,
        generate_chroma_stft_data_and_audio,
        generate_drums_onsets_and_tempo_data_and_audio,
        generate_drums_duration_data_and_audio,
        generate_drums_volume_data_and_audio,
        generate_drums_frequency_ramp_data_and_audio,
        organize_drums_MLA_data_and_audio,
        generate_lyric_data_and_audio,
    ]

    final_data, final_audio = {}, np.array([], dtype=np.float32)
    pause_audio = np.zeros(int(2 * SAMPLE_RATE), dtype=np.float32)
    current_offset = 0.0

    for func in generators:
        # Generate data and audio
        data, audio = func()
        final_data[func.__name__] = _offset_data(data, current_offset)
        final_audio = np.concatenate([final_audio, audio, pause_audio])
        current_offset += (len(audio) + len(pause_audio)) / SAMPLE_RATE
    return final_data, final_audio
