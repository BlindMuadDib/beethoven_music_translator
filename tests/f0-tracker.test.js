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
    let canvas, mockCtx, f0Data, volumeData;
    let tracker; // Declare tracker here so it is available in all tests

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
            // Add properties for strokeStyle, fillStyle, font, textAlign
            set strokeStyle(val) { this._strokeStyle = val; }, get strokeStyle() { return this._strokeStyle; },
            set fillStyle(val) { this._fillStyle = val; }, get fillStyle() { return this._fillStyle; },
            set font(val) { this._font = val; }, get font() { return this._font; },
            set textAlign(val) { this._textAlign = val; }, get textAlign() { return this._textAlign; },
        };
        canvas = {
            getContext: jest.fn().mockReturnValue(mockCtx),
            offsetWidth: 600,
            offsetHeight: 200,
        };
        f0Data = {
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
        volumeData = {
            vocals: { rms_values: [[0.1, 0.2], [0.2, 0.5], [0.3, 0.8]] }, // min: 0.2, max: 0.8
            // bass volume data is intentionally missing to test robustness
        };
        // Initialize the tracker in beforeEach
        tracker = new F0Tracker(canvas, f0Data, volumeData);
    });

    test('update() should draw the Y-axis and legend', () => {
        tracker.update(0.05);

        // Assert that it draws the grid lines and labels
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringMatching(/Hz/), expect.any(Number), expect.any(Number));
        expect(mockCtx.lineTo).toHaveBeenCalled();
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringContaining('vocals'), expect.any(Number), expect.any(Number));
        expect(mockCtx.fillText).toHaveBeenCalledWith(expect.stringContaining('bass'), expect.any(Number), expect.any(Number));
    });

    test('constructor should process both F0 and volume data', () => {
        expect(tracker.f0Data).toBe(f0Data);
        expect(tracker.volumeData).toBeDefined();
        // Check that volume data was normalized and stored
        expect(tracker.volumeData.vocals.minRms).toBe(0.2);
        expect(tracker.volumeData.vocals.maxRms).toBe(0.8);
    });

    test('update() should call drawBall with a calculated size when volume data is present', () => {
        const drawBallSpy = jest.spyOn(tracker, 'drawBall');

        tracker.update(0.3); // Time where vocals have both F0 and volume

        // Check that drawBall was called for vocals
        const vocalsCall = drawBallSpy.mock.calls.find(call => call[0] === 'vocals');
        expect(vocalsCall).toBeDefined();

        // At time 0.2, vocal RMS is 0.8, which is max, so normalized volume is 1
        expect(vocalsCall[3]).toBe(1); // normalizedVolume
        expect(vocalsCall[2]).toBe(221); // f0
    });

    test('update() should call drawBall with a default size when volume data is missing for an instrument', () => {
        const drawBallSpy = jest.spyOn(tracker, 'drawBall');

        tracker.update(0.1); // Time where bass has F0 but no volume data

        const bassCall = drawBallSpy.mock.calls.find(call => call[0] === 'bass');
        expect(bassCall).toBeDefined();

        // Expect the default volume (e.g., 0.5) when data is missing
        const DEFAULT_VOLUME = 0.5
        expect(bassCall[3]).toBe(DEFAULT_VOLUME); // normalizedVolume
        expect(bassCall[2]).toBe(110); // f0
    });

    test('update() should NOT draw a ball if F0 is null, even if volume exists', () => {
        const drawBallSpy = jest.spyOn(tracker, 'drawBall');

        tracker.update(0.2); // Time where vocals have a volume but F0 is null

        const vocalsCall = drawBallSpy.mock.calls.find(call => call[0] === 'vocals');
        expect(vocalsCall).toBeUndefined(); // Should not be called
    });

    test('drawBall() should calculate radius based on normalized volume', () => {
        const spacing = 100; // Provide a mock spacing value for the test

        mockCtx.arc.mockClear();
        // Test with minimum volume (should be > 0)
        tracker.drawBall('vocals', 150, 220, 0, spacing); // volume = 0
        let radius = mockCtx.arc.mock.calls[0][2];
        expect(radius).toBe(tracker.config.minRadius);
        expect(radius).toBe(4);

        // Test with maximum volume
        mockCtx.arc.mockClear();
        tracker.drawBall('vocals', 150, 220, 1, spacing); // volume = 1
        radius = mockCtx.arc.mock.calls[0][2];
        const maxRadius = (spacing / 2);
        const expectedMaxRadius = tracker.config.minRadius + (maxRadius - tracker.config.minRadius);
        expect(radius).toBeCloseTo(expectedMaxRadius)
    });

    test('drawBall() should calculate static Y-position independent of volume/radius but based on maximum possible radius for the frame', () => {
        // Define an F0 value and verify its Y-position
        const testF0 = 500;
        const testX = 200;
        const testSpacing = 50; // Simulate an instrument spacing for this frame

        // calculate max radius for THIS frame based on testSpacing
        const maxRadiusForFrame = Math.max(tracker.config.minRadius, testSpacing / 2);

        // Capture initial canvas dimensions and F0Tracker config for calculation
        const canvasHeight = canvas.offsetHeight;
        const baseDrawingPadding = tracker.config.baseDrawingPadding;

        // Expected Y calculation based on the new logic in drawBall
        const totalVerticalOffset = maxRadiusForFrame + baseDrawingPadding;
        const effectiveCanvasHeight = canvasHeight - (2 * totalVerticalOffset);

        const f0Min = tracker.config.defaultF0Min;
        const f0Max = tracker.config.defaultF0Max;

        const yMapped = ((testF0 - f0Min) / (f0Max - f0Min)) * effectiveCanvasHeight;
        const expectedY = totalVerticalOffset + (effectiveCanvasHeight - yMapped);

        mockCtx.arc.mockClear();

        // Test with low volume
        tracker.drawBall('vocals', testX, testF0, 0, testSpacing);
        const yLowVolume = mockCtx.arc.mock.calls[0][1];
        expect(yLowVolume).toBeCloseTo(expectedY);

        mockCtx.arc.mockClear();
        // Test with high volume
        tracker.drawBall('vocals', testX, testF0, 1, testSpacing);
        const yHighVolume = mockCtx.arc.mock.calls[0][1];
        expect(yHighVolume).toBeCloseTo(expectedY);

        // Assert that Y position is the same regardless of volume
        expect(yLowVolume).toBeCloseTo(yHighVolume);
    });

    test('update method should handle missing instrument data gracefully', () => {
        const incompleteF0Data = {
            vocals: { times: [0.1], f0_values: [220], time_interval: 0.1 }
            // bass data is missing
        };
        const tempTracker = new F0Tracker(canvas, incompleteF0Data);
        mockCtx.fillText.mockClear();

        tempTracker.update(0.1);
        // Check that it attempts to draw the legend for all active instruments,
        // include those with missing data.
        // Example: Check if "bass (no data)" was drawn
        const fillTextCalls = mockCtx.fillText.mock.calls;
        const bassLegendDrawn = fillTextCalls.some(call => call[0].includes('bass (no data)'));
        expect(bassLegendDrawn).toBe(true);
        const vocalsLegendDrawn = fillTextCalls.some(call => call[0].includes('vocals'));
        expect(vocalsLegendDrawn).toBe(true);
    });
});
