import { jest, describe, test, expect } from '@jest/globals';

// Define mock functions *before* the imports that use them
const mockLyricTrackerInstance = { update: jest.fn() };
const mockF0TrackerInstance = { update: jest.fn() };
const mockVolumeTrackerInstance = { setData: jest.fn(), update: jest.fn() };
const mockDrumTrackerInstance = { update: jest.fn() };
const mockSetupAudioPlayer = jest.fn();

// Create mock constructors that return our instances
const mockLyricTracker = jest.fn().mockImplementation(() => mockLyricTrackerInstance);
const mockF0Tracker = jest.fn().mockImplementation(() => mockF0TrackerInstance);
mockVolumeTracker = jest.fn().mockImplementation(() => mockVolumeTrackerInstance);
mockDrumTracker = jest.fn().mockImplementation(() => mockDrumTrackerInstance);

// Mock the sub-modules to isolate the player facade's logic
jest.doMock('../www/js/player/lyric-tracker.js', () => ({ LyricTracker: mockLyricTracker }));
jest.doMock('../www/js/player/f0-tracker.js', () => ({ F0Tracker: mockF0Tracker }));
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
            F0Tracker: mockF0Tracker,
            VolumeTracker: mockVolumeTracker,
            DrumTracker: mockDrumTracker,
            setupAudioPlayer: mockSetupAudioPlayer,
        };

        // Set up the required DOM
        document.body.innerHTML = `
            <div id="song-title"></div>
            <audio id="audio-player"></audio>
            <canvas id="lyric-canvas"></canvas>
            <canvas id="f0-canvas"></canvas>
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
            f0_analysis: {
                vocals: {
                    times: [0.01, 0.02, 0.03],
                    f0_values: [220.0, 220.1, 220.5],
                    time_interval: 0.01
                },
                bass: {
                    times: [0.01, 0.02, 0.03],
                    f0_values: [110.0, null, 110.2],
                    time_interval: 0.01
                },
            },
            volume_analysis: {
                overall_rms: [[0.01, 0.5], [0.02, 0.7]],
                instruments: {
                    vocals: {
                        rms_values: [[0.01, 0.3], [0.02, 0.4]]
                    },
                    bass: {
                        rms_values: [[0.01, 0.4], [0.02, 0.3]]
                    }
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
        expect(mockF0Tracker).toHaveBeenCalledWith(expect.anything(), mockResultData.f0_analysis, mockResultData.volume_analysis.instruments);
        expect(mockDrumTracker).toHaveBeenCalledWith(expect.any(HTMLCanvasElement), mockResultData.drum_analysis);

        // Assert that the mock instance was called
        expect(mockVolumeTrackerInstance.setData).toHaveBeenCalledWith(mockResultData.volume_analysis.overall_rms);

        // Assert that the audio player setup was called
        expect(mockSetupAudioPlayer).toHaveBeenCalled();
    });
});
