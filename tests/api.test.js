import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import { submitJob, pollJobStatus } from '../www/js/api.js';

// Mock the global fetch function
global.fetch = jest.fn();

describe('API Module', () => {
    beforeEach(() => {
        // Clear all instances and calls to constructor and all methods:
        fetch.mockClear();
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

    test('submitJob should throw and error on a failed request', async () => {
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
});
