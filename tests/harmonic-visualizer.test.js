import { jest } from '@jest/globals';

jest.unstable_mockModule('../www/js/player/TimeSeriesAccessor.js', () => ({
    TimeSeriesAccessor: jest.fn().mockImplementation(() => {
        return {
            ensureDataForTime: jest.fn(),
            getElementAtTime: jest.fn(),
            isDataAvailableForTime: jest.fn().mockReturnValue(true),
        };
    }),
}));

const { HarmonicVisualizer } = await import('../www/js/player/harmonic-visualizer.js');
const { TimeSeriesAccessor: MockAccessor } = await import('../www/js/player/TimeSeriesAccessor.js');

describe('HarmonicVisualizer', () => {
    // Mock the canvas and context before each test
    let mockCanvas, mockCtx, mockAccessorInstance, mockData;

    beforeEach(() => {
        document.body.innerHTML = '<div id="frequency-axis"></div><div id="chroma-key"></div>';
        mockCanvas = {
            width: 800,
            height: 600,
            offsetWidth: 801,
            offsetHeight: 601,
            getContext: jest.fn().mockReturnValue({
                clearRect: jest.fn(),
                beginPath: jest.fn(),
                arc: jest.fn(),
                lineTo: jest.fn(),
                moveTo: jest.fn(),
                closePath: jest.fn(),
                fill: jest.fn(),
                stroke: jest.fn(),
                fillRect: jest.fn(),
                save: jest.fn(),
                restore: jest.fn(),
                clip: jest.fn(),
                rect: jest.fn(),
                bezierCurveTo: jest.fn(),
                translate: jest.fn(),
                rotate: jest.fn(),
                ellipse: jest.fn(),
                fillText: jest.fn(),
            }),
            // Mock addEventListener for canvas resize observer
            addEventListener: jest.fn(),
        };

        // Mock ResizeObserver
        global.ResizeObserver = jest.fn(cb => ({
            observe: jest.fn(() => cb()), // Immediately invoke callback for testing
            unobserve: jest.fn(),
            disconnect: jest.fn(),
        }));

        mockCtx = mockCanvas.getContext();
        mockAccessorInstance = new MockAccessor();
        MockAccessor.mockClear();

        mockData = {
            full_track_analysis: {
                duration: 10,
                tempo: 120,
            },
            stem_analyses: {
                vocals: {
                    stream_accessor: mockAccessorInstance,
                    temporal_features: {
                        onsets: [1.0],
                        beats: [1.0, 1.5, 2.0],
                        tempo: 100
                    }
                },
                bass: {
                    stream_accessor: mockAccessorInstance,
                    temporal_features: {
                        onsets: [1.5, 3.5],
                        beats: [0.5, 1.0, 1.5, 2.0],
                        tempo: 90, // Unique tempo for this stem
                    }
                }
            }
        };
    });


    test('constructor should create and use stream_accessor from input data, and setup resize observer', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        expect(visualizer.canvas).toBe(mockCanvas);

        expect(visualizer.streamAccessors.bass).toBe(mockAccessorInstance);

        expect(visualizer.instrumentOrder).toEqual(['vocals', 'bass']);
        expect(mockCanvas.getContext).toHaveBeenCalledWith('2d');
        expect(global.ResizeObserver).toHaveBeenCalled();
    });

    test('constructor should setup observer but NOT draw Immediately if dimensions are 0', () => {
        // Simulate hidden canvas
        mockCanvas.offsetWidth = 0;
        mockCanvas.offsetHeight = 0;
        mockCanvas.width = 0;
        mockCanvas.height = 0;

        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const updateSpy = jest.spyOn(visualizer, 'update');

        // Trigger resize (via observer) but still 0
        visualizer.resize();

        expect(updateSpy).not.toHaveBeenCalled();

        // Now give it size
        mockCanvas.offsetWidth = 800;
        mockCanvas.offsetHeight = 600;
        visualizer.resize();

        expect(updateSpy).toHaveBeenCalled();
    });

    test('resize should update canvas dimensions and redraw', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const updateSpy = jest.spyOn(visualizer, 'update');

        visualizer.resize();

        expect(mockCanvas.width).toBe(801);
        expect(mockCanvas.height).toBe(601);
        expect(updateSpy).toHaveBeenCalled();
    });

    test('update draws columns for all active instruments', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawInstrumentColumn = jest.fn();
        visualizer.update(2.5);
        expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 801, 601);
        expect(visualizer.drawInstrumentColumn).toHaveBeenCalledTimes(2);
    });

    test('update should not draw if no active instruments', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.instrumentOrder = [];
        const drawColumnSpy = jest.spyOn(visualizer, 'drawInstrumentColumn');
        visualizer.update(1.0);
        expect(drawColumnSpy).not.toHaveBeenCalled();
    });

    test('update should retry drawing axes if container is empty', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const axisContainer = document.getElementById('frequency-axis');

        // Manually clear it
        axisContainer.innerHTML = '';

        visualizer.update(0.1);

        // Should have re-populated
        expect(axisContainer.childElementCount).toBeGreaterThan(0);
    });

    test('drawInstrumentColumn should get data from accessor, use stem-specific tempo and draw blob with flatness and mfccs', () => {
        const mockTimeSlice = {
            f0_data: 150, rms: 0.5,
            spectral_centroid: 1200,
            spectral_bandwidth: 600,
            spectral_flatness: 0.8,
            spectrogram: [0.2, 0.5, 0.4],
            frequencies: [100, 200, 300],
            mfccs: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
        };
        mockAccessorInstance.getElementAtTime.mockReturnValue(mockTimeSlice);

        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawTempoLines = jest.fn();
        visualizer.drawBlob = jest.fn();
        visualizer.drawChromaHoops = jest.fn();
        visualizer.drawTemporalEffects = jest.fn();

        const columnX = 100;
        const columnWidth = 200;
        visualizer.currentTime = 2;

        visualizer.drawInstrumentColumn(columnX, columnWidth, 'bass', mockData.stem_analyses.bass);

        const expectedBlobWidth = visualizer.mapValueToBlobWidth(mockTimeSlice.rms, columnWidth / 2);

        // The color passed should use mapValueToLightness
        const expectedHue = visualizer.mapValueToHue(mockTimeSlice.spectral_rolloff, visualizer.config.spectralRolloffMax);
        const expectedSaturation = visualizer.mapValueToSaturation(mockTimeSlice.spectral_bandwidth, visualizer.config.spectralBandwidthMax);
        const expectedLightness = visualizer.mapValueToLightness(mockTimeSlice.spectral_centroid, 10000);
        const expectedColor = `hsla(${expectedHue}, ${expectedSaturation}%, ${expectedLightness}%, 0.8)`;

        expect(visualizer.drawChromaHoops).toHaveBeenCalledWith(
            expect.any(Number), // centerX
            expect.any(Number), // centerY
            columnWidth, // Check that columnWidth is passed correctly
            mockTimeSlice.chroma_stft
        );

        expect(mockAccessorInstance.getElementAtTime).toHaveBeenCalledWith(2);
        expect(visualizer.drawTempoLines).toHaveBeenCalledWith(columnX, columnWidth, 90);
        expect(visualizer.drawBlob).toHaveBeenCalledWith(
            expect.any(Number), // x
            expect.any(Number), // radius
            expectedColor, // color
            150, // f0 at time 2
            1200, // centroid at time 2
            600, // bandwidth at time 2
            0.8, // flatness at time 2
            [0.2, 0.5, 0.4], // spectrogram at time 2
            [100, 200, 300], // frequencies
            expect.any(Array) // MFCCs
        );
    });

    test('drawInstrumentColumn should correctly draw blob as touching the borders of its column at max width/volume', () => {
        // When multiple instruments are at max volume it is like not much
        // else can cut through the noise, the visual should be similar.
        // If an instrument is at its max volume, it should practically touch
        // the borders of its column. If two adjacent instruments are at max
        // volume, their blobs should practically touch one another.
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        // Set rmsMax to 1 for predictable normalization
        visualizer.config.rmsMax = 1.0;
        const mockTimeSlice = {
            rms: 1.0, f0_data: 150, spectrogram: [1],
            frequencies: [150, 1000], mfccs: []
        };
        mockAccessorInstance.getElementAtTime.mockReturnValue(mockTimeSlice);
        const drawBlobSpy = jest.spyOn(visualizer, 'drawBlob');
        const drawMfccSpy = jest.spyOn(visualizer, 'drawMfccTexture');

        // With 2 instruments, each column is roughly half the canvas width
        const columnWidth = (mockCanvas.width - visualizer.config.columnGap) / 2;
        const expectedRadius = columnWidth / 2;
        const xPos = columnWidth / 2; // For the first column

        const expectedLightness = visualizer.mapValueToLightness(undefined, 10000); // centroid is undefined here, will be treated as NaN or defaulting, might need to adjust test to pass a centroid
        const expectedColor = `hsla(${visualizer.mapValueToHue(undefined, visualizer.config.spectralRolloffMax)}, ${visualizer.mapValueToSaturation(undefined, visualizer.config.spectralBandwidthMax)}%, ${expectedLightness}%, 0.8)`;

        visualizer.update(1.0); // Trigger draw

        const normalizedMinY = visualizer.mapValueToLogNormalizedY(1000); // Highest frequency
        const expectedMinY = mockCanvas.height - (normalizedMinY * mockCanvas.height);

        const normalizedMaxY = visualizer.mapValueToLogNormalizedY(150); // Lowest frequency
        const expectedMaxY = mockCanvas.height - (normalizedMaxY * mockCanvas.height);

        const expectedMinX = xPos - expectedRadius;
        const expectedMaxX = xPos + expectedRadius;

        // We expect drawBlob to be called with a radius that is half the
        // column width
        expect(drawBlobSpy).toHaveBeenCalledWith(
            expect.any(Number),
            columnWidth / 2, // The radius should be half the column width
            expectedColor,
            expect.any(Number),
            undefined, // centroid
            undefined, // bandwidth
            undefined, // flatness
            expect.any(Array),
            expect.any(Array),
            expect.any(Array)
        );

        // We expect drawMfccTexture to be called with bounds instead of center/radius
        expect(drawMfccSpy).toHaveBeenCalledWith(
            expectedMinY,
            expectedMaxY,
            expectedMinX,
            expectedMaxX,
            expect.any(Array)
        );
    });

    test('mapValueToLightness properly maps spectral centroid to lightness percentage', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.config.baseLightness = 50;

        // 0 centroid should yield baseLightness * 0 + 30 = 30
        expect(visualizer.mapValueToLightness(0, 10000)).toBe(30);
        // max centroid should yield baseLightness * 1 + 30 = 90
        expect(visualizer.mapValueToLightness(10000, 10000)).toBe(80);
        // half centroid should yield baseLightness * 0.5 + 30 = 55
        expect(visualizer.mapValueToLightness(5000, 10000)).toBe(55);
        // over max should cap at 1
        expect(visualizer.mapValueToLightness(20000, 10000)).toBe(80);
    });

    test('drawBlobSimple is called when f0 is null', () => {
        const mockTimeSlice = {
            f0_data: null, rms: 0.5,
            spectral_centroid: 1200,
            spectral_bandwidth: 600,
            spectral_flatness: 0.8,
            spectrogram: [0.2, 0.5, 0.4],
            frequencies: [100, 200, 300],
            mfccs: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
        };
        mockAccessorInstance.getElementAtTime.mockReturnValue(mockTimeSlice);

        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawBlob = jest.fn();
        visualizer.drawBlobSimple = jest.fn();

        const columnX = 100;
        const columnWidth = 200;
        visualizer.currentTime = 1;
        visualizer.drawInstrumentColumn(columnX, columnWidth, 'bass', mockData.stem_analyses.bass);

        expect(visualizer.drawBlob).not.toHaveBeenCalled();
        expect(visualizer.drawBlobSimple).toHaveBeenCalled();
    });

    test('drawInstrumentColumn should not draw blob or chroma hoops if timeSlice is null', () => {
        mockAccessorInstance.getElementAtTime.mockReturnValue(null);
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const drawBlobSpy = jest.spyOn(visualizer, 'drawBlob');
        const drawBlobSimpleSpy = jest.spyOn(visualizer, 'drawBlobSimple');

        visualizer.drawInstrumentColumn(100, 200, 'vocals', mockData.stem_analyses.vocals);

        expect(drawBlobSpy).not.toHaveBeenCalled();
        expect(drawBlobSimpleSpy).not.toHaveBeenCalled();
    });

    test('createDynamicPath uses spectrogram data to draw a smooth path for low spectral flatness', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawMfccTexture = jest.fn(); // Mock this to isolate the lineTo calls
        const spectrogram = [0.1, 0.5, 0.2, 0.7];
        const frequencies = [0, 1000, 2000, 3000];
        const radius = 50;
        const flatness = 0.1;
        visualizer.createDynamicPath(400, spectrogram, frequencies, radius, flatness);
        expect(mockCtx.moveTo).toHaveBeenCalled();
        expect(mockCtx.lineTo).toHaveBeenCalledTimes(spectrogram.length * 2);
    });

    test('createDynamicPath should draw an increasingly fuzzy/jagged path as spectral flatness increases', () => {
        // As the quality of the instrument's sound becomes noisier or more
        // distorted, the line that defines the blob should become
        // increasingly fuzzy and jagged so 0 is a smooth line, and 1 is a
        // deep, jagged path
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const spectrogram = [0.1, 0.5, 0.2, 0.7];
        const frequencies = [100, 1000, 2000, 3000, 4000, 5000];
        const radius = 50;

        // Determine the amount of lines called when smooth for comparison
        visualizer.createDynamicPath(400, spectrogram, frequencies, radius, 0.1);
        const smoothCallCount = mockCtx.lineTo.mock.calls.length;

        // High flatness should subdivide lines and add jitter, resulting in
        // more calls
        mockCtx.lineTo.mockClear();
        visualizer.createDynamicPath(400, spectrogram, frequencies, radius, 0.9);
        const jaggedCallCount = mockCtx.lineTo.mock.calls.length;

        // Expect significantly more lineTo calls for a jagged line due to subdivision
        expect(jaggedCallCount).toBeGreaterThan(smoothCallCount * 2);
    });

    test('drawMfccTexture generates a pattern of various shapes, lines and curves based on MFCCs and tessellates it on the blob', () => {
        // This test does not properly assert the tessellations. While shapes
        // are being drawn within the blob, they do not spread evenly
        // throughout the blob; some are in small parts of the blob so the
        // shapes cannot be seen. This test needs to assert that unique shapes
        // are created and also assert a mosaic of those unique shapes is
        // created, and finally assert the pattern tessellates across the
        // entirety of the blob.
        // The shapes can all be the same size or varying sizes, whatever is
        // easiest.
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const mfccs = [10, -5, 8, -2, 5, 1, 4, 6, -9, 3, -1, 7, 2, 14, -0.55, 4, -2, -3, -2.5, 0.9991];
        const radius = 100;
        const x = 400;
        const centerY = 300;
        // Mock the frequencies to define the blob's vertical extent
        const frequencies = [100, 8000]; // From 100Hz, 8000Hz

        // Define the blob's approx bounding box for our test
        const minY = centerY - radius;
        const maxY = centerY + radius;
        const minX = x - radius;
        const maxX = x + radius;

        // Spy on `beginPath` as it's called once per shape
        const beginPathSpy = jest.spyOn(mockCtx, 'beginPath');

        const moveToSpy = jest.spyOn(mockCtx, 'moveTo');

        // Execute the function
        visualizer.drawMfccTexture(minY, maxY, minX, maxX, mfccs, frequencies);

        // Make sure it drew some shapes
        expect(beginPathSpy.mock.calls.length).toBeGreaterThan(0);

        // Assert that the grid cells drawn are within our bounds
        // (with a small margin of error for the cell size)
        const cellSize = Math.max(40, mockCanvas.height / 15);
        for (const call of moveToSpy.mock.calls) {
            const [shapeX, shapeY] = call;
            expect(shapeX).toBeGreaterThanOrEqual(minX - cellSize);
            expect(shapeX).toBeLessThanOrEqual(maxX + cellSize);
            expect(shapeY).toBeGreaterThanOrEqual(minY - cellSize);
            expect(shapeY).toBeLessThanOrEqual(maxY + cellSize);
        }
    });

    test('drawMfccTexture should calculate vertical bounds strictly using the physical radius, not frequency constraints', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const mfccs = [10, -5, 8, -2, 5, 1, 4, 6, -9, 3, -1, 7, 2, 14, -0.55, 4, -2, -3, -2.5, 0.9991];
        const radius = 100;
        const x = 400;
        const centerY = 300;

        const minY = centerY - radius;
        const maxY = centerY + radius;
        const minX = x - radius;
        const maxX = x + radius;

        // Pass high frequencies that would normally squash the texture upwards
        const highFrequencies = [6000, 8000];

        let minCellY = Infinity;
        let maxCellY = -Infinity;

        // Spy on moveTo to intercept the physical Y coordinates being drawn
        jest.spyOn(mockCtx, 'moveTo').mockImplementation((px, py) => {
            if (py < minCellY) minCellY = py;
            if (py > maxCellY) maxCellY = py;
        });

        visualizer.drawMfccTexture(minY, maxY, minX, maxX, mfccs, highFrequencies);

        // The texture should span the physical limits of the blob
        // (minY to maxY) regardless of the highFrequencies array passed.
        expect(minCellY).toBeLessThan(minY + 50); // Allowing for grid cell margins
        expect(maxCellY).toBeGreaterThan(maxY - 50); // Allowing for grid cell margins
    })

    test('drawTemporalEffects should draw onset flash within decay window', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        // Set current time to be 50ms after the first onset (at 1.0s)
        visualizer.currentTime = 1.05;

        visualizer.drawTemporalEffects(100, 200, mockData.stem_analyses.vocals, 1050);

        // Expect fillRect to be called for the onset
        expect(mockCtx.fillRect).toHaveBeenCalled();
    });

    test('drawTemporalEffects should draw beat square within decay window', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        // Set current time to be 100ms after the first beat (at 0.5s)
        visualizer.currentTime = 0.6;

        visualizer.drawTemporalEffects(100, 200, mockData.stem_analyses.bass, 600);

        // Expect fillRect to be called for the beat
        expect(mockCtx.fillRect).toHaveBeenCalled();
    });

    test('drawTemporalEffects should not draw if outside decay window', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.currentTime = 5.0;

        visualizer.drawTemporalEffects(100, 200, mockData.stem_analyses.vocals, 5000);

        expect(mockCtx.fillRect).not.toHaveBeenCalled();
    });

    test('drawTempoLines should keep each instruments tempo lines contained within its own instrumentColumn', () => {
        // It appears that sometimes tempo lines start to overlap one another
        // which can be visually confusing, jarring and unappealing
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        mockAccessorInstance.getElementAtTime.mockReturnValue({ rms: 0.5, frequencies: [100, 200] });

        // Spy on the context's clip and rect methods
        const clipSpy = jest.spyOn(mockCtx, 'clip');
        const rectSpy = jest.spyOn(mockCtx, 'rect');

        visualizer.update(0.1); // Update at a time that gives a scroll offset

        // Verify the clipping rectangle for the first column
        const columnWidth = (mockCanvas.width - visualizer.config.columnGap) / 2;
        expect(rectSpy).toHaveBeenCalledWith(0, 0, columnWidth, mockCanvas.height);

        // Verify the clipping rectangle for the second column
        const columnX = columnWidth + visualizer.config.columnGap;
        expect(rectSpy).toHaveBeenCalledWith(columnX, 0, columnWidth, mockCanvas.height);
    });

    test('drawChromaHoops should not draw hoop unless the timeSlice has a high enough chroma_stft value', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const chromaStft = [0.9, 0.05, 0.8, 0.0, 0.7, 0, 0, 0, 0.86, 0, 0, 0.1];
        const strokeSpy = jest.spyOn(mockCtx, 'stroke');

        visualizer.drawChromaHoops(100, 100, 200, chromaStft);

        // Should be called for 0.9 and 0.86 (2 times)
        // The current threshold is 90% of max value (0.9 * 0.9 = 0.81)
        expect(strokeSpy).toHaveBeenCalledTimes(2);
    });

    test('drawChromaHoops should draw hoops at a constant horizontal radius based on the column width', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const chromaStft = new Array(12).fill(0.8);
        const ellipseSpy = jest.spyOn(mockCtx, 'ellipse');

        // Call with two different blob widths but the same column width
        const columnWidth = 200;
        visualizer.drawChromaHoops(150, 300, columnWidth, chromaStft);

        // Expected horizontal radius is half the column width
        const expectedRadiusX = columnWidth / 2;

        // Check the arguments of the first call to ellipse
        const [, , radiusX, radiusY] = ellipseSpy.mock.calls[0];
        expect(radiusX).toBe(expectedRadiusX);
        expect(radiusY).toBe(8); // The fixed vertical radius

        // All 12 hoops should have the same horizontal radius
        ellipseSpy.mock.calls.forEach(callArgs => {
            expect(callArgs[2]).toBe(expectedRadiusX);
        });
    });

    test('drawChromaHoops should align with drawChromaKey so that the hoops have the same color and y-grid as the key', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawChromaKey();

        const chromaStft = new Array(12).fill(1.0);
        const ellipseSpy = jest.spyOn(mockCtx, 'ellipse');

        visualizer.drawChromaHoops(150, 300, 200, chromaStft);

        const keyContainer = document.getElementById('chroma-key');
        const labels = Array.from(keyContainer.children);

        expect(ellipseSpy).toHaveBeenCalledTimes(12);
        expect(labels.length).toBe(12);

        for (let i = 0; i < 12; i++) {
            const hoopY = ellipseSpy.mock.calls[i][1];
            const labelY = parseFloat(labels[i].style.top);

            expect(hoopY).toBeCloseTo(labelY, 5);

            // The browser standardizes hsl strings slightly, so we can just verify it is correctly assigned 
            // in the visualizer method if we wanted, but the key assertion here is the Y coordinate matches
        }
    });
    test('drawFrequencyAxis should correctly draw the axis in the same scale as the blob y-axes', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        // C4 frequency
        const c4Freq = 261.63;

        // Mock getElementAtTime to return data with C4 as the fundamental
        // frequency
        const mockTimeSlice = {
            f0_data: c4Freq, rms: 0.5, spectrogram: [1, 1],
            frequencies: [c4Freq, 8000], mfccs: [],
        };
        mockAccessorInstance.getElementAtTime.mockReturnValue(mockTimeSlice);
        const drawF0BallSpy = jest.spyOn(visualizer, 'drawF0Ball');

        // Trigger an update, which will call drawInstrumentColumn -> drawBlob -> drawF0Ball
        visualizer.update(1.0);

        // Get the Y position calculated by the drawing logic
        const f0BallY = drawF0BallSpy.mock.calls[0][1];

        // Now, get the Y position calculated for the axis label
        const axisContainer = document.getElementById('frequency-axis');
        const c4Label = Array.from(axisContainer.children).find(el => el.textContent === 'C4');
        const labelTopPercent = parseFloat(c4Label.style.top);
        const expectedLabelY = (labelTopPercent / 100) * mockCanvas.height;

        // They should be very close (allowing for minor floating point differences)
        expect(f0BallY).toBeCloseTo(expectedLabelY, 0);
    });

    test('drawFrequencyAxis should allow user to switch between C and Hz values', () => {
        // Make clicking the Frequency axis change the display from C2, C3,
        // C4, ... to the Hz equivalents. Clicking again reverts the display
        const axisContainer = document.getElementById('frequency-axis');
        // Attach a real event listener to the mocked element to test the logic
        const listeners = {};
        axisContainer.addEventListener = jest.fn((event, cb) => {
            listeners[event] = cb;
        });

        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);

        // Initial state: Should be note names
        let firstLabel = axisContainer.querySelector('div');
        expect(firstLabel.textContent).toBe('C2');

        // Simulate a click
        listeners.click();

        // After click: Should be Hz values
        firstLabel = axisContainer.querySelector('div');
        expect(firstLabel.textContent).toBe('65.41 Hz');

        // Simulate another click
        listeners.click();

        // After second click: Should be note names again
        firstLabel = axisContainer.querySelector('div');
        expect(firstLabel.textContent).toBe('C2');
    });

    test('drawFrequencyAxis labels (namely the Hz values) should stay within the canvas window', () => {
        // The C values stay in the canvas, but when the axis is clicked and
        // switched to Hz values, the thousand-place falls outside of the
        // canvas and gets clipped
        const axisContainer = document.getElementById('frequency-axis');
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);

        // Switch to Hz mode
        visualizer.axisDisplayMode = 'hz';
        visualizer.drawFrequencyAxis();

        // Check the style of one of the generated labels
        const highFreqLabel = Array.from(axisContainer.children).find(
            el => el.textContent.includes('4186.01')
        );

        expect(highFreqLabel.style.textAlign).toBe('right');
    });
});
