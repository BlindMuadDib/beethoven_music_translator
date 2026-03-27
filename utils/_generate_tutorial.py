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

def _create_filtered_noise_audio(duration_seconds, start_freq, end_freq, filter_type='low'):
    """
    Helper to generate audio for spectral ramps.
    filter_type: 'low' for lowpass (Rolloff), 'band' for bandpass (Centroid)
    """
    t = _create_time_array(duration_seconds)
    noise = np.random.normal(0, 0.5, len(t))
    audio = np.zeros_like(noise)

    num_segments = 100
    segment_len = len(t) // num_segments
    freqs = np.linspace(start_freq, end_freq, num_segments)

    for i in range(num_segments):
        start, end = i * segment_len, (i + 1) * segment_len
        nyquist = 0.5 * SAMPLE_RATE
        center_freq = np.clip(freqs[i], 20, nyquist - 100)

        if filter_type == 'band':
            # Bandpass creates a resonant "wah" sound
            width = center_freq * 0.5
            low = np.clip(center_freq - width/2, 20, nyquist-1)
            high = np.clip(center_freq + width/2, low+10, nyquist-1)
            b, a = butter(4, [low/nyquist, high/nyquist], btype='band')
        else:
            # Lowpass creates a "muffling/opening" sound
            cutoff = np.clip(center_freq, 20, nyquist-1)
            b, a = butter(4, cutoff/nyquist, btype='low')

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
        # Spectrogram must correspond to frequencies for the blob to draw
        # correctly. We provide 2 points to ensure createDynamicPath has a
        # line to draw
        f = frequencies[i]
        data.append(_create_frame_data(time, {
            "frequencies": [f, f * 2],
            "spectrogram": [1.0, 0.5],
            "f0_data": f
        }))

    # --- Generating Corresponding Audio ---
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
        frame_data = _create_frame_data(time,
                                        {"f0_data": 440.0,
                                         "rms": rms_values[i]})
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

    # Create symmetrical envelopes so volume peaks in middle and drops at end
    # Track 1: Central Triangle (Peaks at 50%)
    peak1 = total_frames // 2
    rms1 = np.concatenate([
        np.linspace(0, 0.8, peak1),
        np.linspace(0.8, 0, total_frames - peak1)
    ])

    # Track 2: Early Peak (Peaks at 33%)
    peak2 = total_frames // 3
    rms2 = np.concatenate([
        np.linspace(0, 0.8, peak2),
        np.linspace(0.8, 0, total_frames - peak2)
    ])

    # Track 3: Late Peak (Peaks at 66%)
    peak3 = (total_frames * 2) // 3
    rms3 = np.concatenate([
        np.linspace(0, 0.8, peak3),
        np.linspace(0.8, 0, total_frames - peak3)
    ])

    # Ensure lengths match exactly due to rounding
    rms1 = np.resize(rms1, total_frames)
    rms2 = np.resize(rms2, total_frames)
    rms3 = np.resize(rms3, total_frames)

    # Overall Volume (Sum)
    overall_rms = np.clip(rms1 + rms2 + rms3, 0, 1.0)
    times = np.linspace(0, duration_seconds, total_frames).tolist()

    data = {
        "overall": {"times": times, "values": overall_rms.tolist()},
        "tracks": [
            [_create_frame_data(times[i], {
                "rms": rms1[i], 
                "f0_data": 261.63, 
                "frequencies": [261.63 * (n+1) for n in range(8)], 
                "spectrogram": [rms1[i] * v for v in [0.8, 0.4, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005]]
            }) for i in range(total_frames)],
            [_create_frame_data(times[i], {
                "rms": rms2[i], 
                "f0_data": 329.63, 
                "frequencies": [329.63 * (n+1) for n in range(8)], 
                "spectrogram": [rms2[i] * v for v in [0.8, 0.4, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005]]
            }) for i in range(total_frames)],
            [_create_frame_data(times[i], {
                "rms": rms3[i], 
                "f0_data": 392.00, 
                "frequencies": [392.00 * (n+1) for n in range(8)], 
                "spectrogram": [rms3[i] * v for v in [0.8, 0.4, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005]]
            }) for i in range(total_frames)],
        ]
    }

    # Audio generation matching the envelopes
    t = _create_time_array(duration_seconds)
    len_t = len(t)
    tone1 = np.sin(2 * np.pi * 261.63 * t) # C4
    tone2 = np.sin(2 * np.pi * 329.63 * t) # E4
    tone3 = np.sin(2 * np.pi * 392.00 * t) # G4

    # Audio envelopes (matching data shapes)
    p1 = len_t // 2
    env1 = np.concatenate([
        np.linspace(0, 1, p1), np.linspace(1, 0, len_t - p1)
    ])

    p2 = len_t // 3
    env2 = np.concatenate([
        np.linspace(0, 0.9, p2), np.linspace(0.9, 0, len_t - p2)
    ])

    p3 = (len_t * 2) // 3
    env3 = np.concatenate([
        np.linspace(0, 0.9, p3), np.linspace(0.9, 0, len_t - p3)
    ])

    # Resize to ensure safety against rounding
    env1 = np.resize(env1, len_t)
    env2 = np.resize(env2, len_t)
    env3 = np.resize(env3, len_t)

    # Combine tones
    audio = (tone1 * env1 + tone2 * env2 + tone3 * env3) / 3.0
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
        beats_per_second = tempo / 60
        beat_interval = 1.0 / beats_per_second

        for i in range(total_frames):
            time = round(current_time_offset + (i * time_per_frame), 3)
            # Modulate RMS to match beat
            local_time = i * time_per_frame
            dist_to_beat = min(abs(local_time % beat_interval),
                               abs((local_time % beat_interval) - beat_interval))
            rms = 0.8 if dist_to_beat < 0.05 else 0.0

            frame_data = _create_frame_data(
                time,
                {"rms": rms, "f0_data": 440.0, "tempo": tempo}
            )
            all_data.append(frame_data)

        # Audio: Metronome clicks
        t = _create_time_array(segment_duration)
        audio_segment = np.zeros_like(t)
        interval = int(SAMPLE_RATE / beats_per_second)
        for i in range(0, len(audio_segment), interval):
            click_len = int(SAMPLE_RATE * 0.02)
            if i + click_len < len(audio_segment):
                audio_segment[i:i+click_len] = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.02, click_len)) * 0.8

        all_audio = np.concatenate([all_audio, audio_segment])
        current_time_offset += segment_duration

    return all_data, all_audio.astype(np.float32)

