import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Use unstable_mockModule BEFORE importing the module under test
jest.unstable_mockModule('../www/js/player/TimeSeriesAccessor.js', () => ({
    TimeSeriesAccessor: jest.fn().mockImplementation(() => ({
        // This is a mock instance
    }))
}));
jest.unstable_mockModule('../www/js/utils.js', () => ({
    calculateTotalFrames: jest.fn().mockReturnValue(1000) // Return a realistic mock value
}));

// Dynamically import app.js after mocking
const { init, handleFormSubmit, handleLocalFileSubmit } = await import('../www/js/app.js');
// Import the mocked modules to assert against them
const { TimeSeriesAccessor } = await import('../www/js/player/TimeSeriesAccessor.js');
const { calculateTotalFrames } = await import('../www/js/utils.js');

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlPath = path.resolve(__dirname, '../www/index.html')

// --- Mock Globals ---
// Mock JSZip
const mockZipFile = {
    async: jest.fn()
};
const mockZipInstance = {
    loadAsync: jest.fn(),
    file: jest.fn(() => mockZipFile)
};
global.JSZip = jest.fn(() => mockZipInstance);

// Mock URL.createObjectURL
global.URL.createObjectURL = jest.fn(() => 'blob:http://localhost/mock-audio-url');
global.URL.revokeObjectURL = jest.fn();

// --- End Mock Globals ---

