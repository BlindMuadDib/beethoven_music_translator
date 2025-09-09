import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';

// Define mock functions *before* the imports that use them
const mockLyricTrackerInstance = { update: jest.fn() };
const mockHarmonicVisualizerInstance = {
    update: jest.fn(),
    streamAccessors: { vocals: { ensureDataForTime: jest.fn() } }
};
const mockVolumeTrackerInstance = { setData: jest.fn(), update: jest.fn() };
const mockDrumTrackerInstance = { update: jest.fn() };
const mockSetupAudioPlayer = jest.fn();

// Create mock constructors that return our instances
const mockLyricTracker = jest.fn().mockImplementation(() => mockLyricTrackerInstance);
const mockHarmonicVisualizer = jest.fn().mockImplementation(() => mockHarmonicVisualizerInstance);
mockVolumeTracker = jest.fn().mockImplementation(() => mockVolumeTrackerInstance);
mockDrumTracker = jest.fn().mockImplementation(() => mockDrumTrackerInstance);

// Mock the sub-modules to isolate the player facade's logic
jest.unstable_mockModule('../www/js/player/lyric-tracker.js', () => ({ LyricTracker: mockLyricTracker }));
jest.doMock('../www/js/player/harmonic-visualizer.js', () => ({ HarmonicVisualizer: mockHarmonicVisualizer }));
jest.unstable_mockModule('../www/js/player/volume-tracker.js', () => ({ VolumeTracker: mockVolumeTracker }));
jest.unstable_mockModule('../www/js/player/drum-tracker.js', () => ({ DrumTracker: mockDrumTracker }));
jest.unstable_mockModule('../www/js/player/audio-player.js', () => ({ setupAudioPlayer: mockSetupAudioPlayer }));

// Now import initPlayer. It will use the mocked versions of the dependencies.
const { initPlayer } = await import('../www/js/player.js');

describe('Player Facade Integration)', () => {
    let audioPlayer;

    beforeEach(() => {
        // Clear all mocks before each test
        jest.clearAllMocks();
        jest.useFakeTimers();

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
        <div id="status-message"></div>
        `;
        audioPlayer = document.getElementById('audio-player');
    });

    afterEach(() => {
        jest.useRealTimers();
    });

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
                vocals: {},
                bass: {},
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

    // Explicitly pass the mocked constructors in the dependencies object
    const mockedDependencies = {
        LyricTracker: mockLyricTracker,
        HarmonicVisualizer: mockHarmonicVisualizer,
        VolumeTracker: mockVolumeTracker,
        DrumTracker: mockDrumTracker,
        setupAudioPlayer: mockSetupAudioPlayer,
    };

    test('initPlayer should correctly initialize all trackers', () => {
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

    test('timeupdate event on audio player should call update on all trackers and visualizers', () => {
        initPlayer(mockResultData, jest.fn(), mockedDependencies);

        const audioPlayer = document.getElementById('audio-player');
        audioPlayer.currentTime = 1.23; // Set mock time

        // Dispatch the event
        audioPlayer.dispatchEvent(new Event('timeupdate'));

        // Assert that each tracker's update method was called with the correct time
        expect(mockLyricTrackerInstance.update).toHaveBeenCalledWith(1.23);
        expect(mockHarmonicVisualizerInstance.update).toHaveBeenCalledWith(1.23);
        expect(mockVolumeTrackerInstance.update).toHaveBeenCalledWith(1.23);
        expect(mockDrumTrackerInstance.update).toHaveBeenCalledWith(1.23);
    });

    test('seeking event should trigger data buffering', () => {
        initPlayer(mockResultData, jest.fn(), mockedDependencies);
        audioPlayer.currentTime = 50.0;
        audioPlayer.dispatchEvent(new Event('seeking'));
        expect(mockHarmonicVisualizerInstance.streamAccessors.vocals.ensureDataForTime).toHaveBeenCalledWith(50.0);
    });

    test('buffering interval should call ensureDataForTimewhen playing', () => {
        initPlayer(mockResultData, jest.fn(), mockedDependencies);

        // Simulate player is playing
        Object.defineProperty(audioPlayer, 'paused', { value: false });
        // Mock the read-only 'duration' property
        Object.defineProperty(audioPlayer, 'duration', { value: 100, writeable: true });
        audioPlayer.currentTime = 10;

        // Advance timers by 2 seconds to trigger the interval
        jest.advanceTimersByTime(2000);

        // Expect it to buffer 30 seconds ahead
        expect(mockHarmonicVisualizerInstance.streamAccessors.vocals.ensureDataForTime).toHaveBeenCalledWith(40);
    });

    test('should throw error and display message if a canvas is missing', () => {
        document.getElementById('drum-canvas').remove(); // Remove an element
        const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

        initPlayer(mockResultData, jest.fn(), mockedDependencies);

        const statusMessage = document.getElementById('status-message');
        expect(consoleSpy).toHaveBeenCalledWith("! FATAL: Failed to initialize the player UI.", expect.any(Error));
        expect(statusMessage.textContent).toContain('Missing player UI elements');
        expect(statusMessage.style.display).toBe('block');

        consoleSpy.mockRestore();
    });

    test('should throw error and display message if dependencies are invalid', () => {
        const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const invalidDeps = { ...mockedDependencies, DrumTracker: null };

        initPlayer(mockResultData, jest.fn(), invalidDeps);

        const statusMessage = document.getElementById('status-message');
        expect(consoleSpy).toHaveBeenCalledWith("! FATAL: Failed to initialize the player UI.", expect.any(Error));
        expect(statusMessage.textContent).toContain('Missing or invalid dependencies');
        expect(statusMessage.style.display).toBe('block');

        consoleSpy.mockRestore();
    })
});