def generate_harmonic_beats_and_onsets_data_and_audio(duration_seconds=10):
    """
    Generates a track with steady onsets and beats.
    """
    tempo = 120
    time_per_beat = 60 / tempo

    beats = np.arange(0, duration_seconds, time_per_beat).tolist()
    # Place onsets on the off-beats
    onsets = (np.arange(0, duration_seconds, time_per_beat) + time_per_beat / 2).tolist()

    # Data is not frame-based for this, but static features.
    # Return it in a format that can be placed in `temporal_features`
    data = {"beats": beats, "onsets": onsets, "tempo": tempo}

    # Audio
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    # Generate Audio
    for b in beats:
        idx, dur = int(b * SAMPLE_RATE), int(SAMPLE_RATE * 0.05)
        if idx+dur < len(audio):
            audio[idx:idx+dur] = np.sin(2*np.pi*500*np.linspace(0,
                                                                0.05,
                                                                dur))*0.7
    for o in onsets:
        idx, dur = int(o * SAMPLE_RATE), int(SAMPLE_RATE * 0.05)
        if idx+dur < len(audio):
            audio[idx:idx+dur] = np.sin(2*np.pi*1200*np.linspace(0,
                                                                 0.05,
                                                                 dur))*0.7

    return data, audio.astype(np.float32)

# def generate_harmonic_f0_data_and_audio(duration_seconds=10):
# This function is redundant given the method for generate_harmonic_pitch_ramp_data_and_audio

def generate_harmonic_spectral_centroid_data_and_audio(duration_seconds=10):
    """
    Generates a ramp for spectral centroid using BANDPASS filter (wah effect).
    """
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

    audio_up = _create_filtered_noise_audio(duration_seconds/2, 500, 4000,
                                            filter_type='band')
    audio_down = _create_filtered_noise_audio(duration_seconds/2, 4000, 500,
                                              filter_type='band')
    audio = np.concatenate([audio_up, audio_down])
    audio = audio * (0.8 / np.max(np.abs(audio)))

    return data, audio.astype(np.float32)

