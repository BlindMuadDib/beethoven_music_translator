import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import { getF0ValueAtTime, F0Tracker } from '../www/js/player/f0-tracker.js';

describe('getF0ValueAtTime (Pure Function)', () => {
    const mockTimes = [0.0, 0.1, 0.2, 0.3, 0.4];
    const mockF0s = [100, 110, null, 130, 140];

    test('should return correct F0 value when currentTime matches a time point closely', () => {
        expect(getF0ValueAtTime(mockF0s, mockTimes, 0.105, 0.02)).toBe(110);
    });

    test('should return null if F0 value at the closest time is null', () => {
        expect(getF0ValueAtTime(mockF0s, mockTimes, 0.2, 0.02)).toBe(null);
    });

    test('should return null if no time point is within the threshold', () => {
        expect(getF0ValueAtTime(mockF0s, mockTimes, 0.16, 0.02)).toBe(null);
    });
});

describe('F0Tracker Class', () => {
    let canvas, mockCtx;
    const f0Data = {
        // This is what the API returns under 'f0_analysis'
        vocals: {
            times: [0.1, 0.2, 0.3],
            f0_values: [220, null, 221],
            time_interval: 0.1
        },
        bass: {
            times: [0.1, 0.2, 0.3],
            f0_values: [110,null, 66],
            time_interval: 0.1
        },
    };

    beforeEach(() => {
        mockCtx = {
            clearRect: jest.fn(),
            fillText: jest.fn(),
            beginPath: jest.fn(),
            arc: jest.fn(),
            fill: jest.fn(),
            closePath: jest.fn(),
            moveTo: jest.fn(),
            lineTo: jest.fn(),
            stroke: jest.fn(),
        };
        canvas = {
            getContext: jest.fn().mockReturnValue(mockCtx),
            offsetWidth: 600,
            offsetHeight: 200,
        };
    });

    test('update() should draw the Y-axis and legend', () => {
        const tracker = new F0Tracker(canvas, f0Data);
        tracker.update(0.05);

        // Assert that it draws the grid lines and labels
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringMatching(/Hz/), expect.any(Number), expect.any(Number));
        expect(mockCtx.lineTo).toHaveBeenCalled();
    });

    test('update() should draw a ball for an active F0 value', () => {
        const tracker = new F0Tracker(canvas, f0Data);

        // Clear the mock history before calling the update test
        mockCtx.arc.mockClear();
        tracker.update(0.3);

        // Assert that it draws the grid lines and labels
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringMatching(/Hz/), expect.any(Number), expect.any(Number));
        expect(mockCtx.lineTo).toHaveBeenCalled();
        // Assert that the ball drawing function is called for the 'vocals' and 'bass' instruments
        expect(mockCtx.arc).toHaveBeenCalledTimes(2);
    });

    test('update() should NOT draw a ball if no F0 value is found for the current time', () => {
        const tracker = new F0Tracker(canvas, f0Data);

        // Clear the mock history before calling the update test
        mockCtx.arc.mockClear();
        tracker.update(0.2)

        // Assert that it draws the grid lines and labels
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringMatching(/Hz/), expect.any(Number), expect.any(Number));
        expect(mockCtx.lineTo).toHaveBeenCalled();
        // Assert that no ball is drawn
        expect(mockCtx.arc).not.toHaveBeenCalled()
    })

    test('update method should handle missing instrument data gracefully', () => {
        const incompleteF0Data = {
            vocals: { times: [0.1], f0_values: [220], time_interval: 0.1 }
            // bass data is missing
        };
        const tracker = new F0Tracker(canvas, incompleteF0Data);
        mockCtx.fillText.mockClear();

        tracker.update(0.1);
        // Check that it attempts to draw the legend for all active instruments,
        // include those with missing data.
        // Example: Check if "bass (no data)" was drawn
        const fillTextCalls = mockCtx.fillText.mock.calls;
        const bassLegendDrawn = fillTextCalls.some(call => call[0].includes('bass (no data)'));
        expect(bassLegendDrawn).toBe(true);
    });
});
