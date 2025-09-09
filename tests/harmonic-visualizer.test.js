import { jest } from '@jest/globals';

jest.unstable_mockModule('../www/js/player/TimeSeriesAccessor.js', () => ({
    TimeSeriesAccessor: jest.fn().mockImplementation(() => {
        return {
            ensureDataForTime: jest.fn(),
            getElementAtTime: jest.fn(),
        };
    }),
}));

const { HarmonicVisualizer } = await import('../www/js/player/harmonic-visualizer.js');
const { TimeSeriesAccessor: MockAccessor } = await import('../www/js/player/TimeSeriesAccessor.js');

describe('HarmonicVisualizer', () => {
    // Mock the canvas and context before each test
    let mockCanvas, mockCtx, mockAccessorInstance, mockData;

    beforeEach(() => {
        document.body.innerHTML = '<div id="frequency-axis"></div>';
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
                bezierCurveTo: jest.fn(),
                translate: jest.fn(),
                rotate: jest.fn(),
            }),
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
        expect(mockAccessorInstance.ensureDataForTime).toHaveBeenCalledWith(0);
        expect(visualizer.instrumentOrder).toEqual(['vocals', 'bass']);
        expect(mockCanvas.getContext).toHaveBeenCalledWith('2d');
        expect(global.ResizeObserver).toHaveBeenCalled();
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

    test('drawInstrumentColumn should get data from accessor, use stem-specific tempo and draws blob with flatness and mfccs', () => {
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

        const expectedBlobWidth = visualizer.mapValueToBlobWidth(mockTimeSlice.rms, columnWidth * visualizer.config.maxBlobWidthRatio);
        expect(visualizer.drawChromaHoops).toHaveBeenCalledWith(
            expect.any(Number), // centerX
            expect.any(Number), // centerY
            expectedBlobWidth, // Check that blobWidth is passed correctly
            mockTimeSlice.chroma_stft
        );

        expect(mockAccessorInstance.getElementAtTime).toHaveBeenCalledWith(2);
        expect(visualizer.drawTempoLines).toHaveBeenCalledWith(columnX, columnWidth, 90);
        expect(visualizer.drawBlob).toHaveBeenCalledWith(
            expect.any(Number), // x
            expect.any(Number), // radius
            expect.any(String), // color
            150, // f0 at time 2
            1200, // centroid at time 2
            600, // bandwidth at time 2
            0.8, // flatness at time 2
            [0.2, 0.5, 0.4], // spectrogram at time 2
            [100, 200, 300], // frequencies
            expect.any(Array) // MFCCs
        );
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

    test('drawInstrumentColumn should not draw blob if timeSlice is null', () => {
        mockAccessorInstance.getElementAtTime.mockReturnValue(null);
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        const drawBlobSpy = jest.spyOn(visualizer, 'drawBlob');
        const drawBlobSimpleSpy = jest.spyOn(visualizer, 'drawBlobSimple');

        visualizer.drawInstrumentColumn(100, 200, 'vocals', mockData.stem_analyses.vocals);

        expect(drawBlobSpy).not.toHaveBeenCalled();
        expect(drawBlobSimpleSpy).not.toHaveBeenCalled();
    });

    test('createDynamicPath uses spectrogram data to draw a non-jagged path', () => {
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

    test('createDynamicPath uses spectrogram data to draw a jagged path for high flatness', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawMfccTexture = jest.fn();
        const spectrogram = [0.1, 0.5, 0.2, 0.7];
        const frequencies = [0, 1000, 2000, 3000];
        const radius = 50;
        const flatness = 0.9;
        visualizer.createDynamicPath(400, spectrogram, frequencies, radius, flatness);
        expect(mockCtx.moveTo).toHaveBeenCalled();
        expect(mockCtx.lineTo).toHaveBeenCalledTimes(spectrogram.length * 2);
    });

    test('drawMfccTexture draws polygons based on MFCCs', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);

        // .getElement() must be used to retrieve the data from the accessor
        const mfccsSlice = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];
        visualizer.drawMfccTexture(400, 300, 50, mfccsSlice);

        expect(mockCtx.save).toHaveBeenCalled();
        expect(mockCtx.clip).toHaveBeenCalled();
        expect(mockCtx.beginPath).toHaveBeenCalled();
        expect(mockCtx.fill).toHaveBeenCalled();
        expect(mockCtx.restore).toHaveBeenCalled();
    });

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
    })
});