def generate_harmonic_spectral_rolloff_data_and_audio(duration_seconds=10):
    """
    Generates a ramp for spectral rolloff using LOWPASS filter (muffling).
    """
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
        frame_data["spectral_rolloff"] = values[i]
        data.append(frame_data)

    audio_up = _create_filtered_noise_audio(duration_seconds/2, 500, 8000,
                                            filter_type='low')
    audio_down = _create_filtered_noise_audio(duration_seconds/2, 8000, 500,
                                              filter_type='low')
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
            frame_data = _create_frame_data(time, {"f0_data": freq, "frequencies": [freq]})
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
        bps = tempo / 60
        for i in range(int(segment_duration * bps)):
            onset = current_time_offset + (i / bps)
            # Use helper to ensure all spectral fields are present
            data.append(_create_hit_data(onset))
            idx, dur = int(onset*SAMPLE_RATE), int(0.05*SAMPLE_RATE)
            if idx+dur < len(audio):
                audio[idx:idx+dur] = np.random.uniform(-1, 1, dur)*0.5
        current_time_offset += segment_duration
    return data, audio.astype(np.float32)

def generate_drums_duration_data_and_audio(duration_seconds=5):
    """
    Generates a short hit and a long hit.
    """
    # Use _create_hit_data to populate required spectral fields
    data = [
        _create_hit_data(1.0, {
            "onset_time": 1.0,
            "duration": 0.1,
            "drum_category": "snare",
            "relative_volume": 0.8
        }),
        _create_hit_data(3.0, {
            "onset_time": 3.0,
            "duration": 1.5,
            "drum_category": "cymbal",
            "relative_volume": 0.8
        }),
    ]
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)

    # Short hit (snare-like noise burst with fast decay)
    start_idx_1 = int(1.0 * SAMPLE_RATE)
    len_1 = int(0.1 * SAMPLE_RATE)
    noise_1 = np.random.uniform(-1, 1, len_1)
    decay_1 = np.linspace(1, 0, len_1)**2
    audio[start_idx_1:start_idx_1+len_1] = noise_1 * decay_1 * 0.8

    # Long hit (cymbal with slow decay)
    start_idx_2 = int(3.0 * SAMPLE_RATE)
    len_2 = int(1.5 * SAMPLE_RATE)
    # Cymbal sound is more complex: mix of sawtooth waves
    cymbal = sum(sawtooth(2*np.pi*f*np.linspace(0, 1.5, len_2)) for f in [200, 550, 900, 1300])/4.0
    decay_2 = np.linspace(1, 0, len_2)**0.5
    audio[start_idx_2 : start_idx_2 + len_2] = cymbal * decay_2 * 0.8

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
        idx = int(hit['onset_time'] * SAMPLE_RATE)
        dur = int(hit['duration'] * SAMPLE_RATE)
        if idx+dur < len(audio):
            audio[idx:idx+dur] = np.random.uniform(-1, 1, dur) * (np.linspace(1,0,dur)**2) * hit['relative_volume'] * 0.7

    return data, audio.astype(np.float32)

