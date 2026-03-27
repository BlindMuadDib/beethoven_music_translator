"""
Test suite for _generate_tutorial.py, which is responsible for automatically
generating the data and audio needed for the front-end to make a comprehensive
tutorial video.

Each function of the front-end needs its own isolated demonstration of the
range of possible values with an audio file that allows users to understand the
basic concepts of each piece of the translator they are viewing. Concepts like
MFCC may be too large to tackle the range of possibilities so a dumbed-down
version is acceptable
Elements that need isolated range demonstrations:
    Harmonic:
        Pitch (ramped up and down),
        Track volume (ramped up and down),
        Overall volume (ramped up and down),
        Tempo (slow, medium, fast),
        Beats (on/off),
        Onsets (on/off),
        f0_data (ramped up and down),
        Spectral_centroid (ramped up and down),
        spectral_rolloff (ramped up and down),
        spectral_flatness (ramped up and down),
        mfccs (simply show two or three drastic variations as a placeholder)
        chroma_stft (show each note individually, show some chords),
    Drum: (hits for each drum categories/types/qualifiers can be pulled from the training data if necessary)
        onsets (on/off),
        tempo (slow, med, fast)
        duration (short vs long),
        relative_volume (ramped up and down),
        dominant_frequency (ramped up and down),
        spectral_centroid (ramped up and down),
        spectral_rolloff (ramped up and down),
        spectral_flux (ramped up and down),
        DrumMLA: (not all categories, types and qualifiers are compatible with each other,
                  for full list of compatibilites see pasted list from musictranslator/drum_service/DrumMLA.py:
            self.drum_categories = ['kick', 'snare', 'tom', 'cymbal', 'other']
            self.drum_types = {
                'kick': ['bass'],
                'snare': ['open_band', 'closed_band'],
                'tom': ['med_high', 'med_low', 'mid', 'low', 'high'],
                'cymbal': ['crash', 'hihat', 'ride', 'gong', 'unknown'],
                'other': ['cowbell', 'unknown']
            }
            self.drum_qualifiers = {
                'snare': ['rimshot', 'brush', 'chains', 'no_qualifier'],
                'tom': ['rimshot', 'brush', 'chains', 'no_qualifier'],
                'kick': ['no_qualifier'],
                'other': ['no_qualifier', 'muted', 'brush', 'chains'],

                'cymbal': {
                    'crash': ['full', 'mid', 'bell', 'muted', 'brush', 'chains', 'no_qualifier',
                            'full_muted', 'mid_muted', 'bell_muted',
                            'full_brush', 'mid_brush', 'bell_brush',
                            'full_chains', 'mid_chains', 'bell_chains',
                            'brush_muted', 'chains_muted',
                            'bell_brush_muted', 'bell_chains_muted',
                            'mid_brush_muted', 'mid_chains_muted',
                            'full_brush_muted', 'full_chains_muted',
                            'brush_bell', 'chains_bell',
                            'brush_full', 'chains_full',
                            'brush_mid', 'chains_mid',
                            'brush_bell_muted', 'chains_bell_muted',
                            'brush_full_muted', 'chains_full_muted',
                            'brush_mid_muted', 'chains_mid_muted',
                            ],
                    'hihat': ['open', 'close', 'muted', 'brush', 'chains', 'no_qualifier',
                            'open_muted', 'close_muted',
                            'open_brush', 'open_chains',
                            'close_brush', 'close_chains',
                            'brush_muted', 'chains_muted',
                            'brush_open', 'brush_close',
                            'chains_open', 'chains_close',
                            'brush_muted_open', 'brush_muted_close',
                            'chains_muted_open', 'chains_muted_close'
                            ],
                    'ride': ['bell', 'mid', 'muted', 'no_qualifier', 'brush', 'chains',
                            'bell_muted', 'mid_muted',
                            'bell_brush', 'mid_brush',
                            'bell_chains', 'mid_chains',
                            'brush_muted', 'chains_muted',
                            'brush_bell', 'chains_bell',
                            'brush_mid', 'chains_mid',
                            'brush_bell_muted', 'chains_bell_muted',
                            'brush_mid_muted', 'chains_mid_muted',
                            ],
                    'gong': ['muted', 'brush', 'chains', 'no_qualifier',
                            'brush_muted', 'chains_muted'
                            ],
                    'unknown': ['full', 'mid', 'bell', 'muted', 'brush',
                                'chains', 'no_qualifier',
                                'full_muted', 'mid_muted', 'bell_muted',
                                'full_brush', 'mid_brush', 'bell_brush',
                                'full_chains', 'mid_chains',
                                'bell_chains', 'brush_muted',
                                'chains_muted', 'bell_brush_muted',
                                'bell_chains_muted', 'mid_brush_muted',
                                'mid_chains_muted', 'full_brush_muted',
                                'full_chains_muted', 'brush_bell',
                                'chains_bell', 'brush_full',
                                'chains_full', 'brush_mid', 'chains_mid',
                                'brush_bell_muted', 'chains_bell_muted',
                                'brush_full_muted', 'chains_full_muted',
                                'brush_mid_muted', 'chains_mid_muted',
                            ]
                })
    Lyrics:
        Basic text display with onsets
    Overall_volume:
        Create a multitrack dataset/audio that starts very quite,
        with one or two instruments getting louder at a time until all
        instruments are max volume, making Overall_volume max volume.
        Then do a similar process in reverse.

Each function should be allotted about 5-15 seconds in the first iteration
Descriptions will be handled manually after successful generation of the
tutorial audio and data.
"""
import unittest
import numpy as np
from utils import _generate_tutorial

