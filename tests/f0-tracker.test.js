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
    let mockCanvas, mockCtx;
    const mockF0AnalysisData = {
        // This is what the API returns under 'f0_analysis'
        vocals: {
            times: [0.0, 0.1, 0.2],
            f0_values: [220, 221, null],
            time_interval: 0.1
        },
        bass: {
            times: [0.0, 0.1],
            f0_values: [110, 112],
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
        mockCanvas = {
            getContext: () => mockCtx,
            width: 600,
            height: 200,
            offsetWidth: 600,
            offsetHeight: 200,
        };
    });

    test('constructor should initialize canvas and draw initial state', () => {
        const tracker = new F0Tracker(mockCanvas, mockF0AnalysisData);
        expect(tracker.canvas).toBe(mockCanvas);
        expect(tracker.ctx).toBe(mockCtx);
        expect(tracker.f0Data).toEqual(mockF0AnalysisData);
        expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 600, 200);
    });

    test('update method should clear canvas and attempt to draw F0 data', () => {
        const tracker = new F0Tracker(mockCanvas, mockF0AnalysisData);
        mockCtx.clearRect.mockClear(); // Clear calls from constructor

        tracker.update(0.1);
        expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 600, 200);
        // We expect fillText to be called for legend and Y-axis labels
        expect(mockCtx.fillText).toHaveBeenCalled();
        // We expect arc and fill to be called if there's F0 data at currentTime
        expect(mockCtx.arc).toHaveBeenCalled();
        expect(mockCtx.fill).toHaveBeenCalled();
    });

    test('update method should handle missing instrument data gracefully', () => {
        const incompleteF0Data = {
            vocals: { times: [0.1], f0_values: [220], time_interval: 0.1 }
            // bass data is missing
        };
        const tracker = new F0Tracker(mockCanvas, incompleteF0Data);
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
