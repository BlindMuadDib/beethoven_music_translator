import { jest, describe, test, expect, beforeEach } from '@jest/globals';
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

    beforeEach(() => {
        // Create simple mock objects for our dependencies
        const html = fs.readFileSync(htmlPath, 'utf8');
        document.body.innerHTML = html;
        form = document.getElementById('translate-form');

        // Create pure mock objects for each dependency
        mockUi = {
            cacheDOMElements: jest.fn(),
            updateUIVisibility: jest.fn(),
            setSubmitButtonDisabled: jest.fn(),
            showStatusMessage: jest.fn(),
            updateAuthUI: jest.fn(),
        };
        mockApi = {
            submitJob: jest.fn(),
            pollJobStatus: jest.fn(),
            checkAuthStatus: jest.fn(),
        };
        mockPlayer = {
            initPlayer: jest.fn(),
        };

        // Clear all mock implementatios and calls
        jest.clearAllMocks();
        TimeSeriesAccessor.mockClear();
        calculateTotalFrames.mockClear();
        global.JSZip.mockClear();
        mockZipInstance.loadAsync.mockClear();
        mockZipInstance.file.mockClear();
        global.URL.createObjectURL.mockClear();
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
    });

    describe('handleFormSubmit()', () => {

        test('Successful submission should transition UI through all states: status -> player', async () => {
            // Arrange
            mockApi.submitJob.mockResolvedValue({ job_id: 'job-123' });
            mockApi.pollJobStatus.mockResolvedValue({ result: {
                "mapped_result": [{
                    'line_text': 'example line',
                    'words': [
                        {'text': 'example', 'start': 0.1, 'end': 0.5},
                        {'text': 'line', 'start': 0.6, 'end': 1.0},
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
            } });
            const mockEvent = { preventDefault: jest.fn() };

            await handleFormSubmit(mockEvent, mockUi, mockApi, mockPlayer)

            // Assert the entire flow was orchestrated correctly\
            expect(mockEvent.preventDefault).toHaveBeenCalledTimes(1);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(true);
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Uploading files...');
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('status');

            expect(mockApi.submitJob).toHaveBeenCalledTimes(1);
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith('Processing... This may take several minutes.');
            expect(mockApi.pollJobStatus).toHaveBeenCalledWith('job-123', mockUi.showStatusMessage);

            expect(mockPlayer.initPlayer).toHaveBeenCalledWith({
                "mapped_result": [{
                    'line_text': 'example line',
                    'words': [
                        {'text': 'example', 'start': 0.1, 'end': 0.5},
                        {'text': 'line', 'start': 0.6, 'end': 1.0},
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

        test('Sad Path: API submission failure should show an error message and re-enable the form', async () => {
            // Arrange: Mock a failed API call
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
            mockApi.submitJob.mockResolvedValue({ job_id: 'job-123' });
            mockApi.pollJobStatus.mockResolvedValue({ result: {
                "mapped_result": [{
                    'line_text': 'example line',
                    'words': [
                        {'text': 'example', 'start': 0.1, 'end': 0.5},
                        {'text': 'line', 'start': 0.6, 'end': 1.0},
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
            } });
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
            // The UI should NOT be stuck on the player view
            expect(mockUi.updateUIVisibility).not.toHaveBeenCalledWith('player');
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
                drum_analysis: { hits: [{ onset_time: 0.1, time: 0.1 }] },
            });
            mockStaticJson = JSON.stringify({
                full_track_analysis: { duration: 10.0 },
                stem_analyses: {
                    vocals: {
                        stream_file_path: "streams/vocals.ndjson",
                        temporal_features: { /* ... */ }
                    }
                }
            });
            mockNdjson = JSON.stringify({ time: 0.1 }); // a single line

            mockZipInstance.loadAsync.mockResolvedValue(mockZipInstance);
            mockZipInstance.file.mockImplementation((filename) => {
                if (filename === 'result.json') return { async: () => Promise.resolve(mockResultJson) };
                if (filename === 'harmonic_static.json') return { async: () => Promise.resolve(mockStaticJson) };
                if (filename === 'streams/vocals.ndjson') return { async: () => Promise.resolve(mockNdjson) };
                return null;
            });
        });

        test('should successfully load and process local files', async () => {
            // Act
            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer);

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
            expect(mockZipInstance.file).toHaveBeenCalledWith('streams/vocals.ndjson');
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
                        stem_analyses: expect.objectContaining({
                            vocals: expect.objectContaining({
                                stream_accessor: expect.any(Object)
                            })
                        })
                    })
                }),
                expect.any(Function),
                mockPlayer
            );

            // 5. Final UI state
            expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
        });

        test('should handle zip processing error and reset UI', async () => {
            // Arrange
            const zipError = new Error('Invalid zip file');
            mockZipInstance.loadAsync.mockRejectedValue(zipError);

            // Act
            await handleLocalFileSubmit(mockMtrFile, mockAudioFile, mockUi, mockPlayer);

            // Assert
            expect(mockPlayer.initPlayer).not.toHaveBeenCalled();
            expect(mockUi.showStatusMessage).toHaveBeenCalledWith(`Error: ${zipError.message}`);
            expect(mockUi.setSubmitButtonDisabled).toHaveBeenCalledWith(false);
        });

        test('should do nothing if files are missing', async () => {
            await handleLocalFileSubmit(null, mockAudioFile, mockUi, mockPlayer);
            expect(global.JSZip).not.toHaveBeenCalled();

            await handleLocalFileSubmit(mockMtrFile, null, mockUi, mockPlayer);
            expect(global.JSZip).not.toHaveBeenCalled();
        });
    });
});