class TestTutorialGeneration(unittest.TestCase):
    def test_generate_harmonic_pitch_ramp_data_and_audio(self):
        """
        Should keep all values constant except pitch,
        Pitch should start at low threshold, rise to the top and fall down
        """
        # Define the constants for the test
        duration_seconds = 5

        # Call the function to get the generated data and audio
        data, audio = _generate_tutorial.generate_harmonic_pitch_ramp_data_and_audio(duration_seconds)

        # 1. Test the data structure and types
        self.assertIsInstance(data, list)
        self.assertIsInstance(audio, np.ndarray)
        self.assertTrue(len(data) > 0, "Data list should not be empty")

        # 2. Test the contents of a data frame
        first_frame = data[0]
        self.assertIn("time", first_frame)
        self.assertIn("f0_data", first_frame)
        self.assertIn("rms", first_frame)
        self.assertEqual(first_frame['time'], 0.0)

        # 3. Test the pitch ramp logic
        # The f0_data should be higher in the middle than at the start
        # and lower at the end than in the middle
        start_pitch = data[0]['f0_data']
        mid_pitch = data[len(data) // 2]['f0_data']
        end_pitch = data[-1]['f0_data']

        self.assertGreater(mid_pitch, start_pitch,
                           "Pitch should increase from start to middle")
        self.assertLess(end_pitch, mid_pitch,
                        "Pitch should decrease from middle to end")
        # Let's check that it ends near where it started
        self.assertAlmostEqual(start_pitch, end_pitch, delta=10,
                               msg="Pitch should end near its starting frequency")

        # 4. Test audio properties
        expected_audio_length = duration_seconds * _generate_tutorial.SAMPLE_RATE
        self.assertAlmostEqual(len(audio), expected_audio_length, delta=1,
                               msg="Audio length should match duration * sample_rate")

    def test_generate_harmonic_volume_ramp_data_and_audio(self):
        """
        Should keep all values constant except track volume.
        Track volume should start at a low value, rise to max volume and fall
        back down
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_harmonic_volume_ramp_data_and_audio(duration_seconds)

        self.assertIsInstance(data, list)
        self.assertTrue(len(data) > 0)

        start_rms = data[1]['rms'] # index 1 to avoid potential initial 0
        mid_rms = data[len(data) // 2]['rms']
        end_rms = data[-2]['rms'] # index -2 to avoid potential final 0

        self.assertAlmostEqual(start_rms, 0.0, delta=0.1)
        self.assertGreater(mid_rms, start_rms)
        self.assertLess(end_rms, mid_rms)
        self.assertAlmostEqual(start_rms, end_rms, delta=0.1)

        # Check that other values are constant
        self.assertEqual(data[10]['f0_data'], data[len(data)//2]['f0_data'])

        expected_audio_length = duration_seconds * _generate_tutorial.SAMPLE_RATE
        self.assertAlmostEqual(len(audio), expected_audio_length, delta=1)

    def test_generate_overall_volume_ramp_data_and_audio(self):
        """
        Should generate multiple tracks where all values are constant except
        volume.
        Tracks and overall_volume should start at rms=0, then one or two tracks
        should increase in volume at a time until all tracks are max volume,
        making overall_volume max, then decrease the volume in a similar
        fashion
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_overall_volume_ramp_data_and_audio(duration_seconds)

        self.assertIsInstance(data, dict)
        self.assertIn('overall', data)
        self.assertIn('tracks', data)

        # Check overall volume ramp
        values = data['overall']['values']
        self.assertTrue(len(values) > 0)
        start_rms = values[1]
        mid_rms = values[len(values) // 2]
        end_rms = values[-2]
        self.assertAlmostEqual(start_rms, 0.0, delta=0.1)
        self.assertGreater(mid_rms, end_rms)

        # Check tracks
        tracks = data['tracks']
        self.assertEqual(len(tracks), 3)
        self.assertEqual(len(tracks[0]), len(values)) # Should match frame count
        self.assertIn('frequencies', tracks[0][0])
        self.assertIn('spectrogram', tracks[0][0])

    def test_generate_harmonic_tempos_data_and_audio(self):
        """
        Should generate three subsequent audio/data segments of varying tempos.
        1st should be slow tempo, 2nd medium, 3rd fast
        """
        duration_seconds = 15
        data, audio = _generate_tutorial.generate_harmonic_tempos_data_and_audio(duration_seconds)

        segment_len = len(data) // 3
        tempo1 = data[segment_len // 2]['tempo']
        tempo2 = data[segment_len + (segment_len // 2)]['tempo']
        tempo3 = data[2 * segment_len + (segment_len // 2)]['tempo']

        self.assertEqual(tempo1, 60)
        self.assertEqual(tempo2, 120)
        self.assertEqual(tempo3, 180)
        self.assertGreater(tempo2, tempo1)
        self.assertGreater(tempo3, tempo2)

        expected_audio_length = duration_seconds * _generate_tutorial.SAMPLE_RATE
        self.assertAlmostEqual(len(audio), expected_audio_length, delta=1)

    def test_generate_harmonic_beats_and_onsets_data_and_audio(self):
        """
        Should generate a track with onset and beat data that aligns with a
        steady tempo.
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_harmonic_beats_and_onsets_data_and_audio(duration_seconds)

        self.assertIn('beats', data)
        self.assertIn('onsets', data)
        self.assertIn('tempo', data)
        self.assertEqual(data['tempo'], 120)

        # 120 bpm = 2 bps = beat every 0.5s
        self.assertAlmostEqual(data['beats'][1], 0.5)
        self.assertAlmostEqual(data['onsets'][0], 0.25)
    #
    # def test_generate_harmonic_f0_data_and_audio(self):
    #     """
    #     Should generate a rising and falling f0_data ramp to show the concept
    #     and its range.
    #     """
    #     duration_seconds = 5
    #     data, audio = _generate_tutorial.generate_harmonic_f0_data_and_audio(duration_seconds)
    #     start_f0 = data[0]['f0_data']
    #     mid_f0 = data[len(data) // 2]['f0_data']
    #     end_f0 = data[-1]['f0_data']
    #
    #     self.assertGreater(mid_f0, start_f0)
    #     self.assertLess(end_f0, mid_f0)
    #     self.assertAlmostEqual(start_f0, end_f0, delta=10)

    def test_generate_harmonic_spectral_centroid_data_and_audio(self):
        """
        Should generate a track with low spectral_centroid that rises to max,
        then drops back down while other elements remain constant.
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_harmonic_spectral_centroid_data_and_audio(duration_seconds)
        start_val = data[1]['spectral_centroid']
        mid_val = data[len(data) // 2]['spectral_centroid']
        end_val = data[-2]['spectral_centroid']

        self.assertGreater(mid_val, start_val)
        self.assertLess(end_val, mid_val)
        self.assertAlmostEqual(start_val, end_val, delta=100)

    def test_generate_harmonic_spectral_rolloff_data_and_audio(self):
        """
        Should generate a track with low spectrall rolloff that rises to max,
        then drops back down while other elements remain constant.
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_harmonic_spectral_rolloff_data_and_audio(duration_seconds)
        start_val = data[1]['spectral_rolloff']
        mid_val = data[len(data) // 2]['spectral_rolloff']
        end_val = data[-2]['spectral_rolloff']

        self.assertGreater(mid_val, start_val)
        self.assertLess(end_val, mid_val)
        self.assertAlmostEqual(start_val, end_val, delta=100)

    def test_generate_harmonic_spectral_flatness_data_and_audio(self):
        """
        Should generate a track with low spectrall flatness that rises to max,
        then drops back down while other elements remain constant.
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_harmonic_spectral_flatness_data_and_audio(duration_seconds)

        start_flatness = data[1]['spectral_flatness']
        mid_flatness = data[len(data) // 2]['spectral_flatness']
        end_flatness = data[-2]['spectral_flatness']

        self.assertLess(start_flatness, 0.1)
        self.assertGreater(mid_flatness, 0.9)
        self.assertGreater(mid_flatness, start_flatness)
        self.assertLess(end_flatness, mid_flatness)
        self.assertAlmostEqual(start_flatness, end_flatness, delta=0.1)

    def test_generate_harmonic_mfccs_data_and_audio(self):
        """
        Should generate a track with three subsequent, drastically different
        mfccs coefficients while other elements remain constant.
        """
        duration_seconds = 12
        data, audio = _generate_tutorial.generate_harmonic_mfccs_data_and_audio(duration_seconds)

        segment_len = len(data) // 3
        mfccs1 = data[segment_len // 2]['mfccs']
        mfccs2 = data[segment_len + (segment_len // 2)]['mfccs']
        mfccs3 = data[2 * segment_len + (segment_len // 2)]['mfccs']

        self.assertNotEqual(mfccs1, mfccs2)
        self.assertNotEqual(mfccs2, mfccs3)
        self.assertEqual(len(mfccs1), 20)
        self.assertEqual(len(mfccs2), 20)
        self.assertEqual(len(mfccs3), 20)
        self.assertEqual(data[10]['mfccs'], mfccs1) # Check constancy within segment

    def test_generate_chroma_stft_data_and_audio(self):
        """
        Should generate a track that progresses through the scale, then
        creates 4 or 5 subsequent, well-defined chords. Values not associated
        with pitch should remain constant.
        """
        duration_seconds = 16
        data, audio = _generate_tutorial.generate_chroma_stft_data_and_audio(duration_seconds)

        # Test the scale part
        frame_per_note = int(1.0 * _generate_tutorial.FRAME_RATE)
        for i in range(12):
            frame = data[i * frame_per_note + 5] # sample middle of note
            expected_freq = 261.63 * (2**(i/12))

            self.assertAlmostEqual(frame['chroma_stft'][i], 1.0)
            self.assertEqual(sum(x > 0.1 for x in frame['chroma_stft']), 1)

            # Assert that the f0_data actually moves with the chroma note
            self.assertAlmostEqual(frame['f0_data'], expected_freq, delta=1.0)
            self.assertGreater(len(frame['frequencies']), 0)
            self.assertGreater(frame['frequencies'][0], 0)

        # Test the chord part
        chord_start_frame = int(12.0 * _generate_tutorial.FRAME_RATE)
        chord_frame = data[chord_start_frame + 10]
        # C-Major: C, E, G -> 0, 4, 7
        self.assertAlmostEqual(chord_frame['chroma_stft'][0], 1.0)
        self.assertAlmostEqual(chord_frame['chroma_stft'][4], 1.0)
        self.assertAlmostEqual(chord_frame['chroma_stft'][7], 1.0)
        self.assertEqual(sum(x > 0.1 for x in chord_frame['chroma_stft']), 3)

    def test_generate_drums_onsets_and_tempo_data_and_audio(self):
        """
        Tempo and onsets are very similar to that of harmonic and can basically
        be replicated in one function to show the same concept but in the
        drum context. All other values should remain constant.
        """
        duration_seconds = 15
        data, audio = _generate_tutorial.generate_drums_onsets_and_tempo_data_and_audio(duration_seconds)

        # Check tempo segments
        hits_in_seg1 = [h for h in data if h['onset_time'] < 5]
        hits_in_seg2 = [h for h in data if 5 <= h['onset_time'] < 10]
        hits_in_seg3 = [h for h in data if 10 <= h['onset_time'] < 15]

        # 60 bpm = 1 bps, ~5 hits in 5 sec
        self.assertAlmostEqual(len(hits_in_seg1), 5, delta=1)
        # 120 bpm = 2 bps, ~10 hits in 5 sec
        self.assertAlmostEqual(len(hits_in_seg2), 10, delta=1)
        # 180 bpm = 3 bps, ~15 hits in 5 sec
        self.assertAlmostEqual(len(hits_in_seg3), 15, delta=1)

    def test_generate_drums_duration_data_and_audio(self):
        """
        Should generate a short (<0.2s) hit, pause briefly, then generate a
        long (>1s) hit. All other values should remain constant.
        """
        duration_seconds = 5
        data, audio = _generate_tutorial.generate_drums_duration_data_and_audio(duration_seconds)

        self.assertEqual(len(data), 2)
        self.assertLess(data[0]['duration'], 0.2)
        self.assertGreater(data[1]['duration'], 1.0)

    def test_generate_drums_volume_data_and_audio(self):
        """
        This test is also essentially identical to its harmonic counterpart,
        provides the user with context.
        """
        duration_seconds = 10
        data, audio = _generate_tutorial.generate_drums_volume_data_and_audio(duration_seconds)

        self.assertGreater(len(data), 10)
        start_vol = data[0]['relative_volume']
        mid_vol = data[len(data) // 2]['relative_volume']
        end_vol = data[-1]['relative_volume']

        self.assertLess(start_vol, 0.2)
        self.assertGreater(mid_vol, 0.9)
        self.assertGreater(mid_vol, start_vol)
        self.assertLess(end_vol, mid_vol)

    def test_generate_drums_frequency_ramp_data_and_audio(self):
        """
        This test is also essentially identical to its harmonic counterpart,
        provides the user with context of the drum.
        Given frequency has a small effect on the y-axis in drums,
        combine this with the following test_generate_drums_spectral_centroid...
        Keep all other values constant.
        """
        duration_seconds = 10
        data, audio = _generate_tutorial.generate_drums_frequency_ramp_data_and_audio(duration_seconds)

        self.assertGreater(len(data), 10)
        start_freq = data[0]['dominant_frequency']
        mid_freq = data[len(data) // 2]['dominant_frequency']
        end_freq = data[-1]['dominant_frequency']

        self.assertGreater(mid_freq, start_freq)
        self.assertLess(end_freq, mid_freq)
        self.assertAlmostEqual(start_freq, end_freq, delta=100)

        # Check that spectral_centroid follows the same pattern
        self.assertGreater(data[len(data) // 2]['spectral_centroid'],
                           data[0]['spectral_centroid'])
    #
    # def test_generate_drums_spectral_centroid_data_and_audio(self):
    #     """
    #     Should generate a track that starts with a low spectral centroid
    #     that ramps up then back down
    #     Consider combining this test with the previous test_generate_drums_frequency
    #     since both contribute to y-axis in drums.
    #     Keep all other values constant.
    #     """
    #     raise Exception("Test is not yet implemented, please write test case.")

    def test_organize_drums_MLA_data_and_audio(self):
        """
        Should pull an example of each permutation/combination of DrumMLA
        classifications from data_backend/drum_samples/ (audio files) and
        data_backend/drum_sample_features.json (data) then present them
        subsequently with short pauses between each. May go over the standard
        timeframe for each function. Should keep all elements not relevant to
        DrumMLA classifications constant.
        """
        duration_seconds = 20
        data, audio = _generate_tutorial.organize_drums_MLA_data_and_audio(duration_seconds)

        self.assertEqual(len(data), 7)
        self.assertEqual(data[0]['drum_category'], 'kick')
        self.assertEqual(data[1]['drum_category'], 'snare')
        self.assertEqual(data[2]['qualifier'], 'rimshot')
        self.assertEqual(data[3]['qualifier'], 'close')
        self.assertEqual(data[4]['qualifier'], 'open')

    def test_generate_lyric_data_and_audio(self):
        """
        Should generate a simple vocal track primarily for lyric tracking
        demonstration, but should also include its harmonic data/audio for
        context.
        If generating this cannot be easily automated, I can record a sample
        audio.
        """
        duration_seconds = 10
        data, audio = _generate_tutorial.generate_lyric_data_and_audio(duration_seconds)

        self.assertIn('lyrics', data)
        self.assertIn('harmonic', data)

        lyrics = data['lyrics']
        harmonic = data['harmonic']

        self.assertEqual(len(lyrics), 2)
        self.assertEqual(lyrics[0]['words'][0]['word'], 'This')
        self.assertGreater(len(harmonic), 100)

        # Check that harmonic data aligns with a word
        # Word "first" is at 2.2-2.7s
        frame_at_2_3s_index = int(2.3 * _generate_tutorial.FRAME_RATE)
        self.assertGreater(harmonic[frame_at_2_3s_index]['f0_data'], 0)
        self.assertGreater(harmonic[frame_at_2_3s_index]['rms'], 0)

        # Check silence between lines
        frame_at_4_0s_index = int(4.0 * _generate_tutorial.FRAME_RATE)
        self.assertEqual(harmonic[frame_at_4_0s_index]['f0_data'], 0)
        self.assertEqual(harmonic[frame_at_4_0s_index]['rms'], 0)

    def test_combine_generated_mock_audio_and_data(self):
        """
        Tests that after all audio and data is generated, it is combined into
        a single, unified JSON structure matching the frontend schema.
        """
        data, audio = _generate_tutorial.combine_generated_mock_audio_and_data()

        # 1. Assert Top-Level Unified Schema keys
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get('job_id'), "tutorial_mode")
        self.assertEqual(data.get('status'), "finished")

        self.assertIn('harmonic_analysis', data)
        self.assertIn('drum_analysis', data)
        self.assertIn('mapped_result', data)

        # 2. Assert Harmonic Analysis Structure (Column-oriented)
        harmonic = data['harmonic_analysis']
        self.assertIn('full_track_analysis', harmonic)
        fta = harmonic['full_track_analysis']

        # Check for existence of merged lists (that pivot worked)
        self.assertIsInstance(fta.get('f0_data'), list)
        self.assertIsInstance(fta.get('rms'), list)

        # Check that the duration calculation sums up the offsets
        self.assertIn('duration', fta)
        self.assertGreater(fta['duration'], 150,
                           "Total duration should be substantial (>150s)")

        # Check Stems
        stems = harmonic['stem_analyses']
        self.assertIn('Tutorial_Demonstration', stems)
        self.assertIn('Track_1', stems)
        self.assertIn('Track_2', stems)

        # Verify Track 1 is populated (even if mostly silent, it should have frames)
        self.assertGreater(len(stems['Track_1']['frames']), 100)

        # 3. Assert Drum Analysis Structure
        drums = data['drum_analysis']
        self.assertIn('hits', drums)
        self.assertIsInstance(drums['hits'], list)
        self.assertGreater(len(drums['hits']), 10,
                           "Should have accumulated many drum hits")

        # Verify a hit has spectral data
        hit = drums['hits'][-1]
        self.assertIn('spectral_centroid', hit)

        # 4. Assert Lyrics Structure
        lyrics = data['mapped_result']
        self.assertIsInstance(lyrics, list)
        self.assertGreater(len(lyrics), 0)

        # 5. Verify Time Offsets
        # Lyrics are generated last in the sequence.
        # Their timestamps must be offset significantly from 0.
        first_lyric_start = lyrics[0]['line_start_time']
        self.assertGreater(first_lyric_start, 100,
                           f"Lyrics start time ({first_lyric_start}) should be offset to the end of the track")

        # 6. Audio Integrity
        self.assertIsInstance(audio, np.ndarray)
        # Audio length should match the duration in the data (roughly)
        expected_min_samples = 150 * _generate_tutorial.SAMPLE_RATE
        self.assertGreater(len(audio), expected_min_samples)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
