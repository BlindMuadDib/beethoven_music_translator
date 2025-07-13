import { jest, describe, test, expect } from '@jest/globals';

// Define mock functions *before* the imports that use them
const mockLyricTracker = jest.fn();
const mockF0Tracker = jest.fn();
const mockVolumeTracker = jest.fn();
const mockSetupAudioPlayer = jest.fn();

// Mock the sub-modules to isolate the player facade's logic
jest.doMock('../www/js/player/lyric-tracker.js', () => ({ LyricTracker: mockLyricTracker }));
jest.doMock('../www/js/player/f0-tracker.js', () => ({ F0Tracker: mockF0Tracker }));
jest.doMock('../www/js/player/volume-tracker.js', () => ({ VolumeTracker: mockVolumeTracker }));
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
            setupAudioPlayer: mockSetupAudioPlayer,
        };

        // Set up the required DOM
        document.body.innerHTML = `
            <div id="song-title"></div>
            <audio id="audio-player"></audio>
            <canvas id="lyric-canvas"></canvas>
            <canvas id="f0-canvas"></canvas>
            <canvas id="overall-volume-canvas"></canvas>
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
        expect(mockVolumeTracker).toHaveBeenCalledWith('overall-volume-canvas');

        // Assert that the audio player setup was called
        expect(mockSetupAudioPlayer).toHaveBeenCalled();
    });
});
