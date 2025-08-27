import { jest, describe, test, expect } from '@jest/globals';

// Define mock functions *before* the imports that use them
const mockLyricTrackerInstance = { update: jest.fn() };
const mockHarmonicVisualizerInstance = { update: jest.fn() };
const mockVolumeTrackerInstance = { setData: jest.fn(), update: jest.fn() };
const mockDrumTrackerInstance = { update: jest.fn() };
const mockSetupAudioPlayer = jest.fn();

// Create mock constructors that return our instances
const mockLyricTracker = jest.fn().mockImplementation(() => mockLyricTrackerInstance);
const mockHarmonicVisualizer = jest.fn().mockImplementation(() => mockHarmonicVisualizerInstance);
mockVolumeTracker = jest.fn().mockImplementation(() => mockVolumeTrackerInstance);
mockDrumTracker = jest.fn().mockImplementation(() => mockDrumTrackerInstance);

// Mock the sub-modules to isolate the player facade's logic
jest.doMock('../www/js/player/lyric-tracker.js', () => ({ LyricTracker: mockLyricTracker }));
jest.doMock('../www/js/player/harmonic-visualizer.js', () => ({ HarmonicVisualizer: mockHarmonicVisualizer }));
jest.doMock('../www/js/player/volume-tracker.js', () => ({ VolumeTracker: mockVolumeTracker }));
jest.doMock('../www/js/player/drum-tracker.js', () => ({ DrumTracker: mockDrumTracker }));
jest.doMock('../www/js/player/audio-player.js', () => ({ setupAudioPlayer: mockSetupAudioPlayer }));

// Now import initPlayer. It will use the mocked versions of the dependencies.
const { initPlayer } = await import('../www/js/player.js');

describe('Player Facade Integration)', () => {

    test('initPlayer should correctly initialize and update all trackers', () => {
        // Arrange
        // Explicitly pass the mocked constructors in the dependencies object
        const mockedDependencies = {
            LyricTracker: mockLyricTracker,
            HarmonicVisualizer: mockHarmonicVisualizer,
            VolumeTracker: mockVolumeTracker,
            DrumTracker: mockDrumTracker,
            setupAudioPlayer: mockSetupAudioPlayer,
        };

        // Set up the required DOM
        document.body.innerHTML = `
            <div id="song-title"></div>
            <audio id="audio-player"></audio>
            <canvas id="lyric-canvas"></canvas>
            <canvas id="harmonic-canvas"></canvas>
            <canvas id="overall-volume-canvas"></canvas>
            <canvas id="drum-canvas"></canvas>
            <button id="player-play-pause"></button>
            <button id="player-stop"></button>
            <button id="player-rewind"></button>
            <button id="player-ffwd"></button>
            <input id="volume-control" type="range" />
        `;

        const mockResultData = {
            mapped_result: [{
                line_text: 'example line',
                words: [
                    {word: 'example', start: 0.01, end: 0.02},
                    {word: 'line', start: 0.02, end: 0.03},
                ],
                line_start_time: 0.01,
                line_end_time: 0.03
            }],
            harmonic_analysis: {
                full_track_analysis: {
                    duration: 0.5,
                    tempo: 136,
                    rms_overall: {
                        times: [0.1, 0.2, 0.3],
                        values: [0.88, 0.99, 0.94]
                    }
                },
                stem_analyses: {
                    vocals: {
                        f0_data: {
                            times: [0.1, 0.2, 0.3],
                            f0_values: [440, 660, 880],
                        },
                        spectral_features: {
                            times: [0.1, 0.2, 0.3],
                            frequencies: [880, 1320, 1760],
                            spectrogram: [1000, 500, 4000],
                            rms: [0.84, 0.43, 0.91],
                            spectral_centroid: [1200, 4500, 3000],
                            spectral_bandwidth: [2000, 800, 1600],
                            spectral_rolloff: [1600, 3200, 100],
                            spectral_flatness: [100, 50, 22],
                        },
                        timbral_features: {
                            mfccs: [-150, -100, -95, -60, -40, -30, -20, -10, -5, -1, -0.99, -0.60, -0.01],
                            chroma_stft: [44, 22],
                        },
                        temporal_features: {
                            onsets: [0.1],
                            tempo: 136.0,
                            beats: [0.1],
                        }
                    },
                    bass: {
                        f0_data: {
                            times: [0.1, 0.2, 0.3],
                            f0_values: [null, 80, 100],
                        },
                        spectral_features: {
                            times: [0.1, 0.2, 0.3],
                            frequencies: [null, 220, 300],
                            spectrogram: [null, 400, 500],
                            rms: [0.0, 0.5, 0.4],
                            spectral_centroid: [null, 1200, 2200],
                            spectral_bandwidth: [null, 500, 1000],
                            spectral_rolloff: [null, 2200, 4500],
                            spectral_flatness: [null, 8000, 8000],
                        },
                        timbral_features: {
                            mfccs: [-100, -90, -55, -44, -22, -11, -4, -2, -0.98, -0.77, -0.64, -0.2, -0.004],
                            chroma_stft: [null, 3000, 222],
                        },
                        temporal_features: {
                            onsets: [0.2],
                            tempo: 136.0,
                            beats: [0.2],
                        }
                    },
                    other: null
                }
            },
            drum_analysis: {
                tempo: 120,
                hits: [
                    {
                        onset_time: 0.5,
                        duration: 0.1,
                        relative_volume: 0.123,
                        dominant_frequency: 440.0,
                        spectral_centroid: 500.0,
                        spectral_rolloff: 1500.0,
                        spectral_flux: 0.05,
                        mfccs: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                        drum_type: 'snare_drum',
                        confidence: 0.95
                    },
                    {
                        onset_time: 1.2,
                        duration: 0.08,
                        relative_volume: 0.098,
                        dominant_frequency: 220.0,
                        spectral_centroid: 300.0,
                        spectral_rolloff: 1000.0,
                        spectral_flux: 0.03,
                        mfccs: [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                        drum_type: 'bass_drum',
                        confidence: 0.90
                    },
                ]
            },
            audio_url: 'fake.wav',
            original_filename: 'fake.wav'
        };

        // ACT: Call initPlayer directly. The internal imports within initPlayer
        // will resolve to the mocked version because of jest.mock at the top.
        // You only need to pass the mockResultData and the onAudioEnded
        initPlayer(mockResultData, jest.fn(), mockedDependencies);

        // Assert that the mocked constructors for our trackers were called with the correct data
        expect(mockLyricTracker).toHaveBeenCalledWith(expect.anything(), mockResultData.mapped_result);
        expect(mockHarmonicVisualizer).toHaveBeenCalledWith(expect.anything(), mockResultData.harmonic_analysis);
        expect(mockDrumTracker).toHaveBeenCalledWith(expect.any(HTMLCanvasElement), mockResultData.drum_analysis);

        // Assert that the mock instance was called
        expect(mockVolumeTrackerInstance.setData).toHaveBeenCalledWith(mockResultData.harmonic_analysis.full_track_analysis);

        // Assert that the audio player setup was called
        expect(mockSetupAudioPlayer).toHaveBeenCalled();
    });
});
