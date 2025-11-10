import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import { TimeSeriesAccessor } from '../www/js/player/TimeSeriesAccessor.js';

global.fetch = jest.fn();

describe('TimeSeriesAccessor', () => {
    let consoleErrorSpy;

    beforeEach(() => {
        fetch.mockClear();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    describe('constructor', () => {
        test('initializes correctly for a URL source', () => {
            const accessor = new TimeSeriesAccessor('/api/stream/url', 1000);
            expect(accessor.isUrlSource).toBe(true);
            expect(accessor.streamUrl).toBe('/api/stream/url');
            expect(accessor.totalElements).toBe(1000);
            expect(accessor.times.length).toBe(1000);
        });

        test('initializes correctly with a raw data array (drum hits)', () => {
            const rawHits = [{ onset_time: 0.1 }, { onset_time: 0.2 }];
            const accessor = new TimeSeriesAccessor(rawHits, rawHits.length);
            expect(accessor.isUrlSource).toBe(false);
            expect(accessor.chunks.get(0)).toEqual(rawHits);
            expect(accessor.times).toEqual([0.1, 0.2]);
        });

        test('initializes correctly with a valid JSON string', () => {
            const rawHits = [{ time: 0.1 }, { time: 0.2 }];
            const accessor = new TimeSeriesAccessor(JSON.stringify(rawHits), rawHits.length);
            expect(accessor.isUrlSource).toBe(false);
            expect(accessor.chunks.get(0)).toEqual(rawHits);
            expect(accessor.times).toEqual([0.1, 0.2]);
        });

        test('logs an error for invalid JSON string source', () => {
            const accessor = new TimeSeriesAccessor('invalid-json', 2);
            expect(consoleErrorSpy).toHaveBeenCalled();
            expect(accessor.chunks.get(0)).toEqual([]);
            expect(accessor.times).toEqual([null, null]);
        });

        test('throws RangeError for undefined totalElements', () => {
            expect(() => new TimeSeriesAccessor('/api/stream/url')).toThrow(RangeError);
            expect(() => new TimeSeriesAccessor('/api/stream/url', -1)).toThrow(RangeError);
        });
    });

    describe('ensureDataForTime', () => {
        test('triggers a fetch for an unloaded chunk', async () => {
            const accessor = new TimeSeriesAccessor('/api/stream/url', 100, 50);
            // Mock a successful fetch that returns an empty array of lines for
            // simplicity
            fetch.mockResolvedValueOnce({
                ok: true,
                text: async () => ''
            });

            // Spy on the internal method to force it to look in the second
            // chunk (index 1). An index of 75 falls into the chunk starting
            // at 50.
            const findIndexSpy = jest.spyOn(accessor, '_findClosestIndexBinary').mockReturnValue(75);

            await accessor.ensureDataForTime(3.0);

            // A time of 3.0 with a single loaded time of 0.1 will cause the
            // binary search to return the highest possible index, triggering
            // a new fetch.
            expect(fetch).toHaveBeenCalledTimes(1);
            expect(fetch).toHaveBeenCalledWith(expect.stringContaining('start=50&end=100'));
            findIndexSpy.mockRestore();
        });

        test('appends query params correctly if URL already has some', async () => {
            const accessor = new TimeSeriesAccessor('/api/harmonic/stream/url?stem=vocals', 100, 50);
            fetch.mockResolvedValueOnce({ ok: true, text: async () => '' });
            accessor.times[0] = 0.1;
            const findIndexSpy = jest.spyOn(accessor, '_findClosestIndexBinary').mockReturnValue(75);

            await accessor.ensureDataForTime(3.0);
            expect(fetch).toHaveBeenCalledWith('/api/harmonic/stream/url?stem=vocals&start=50&end=100');
            findIndexSpy.mockRestore();
        });

        test('handles fetch failure gracefully', async () => {
            const accessor = new TimeSeriesAccessor('/api/stream/url', 100, 50);
            fetch.mockRejectedValueOnce(new Error('Network failure'));
            const findIndexSpy = jest.spyOn(accessor, '_findClosestIndexBinary').mockReturnValue(75);

            await accessor.ensureDataForTime(3.0);

            expect(consoleErrorSpy).toHaveBeenCalledWith('Error fetching chunk 1:', expect.any(Error));
            expect(accessor.requests.has(1)).toBe(false); // Should clear request to allow retry
            expect(accessor.chunks.has(1)).toBe(false); // Should not store a failed chunk
            findIndexSpy.mockRestore();
        });
    });

    describe('Data Access', () => {
        let accessor;
        const chunkData = [
            { time: 0.1, value: 'a' }, { time: 0.2, value: 'b' },
            { time: 0.3, value: 'c' }, { time: 0.4, value: 'd' }
        ];

        beforeEach(() => {
            accessor = new TimeSeriesAccessor(chunkData, 4);
        });

        test('getElementAtTime returns the closest element from a loaded chunk', async () => {
            const element = accessor.getElementAtTime(0.202);
            expect(element).toEqual({ time: 0.2, value: 'b' });
        });

        test('getElementAtTime returns the correct element', () => {
            expect(accessor.getElementAtIndex(3)).toEqual({ time: 0.4, value: 'd' });
        });

        test('getElementAtIndex returns null for out-of-bounds index', () => {
            expect(accessor.getElementAtIndex(-1)).toBeNull();
            expect(accessor.getElementAtIndex(4)).toBeNull();
        });

        test('getElementAtTime returns null for unloaded data', () => {
            const urlAccessor = new TimeSeriesAccessor('/api/data', 100)
            expect(urlAccessor.getElementAtTime(1.5)).toBeNull();
        });
    });

    describe('_findClosestIndexBinary', () => {
        test(' correctly finds the index in a partially populated array', () => {
            const accessor = new TimeSeriesAccessor('/api/stream/url', 10, 10);
            accessor.times = [0, 1, 2, 3, 4, 5, 6, 7, null, null];

            // The real implementation is called, not a mock
            expect(accessor._findClosestIndexBinary(3.6)).toBe(4);
            expect(accessor._findClosestIndexBinary(8.0)).toBe(7);
            expect(accessor._findClosestIndexBinary(0.1)).toBe(0);
        });

        test('returns 0 if no times are loaded', () => {
            const accessor = new TimeSeriesAccessor('/api/stream/url', 10, 10);
            expect(accessor._findClosestIndexBinary(3.6)).toBe(0);
        });
    });
});
