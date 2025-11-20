import { jest, describe, test, expect } from '@jest/globals';
import { SpectrogramAccessor } from '../www/js/player/SpectrogramAccessor.js';

describe('SpectrogramAccessor', () => {
    const rawData = [
        [0.1, 0.2], // Slice 0
        [0.3, 0.4], // Slice 1
        [0.5, 0.6], // Slice 2
    ];
    const dataString = JSON.stringify(rawData);

    test('constructor should store the inner data string correctly', () => {
        const accessor = new SpectrogramAccessor(dataString);
        expect(accessor.dataString).toBe(dataString.substring(1, dataString.length - 1));
    });

    test('getSlice should parse and return the correct slice by index', () => {
        const accessor = new SpectrogramAccessor(dataString);

        // Retrieve a middle slice
        const slice1 = accessor.getSlice(1);
        expect(slice1).toEqual([0.3, 0.4]);

        // Retrieve the first slice
        const slice0 = accessor.getSlice(0);
        expect(slice0).toEqual([0.1, 0.2]);
    });

    test('getSlice should return from cache on subsequent calls', () => {
        const accessor = new SpectrogramAccessor(dataString);

        // The first call will parse it
        const slice1_firstCall = accessor.getSlice(1);
        expect(slice1_firstCall).toEqual([0.3, 0.4]);

        // Spy on JSON.parse to ensure it's NOT called again for the same slice
        const jsonParseSpy = jest.spyOn(JSON, 'parse');
        const slice1_secondCall = accessor.getSlice(1);

        expect(slice1_secondCall).toEqual([0.3, 0.4]); // Should still get correct data
        expect(jsonParseSpy).not.toHaveBeenCalled(); // Assert that it came from cache

        jsonParseSpy.mockRestore();
    });

    test('getSlice should return null for an out-of-bounds index', () => {
        const accessor = new SpectrogramAccessor(dataString);
        const slice = accessor.getSlice(99);
        expect(slice).toBeNull();
    });

    test('getSlice should handle an empty data string', () => {
        const accessor = new SpectrogramAccessor("[]");
        const slice = accessor.getSlice(0);
        expect(slice).toBeNull();
    });
});