def generate_drums_frequency_ramp_data_and_audio(duration_seconds=10):
    """
    Generates drum hits with ramping frequency features.
    """
    num_hits = 20
    times = np.linspace(1, duration_seconds - 1, num_hits)

    midpoint = num_hits // 2
    rising = np.linspace(200, 2500, num=midpoint)
    falling = np.linspace(2500, 200, num=num_hits-midpoint)
    freqs = np.concatenate([rising, falling])
    data = [_create_hit_data(times[i],
                             {"dominant_frequency": freqs[i],
                              "spectral_centroid": freqs[i]*1.5}) for i in range(num_hits)]
    t = _create_time_array(duration_seconds)
    audio = np.zeros_like(t)
    for i, hit in enumerate(data):
        idx = int(hit['onset_time']*SAMPLE_RATE)
        dur = int(hit['duration']*SAMPLE_RATE)
        if idx+dur < len(audio):
            audio[idx:idx+dur] = chirp(np.linspace(0, hit['duration'], dur),
                                       f0=freqs[i],
                                       f1=freqs[i]*1.5,
                                       t1=hit['duration']) * 0.7
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

    step = duration_seconds / (len(hits) + 1)

    for i, hit in enumerate(hits):
        onset = (i + 1) * step
        # Use helper to ensure spectral fields
        data.append(_create_hit_data(onset, {
            "duration": 0.5, "drum_category": hit["category"],
            "drum_type": hit["type"], "qualifier": hit["qualifier"],
            "relative_volume": 0.8
        }))

        # Generate audio for the hit
        idx = int(onset*SAMPLE_RATE)
        dur = int(0.5*SAMPLE_RATE)

        wave = np.zeros(dur)
        if hit["sound"] == "low_thud":
            thud_t = np.linspace(0, 0.5, dur)
            wave = np.sin(2*np.pi*60*thud_t) * (np.linspace(1, 0, dur)**3)
        elif hit["sound"] == "noise_burst":
            wave = np.random.uniform(-1, 1, dur) * (np.linspace(1, 0, dur)**2)
        elif hit["sound"] == "sharp_click":
            wave[:int(0.05*SAMPLE_RATE)] = np.random.uniform(-1, 1, int(0.05*SAMPLE_RATE))
        elif hit["sound"] == "short_tiss":
            wave = np.random.uniform(-1, 1, dur) * (np.linspace(1, 0, dur)**4) - np.convolve(np.random.uniform(-1, 1, dur), np.ones(10)/10, 'same')
        elif hit["sound"] == "long_tiss":
            wave = np.random.uniform(-1, 1, dur) * (np.linspace(1, 0, dur)**0.5) - np.convolve(np.random.uniform(-1, 1, dur), np.ones(10)/10, 'same')
        elif hit["sound"] == "mid_thud":
            thud_t = np.linspace(0, 0.5, dur)
            wave = np.sin(2*np.pi*150*thud_t) * (np.linspace(1, 0, dur)**2)
        elif hit["sound"] == "crash_noise":
            wave = np.random.uniform(-1, 1, dur) * (np.linspace(1, 0, dur)**0.3)

        audio[idx:idx+dur] = wave * 0.8

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
    Combines all generated clips into a unified data object and audio stream,
    structured specifically to satisfy HarmonicVisualizer, DrumTracker,
    and VolumeTracker.
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

    final_audio = np.array([], dtype=np.float32)
    pause_audio = np.zeros(int(2 * SAMPLE_RATE), dtype=np.float32)
    current_offset = 0.0

    # Containers for the merged data
    all_harmonic_frames = []    # Tutorial_Demonstration (Main)
    track_1_frames = []         # Track 1
    track_2_frames = []         # Track 2
    track_3_frames = []         # Track 3

    all_drum_hits = []
    all_lyrics = []

    # Specific containers for trackers
    rms_overall_data = {"times": [], "values": []}
    combined_temporal_features = {"tempo": 120, "beats": [], "onsets": []}

    for func in generators:
        # Generate raw data and audio
        data, audio = func()

        # Apply time offset to the data
        offset_data = _offset_data(data, current_offset)

        # Calculate duration of this segment for padding
        seg_duration = len(audio) / SAMPLE_RATE
        num_seg_frames = int(seg_duration * FRAME_RATE)
        seg_times = [current_offset + (i / FRAME_RATE) for i in range(num_seg_frames)]

        # 1. Overall Volume (VolumeTracker) SPECIAL HANDLING
        # This generator returns column-oriented data {times: [], values: []}
        if func.__name__ == 'generate_overall_volume_ramp_data_and_audio':
            # Append to rms_overall
            rms_overall_data['times'].extend(offset_data['overall']['times'])
            rms_overall_data['values'].extend(offset_data['overall']['values'])

            # Distribute the 3 separate tracks
            tracks = offset_data['tracks'] # List of 3 lists of frames
            # Pad Main with silence
            for t in seg_times:
                all_harmonic_frames.append(_create_frame_data(t,
                                                              {"rms": 0,
                                                               "f0_data": 0}))
            # Add data to stems
            track_1_frames.extend(tracks[0])
            track_2_frames.extend(tracks[1])
            track_3_frames.extend(tracks[2])

        # --- STANDARD HANDLING ---
        else:
            # Pad extra stems with silence
            for t in seg_times:
                silent_frame = _create_frame_data(t,
                                                  {"rms": 0, "f0_data": 0})
                track_1_frames.append(silent_frame)
                track_2_frames.append(silent_frame)
                track_3_frames.append(silent_frame)

            # 2. Lyrics (LyricTracker)
            if func.__name__ == 'generate_lyric_data_and_audio':
                all_lyrics.extend(offset_data['lyrics'])
                all_harmonic_frames.extend(offset_data['harmonic'])
                # Add lyric harmonic data to overall volume
                l_frames = offset_data['harmonic']
                rms_overall_data['times'].extend([f['time'] for f in l_frames])
                rms_overall_data['values'].extend([f.get('rms', 0.0) for f in l_frames])

            # 3. Drums (DrumTracker)
            elif 'drum' in func.__name__:
                # Drum generators return a list of hit objects
                if isinstance(offset_data, list):
                    all_drum_hits.extend(offset_data)
                rms_overall_data['times'].extend(seg_times)
                rms_overall_data['values'].extend([0.0] * num_seg_frames)
                for t in seg_times:
                    all_harmonic_frames.append(
                        _create_frame_data(t, {"rms": 0, "f0_data": 0})
                    )

            # 4. Handle Beats/Onsets (Temporal Features)
            elif isinstance(offset_data, dict) and 'beats' in offset_data:
                combined_temporal_features['beats'].extend(offset_data['beats'])
                combined_temporal_features['onsets'].extend(offset_data['onsets'])
                rms_overall_data['times'].extend(seg_times)
                rms_overall_data['values'].extend([0.0] * num_seg_frames)
                for t in seg_times:
                    # Check if close to a beat or onset
                    is_beat = any(
                        abs(t - b) < 0.02 for b in offset_data['beats']
                    )
                    is_onset = any(
                        abs(t -o) < 0.02 for o in offset_data['onsets']
                    )
                    rms = 0.8 if (is_beat or is_onset) else 0.0
                    f0 = 440.0 if is_beat else 880.0 if is_onset else 0.0
                    all_harmonic_frames.append(
                        _create_frame_data(t, {"rms": 0, "f0_data": 0})
                    )

            # 5. Standard Harmonic Generators (HarmonicVisualizer)
            elif isinstance(offset_data, list):
                times = [f['time'] for f in offset_data]
                values = [f.get('rms', 0.0) for f in offset_data]
                rms_overall_data['times'].extend(times)
                rms_overall_data['values'].extend(values)
                all_harmonic_frames.extend(offset_data)

        # Append audio
        final_audio = np.concatenate([final_audio, audio, pause_audio])

        # Add padding frames for the pause duration
        pause_duration = len(pause_audio) / SAMPLE_RATE
        num_pause_frames = int(pause_duration * FRAME_RATE)
        pause_times = [current_offset + seg_duration + (i / FRAME_RATE) for i in range(num_pause_frames)]

        for t in pause_times:
            silent = _create_frame_data(t, {"rms": 0, "f0_data": 0})
            all_harmonic_frames.append(silent)
            track_1_frames.append(silent)
            track_2_frames.append(silent)
            track_3_frames.append(silent)
            rms_overall_data['times'].append(t)
            rms_overall_data['values'].append(0.0)

        current_offset += seg_duration + pause_duration

    # --- PIVOT DATA ---
    # Convert the list of frames (Row-Oriented) to dict of lists (Column-Oriented)
    # This populates 'f0_data', 'rms', etc. in full_track_analysis
    # Helper function to pivot
    def pivot_frames(frames):
        if not frames: return {}
        # Get keys from the first frame (excluding time if strictly column-
        # oriented but the visualizer often wants time arrays too if not
        # using accessors)
        columns = {}
        keys = frames[0].keys()

        for k in keys:
            # Create a list for every key found in the frames
            columns[k] = [f.get(k, None) for f in frames]
        return columns

    main_columns = pivot_frames(all_harmonic_frames)

    # --- FINAL FORMATTING ---

    final_data_structure = {
        "job_id": "tutorial_mode",
        "status": "finished",
        "harmonic_analysis": {
            # VolumeTracker reads from here
            "full_track_analysis": {
                "duration": current_offset,
                "rms_overall": rms_overall_data,
                **main_columns # MERGE the pivoted data here
            },
            # HarmonicVisualizer iterates over keys in 'stem_analyses'
            "stem_analyses": {
                "Tutorial_Demonstration": {
                    "temporal_features": combined_temporal_features,
                    # This key 'frames' will be used in app.js to create the TimeSeriesAccessor
                    "frames": all_harmonic_frames
                },
                "Track_1": {
                    "temporal_features": {},
                    "frames": track_1_frames
                },
                "Track_2": {
                    "temporal_features": {},
                    "frames": track_2_frames
                },
                "Track_3": {
                    "temporal_features": {},
                    "frames": track_3_frames
                }
            }
        },
        "drum_analysis": {
            "hits": all_drum_hits
        },
        "mapped_result": all_lyrics
    }

    return final_data_structure, final_audio
