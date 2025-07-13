import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import { init, handleFormSubmit } from '../www/js/app.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlPath = path.resolve(__dirname, '../www/index.html')

// --- Test Suite 1: Unit Tests for app.js logic ---
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
        };
        mockApi = {
            submitJob: jest.fn(),
            pollJobStatus: jest.fn(),
        };
        mockPlayer = {
            initPlayer: jest.fn(),
        };
    });

    test('init() should correctly display only the upload UI on page load', () => {
        // Arrange: Use a spy to check if the real ui.updateUIVisibility is called
        const updateSpy = jest.spyOn(mockUi, 'updateUIVisibility');

        // Act: Initialize the application
        init(mockUi, mockApi, mockPlayer, form);

        // Assert: Verify the initial state of the DOM visibility
        expect(updateSpy).toHaveBeenCalledWith('upload');
        expect(updateSpy).toHaveBeenCalledTimes(1);
    });

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
            "f0_analysis": {
                "vocals": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [220.0, 220.1, 220.5],
                    "time_interval": 0.01
                },
                "bass": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [110.0, null, 110.2],
                    "time_interval": 0.01
                },
            },
            "volume_analysis": {
                "overall_rms": [[0.01, 0.5], [0.02, 0.7]],
                "instruments": {
                    "vocals": {
                        "rms_values": [[0.01, 0.4], [0.02, 0.3]]
                    },
                    "bass": {
                        "rms_values": [[0.01, 0.3], [0.02, 0.4]]
                    },
                }
            },
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
            "f0_analysis": {
                "vocals": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [220.0, 220.1, 220.5],
                    "time_interval": 0.01
                },
                "bass": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [110.0, null, 110.2],
                    "time_interval": 0.01
                },
            },
            "volume_analysis": {
                "overall_rms": [[0.01, 0.5], [0.02, 0.7]],
                "instruments": {
                    "vocals": {
                        "rms_values": [[0.01, 0.4], [0.02, 0.3]]
                    },
                    "bass": {
                        "rms_values": [[0.01, 0.3], [0.02, 0.4]]
                    },
                }
            },
            "audio_url": "/shared-data/audio/123-test.wav",
            "original_filename": "Test.wav"
        }, expect.any(Function), mockPlayer);
        expect(mockUi.updateUIVisibility).toHaveBeenCalledWith('player');
    });

    test('Sad Path: API submission failure should show an error message and re-enable the form', async () => {
        // Arrange: Mock a failed API call
        const apiError = new Error('Invalid Access Code');
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
            "f0_analysis": {
                "vocals": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [220.0, 220.1, 220.5],
                    "time_interval": 0.01
                },
                "bass": {
                    "times": [0.01, 0.02, 0.03],
                    "f0_values": [110.0, null, 110.2],
                    "time_interval": 0.01
                },
            },
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
