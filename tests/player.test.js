import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';

// Define mock functions *before* the imports that use them
const mockLyricTrackerInstance = { update: jest.fn() };
const mockHarmonicVisualizerInstance = {
    update: jest.fn(),
    isDataAvailableForTime: jest.fn().mockReturnValue(true),
    ensureDataForTime: jest.fn().mockResolvedValue(undefined),
    streamAccessors: {
        vocals: {
            _fetchChunk: jest.fn().mockResolvedValue(true),
            totalElements: 100,
            chunkSize: 10,
            chunks: new Map(),
            timePerFrame: 512 / 22050,
        }
    },
    isBuffering: false,
};
const mockVolumeTrackerInstance = { setData: jest.fn(), update: jest.fn() };
const mockDrumTrackerInstance = { update: jest.fn() };
const mockSetupAudioPlayer = jest.fn();

// Create mock constructors that return the instances
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
    let mockResultData;
    let mockedDependencies;
    let audioPlayer;
    let playSpy;
    let pauseSpy;
    let logSpy;

    beforeEach(() => {
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
        logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

        // Spy on play/pause methods to track calls
        pauseSpy = jest.spyOn(audioPlayer, 'pause').mockImplementation(() => {
            Object.defineProperty(audioPlayer, 'paused', { value: true, writable: true });
        });
        playSpy = jest.spyOn(audioPlayer, 'play').mockImplementation(() => {
            Object.defineProperty(audioPlayer, 'paused', { value: false, writable: true });
        });
        Object.defineProperty(audioPlayer, 'paused', { value: false, writable: true });
        Object.defineProperty(audioPlayer, 'currentTime', { value: 0, writable: true });

        mockResultData = {
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

        mockedDependencies = {
            LyricTracker: mockLyricTracker,
            HarmonicVisualizer: mockHarmonicVisualizer,
            VolumeTracker: mockVolumeTracker,
            DrumTracker: mockDrumTracker,
            setupAudioPlayer: mockSetupAudioPlayer,
        };

        // Reset mock states
        jest.clearAllMocks();
        mockHarmonicVisualizerInstance.isBuffering = false;
        mockHarmonicVisualizerInstance.streamAccessors.vocals.chunks.clear();
        jest.useFakeTimers();
    });


    afterEach(() => {
        jest.restoreAllMocks();
        jest.useRealTimers();
    });

    describe('initPlayer', () => {
        beforeEach(() => {
            initPlayer(mockResultData, jest.fn(), mockedDependencies);
        });

        test('should correctly initialize all trackers', () => {
            // Assert that the mocked constructors for our trackers were called with the correct data
            expect(mockLyricTracker).toHaveBeenCalledWith(expect.anything(), mockResultData.mapped_result);
            expect(mockHarmonicVisualizer).toHaveBeenCalledWith(expect.anything(), mockResultData.harmonic_analysis);
            expect(mockDrumTracker).toHaveBeenCalledWith(expect.any(HTMLCanvasElement), mockResultData.drum_analysis);

            // Assert that the mock instance was called
            expect(mockVolumeTrackerInstance.setData).toHaveBeenCalledWith(mockResultData.harmonic_analysis.full_track_analysis);

            // Assert that the audio player setup was called
            expect(mockSetupAudioPlayer).toHaveBeenCalled();
        });

        test('should correctly initialize the BufferManager', () => {
            // The BufferManager needs to start upon initialization regardless
            // of the audioPlayer status. Users do not want to wait on the
            // buffer to start and prefer a fluid viewing experience
            expect(logSpy).toHaveBeenCalledWith('[BufferManager] Starting...');
        });
    });

    describe('timeupdate', () => {
        test('event on audio player should call update on all trackers and visualizers', () => {
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

        test('should pause when data is not ready, then buffer and resume when data is ready', async () => {
            // Arrange
            let resolveEnsureData;
            mockHarmonicVisualizerInstance.isDataAvailableForTime
                .mockReturnValueOnce(false)
                .mockReturnValue(true);

            mockHarmonicVisualizerInstance.ensureDataForTime.mockImplementation(() =>
                new Promise(resolve => {
                    resolveEnsureData = resolve;
                })
            );

            initPlayer(mockResultData, jest.fn(), mockedDependencies);
            const playPauseButton = document.getElementById('player-play-pause');
            playPauseButton.textContent = 'Pause'; // Simulate playing state
            Object.defineProperty(audioPlayer, 'paused', { value: false, writable: true });

            // Act
            audioPlayer.dispatchEvent(new Event('timeupdate'));
            await Promise.resolve(); // Let async handler start

            // Assert that the player paused and buffering started
            expect(pauseSpy).toHaveBeenCalled();
            expect(mockHarmonicVisualizerInstance.isBuffering).toBe(true);

            // Resolve the data fetch
            resolveEnsureData();
            await Promise.resolve(); // Let the handler continue

            // Assert that the player resumed playback
            expect(playSpy).toHaveBeenCalled();
            expect(mockHarmonicVisualizerInstance.isBuffering).toBe(false);
        });

        test('should NOT resume playback if user manually paused', async () => {
            let resolveEnsureData;
            // Arrange
            mockHarmonicVisualizerInstance.isDataAvailableForTime.mockReturnValueOnce(false);
            mockHarmonicVisualizerInstance.ensureDataForTime.mockImplementation(() =>
                new Promise(resolve => {
                    resolveEnsureData = resolve;
                })
            );

            const playPauseButton = document.getElementById('player-play-pause');
            playPauseButton.textContent = 'Play';
            Object.defineProperty(audioPlayer, 'paused', { value: true, writable: true });

            initPlayer(mockResultData, jest.fn(), mockedDependencies);

            // Act
            audioPlayer.dispatchEvent(new Event('timeupdate'));
            await Promise.resolve();

            // Resolve the buffer promise
            resolveEnsureData();
            await Promise.resolve();

            // Assert that play was NOT called, because the 'play-pause' button
            // indicates a manual pause
            expect(playSpy).not.toHaveBeenCalled();
        });
    });

    describe('Sad Paths', () => {
        let consoleSpy;
        let statusMessage;

        beforeEach(() => {
            consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
            statusMessage = document.getElementById('status-message');
        });

        afterEach(() => {
            consoleSpy.mockRestore();
        });

        test('should throw error and display message if a canvas is missing', () => {
            document.getElementById('drum-canvas').remove(); // Remove an element
            initPlayer(mockResultData, jest.fn(), mockedDependencies);

            expect(consoleSpy).toHaveBeenCalledWith("! FATAL: Failed to initialize the player UI.", expect.any(Error));
            expect(statusMessage.textContent).toContain('Missing player UI elements');
            expect(statusMessage.style.display).toBe('block');
        });

        test('should throw error and display message if dependencies are invalid', () => {
            const invalidDeps = { ...mockedDependencies, DrumTracker: null };

            initPlayer(mockResultData, jest.fn(), invalidDeps);

            expect(consoleSpy).toHaveBeenCalledWith("! FATAL: Failed to initialize the player UI.", expect.any(Error));
            expect(statusMessage.textContent).toContain('Missing or invalid dependencies');
            expect(statusMessage.style.display).toBe('block');
        });
    });

    describe('BufferManager', () => {
        beforeEach(() => {
            initPlayer(mockResultData, jest.fn(), mockedDependencies);
            logSpy.mockClear();
        });

        test('should fetch chunks in order', async () => {
            const fetchSpy = mockHarmonicVisualizerInstance.streamAccessors.vocals._fetchChunk;

            jest.advanceTimersByTime(500);
            await Promise.resolve();

            expect(fetchSpy).toHaveBeenCalledWith(0);
            expect(fetchSpy).toHaveBeenCalledWith(1);
            expect(fetchSpy).toHaveBeenCalledWith(2);
            fetchSpy.mockClear();
        });

        test('should load chunks incrementally, not all at once', async () => {
            const fetchSpy = mockHarmonicVisualizerInstance.streamAccessors.vocals._fetchChunk;
            // First interval fetches 3 chunks
            jest.advanceTimersByTime(500);
            expect(fetchSpy).toHaveBeenCalledTimes(3);

            // Second interval fetches next 3 chunks
            jest.advanceTimersByTime(500);
            await Promise.resolve(); // flush promises
            expect(fetchSpy).toHaveBeenCalledTimes(6);
        });

        test('should correctly prioritize currentTime in cases where timeupdate brings currentTime passed loaded chunks', async () => {
            // If the user fast forwards the song passed the loaded chunks,
            // the buffer manager should start buffering at the new spot
            const fetchSpy = mockHarmonicVisualizerInstance.streamAccessors.vocals._fetchChunk;
            fetchSpy.mockClear();
            logSpy.mockClear();

            // Simulate user seeking to a time corresponding with chunk 7
            // time -> index -> chunk: 0.17 / (512/22050) = ~7.3 -> chunk 7
            audioPlayer.currentTime = 0.17;
            audioPlayer.dispatchEvent(new Event('seeked'));

            // Let the worker created by the 'seeked' handler run once.
            jest.advanceTimersByTime(500);
            await Promise.resolve(); // Flush microtask queue

            // The buffer manager should now fetch from chunk 7 onwards
            expect(logSpy).toHaveBeenCalledWith('[Player] Seek detected. Restarting buffer at 0.17s.');
            // expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('[BufferManager] Queued chunks from 7.'));
            expect(fetchSpy).toHaveBeenCalledWith(7);
            expect(fetchSpy).toHaveBeenCalledWith(8);
            expect(fetchSpy).toHaveBeenCalledWith(9);
        });

        test('should stop the interval when the queue is empty', async () => {
            // Total chunks = 100 elements / 10 per chunk = 10 chunks.
            // Worker fetches 3 per 500ms. 4 intervals needed (3, 3, 3, 1).
            // This takes 2000ms. The 5th interval at 2500ms will find an
            // empty queue.
            jest.advanceTimersByTime(2500);
            await Promise.resolve(); // Flush promises

            // The worker will process the queue and then stop
            expect(logSpy).toHaveBeenCalledWith('[BufferManager] Queue empty. Stopping worker.');
        });

        test('start should not re-run if already running', () => {
            // The buffer is already running from initPlayer. `logSpy` was
            // cleared in beforeEach. Calling start() via 'play' should not
            // produce another "Starting..." log
            audioPlayer.dispatchEvent(new Event('play'));
            expect(logSpy).not.toHaveBeenCalledWith(expect.stringContaining('[BufferManager] Starting...'))
        });

        test('stop should not re-run if not running', () => {
            // Mock a `stop` call from a source that isn't the audio player
            const cleanupAndReset = mockSetupAudioPlayer.mock.calls[0][2].onStopAndReset;
            cleanupAndReset();
            expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('[BufferManager] Stopping...'));

            logSpy.mockClear();
            // Now call stop() again
            cleanupAndReset();
            expect(logSpy).not.toHaveBeenCalledWith(expect.stringContaining('[BufferManager] Stopping...'));
        });
    });
});
