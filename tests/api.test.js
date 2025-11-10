import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';

// Use unstable mock imports for mocking in ESM
jest.unstable_mockModule('../www/js/player/TimeSeriesAccessor.js', () => ({
    TimeSeriesAccessor: jest.fn().mockImplementation((source, totalElements) => ({
        source,
        totalElements,
        isMock: true, // Add a property to identify the mock instance
        ensureDataForTime: jest.fn().mockResolvedValue(undefined),
    })),
}));
jest.unstable_mockModule('../www/js/utils.js', () => ({
    calculateTotalFrames: jest.fn(),
}));

// Dynamically import the modules after setting up the mocks
const { TimeSeriesAccessor: MockAccessor } = await import('../www/js/player/TimeSeriesAccessor.js');
const { calculateTotalFrames: mockCalculateFrames } = await import('../www/js/utils.js');
const API = await import('../www/js/api.js');

// Mock the global fetch function
global.fetch = jest.fn();

describe('API Module', () => {
    let consoleErrorSpy, consoleWarnSpy;

    beforeEach(() => {
        // Clear all instances and calls to constructor and all methods:
        fetch.mockClear();
        MockAccessor.mockClear();
        mockCalculateFrames.mockReturnValue(1234);
        // Spy on console.error and suppress output during tests
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
        jest.useFakeTimers();
    });

    afterEach(() => {
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    describe('checkAuthStatus', () => {
        test('should return isAuthenticated: true and user data on success', async () => {
            const mockUser = { email: 'test@example.com' };
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockUser,
            });

            const result = await API.checkAuthStatus();

            expect(fetch).toHaveBeenCalledWith('/auth/user/profile');
            expect(result).toEqual({ isAuthenticated: true, user: mockUser });
        });

        test('should return isAuthenticated: false on non-ok response', async () => {
            fetch.mockResolvedValueOnce({ ok: false, status: 401 });
            const result = await API.checkAuthStatus();
            expect(result).toEqual({ isAuthenticated: false });
        });

        test('should return isAuthenticated: false on fetch network error', async () => {
            fetch.mockRejectedValueOnce(new Error('Network failure'));
            const result = await API.checkAuthStatus();
            expect(result).toEqual({ isAuthenticated: false });
            expect(consoleErrorSpy).toHaveBeenCalledWith("Auth status check failed:", expect.any(Error));
        });
    });

    describe('submitJob', () => {
        test('should POST with X-Access-Code header and return job data', async () => {
            const jobData = { job_id: '123-abc' };
            // Mock the fetch call to return a successful response
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => jobData,
            });

            const mockFormData = new FormData();
            const mockAccessCode = 'test_code';

            const result = await API.submitJob(mockFormData, mockAccessCode);

            // Check that fetch was called correctly
            expect(fetch).toHaveBeenCalledWith('/api/translate', {
                method: 'POST',
                headers: { 'X-Access-Code': 'test_code' },
                body: mockFormData,
            });

            // Check that the function returned the correct data
            expect(result).toEqual(jobData);
        });

        test('shoud POST without header if accessCode is null or empty', async () => {
            const jobData = { job_id: '987-zyx' };
            fetch.mockResolvedValueOnce({ ok: true, json: async () => jobData });
            const mockFormData = new FormData();

            await API.submitJob(mockFormData, null);

            expect(fetch).toHaveBeenCalledWith('/api/translate', {
                method: 'POST',
                headers: {},
                body: mockFormData,
            });
        });

        test('should throw an error on a failed request', async () => {
            // Mock the fetch call to return a failed response
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: async () => ({ error: 'Server exploded' }),
            });

            // We expect the function to throw an error, so we wrap it in a try/catch
            // or use Jest's .toThrow() matcher
            await expect(API.submitJob(new FormData(), 'code')).rejects.toThrow('Server exploded');
        });
    });

    describe('pollJobStatus', () => {
        const finishedResultPayload = {
            status: 'finished',
            result: {
                mapped_result: [{
                    'line_text': 'example line',
                    'words': [
                        {'text': 'example', 'start': 0.1, 'end': 0.5},
                        {'text': 'line', 'start': 0.6, 'end': 1.0},
                    ],
                    'line_start_time': 0.1,
                    'line_end_time': 1.0
                }],
                harmonic_analysis: {
                    static_results_url: '/api/results/file/123_harmonic.json',
                    streaming_urls: {
                        vocals: 'api/harmonic/stream/123_vocals.ndjson?stem_path=...',
                        bass: 'api/harmonic/stream/123_bass.ndjson?stem_path=...'
                    }
                },
                drum_analysis: {
                    hits: [{ onset_time: 0.5}, { onset_time: 1.5 }]
                },
                audio_url: '/api/files/123-test.wav',
                original_filename: "Test.wav"
            }
        };

        const staticDataPayload = {
            full_track_analysis: {
                duration: 10,
             tempo: 120
            },
             stem_analyses: {
                 vocals: {
                     temporal_features: {
                         onsets: [1.0],
             beats: [1.0, 2.0]
                     }
                 },
             bass: {
                 temporal_features: {
                     onsets: [1.1],
             beats: [1.1, 2.1]
                 }
             }
             }
        };

        test('should poll until "finished", see a results_url, fetch it, and return merged data', async () => {
            // Set a realistic frame count for 10 seconds
            mockCalculateFrames.mockReturnValue(431);
            // Set up the fetch mock sequence
            fetch
            // For polling
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ status: 'processing' })
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => finishedResultPayload
                })
                // For prepareFinalData call
                .mockResolvedValueOnce({ // Static JSON
                    ok: true,
                    json: async () => staticDataPayload
                });

            const onProgress = jest.fn();
            const pollPromise = API.pollJobStatus('job-123', onProgress);

            // Use runOnlyPendingTimers to execute the setInterval callback once
            await jest.runOnlyPendingTimersAsync();
            expect(onProgress).toHaveBeenCalledWith({ status: 'processing' });
            // Run again for the second poll
            await jest.runOnlyPendingTimersAsync();

            const finalResult = await pollPromise;

            // Check that fetch was called three times with the correct URLs
            expect(fetch).toHaveBeenCalledTimes(3);
            expect(fetch).toHaveBeenCalledWith('/api/results/job-123');
            expect(fetch).toHaveBeenCalledWith('/api/results/file/123_harmonic.json');

            // Check that the MockAccesor was called correctly
            expect(MockAccessor).toHaveBeenCalledTimes(3);
            expect(MockAccessor).toHaveBeenCalledWith('/api/harmonic/stream/123_vocals.ndjson?stem_path=...', 431);
            expect(MockAccessor).toHaveBeenCalledWith('/api/harmonic/stream/123_bass.ndjson?stem_path=...', 431);
            const drumHits = finishedResultPayload.result.drum_analysis.hits;
            expect(MockAccessor).toHaveBeenCalledWith(drumHits, 2);

            // Check the final, merged data structure is correct
            expect(finalResult.result.original_filename).toBe('Test.wav');
            expect(finalResult.result.audio_url).toBe('/api/files/123-test.wav');
            const finalHarmonic = finalResult.result.harmonic_analysis;
            expect(finalHarmonic.full_track_analysis.tempo).toBe(120);
            expect(finalHarmonic.stem_analyses.vocals.stream_accessor.isMock).toBe(true);
            expect(finalHarmonic.stem_analyses.bass.stream_accessor.isMock).toBe(true);
        });

        test('should reject on "failed" status', async () => {
            const failedResult = { status: 'failed', message: 'Analysis failed' };
            fetch.mockResolvedValueOnce({ ok: true, json: async () => failedResult });

            const pollPromise = API.pollJobStatus('job-456', jest.fn());

            // Ensure the expectation is setup before the time fires
            const rejectionPromise = expect(pollPromise).rejects.toThrow('Analysis failed');

            await jest.runAllTimersAsync();

            // Assert the promise rejects with the correct error message
            await rejectionPromise;
        });

        test('should reject on a non-ok fetch response', async () => {
            fetch.mockResolvedValueOnce({ ok: false, status: 500 });

            const pollPromise = API.pollJobStatus('job-123', jest.fn());

            jest.runOnlyPendingTimersAsync();

            await expect(pollPromise).rejects.toThrow('Error fetching results. Status: 500');
        });

        test('should warn return early if static harmonic URL is missing', async () => {
            const resultWithoutUrl = JSON.parse(JSON.stringify(finishedResultPayload));
            delete resultWithoutUrl.result.harmonic_analysis.static_results_url;

            fetch
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => resultWithoutUrl
                });

            const pollPromise = API.pollJobStatus('job-no-url', jest.fn());
            await jest.runAllTimersAsync();
            const finalResult = await pollPromise;

            // fetch should only be called twice (polling), not for static data
            expect(fetch).toHaveBeenCalledTimes(1);
            expect(consoleWarnSpy).toHaveBeenCalledWith("No static harmonic results URL found.");
            expect(finalResult.result).toEqual(resultWithoutUrl.result);
        });
    });

    describe('deleteAudioFile', () => {
        test('should send a DELETE request to the correct endpoint', async () => {
            // Arrange
            fetch.mockResolvedValueOnce({ ok: true });
            const filename = 'jobid_song.wav';

            // Act
            await API.deleteAudioFile(filename);

            // Assert
            expect(fetch).toHaveBeenCalledWith(`/api/cleanup/${filename}`, {
                method: 'DELETE',
            });
            expect(fetch).toHaveBeenCalledTimes(1);
        });

        test('should log an error on a failed DELETE request', async () => {
            fetch.mockResolvedValueOnce({ ok: false });
            await API.deleteAudioFile('jobid_song.wav');
            expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to delete audio file jobid_song.wav on the server.');
        });

        test('should log an error if fetch itself throws', async () => {
            const error = new Error('Network Error');
            fetch.mockRejectedValueOnce(error);
            await API.deleteAudioFile('jobid_song.wav');
            expect(consoleErrorSpy).toHaveBeenCalledWith('Error during deletion of audio file jobid_song.wav:', error);
        });
    });
});
