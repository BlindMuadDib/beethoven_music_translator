import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { submitJob, pollJobStatus, deleteAudioFile } from '../www/js/api.js';

// Mock the global fetch function
global.fetch = jest.fn();

describe('API Module', () => {
    beforeEach(() => {
        // Clear all instances and calls to constructor and all methods:
        fetch.mockClear();
        jest.useFakeTimers();
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test('submitJob should POST form data and return job data', async () => {
        const jobData = { job_id: '123-abc' };
        // Mock the fetch call to return a successful response
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => jobData,
        });

        const mockFormData = new FormData();
        const mockAccessCode = 'test_code';

        const result = await submitJob(mockFormData, mockAccessCode);

        // Check that fetch was called correctly
        expect(fetch).toHaveBeenCalledWith(`/api/translate?access_code=${mockAccessCode}`, {
            method: 'POST',
            body: mockFormData,
        });

        // Check that the function returned the correct data
        expect(result).toEqual(jobData);
    });

    test('submitJob should throw an error on a failed request', async () => {
        // Mock the fetch call to return a failed response
        fetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            json: async () => ({ error: 'Server exploded' }),
        });

        // We expect the function to throw an error, so we wrap it in a try/catch
        // or use Jest's .toThrow() matcher
        await expect(submitJob(new FormData(), 'code')).rejects.toThrow('Server exploded');
    });

    test('pollJobStatus should poll until status is "finished", see a results_url, fetch it, and return merged data', async () => {
        const initialFinishedResult = {
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
                    results_url: 'api/results/file/123-test_harmonic.json'
                },
                audio_url: '/api/files/123-test.wav',
                original_filename: "Test.wav"
            }
        };

        // Mock the final harmonic data that will be fetched from the useRealTimers
        const detailedHarmonicData = {
            job_id: '123',
            full_track_analysis: {
                duration: 10,
                tempo: 120
            },
            stem_analyses: {
                vocals: {
                    f0_data: {
                        times: [1],
                        f0_values: [440]
                    }
                }
            }
        };

        // First call returns "processing", second call returns "finished"
        // Third call is to the harmonic URL
        fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ status: 'processing' })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => initialFinishedResult
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => detailedHarmonicData
            });

        const onProgress = jest.fn();
        const pollPromise = pollJobStatus('job-123', onProgress);

        // Use runOnlyPendingTimers to execute the setInterval callback once
        await jest.runOnlyPendingTimersAsync();
        // Run again for the second poll
        await jest.runOnlyPendingTimersAsync();

        const finalResult = await pollPromise;

        // Check that the final result has the detailed harmonic data merged in
        expect(finalResult.result.harmonic_analysis).toEqual(detailedHarmonicData);
        expect(finalResult.result.original_filename).toBe('Test.wav');
        expect(finalResult.result.audio_url).toBe('/api/files/123-test.wav');

        // Check that fetch was called three times with the correct URLs
        expect(fetch).toHaveBeenCalledTimes(3);
        expect(fetch).toHaveBeenCalledWith('/api/results/job-123');
        expect(fetch).toHaveBeenCalledWith('/api/results/file/123-test_harmonic.json');
    });

    test('pollJobStatus should reject on "failed" status', async () => {
        const failedResult = { status: 'failed', message: 'Custom failure message' };
        fetch.mockResolvedValueOnce({ ok: true, json: async () => failedResult });

        const pollPromise = pollJobStatus('job-123', jest.fn());

        jest.runOnlyPendingTimersAsync();

        // Assert the promise rejects with the correct error message
        await expect(pollPromise).rejects.toThrow('Custom failure message');
    });

    test('pollJobStatus should reject on a non-ok fetch response', async () => {
        fetch.mockResolvedValueOnce({ ok: false, status: 500 });

        const pollPromise = pollJobStatus('job-123', jest.fn());

        jest.runOnlyPendingTimersAsync();

        await expect(pollPromise).rejects.toThrow('Error fetching results. Status: 500');
    });

    test('deleteAudioFile should send a DELETE request to the correct endpoint', async () => {
        // Arrange
        fetch.mockResolvedValueOnce({ ok: true });
        const filename = 'jobid_song.wav';

        // Act
        await deleteAudioFile(filename);

        // Assert
        expect(fetch).toHaveBeenCalledWith(`/api/cleanup/${filename}`, {
            method: 'DELETE',
        });
        expect(fetch).toHaveBeenCalledTimes(1);
    });
});