// --- Test Suite for app.js logic ---
describe('App End-to-End User Flow Integration', () => {
    let mockUi, mockApi, mockPlayer, form;
    let consoleErrorSpy, consoleWarnSpy;

    // Manually mock window.localStorage to ensure reliability in JSDOM
    const localStorageMock = (function () {
        let store = {};
        return {
            getItem: jest.fn(key => store[key] || null),
            setItem: jest.fn((key, value) => { store[key] = String(value); }),
            clear: jest.fn(() => { store = {}; }),
            removeItem: jest.fn(key => { delete store[key]; })
        };
    })();

    beforeEach(() => {
        // Ensure localStorage is mocked on the window object
        Object.defineProperty(window, 'localStorage', { value: localStorageMock, configurable: true });
        localStorageMock.clear();

        // Create simple mock objects for our dependencies
        const html = fs.readFileSync(htmlPath, 'utf8');
        document.body.innerHTML = html;
        form = document.getElementById('translate-form');

        // --- Mock Audio Player Methods ---
        // JSDOM elements do not implement pause() or play(), so we must
        // mock them to prevent "audioPlayer.pause is not a function" errors.
        const audioPlayer = document.getElementById('audio-player');
        if (audioPlayer) {
            audioPlayer.pause = jest.fn();
            audioPlayer.play = jest.fn();
            // We also need to mock the setter for src if logic checks it
            Object.defineProperty(audioPlayer, 'src', {
                get: jest.fn(() => ''),
                set: jest.fn(),
                configurable: true
            });
        }

        // Create pure mock objects for each dependency
        mockUi = {
            cacheDOMElements: jest.fn(),
            updateUIVisibility: jest.fn(),
            setSubmitButtonDisabled: jest.fn(),
            showStatusMessage: jest.fn(),
            updateAuthUI: jest.fn(),
            toggleDownloadButton: jest.fn(),
            setupDownloadButton: jest.fn(),
            showTutorialOverlay: jest.fn(),
            hideTutorialOverlay: jest.fn(),
            updateTutorialStatus: jest.fn(),
            renderLibrary: jest.fn(),
        };
        mockApi = {
            submitJob: jest.fn(),
            pollJobStatus: jest.fn(),
            checkAuthStatus: jest.fn().mockResolvedValue({ isAuthenticated: false }),
            fetchTutorialData: jest.fn().mockResolvedValue({
                app_version: '0.1.4',
                harmonic_analysis: {},
                drum_analysis: {}
            }),
            fetchLibrary: jest.fn().mockResolvedValue([]),
            triggerMtrDownload: jest.fn(),
            fetchTutorialData: jest.fn(),
        };
        mockPlayer = {
            initPlayer: jest.fn(),
        };

        // Clear all mock implementatios and calls
        global.fetch = jest.fn();
        jest.clearAllMocks();
        TimeSeriesAccessor.mockClear();
        calculateTotalFrames.mockClear();
        global.JSZip.mockClear();
        mockZipInstance.loadAsync.mockClear();
        mockZipInstance.file.mockClear();
        global.URL.createObjectURL.mockClear();

        // Spy on console to check for warnings
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => { });
        consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => { });
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
        consoleWarnSpy.mockRestore();
    });

    describe('init()', () => {
        test('should check auth, update UI for a logged-in user, and set visibility to uploadUI', async () => {
            const authData = { isAuthenticated: true, user: { email: 'test@example.com' } };
            mockApi.checkAuthStatus.mockResolvedValue(authData);

            await init(mockUi, mockApi, mockPlayer, form);

            expect(mockApi.checkAuthStatus).toHaveBeenCalledTimes(1);
            expect(mockUi.updateAuthUI).toHaveBeenCalledWith(authData);
            expect(mockUi.cacheDOMElements).toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('upload');

            // Check that listeners were attached
            const localFileInput = document.getElementById('local-file-input');
            const localAudioInput = document.getElementById('local-audio-input');

            // Listeners can't *really* be checked without triggering it,
            // but confirm the element was found and could have a listener.
            expect(localFileInput).not.toBeNull();
            expect(localAudioInput).not.toBeNull();
        });

        test('should handle auth check failure gracefully', async () => {
            const error = new Error('Auth Failed');
            mockApi.checkAuthStatus.mockRejectedValue(error);

            await init(mockUi, mockApi, mockPlayer, form);

            expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to initialize auth status:", error);
            expect(mockUi.updateAuthUI).toHaveBeenCalledWith({ isAuthenticated: false });
        });

        test('should attach and fire libraryBtn click listener successfully', async () => {
            await init(mockUi, mockApi, mockPlayer, form);
            const libraryBtn = document.getElementById('library-btn');

            mockApi.fetchLibrary.mockResolvedValue([{ title: 'Song 1', artist: 'Artist 1' }]);

            const event = new Event('click');
            event.preventDefault = jest.fn();
            libraryBtn.dispatchEvent(event);

            await new Promise(process.nextTick);

            expect(event.preventDefault).toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Fetching library catalog...');
            expect(mockApi.fetchLibrary).toHaveBeenCalled();
            expect(mockUi.renderLibrary).toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('library');
        });

        test('should handle libraryBtn fetch error', async () => {
            await init(mockUi, mockApi, mockPlayer, form);
            const libraryBtn = document.getElementById('library-btn');

            mockApi.fetchLibrary.mockRejectedValue(new Error('API Down'));

            const event = new Event('click');
            event.preventDefault = jest.fn();
            libraryBtn.dispatchEvent(event);

            await new Promise(process.nextTick);

            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Error fetching library. Please try again later.');
        });

        test('should attach and fire tutorialBtn click listener', async () => {
            await init(mockUi, mockApi, mockPlayer, form);
            const tutorialBtn = document.getElementById('tutorial-btn');

            tutorialBtn.click();

            expect(mockApi.fetchTutorialData).toHaveBeenCalled();
        });
    });

    describe('init() sad paths and event logic', () => {
        test('should warn if form element is missing', async () => {
            await init(mockUi, mockApi, mockPlayer, null); // No form
            expect(consoleErrorSpy).toHaveBeenCalledWith("Form element not found for init");
        });

        test('should warn if local file inputs are missing', async () => {
            document.body.innerHTML = ''; // Clear DOM
            await init(mockUi, mockApi, mockPlayer, document.createElement('form'));

            expect(consoleWarnSpy).toHaveBeenCalledWith("Local file input (#local-file-input) not found.");
            expect(consoleWarnSpy).toHaveBeenCalledWith("Local audio input (#local-audio-input) not found.");
        });

        test('LocalFileHandler: should do nothing if only one file is selected', async () => {
            await init(mockUi, mockApi, mockPlayer, form);

            const mtrInput = document.getElementById('local-file-input');

            // Mock file property (read-only jsdom usually, so defineProperty)
            Object.defineProperty(mtrInput, 'files', {
                value: [new File([], 'test.mtr')],
                writable: true
            });

            // Dispatch event
            mtrInput.dispatchEvent(new Event('change'));

            // Expect initPlayer NOT to be called (as audio is missing)
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
        });

        test('LocalFileHandler should trigger processing when BOTH files are present', async () => {
            // Disable tutorial to avoid async waiting in the event handler
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            await init(mockUi, mockApi, mockPlayer, form);

            // Mock files
            const mtrInput = document.getElementById('local-file-input');
            const audioInput = document.getElementById('local-audio-input');

            // Mock files
            const mockMtr = new File(["zip"], "test.mtr", { type: "application/zip" });
            const mockWav = new File(["wav"], "test.wav", { type: "audio/wav" });

            Object.defineProperty(mtrInput, 'files', {
                value: [mockMtr],
                writable: true
            });
            Object.defineProperty(audioInput, 'files', {
                value: [mockWav],
                writable: true
            });

            // Mock zip loading success to let it proceed
            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation(() => ({ async: () => JSON.stringify({}) }));

            // Trigger change on audio input (order doesn't matter)
            audioInput.dispatchEvent(new Event('change'));

            // Wait for async handler
            await Promise.resolve();

            // Now we expect interaction because both files were present
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(true);
            expect(global.JSZip).toHaveBeenCalled();
        });
    });

    describe('Tutorial', () => {
        test('Clicking Tutorial button should fetch assets and init player', async () => {
            // Arrange
            const tutorialBtn = document.getElementById('tutorial-btn');
            const mockTutorialData = { some: "data" };
            mockApi.fetchTutorialData.mockResolvedValue(mockTutorialData);

            // Initialize app to bind listeners
            await init(mockUi, mockApi, mockPlayer, form);

            // Act
            tutorialBtn.click();
            await Promise.resolve();

            // Assert
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
            expect(mockUi.showTutorialOverlay).toHaveBeenCalledWith(expect.any(Function));
            expect(mockPlayer.initPlayer).toHaveBeenCalledWith(
                mockTutorialData,
                expect.any(Function),
                mockPlayer
            );
        });

        test('Preference Checkbox should update localStorage', async () => {
            await init(mockUi, mockApi, mockPlayer, form);
            const checkbox = document.getElementById('disable-auto-tutorial');

            // Act
            checkbox.checked = true;
            checkbox.dispatchEvent(new Event('change'));

            // Assert
            expect(localStorageMock.setItem).toHaveBeenCalledWith('beethoven_disable_tutorial', 'true');
        });

        test('Form Submit with Auto-Tutorial ENABLED should play tutorial then wait for result', async () => {
            // Arrange
            const mockTutorialData = { type: 'tutorial' };
            const mockJobResult = { result: { type: 'real_result' } };

            mockApi.fetchTutorialData.mockResolvedValue(mockTutorialData);
            mockApi.submitJob.mockResolvedValue({ job_id: '123' });
            mockApi.pollJobStatus.mockResolvedValue(mockJobResult);

            // Initialize
            await init(mockUi, mockApi, mockPlayer, form);

            // Act
            const mockEvent = { preventDefault: jest.fn() };
            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer);

            // Assert
            expect(mockApi.fetchTutorialData).toHaveBeenCalled();

            // 1. First initPlayer call is for TUTORIAL
            expect(mockPlayer.initPlayer).toHaveBeenNthCalledWith(1,
                mockTutorialData,
                expect.any(Function),
                mockPlayer
            );
            expect(mockUi.showTutorialOverlay).toHaveBeenCalled();

            // 2. When job finished, it should NOT automatically nuke the
            // tutorial player. It should update the overlay to say "Ready"
            expect(mockApi.submitJob).toHaveBeenCalled();
            expect(mockUi.updateTutorialStatus).toHaveBeenCalledWith('ready', expect.any(Function));

            // Simulate user clicking "View Result"
            const readyCallback = mockUi.updateTutorialStatus.mock.calls[0][1];
            readyCallback();

            // 3. Second initPlayer call is for RESULT
            expect(mockPlayer.initPlayer).toHaveBeenNthCalledWith(2,
                mockJobResult.result,
                expect.any(Function),
                mockPlayer
            );
        });

        test('Form Submit with Auto-Tutorial DISABLED should show status spinner', async () => {
            // Arrange
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');
            // We need to re-check the element since init might have set it based on old state
            const checkbox = document.getElementById('disable-auto-tutorial');
            if (checkbox) checkbox.checked = true;

            mockApi.submitJob.mockResolvedValue({ job_id: '123' });
            mockApi.pollJobStatus.mockResolvedValue({ result: { type: 'real_result' } });

            await init(mockUi, mockApi, mockPlayer, form);

            // Act
            await handleFormSubmit({ preventDefault: jest.fn() }, mockUi, mockApi, mockPlayer);

            // Assert
            expect(mockApi.fetchTutorialData).not.toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');
            // Init player only called once for the result
            expect(mockPlayer.initPlayer).toHaveBeenCalledTimes(1);
        });

        test('Local File Submit with Auto-Tutorial ENABLED should play tutorial', async () => {
            // Arrange
            localStorageMock.removeItem('beethoven_disable_tutorial'); // Ensure enabled
            mockApi.fetchTutorialData.mockResolvedValue({ type: 'tutorial' });

            // Ensure JSZip mock returns valid JSON so execution doesn't fail in the try/catch block
            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') {
                    return {
                        async: () => JSON.stringify({
                            app_version: '0.1.3',
                            drum_analysis: {},
                            harmonic_analysis: {}
                        })
                    };
                }
                if (filename === 'harmonic_static.json') {
                    return {
                        async: () => JSON.stringify({
                            full_track_analysis: { duration: 10 }
                        })
                    };
                }
                return { async: () => "{}" };
            });

            await init(mockUi, mockApi, mockPlayer, form);

            // Act: Trigger local file load (simulated)
            // Note: We can call handleLocalFileSubmit directly to test the logic
            await handleLocalFileSubmit(
                new File([""], "t.mtr"),
                new File([""], "t.wav"),
                mockUi, mockPlayer, mockApi
            );

            // Assert
            expect(mockApi.fetchTutorialData).toHaveBeenCalled(); // Should fetch tutorial
            expect(mockUi.showTutorialOverlay).toHaveBeenCalled();
            expect(mockUi.updateTutorialStatus).toHaveBeenCalledWith('ready', expect.any(Function));
        });

        test('Tutorial should be accessible when user is NOT authenticated)', async () => {
            // Arrange
            const tutorialBtn = document.getElementById('tutorial-btn');
            mockApi.checkAuthStatus.mockResolvedValue({ isAuthenticated: false });
            mockApi.fetchTutorialData.mockResolvedValue({ some: "data" });

            // Initialize app
            await init(mockUi, mockApi, mockPlayer, form);
            tutorialBtn.click();
            await Promise.resolve();

            // Assert 1
            expect(mockApi.fetchTutorialData).toHaveBeenCalledTimes(1);
            expect(mockUi.showTutorialOverlay).toHaveBeenCalled();
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
        });

        test('Tutorial should be accessible when user IS authenticated)', async () => {
            // Arrange
            const tutorialBtn = document.getElementById('tutorial-btn');
            const mockTutorialData = { some: "data" };
            mockApi.checkAuthStatus.mockResolvedValue({ isAuthenticated: true, user: { email: 'user@test.com' } });
            mockApi.fetchTutorialData.mockResolvedValue(mockTutorialData);

            await init(mockUi, mockApi, mockPlayer, form);
            tutorialBtn.click();
            await Promise.resolve();

            // Assert
            expect(mockApi.fetchTutorialData).toHaveBeenCalledTimes(1);
            expect(mockUi.showTutorialOverlay).toHaveBeenCalled();
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
        });
    });

    describe('handleFormSubmit()', () => {

        test('Successful submission should transition UI through all states: status -> player', async () => {
            // Arrange: Disable Tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            mockApi.submitJob.mockResolvedValue({ job_id: 'job-123' });
            mockApi.pollJobStatus.mockResolvedValue({
                result: {
                    "mapped_result": [{
                        'line_text': 'example line',
                        'words': [
                            { 'text': 'example', 'start': 0.1, 'end': 0.5 },
                            { 'text': 'line', 'start': 0.6, 'end': 1.0 },
                        ],
                        'line_start_time': 0.1,
                        'line_end_time': 1.0
                    }],
                    "harmonic_analysis": {
                        "full_track_analysis": {
                            "duration": 0.5,
                            "tempo": 136,
                            "rms_overall": {
                                "times": [0.1, 0.2, 0.3],
                                "values": [0.88, 0.99, 0.94]
                            }
                        },
                        "stem_analyses": {
                            "vocals": {
                                "f0_data": {
                                    "times": [0.1, 0.2, 0.3],
                                    "f0_values": [440, 660, 880],
                                },
                                "spectral_features": {
                                    "times": [0.1, 0.2, 0.3],
                                    "frequencies": [880, 1320, 1760],
                                    "spectrogram": [1000, 500, 4000],
                                    "rms": [0.84, 0.43, 0.91],
                                    "spectral_centroid": [1200, 4500, 3000],
                                    "spectral_bandwidth": [2000, 800, 1600],
                                    "spectral_rolloff": [1600, 3200, 100],
                                    "spectral_flatness": [100, 50, 22],
                                },
                                "timbral_features": {
                                    "mfccs": [-150, -100, -95, -60, -40, -30, -20, -10, -5, -1, -0.99, -0.60, -0.01],
                                    "chroma_stft": [44, 22],
                                },
                                "temporal_features": {
                                    "onsets": [0.1],
                                    "tempo": 136.0,
                                    "beats": [0.1],
                                }
                            },
                            "bass": {
                                "f0_data": {
                                    "times": [0.1, 0.2, 0.3],
                                    "f0_values": [null, 80, 100],
                                },
                                "spectral_features": {
                                    "times": [0.1, 0.2, 0.3],
                                    "frequencies": [null, 220, 300],
                                    "spectrogram": [null, 400, 500],
                                    "rms": [0.0, 0.5, 0.4],
                                    "spectral_centroid": [null, 1200, 2200],
                                    "spectral_bandwidth": [null, 500, 1000],
                                    "spectral_rolloff": [null, 2200, 4500],
                                    "spectral_flatness": [null, 8000, 8000],
                                },
                                "timbral_features": {
                                    "mfccs": [-100, -90, -55, -44, -22, -11, -4, -2, -0.98, -0.77, -0.64, -0.2, -0.004],
                                    "chroma_stft": [null, 3000, 222],
                                },
                                "temporal_features": {
                                    "onsets": [0.2],
                                    "tempo": 136.0,
                                    "beats": [0.2],
                                }
                            },
                            "other": null
                        }
                    },
                    "drum_analysis": [
                        {
                            "onset_time": 0.5,
                            "duration": 0.1,
                            "relative_volume": 0.123,
                            "dominant_frequency": 440.0,
                            "spectral_centroid": 500.0,
                            "spectral_rolloff": 1500.0,
                            "spectral_flux": 0.05,
                            "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                            "drum_type": "snare_drum",
                            "confidence": 0.95
                        },
                        {
                            "onset_time": 1.2,
                            "duration": 0.08,
                            "relative_volume": 0.098,
                            "dominant_frequency": 220.0,
                            "spectral_centroid": 300.0,
                            "spectral_rolloff": 1000.0,
                            "spectral_flux": 0.03,
                            "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                            "drum_type": "bass_drum",
                            "confidence": 0.90
                        },
                    ],
                    "audio_url": "/shared-data/audio/123-test.wav",
                    "original_filename": "Test.wav"
                }
            });
            const mockEvent = { preventDefault: jest.fn() };

            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer)

            // Assert the entire flow was orchestrated correctly\
            expect(mockEvent.preventDefault).toHaveBeenCalledTimes(1);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(true);
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Uploading files...');
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');

            expect(mockApi.submitJob).toHaveBeenCalledTimes(1);
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Processing... This may take several minutes.');
            // Expect any Function because app.js wraps it in an arrow function
            expect(mockApi.pollJobStatus).toHaveBeenCalledWith('job-123', expect.any(Function));

            expect(mockPlayer.initPlayer).toHaveBeenCalledWith({
                "job_id": "job-123",
                "mapped_result": [{
                    'line_text': 'example line',
                    'words': [
                        { 'text': 'example', 'start': 0.1, 'end': 0.5 },
                        { 'text': 'line', 'start': 0.6, 'end': 1.0 },
                    ],
                    'line_start_time': 0.1,
                    'line_end_time': 1.0
                }],
                "harmonic_analysis": {
                    "full_track_analysis": {
                        "duration": 0.5,
                        "tempo": 136,
                        "rms_overall": {
                            "times": [0.1, 0.2, 0.3],
                            "values": [0.88, 0.99, 0.94]
                        }
                    },
                    "stem_analyses": {
                        "vocals": {
                            "f0_data": {
                                "times": [0.1, 0.2, 0.3],
                                "f0_values": [440, 660, 880],
                            },
                            "spectral_features": {
                                "times": [0.1, 0.2, 0.3],
                                "frequencies": [880, 1320, 1760],
                                "spectrogram": [1000, 500, 4000],
                                "rms": [0.84, 0.43, 0.91],
                                "spectral_centroid": [1200, 4500, 3000],
                                "spectral_bandwidth": [2000, 800, 1600],
                                "spectral_rolloff": [1600, 3200, 100],
                                "spectral_flatness": [100, 50, 22],
                            },
                            "timbral_features": {
                                "mfccs": [-150, -100, -95, -60, -40, -30, -20, -10, -5, -1, -0.99, -0.60, -0.01],
                                "chroma_stft": [44, 22],
                            },
                            "temporal_features": {
                                "onsets": [0.1],
                                "tempo": 136.0,
                                "beats": [0.1],
                            }
                        },
                        "bass": {
                            "f0_data": {
                                "times": [0.1, 0.2, 0.3],
                                "f0_values": [null, 80, 100],
                            },
                            "spectral_features": {
                                "times": [0.1, 0.2, 0.3],
                                "frequencies": [null, 220, 300],
                                "spectrogram": [null, 400, 500],
                                "rms": [0.0, 0.5, 0.4],
                                "spectral_centroid": [null, 1200, 2200],
                                "spectral_bandwidth": [null, 500, 1000],
                                "spectral_rolloff": [null, 2200, 4500],
                                "spectral_flatness": [null, 8000, 8000],
                            },
                            "timbral_features": {
                                "mfccs": [-100, -90, -55, -44, -22, -11, -4, -2, -0.98, -0.77, -0.64, -0.2, -0.004],
                                "chroma_stft": [null, 3000, 222],
                            },
                            "temporal_features": {
                                "onsets": [0.2],
                                "tempo": 136.0,
                                "beats": [0.2],
                            }
                        },
                        "other": null
                    }
                },
                "drum_analysis": [
                    {
                        "onset_time": 0.5,
                        "duration": 0.1,
                        "relative_volume": 0.123,
                        "dominant_frequency": 440.0,
                        "spectral_centroid": 500.0,
                        "spectral_rolloff": 1500.0,
                        "spectral_flux": 0.05,
                        "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                        "drum_type": "snare_drum",
                        "confidence": 0.95
                    },
                    {
                        "onset_time": 1.2,
                        "duration": 0.08,
                        "relative_volume": 0.098,
                        "dominant_frequency": 220.0,
                        "spectral_centroid": 300.0,
                        "spectral_rolloff": 1000.0,
                        "spectral_flux": 0.03,
                        "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                        "drum_type": "bass_drum",
                        "confidence": 0.90
                    },
                ],
                "audio_url": "/shared-data/audio/123-test.wav",
                "original_filename": "Test.wav"
            }, expect.any(Function), mockPlayer);
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
        });

        test('Instrumental Submission: Should succeed even if mapped_result is empty', async () => {
            // Arrange: Disabled tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            mockApi.submitJob.mockResolvedValue({ job_id: 'job-inst-1' });
            mockApi.pollJobStatus.mockResolvedValue({
                result: {
                    "mapped_result": [], // INSTRUMENTAL: No lyrics
                    "harmonic_analysis": {
                        "full_track_analysis": { "duration": 10.0 }, // Valid analysis
                        "stem_analyses": {}
                    },
                    "drum_analysis": { "hits_accessor": {} },
                    "audio_url": "test.wav"
                }
            });
            const mockEvent = { preventDefault: jest.fn() };

            // Act
            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer);

            // Assert
            // 1. initPlayer should be called with the instrumental data
            expect(mockPlayer.initPlayer).toHaveBeenCalledWith(
                expect.objectContaining({ mapped_result: [] }),
                expect.any(Function),
                mockPlayer
            );

            // 2. UI should switch to player
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');

            // 3. Download button should be enabled (Instrumental is a valid result)
            expect(mockUi.toggleDownloadButton).toHaveBeenLastCalledWith(true);
        });

        test('Sad Path: API submission failure should show an error message and re-enable the form', async () => {
            // Arrange: Mock a failed API call
            // Disable tutorial for this test to isolate API failure, otherwise tutorial starts first
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            const apiError = new Error('Server Error');
            mockApi.submitJob.mockRejectedValue(apiError);
            const mockEvent = { preventDefault: jest.fn() };

            // Act: Initialize and submit the form
            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer);

            // Assert: The app should handle the error gracefully
            expect(mockApi.pollJobStatus).not.toHaveBeenCalled();
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(`Error: ${apiError.message}`);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(false);
        });

        test('Failure during player initialization should show an error and reset UI', async () => {
            // Arrange: Configure the API to succeed but the player to fail
            // Disable tutorial to skip to result
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            mockApi.submitJob.mockResolvedValue({ job_id: 'job-123' });
            mockApi.pollJobStatus.mockResolvedValue({
                result: {
                    "mapped_result": [{
                        'line_text': 'example line',
                        'words': [
                            { 'text': 'example', 'start': 0.1, 'end': 0.5 },
                            { 'text': 'line', 'start': 0.6, 'end': 1.0 },
                        ],
                        'line_start_time': 0.1,
                        'line_end_time': 1.0
                    }],
                    "harmonic_analysis": {
                        "full_track_analysis": {
                            "duration": 0.5,
                            "tempo": 136,
                            "rms_overall": {
                                "times": [0.1, 0.2, 0.3],
                                "values": [0.88, 0.99, 0.94]
                            }
                        },
                        "stem_analyses": {
                            "vocals": {
                                "f0_data": {
                                    "times": [0.1, 0.2, 0.3],
                                    "f0_values": [440, 660, 880],
                                },
                                "spectral_features": {
                                    "times": [0.1, 0.2, 0.3],
                                    "frequencies": [880, 1320, 1760],
                                    "spectrogram": [1000, 500, 4000],
                                    "rms": [0.84, 0.43, 0.91],
                                    "spectral_centroid": [1200, 4500, 3000],
                                    "spectral_bandwidth": [2000, 800, 1600],
                                    "spectral_rolloff": [1600, 3200, 100],
                                    "spectral_flatness": [100, 50, 22],
                                },
                                "timbral_features": {
                                    "mfccs": [-150, -100, -95, -60, -40, -30, -20, -10, -5, -1, -0.99, -0.60, -0.01],
                                    "chroma_stft": [44, 22],
                                },
                                "temporal_features": {
                                    "onsets": [0.1],
                                    "tempo": 136.0,
                                    "beats": [0.1],
                                }
                            },
                            "bass": {
                                "f0_data": {
                                    "times": [0.1, 0.2, 0.3],
                                    "f0_values": [null, 80, 100],
                                },
                                "spectral_features": {
                                    "times": [0.1, 0.2, 0.3],
                                    "frequencies": [null, 220, 300],
                                    "spectrogram": [null, 400, 500],
                                    "rms": [0.0, 0.5, 0.4],
                                    "spectral_centroid": [null, 1200, 2200],
                                    "spectral_bandwidth": [null, 500, 1000],
                                    "spectral_rolloff": [null, 2200, 4500],
                                    "spectral_flatness": [null, 8000, 8000],
                                },
                                "timbral_features": {
                                    "mfccs": [-100, -90, -55, -44, -22, -11, -4, -2, -0.98, -0.77, -0.64, -0.2, -0.004],
                                    "chroma_stft": [null, 3000, 222],
                                },
                                "temporal_features": {
                                    "onsets": [0.2],
                                    "tempo": 136.0,
                                    "beats": [0.2],
                                }
                            },
                            "other": null
                        }
                    },
                    "drum_analysis": [
                        {
                            "onset_time": 0.5,
                            "duration": 0.1,
                            "relative_volume": 0.123,
                            "dominant_frequency": 440.0,
                            "spectral_centroid": 500.0,
                            "spectral_rolloff": 1500.0,
                            "spectral_flux": 0.05,
                            "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                            "drum_type": "snare_drum",
                            "confidence": 0.95
                        },
                        {
                            "onset_time": 1.2,
                            "duration": 0.08,
                            "relative_volume": 0.098,
                            "dominant_frequency": 220.0,
                            "spectral_centroid": 300.0,
                            "spectral_rolloff": 1000.0,
                            "spectral_flux": 0.03,
                            "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                            "drum_type": "bass_drum",
                            "confidence": 0.90
                        },
                    ],
                    "audio_url": "/shared-data/audio/123-test.wav",
                    "original_filename": "Test.wav"
                }
            });
            const playerError = new Error('Failed to initialize audio context');
            mockPlayer.initPlayer.mockImplementation(() => {
                throw playerError;
            });
            const mockEvent = { preventDefault: jest.fn() };

            // Act: Run the submission handler
            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer)

            // Assert: Verify that the catch block handles the error correctly
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(`Error: ${playerError.message}`);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(false);
            // Check sequence: First 'player' (setup), then 'status' (revert on error)
            expect(mockUi.updateUIVisibility).toHaveBeenNthCalledWith(2, 'player');
            expect(mockUi.updateUIVisibility).toHaveBeenLastCalledWith('status');
        });

        test('Should enable download button for valid tracks', async () => {
            // Arrange
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            mockApi.submitJob.mockResolvedValue({ job_id: 'job-inst' });
            mockApi.pollJobStatus.mockResolvedValue({
                result: {
                    "mapped_result": [], // Empty lyrics (Instrumental)
                    "harmonic_analysis": {
                        "full_track_analysis": { // Presence implies success
                            "duration": 10.0,
                        },
                        "stem_analyses": {}
                    },
                    "drum_analysis": {
                        "hits_accessor": {}, // Presence implies success
                    },
                    "audio_url": "/shared-data/audio/test.wav",
                    "original_filename": "Test.wav"
                }
            });
            const mockEvent = { preventDefault: jest.fn() };

            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer);

            // Assert
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');

            // Verify download button was enabled
            expect(mockUi.setupDownloadButton).toHaveBeenCalledWith(expect.any(Function));
            expect(mockUi.toggleDownloadButton).toHaveBeenCalledWith(true);
        });

        test('Should DISABLE download button if harmonic analysis failed', async () => {
            // Arrange
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            mockApi.submitJob.mockResolvedValue({ job_id: 'job-fail' });
            mockApi.pollJobStatus.mockResolvedValue({
                result: {
                    "mapped_result": [],
                    "harmonic_analysis": {
                        // Missing full_track_analysis means static JSON fetch failed or didn't happen
                        "error": "Failed"
                    },
                    "drum_analysis": { "hits_accessor": {} },
                    "audio_url": "/shared-data/audio/test.wav",
                    "original_filename": "Test.wav"
                }
            });
            const mockEvent = { preventDefault: jest.fn() };

            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer);

            // Assert
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
            // Verify download button was NOT enabled (warn was logged)
            expect(mockUi.setupDownloadButton).not.toHaveBeenCalled();
            // It might be called with 'false' at start, but not 'true'
            expect(mockUi.toggleDownloadButton).not.toHaveBeenCalledWith(true);
        });
    });

    describe('handleLocalFileSubmit()', () => {
        let mockMtrFile, mockAudioFile, mockResultJson, mockStaticJson, mockNdjson;

        beforeEach(() => {
            // 1. Mock the files
            mockMtrFile = new File(["zipcontent"], "song.mtr", { type: "application/zip" });
            mockAudioFile = new File(["audiocontent"], "song.wav", { type: "audio/wav" });

            // 2. Mock the zip contents
            mockResultJson = JSON.stringify({
                app_version: '0.1.3',
                drum_analysis: { hits: [{ onset_time: 0.1, time: 0.1 }] },
                harmonic_analysis: {
                    streaming_urls: { vocals: "vocals.ndjson" }
                }
            });
            mockStaticJson = JSON.stringify({
                full_track_analysis: { duration: 10.0 },
                stem_analyses: {
                    vocals: {
                        temporal_features: { /* ... */ }
                    }
                }
            });
            mockNdjson = JSON.stringify({ time: 0.1 }); // a single line

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);

            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(mockResultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve(mockStaticJson) };
                // Note: The logic in app.js reads the filename from result.json (vocals.ndjson)
                // We must match what result.json says
                if (filename === 'vocals.ndjson') return { async: () => Promise.resolve(mockNdjson) };
                return null;
            });
        });

        test('should successfully load and process local files and hide download button', async () => {
            // Arrange: Disable tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            // Act
            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer, mockApi);

            // Assert
            // 1. UI state changes
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(true);
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Loading local file...');
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');

            // 2. File processing
            expect(global.JSZip).toHaveBeenCalledTimes(1);
            expect(mockZipInstance.loadAsync).toHaveBeenCalledWith(mockMtrFile);
            expect(mockZipInstance.file).toHaveBeenCalledWith('result.json');
            expect(mockZipInstance.file).toHaveBeenCalledWith('harmonic_static.json');
            expect(mockZipInstance.file).toHaveBeenCalledWith('vocals.ndjson');
            expect(global.URL.createObjectURL).toHaveBeenCalledWith(mockAudioFile);

            // 3. Data-toAccessor pipeline
            expect(calculateTotalFrames).toHaveBeenCalledWith(10.0);
            expect(TimeSeriesAccessor).toHaveBeenCalledTimes(2); // 1 for vocals, 1 for drums
            expect(TimeSeriesAccessor).toHaveBeenCalledWith([{ time: 0.1 }], 1); // For vocals
            expect(TimeSeriesAccessor).toHaveBeenCalledWith([{ onset_time: 0.1, time: 0.1 }], 1); // For drums

            // 4. Player initialization
            expect(mockPlayer.initPlayer).toHaveBeenCalledTimes(1);
            expect(mockPlayer.initPlayer).toHaveBeenCalledWith(
                expect.objectContaining({
                    audio_url: 'blob:http://localhost/mock-audio-url',
                    drum_analysis: expect.objectContaining({
                        hits_accessor: expect.any(Object)
                    }),
                    harmonic_analysis: expect.objectContaining({
                        stem_analyses: expect.objectContaining({})
                    })
                }),
                expect.any(Function),
                mockPlayer
            );

            // 5. Final UI state
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');

            // Ensure download button is explicitly hidden for local files
            expect(mockUi.toggleDownloadButton).toHaveBeenCalledWith(false);
        });

        test('should handle zip processing error and reset UI', async () => {
            // Arrange
            // Disable tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            const zipError = new Error('Invalid zip file');
            mockZipInstance.loadAsync.mockRejectedValue(zipError);

            // Act
            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer, mockApi);

            // Assert
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(`Error: ${zipError.message}`);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(false);
        });

        test('should do nothing if files are missing', async () => {
            await handleLocalFileSubmit(null, mockAudioFile, mockUi, mockPlayer);
            expect(global.JSZip).not.toHaveBeenCalled();

            await handleLocalFileSubmit(mockMtrFile, null, mockUi, mockPlayer, mockApi);
            expect(global.JSZip).not.toHaveBeenCalled();
        });

        test('should ACCEPT file with exact version match (0.1.3)', async () => {
            // Disable tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            const resultJson = JSON.stringify({
                app_version: '0.1.3', // EXACT MATCH
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            // Mock the zip returning this specific version
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve(mockStaticJson) };
                return null;
            });

            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer, mockApi);

            // Should proceed to initialization
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
        });

        test('should ACCEPT file with older patch version (0.1.1) - Backwards Compatibility', async () => {
            // Disable tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            const resultJson = JSON.stringify({
                app_version: '0.1.1', // COMPATIBLE PATCH
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve(mockStaticJson) };
                return null;
            });

            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer, mockApi);

            expect(mockPlayer.initPlayer).toHaveBeenCalled();
        });

        test('should REJECT file with different minor version (0.2.0)', async () => {
            // Disable tutorial
            localStorageMock.setItem('beethoven_disable_tutorial', 'true');

            const resultJson = JSON.stringify({
                app_version: '0.2.0', // INCOMPATIBLE MINOR
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                return null;
            });

            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer, mockApi);

            // Should fail before initialization
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(expect.stringContaining('Version mismatch'));
        });
    });

    describe('handleLibrarySongLoad()', () => {
        let handleLibrarySongLoad;

        beforeEach(async () => {
            const app = await import('../www/js/app.js');
            handleLibrarySongLoad = app.handleLibrarySongLoad;
        });

        test('should fetch MTR, parse zip, and init player', async () => {
            const mockSong = {
                artist: 'Test Artist',
                title: 'Test Song',
                mtr_url: '/api/library/file/test.mtr',
                audio_url: '/api/files/test.wav'
            };

            const mockMtrBuffer = new ArrayBuffer(8);
            fetch.mockResolvedValueOnce({
                ok: true,
                arrayBuffer: async () => mockMtrBuffer
            });

            const resultJson = JSON.stringify({
                app_version: '0.1.4',
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve('{}') };
                return null;
            });

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Loading Test Song from library...');
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');

            expect(fetch).toHaveBeenCalledWith('/api/library/file/test.mtr');
            expect(global.JSZip).toHaveBeenCalled();
            expect(mockZipInstance.loadAsync).toHaveBeenCalledWith(mockMtrBuffer);

            expect(mockPlayer.initPlayer).toHaveBeenCalledWith(
                expect.objectContaining({ app_version: '0.1.4', audio_url: '/api/files/test.wav' }),
                expect.any(Function),
                mockPlayer
            );
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
        });

        test('should handle network error gracefully', async () => {
            const mockSong = { mtr_url: '/api/error.mtr' };
            fetch.mockRejectedValueOnce(new Error('Network disconnected'));

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(expect.stringContaining('Network disconnected'));
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(false);
        });

        test('should REJECT library song with missing result.json', async () => {
            const mockSong = { mtr_url: '/api/library/file/invalid.mtr', audio_url: '/api/files/test.wav', title: 'Invalid' };
            fetch.mockResolvedValueOnce({
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8)
            });

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => null); // Nothing found

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            // Should fail before initialization
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(expect.stringContaining('result.json is required'));
        });

        test('should REJECT library song with version mismatch', async () => {
            const mockSong = { mtr_url: '/api/library/file/mismatch.mtr', audio_url: '/api/files/test.wav', title: 'Mismatch' };
            fetch.mockResolvedValueOnce({
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8)
            });

            const resultJson = JSON.stringify({
                app_version: '0.2.0', // INCOMPATIBLE MINOR
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                return null;
            });

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            // Should fail before initialization
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(expect.stringContaining('Version mismatch'));
        });

        test('should ACCEPT library song with missing harmonic_static.json', async () => {
            const mockSong = { mtr_url: '/api/library/file/noharmonic.mtr', audio_url: '/api/files/test.wav', title: 'No Harmonic' };
            fetch.mockResolvedValueOnce({
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8)
            });

            const resultJson = JSON.stringify({
                app_version: '0.1.3',
                drum_analysis: { hits: [] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                return null; // NO harmonic_static.json
            });

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            // Should proceed to initialization with empty harmonic data
            expect(mockPlayer.initPlayer).toHaveBeenCalled();
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
        });

        test('should process library song with valid drum hits', async () => {
            const mockSong = { mtr_url: '/api/library/file/drums.mtr', audio_url: '/api/files/test.wav', title: 'Drums' };
            fetch.mockResolvedValueOnce({
                ok: true,
                arrayBuffer: async () => new ArrayBuffer(8)
            });

            const resultJson = JSON.stringify({
                app_version: '0.1.4',
                drum_analysis: { hits: [{ onset_time: 1.0 }, { onset_time: 2.0 }] },
                harmonic_analysis: { streaming_urls: {} }
            });

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(resultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve('{"full_track_analysis": {"duration": 10}}') };
                return null;
            });

            await handleLibrarySongLoad(mockSong, mockUi, mockPlayer, mockApi);

            // Should proceed to initialization
            expect(mockPlayer.initPlayer).toHaveBeenCalledWith(
                expect.objectContaining({
                    app_version: '0.1.4',
                    audio_url: '/api/files/test.wav',
                    drum_analysis: expect.objectContaining({
                        hits_accessor: expect.anything()
                    })
                }),
                expect.any(Function),
                mockPlayer
            );
        });
    });
});
