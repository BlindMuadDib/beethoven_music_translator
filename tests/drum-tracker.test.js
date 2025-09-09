import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';

jest.unstable_mockModule('../www/js/player/TimeSeriesAccessor.js', () => ({
    TimeSeriesAccessor: jest.fn().mockImplementation((source, totalElements) => ({
        source,
        totalElements,
        getElementAtIndex: jest.fn(),
        _findClosestIndexBinary: jest.fn().mockReturnValue(0), // Default mock
    })),
}));

const { DrumTracker } = await import('../www/js/player/drum-tracker.js');
const { TimeSeriesAccessor: MockAccessor } = await import ('../www/js/player/TimeSeriesAccessor.js');

describe('DrumTracker', () => {
    let canvas, ctx, mockDrumAnalysis, mockHitsAccessor;
    const mockHits = [
        {
            "onset_time": 0.5,
            "duration": 0.1,
            "relative_volume": 0.5,
            "dominant_frequency": 440.0,
            "spectral_centroid": 500.0,
            "spectral_rolloff": 1500.0,
            "spectral_flux": 0.5,
            "mfccs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
            "drum_category": "snare",
            "category_confidence": 0.98,
            "drum_type": "unknown",
            "type_confidence": 0.0,
            "qualifier": "brush",
            "qualifier_confidence": 0.91
        },
        {
            "onset_time": 1.2,
            "duration": 0.08,
            "relative_volume": 0.3,
            "dominant_frequency": 220.0,
            "spectral_centroid": 300.0,
            "spectral_rolloff": 1000.0,
            "spectral_flux": 0.3,
            "mfccs": [13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
            "drum_category": "kick",
            "category_confidence": 0.93,
            "drum_type": "bass",
            "type_confidence": 1.0,
            "qualifier": "no_qualifier",
            "qualifier_confidence": 1.0
        },
        {
            "onset_time": 1.5,
            "duration": 0.8, // Longer duration for decay test
            "relative_volume": 0.7,
            "dominant_frequency": 5000.0,
            "spectral_centroid": 4500.0,
            "spectral_rolloff": 6000.0,
            "spectral_flux": 0.8,
            "mfccs": [],
            "drum_category": "cymbal",
            "category_confidence": 0.97,
            "drum_type": "hihat",
            "type_confidence": 0.98,
            "qualifier": "open",
            "qualifier_confidence": 0.90
        },
        {
            "onset_time": 2.0,
            "duration": 0.4,
            "relative_volume": 0.6,
            "dominant_frequency": 1200.0,
            "spectral_centroid": 1500.0,
            "spectral_rolloff": 2500.0,
            "spectral_flux": 0.6,
            "mfccs": [],
            "drum_category": "tom",
            "category_confidence": 0.92,
            "drum_type": "low",
            "type_confidence": 0.85,
            "qualifier": "rimshot",
            "qualifier_confidence": 0.94
        },
        {
            "onset_time": 2.5,
            "duration": 0.6,
            "relative_volume": 0.7,
            "dominant_frequency": 8000.0,
            "spectral_centroid": 7000.0,
            "spectral_rolloff": 7500.0,
            "spectral_flux": 0.9,
            "mfccs": [],
            "drum_category": "cymbal",
            "category_confidence": 0.99,
            "drum_type": "crash",
            "type_confidence": 0.99,
            "qualifier": "full",
            "qualifier_confidence": 0.91
        }
    ];

    beforeEach(() => {
        // Mock ResizeObserver in the test environment
        global.ResizeObserver = jest.fn(cb => ({
            observe: jest.fn(),
            unobserve: jest.fn(),
            disconnect: jest.fn(),
        }));

        ctx = {
            clearRect: jest.fn(),
            beginPath: jest.fn(),
            moveTo: jest.fn(),
            lineTo: jest.fn(),
            stroke: jest.fn(),
            fill: jest.fn(),
            arc: jest.fn(),
            rect: jest.fn(),
            closePath: jest.fn(),
            save: jest.fn(),
            restore: jest.fn(),
            measureText: jest.fn(() => ({ width: 50 })), // Mock for drawTooltip
            fillText: jest.fn(),
            fillRect: jest.fn(),
            roundRect: jest.fn(), // For drawLegend,
            shadowColor: '', shadowBlur: 0,
            fillStyle: '', strokeStyle: '',
            lineWidth: 0, font: '', textAlign: '', globalAlpha: 1
        };

        canvas = {
            getContext: jest.fn(() => ctx),
            getBoundingClientRect: jest.fn(() => ({
                width: 800, height: 400,
                left: 0, top: 0
            })),
            addEventListener: jest.fn(),
            removeEventListener: jest.fn(),
        };

        // Setup the mock accessor instance
        mockHitsAccessor = new MockAccessor(mockHits, mockHits.length);
        mockDrumAnalysis = {
            tempo: 120,
            hits_accessor: mockHitsAccessor
        };

        MockAccessor.mockClear();
    });

    test('constructor should use the hits_accessor from drumAnalysis', () => {
        // Act
        const tracker = new DrumTracker(canvas, mockDrumAnalysis);

        // Assert
        expect(tracker).toBeInstanceOf(DrumTracker);
        expect(tracker.tempo).toBe(120);
        expect(tracker.hitsAccessor).toBe(mockHitsAccessor);
        expect(canvas.getContext).toHaveBeenCalledWith('2d');
        // Ensure resizeCanvas is called on init
        expect(canvas.width).toBe(800);
        expect(canvas.height).toBe(400);
    });

    test('should throw an error if an invalid canvas is provided', () => {
        // Assert
        expect(() => {
            new DrumTracker(null, mockDrumAnalysis);
        }).toThrow("A valid canvas element must be provided.");
    });

    describe('resizeCanvas', () => {
        test('should update canvas dimensions and redraw', ()=> {
            const tracker = new DrumTracker(canvas, mockDrumAnalysis);
            // Reset mocks to check calls *after* initial setup
            jest.clearAllMocks();
            const drawSpy = jest.spyOn(tracker, 'draw');

            canvas.getBoundingClientRect.mockReturnValue({ width: 1000, height: 500 });

            tracker.resizeCanvas();

            expect(canvas.width).toBe(1000);
            expect(canvas.height).toBe(500);
            expect(drawSpy).toHaveBeenCalled();
            expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 1000, 500);
            drawSpy.mockRestore();
        });
    });

    describe('update', () => {
        let tracker;
        let drawSpy;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            drawSpy = jest.spyOn(tracker, 'draw');
            drawSpy.mockClear(); // Clear initial draw call from constructor
        });

        test('should call draw if currentTime changes significantly', () => {
            tracker.update(0.1);
            expect(drawSpy).toHaveBeenCalledWith(0.1);

            drawSpy.mockClear();
            tracker.update(0.1 + 1 / 60 + 0.001); // Significant change
            expect(drawSpy).toHaveBeenCalledWith(expect.any(Number));
        });

        test('should not call draw if currentTime does not change significantly', () => {
            tracker.update(0.1);
            drawSpy.mockClear(); // Clear first call

            tracker.update(0.1 + 1 / 60 - 0.001); // Insignificant change
            expect(drawSpy).not.toHaveBeenCalled();

            tracker.update(0.1); // No change
            expect(drawSpy).not.toHaveBeenCalled();
        });
    });

    describe('draw', () => {
        let tracker;
        let drawShapeSpy, drawLegendSpy, drawTooltipSpy;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            // Clear all ctx mocks from constructor's draw and resize calls
            jest.clearAllMocks();
            drawShapeSpy = jest.spyOn(tracker, 'drawShape');

            // Mock helper methods to isolate the 'draw' method's functionality
            drawLegendSpy = jest.spyOn(tracker, 'drawLegend').mockImplementation(() => {});
            drawTooltipSpy = jest.spyOn(tracker, 'drawTooltip').mockImplementation(() => {});
        });

        afterEach(() => {
            jest.restoreAllMocks();
        });

        test('should clear canvas and call drawing helper methods', () => {
            const drawTempoLinesSpy = jest.spyOn(tracker, 'drawTempoLines');
            const drawNowLineSpy = jest.spyOn(tracker, 'drawNowLine');
            // Mock accessor to return a hit to ensure drawShap is called
            mockHitsAccessor.getElementAtIndex.mockImplementation(i => mockHits[i] || null);

            tracker.update(0.55); // Time when first hit is active

            expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, canvas.width, canvas.height);
            expect(drawTempoLinesSpy).toHaveBeenCalledWith(0.55, canvas.width, canvas.height);
            expect(drawNowLineSpy).toHaveBeenCalledWith(canvas.width, canvas.height);
            expect(drawShapeSpy).toHaveBeenCalledTimes(2); // Only one hit active at 0.55

            expect(drawLegendSpy).toHaveBeenCalled();
            expect(drawTooltipSpy).toHaveBeenCalled();
            expect(ctx.globalAlpha).toBeCloseTo(1.0); // Reset after shapes

            drawTempoLinesSpy.mockRestore();
            drawNowLineSpy.mockRestore();
            drawLegendSpy.mockRestore();
            drawTooltipSpy.mockRestore();
        });

        test('should call drawShape for active hits using the accessor', () => {
            // Mock the accessor to return the test hits
            mockHitsAccessor.getElementAtIndex.mockImplementation(i => mockHits[i] || null);
            mockHitsAccessor._findClosestIndexBinary.mockReturnValue(0);

            tracker.update(0.0); // No hits
            expect(drawShapeSpy).not.toHaveBeenCalled();

            drawShapeSpy.mockClear();
            mockHitsAccessor.getElementAtIndex.mockImplementation(i => mockHits[i] || null);
            mockHitsAccessor._findClosestIndexBinary.mockReturnValue(0);


            tracker.update(0.51); // First hit active

            expect(mockDrumAnalysis.hits_accessor._findClosestIndexBinary).toHaveBeenCalled();
            expect(mockDrumAnalysis.hits_accessor.getElementAtIndex).toHaveBeenCalled();
            expect(drawShapeSpy).toHaveBeenCalledTimes(2);
            drawShapeSpy.mockClear();

            tracker.update(1.25); // Second hit active
            expect(mockDrumAnalysis.hits_accessor._findClosestIndexBinary).toHaveBeenCalled();
            expect(mockDrumAnalysis.hits_accessor.getElementAtIndex).toHaveBeenCalled();
            expect(drawShapeSpy).toHaveBeenCalledTimes(2)
            drawShapeSpy.mockClear();

            tracker.update(1.0); // Neither hit active
            expect(drawShapeSpy).not.toHaveBeenCalled();
        });
    });

    describe('drawTempoLines', () => {
        let tracker;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            jest.clearAllMocks(); // Clear calls from constructor
        });

        test('should draw multiple vertical tempo lines', () => {
            tracker.drawTempoLines(0, canvas.width, canvas.height);

            const pixelsPerBeat = 150;
            const expectedLines = Math.ceil(canvas.width / pixelsPerBeat);
            // Adjust for loop starting at x = -scrollOffset; if
            // scrollOffset is 0, it starts at 0, and runs up to <
            // width. This is usually Math.floor(width /
            // pixelsPerBeat) + 1, or just calculate the loop
            // iterations. For width 800, pixelsPerBeat 150:
            // 0, 150, 300, 450, 600, 750 (6 lines)
            const expectedCalls = Math.floor(canvas.width / pixelsPerBeat) + 1;

            expect(ctx.beginPath).toHaveBeenCalled();
            expect(ctx.moveTo).toHaveBeenCalledTimes(expectedCalls);
            expect(ctx.lineTo).toHaveBeenCalledTimes(expectedCalls);
            expect(ctx.stroke).toHaveBeenCalledTimes(expectedCalls);

            // Check if coordinates for some lines are within
            // expected range (exact number of calls depends on
            // scrollOffset and width, so verify pattern)
            const firstMNoveToX = ctx.moveTo.mock.calls[0][0];
            expect(firstMNoveToX).toBeCloseTo(0); // At currentTime 0, scrollOffset is 0
            expect(ctx.moveTo.mock.calls[0][1]).toBe(0);
            expect(ctx.lineTo.mock.calls[0][1]).toBe(canvas.height);
        });

        test('should apply scroll offset based on current time', () => {
            const pixelsPerBeat = 150;
            const timePerBeat = 60 / tracker.tempo; // 120 bpm -> 0.5 seconds per beat

            tracker.drawTempoLines(timePerBeat / 2, canvas.width, canvas.height); // Halfway through a beat
            const expectedOffset = -(timePerBeat / 2 / timePerBeat * pixelsPerBeat); // -75
            expect(ctx.moveTo.mock.calls[0][0]).toBeCloseTo(expectedOffset);
        });
    });

    describe('drawNowLine', () => {
        let tracker;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            jest.clearAllMocks();
        });

        test('should draw a single vertical line at staticXPosition', () => {
            const expectedX = canvas.width * tracker.config.staticXPosition;

            tracker.drawNowLine(canvas.width, canvas.height);

            expect(ctx.beginPath).toHaveBeenCalledTimes(1);
            expect(ctx.moveTo).toHaveBeenCalledWith(expectedX, 0);
            expect(ctx.lineTo).toHaveBeenCalledWith(expectedX, canvas.height);
            expect(ctx.stroke).toHaveBeenCalledTimes(1);
        });
    });

    // --- Helper Methods Tests ---

    describe('getYPosition', () => {
        let tracker;
        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
        });

        test('should return correct base Y position for drum types', () => {
            // Snare Drum (yAxisMap: 0.6)
            let hit = { drum_category: 'snare', drum_type: 'open_band', spectral_centroid: 0, dominant_frequency: 0 };
            expect(tracker.getYPosition(hit)).toBeCloseTo(0.6 + 0.5 * 0.1, 2); // 0.6 base + max positive offset for low pitch

            // Bass Drum (yAxisMap: 0.9)
            hit = { drum_category: 'kick', drum_type: 'bass', spectral_centroid: 0, dominant_frequency: 0 };
            expect(tracker.getYPosition(hit)).toBeCloseTo(0.9 + 0.5 * 0.1, 2);

            // Hi-hat (yAxisMap: 0.25)
            hit = { drum_category: 'cymbal', drum_type: 'hihat', spectral_centroid: 0, dominant_frequency: 0 };
            expect(tracker.getYPosition(hit)).toBeCloseTo(0.3, 2);
        });

        test('should adjust Y position based on pitch (spectral_centroid and dominant_frequency)', () => {
            // High pitch should move Y up (decrease Y value)
            let highPitchHit = { drum_category: 'snare', drum_type: 'closed_band', spectral_centroid: 7000, dominant_frequency: 8000 };
            let yPosHigh = tracker.getYPosition(highPitchHit);

            expect(yPosHigh).toBeCloseTo(0.47, 2);

            // Low pitch should move Y down (increase Y value)
            let lowPitchHit = { drum_category: 'snare', drum_type: 'closed_band', spectral_centroid: 100, dominant_frequency: 50 };
            let yPosLow = tracker.getYPosition(lowPitchHit);

            expect(yPosLow).toBeCloseTo(0.64775, 2);

            expect(yPosLow).toBeGreaterThan(yPosHigh);
        });

        test('should cap Y position between 0 and .95', () => {
            let hitVeryHighPitch = { drum_category: 'cymbal', drum_type: 'crash', spectral_centroid: 10000, dominant_frequency: 10000 };
            expect(tracker.getYPosition(hitVeryHighPitch)).toBeCloseTo(0, 2);

            let hitVeryLowPitch = { drum_category: 'kick', drum_type: 'bass', spectral_centroid: 1, dominant_frequency: 1 };
            expect(tracker.getYPosition(hitVeryLowPitch)).toBeCloseTo(.95, 2);
        });
    });

    describe('getColor', () => {
        let tracker;
        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
        });

        test('should generate HSL color based on spectral properties', () => {
            // Hit with low rolloff (reddish hue) and low flux (low saturation)
            let hit1 = { spectral_rolloff: 500, spectral_flux: 0.1 };
            let color1 = tracker.getColor(hit1);
            // hue = 0, sat = 70 + 30 * (0.1/1) = 73, light = 60
            expect(color1).toBe('hsl(0, 73%, 60%)');

            // Hit with mid rolloff (bluish-green hue) and mid flux (mid saturation)
            let hit2 = { spectral_rolloff: 4000, spectral_flux: 0.5 };
            let color2 = tracker.getColor(hit2);
            // hue = 240 * ((4000-500)/7500) = 240 * (3500/7500) = 240 * 0.4666... = 112
            // sat = 70 + 30 * (0.5/1) = 85, light = 60
            expect(color2).toBe('hsl(112, 85%, 60%)');

            // Hit with high rolloff (bluish hue) and high flux (high saturation)
            let hit3 = { spectral_rolloff: 8000, spectral_flux: 1.0 };
            let color3 = tracker.getColor(hit3);
            // hue = 240 * ((8000-500)/7500) = 240 * (7500/7500) = 240
            // sat = 70 + 30 * (1.0/1) = 100, light = 60
            expect(color3).toBe('hsl(240, 100%, 60%)');
        });

        test('should cap hue, saturation values', () => {
            let hitExtreme = { spectral_rolloff: 10000, spectral_flux: 2.0 };
            let colorExtreme = tracker.getColor(hitExtreme);
            expect(colorExtreme).toBe('hsl(240, 100%, 60%)'); // Max values
        });
    });

    describe('getSize', () => {
        let tracker;
        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            tracker.config.maxSize = 100; // Set a known max size for easier calculation
        });

        test('should calculate size based on relative volume and decay', () => {
            const hit = { onset_time: 1.0, duration: 0.5, relative_volume: 0.8 }; // max size = 100 * 0.8 = 80

            // At onset time, full size
            expect(tracker.getSize(hit, 1.0)).toBeCloseTo(80);

            // Halfway through duration, 50% decay for hits with duration > 0.15
            // Here duration is 0.5, so decay applies
            expect(tracker.getSize(hit, 1.25)).toBeCloseTo(80 * (1 - (0.25 / 0.5))); // 80 * 0.5 = 40

            // At end of duration, size should be 0
            expect(tracker.getSize(hit, 1.5)).toBeCloseTo(80 * (1 - (0.5 / 0.5))); // 80 * 0 = 0

            // After duration, size should remain 0 (or very close)
            expect(tracker.getSize(hit, 2.0)).toBeCloseTo(0);
        });

        test('should not apply decay for hits with very short duration', () => {
            const shortHit = { onset_time: 1.0, duration: 0.1, relative_volume: 0.8 };
            // Decay threshold is 0.15, so decayFactor should remain 1.0 for this hit
            expect(tracker.getSize(shortHit, 1.05)).toBeCloseTo(100 * 0.8 * 1.0);
        });
    });

    describe('getShape', () => {
        let tracker;
        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
        });

        test('should return correct shape for specific drum types', () => {
            expect(tracker.getShape('kick')).toBe('hexagon');
            expect(tracker.getShape('snare')).toBe('circle');
            expect(tracker.getShape('cowbell')).toBe('rectangle');
            expect(tracker.getShape('other')).toBe('square');
        });

        test('should return grouped shape for tom types', () => {
            expect(tracker.getShape('tom')).toBe('pentagon');
        });

        test('should return grouped shape for hihat types', () => {
            expect(tracker.getShape('hihat')).toBe('triangle');
        });

        test('should return grouped shape for cymbal types', () => {
            expect(tracker.getShape('cymbal', 'ride')).toBe('trapezoid');
            expect(tracker.getShape('cymbal', 'crash')).toBe('trapezoid');
            expect(tracker.getShape('cymbal', 'unknown')).toBe('trapezoid');
        });

        test('should return other/unknown for unrecognized types', () => {
            expect(tracker.getShape('xylophone')).toBe('square');
        });
    });

    describe('drawShape', () => {
        let tracker;
        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            jest.clearAllMocks(); // Clear ctx mocks from constructor
        });

        const testShapeDrawing = (shape, expectedMethod) => {
            const x = 100, y = 100, size = 50, color = 'red';
            const radius = size / 2;

            // Clear specific ctx methods before each drawShape call
            // in this helper. This is crucial because drawShape calls
            // multiple ctx methods, and they need to be fresh for
            // each shape test.
            ctx.clearRect.mockClear();
            ctx.beginPath.mockClear();
            ctx.moveTo.mockClear();
            ctx.lineTo.mockClear();
            ctx.stroke.mockClear();
            ctx.fill.mockClear();
            ctx.arc.mockClear();
            ctx.rect.mockClear();
            ctx.closePath.mockClear();
            ctx.save.mockClear();
            ctx.restore.mockClear();

            tracker.drawShape(x, y, size, shape, color);

            expect(ctx.save).toHaveBeenCalled();

            expect(ctx.beginPath).toHaveBeenCalled();
            expect(ctx[expectedMethod]).toHaveBeenCalled(); // Check specific drawing method
            expect(ctx.closePath).toHaveBeenCalled();
            expect(ctx.fill).toHaveBeenCalled();
            expect(ctx.stroke).toHaveBeenCalled();
            expect(ctx.restore).toHaveBeenCalled();
        };

        test('should draw a circle', () => {
            testShapeDrawing('circle', 'arc');
            expect(ctx.arc).toHaveBeenCalledWith(100, 100, 25, 0, 2 * Math.PI);
        });

        test('should draw a square', () => {
            testShapeDrawing('square', 'rect');
            expect(ctx.rect).toHaveBeenCalledWith(100 - 25, 100 - 25, 50, 50);
        });

        test('should draw a triangle', () => {
            testShapeDrawing('triangle', 'moveTo'); // Triangle uses moveTo and lineTo
            expect(ctx.lineTo).toHaveBeenCalledTimes(2); // Two lines after initial moveTo
        });

        test('should draw a hexagon', () => {
            testShapeDrawing('hexagon', 'moveTo'); // Triangle uses polygon helper
            expect(ctx.lineTo).toHaveBeenCalledTimes(6); // 6 sides
        });

        test('should draw a pentagon', () => {
            testShapeDrawing('pentagon', 'moveTo'); // Pentagon uses polygon helper
            expect(ctx.lineTo).toHaveBeenCalledTimes(5); // 5 sides
        });

        test('should draw a trapezoid', () => {
            testShapeDrawing('trapezoid', 'moveTo'); // Trapezoid uses moveTo and lineTo
            expect(ctx.lineTo).toHaveBeenCalledTimes(3);
        });

        test('should draw a rectangle', () => {
            testShapeDrawing('rectangle', 'rect');
            expect(ctx.rect).toHaveBeenCalledWith(100 - 25, 100 - 25 / 2, 50, 25);
        });
    });

    describe('drawLegend', () => {
        let tracker;
        let drawShapeSpy;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            jest.clearAllMocks();
            drawShapeSpy = jest.spyOn(tracker, 'drawShape');
        });

        afterEach(() => {
            drawShapeSpy.mockRestore();
        });

        test('should draw legend background and title', () => {
            tracker.drawLegend();

            expect(ctx.strokeStyle).toBe('rgba(255, 255, 255, 0.9)');
            expect(ctx.lineWidth).toBe(1);
            expect(ctx.beginPath).toHaveBeenCalled();
            expect(ctx.roundRect).toHaveBeenCalled();
            expect(ctx.fill).toHaveBeenCalled();
            expect(ctx.stroke).toHaveBeenCalled();

            expect(ctx.fillStyle).toBe('#FFFFFF');

            expect(ctx.fillText).toHaveBeenCalledWith('Instrument Key', expect.any(Number), expect.any(Number));
        });

        test('should draw each legend item with its shape and text', () => {
            const itemsCount = Object.keys(tracker.config.shapes).length;
            const drawShapeSpy = jest.spyOn(tracker, 'drawShape');

            tracker.drawLegend();

            expect(drawShapeSpy).toHaveBeenCalledTimes(itemsCount);
            expect(drawShapeSpy).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), 15, expect.any(String), 'hsl(0, 0%, 80)', 1);

            expect(ctx.fillText).toHaveBeenCalledTimes(itemsCount + 1); // +1 for title
            expect(ctx.font).toContain('11px sans-serif');
            expect(ctx.textAlign).toBe('left');
        });
    });

    describe('Tooltip Handling', () => {
        let tracker;
        let drawTooltipSpy;

        beforeEach(() => {
            tracker = new DrumTracker(canvas, mockDrumAnalysis);
            drawTooltipSpy = jest.spyOn(tracker, 'drawTooltip');
            jest.clearAllMocks(); // Clear ctx mocks from constructor
            drawTooltipSpy.mockClear();
        });

        test('handleMouseMove should set hoveredHit using the accessor if mouse is over a visible hit', () => {
            tracker.lastTime = 0.55; // Ensure hit is visible
            mockHitsAccessor.getElementAtIndex.mockReturnValue(mockHits[0]);

            // Simulate mouse being directly over the first hit's calculated
            // position
            const hitX = tracker.getYPosition(mockHits[0]) * canvas.getBoundingClientRect().height;
            const hitY = tracker.config.staticXPosition * canvas.getBoundingClientRect().width;

            // Simulate mouse movement over the snare drum
            const mockEvent = {
                clientX: hitX,
                clientY: hitY,
            };
            tracker.handleMouseMove(mockEvent);

            expect(tracker.hoveredHit).not.toBeNull();
            expect(tracker.hoveredHit.drum_category).toBe('snare');
        });

        test('handleMouseMove should clear hoveredHit if mouse is not over any visible hit', () => {
            tracker.hoveredHit = { ...mockHits[0] }; // Set a hovered hit initially
            tracker.lastTime = 0.0; // No hits visible at this time
            mockHitsAccessor.getElementAtIndex.mockReturnValue(null);

            const mockEvent = { clientX: 10, clientY: 10 }; // Any position
            tracker.handleMouseMove(mockEvent);

            expect(tracker.hoveredHit).toBeNull();
        });

        test('drawTooltip should draw tooltip if hoveredHit is set', () => {
            tracker.hoveredHit = {
                drum_category: 'snare',
                category_confidence: 0.955,
                drum_type: 'closed_band',
                type_confidence: 0.881,
                qualifier: 'rimshot',
                qualifier_confidence: 0.912,
                lastX: 150,
                lastY: 200
            };

            tracker.drawTooltip();

            const startX = tracker.hoveredHit.lastX + 15 + 10;
            const startY = tracker.hoveredHit.lastY + 20;

            expect(ctx.fillRect).toHaveBeenCalled();
            expect(ctx.fillStyle).toBe('white');
            expect(ctx.fillText).toHaveBeenCalledWith('Category: snare', startX, startY);
            expect(ctx.fillText).toHaveBeenCalledWith('  └ Confidence: 95.5%', startX, startY + 18);
            expect(ctx.fillText).toHaveBeenCalledWith('Type: closed band', startX, startY + 36); // Expect "closed band" (with space)
            expect(ctx.fillText).toHaveBeenCalledWith('  └ Confidence: 88.1%', startX, startY + 54);
            expect(ctx.fillText).toHaveBeenCalledWith('Qualifier: rimshot', startX, startY + 72); // Check for the qualifier line
            expect(ctx.fillText).toHaveBeenCalledWith('  └ Confidence: 91.2%', startX, startY + 90);
        });

        test('drawTooltip should not draw if hoveredHit is null', () => {
            tracker.hoveredHit = null;
            tracker.drawTooltip();
            expect(ctx.fillRect).not.toHaveBeenCalled();
            expect(ctx.fillText).not.toHaveBeenCalled();
        });

        test('handleMouseOut should clear hoveredHit', () => {
            tracker.hoveredHit = { ...mockHits[0] };
            tracker.handleMouseOut();
            expect(tracker.hoveredHit).toBeNull();
        });
    });
});
