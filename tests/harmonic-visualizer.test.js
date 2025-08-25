import { HarmonicVisualizer } from '../www/js/player/harmonic-visualizer.js';
import { jest } from '@jest/globals';

// Mock the canvas and context before each test
let mockCanvas;
let mockCtx;

beforeEach(() => {
    mockCanvas = {
        width: 800,
        height: 600,
        offsetWidth: 800,
        offsetHeight: 600,
        getContext: jest.fn(() => mockCtx),
    };

    mockCtx = {
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
    };
});

describe('HarmonicVisualizer', () => {
    const mockData = {
        full_track_analysis: {
            duration: 10,
            tempo: 120,
            rms_overall: {
                times: [0, 5, 10],
                values: [0.1, 0.5, 0.2]
            }
        },
        stem_analyses: {
            bass: {
                f0_data: { times: [0, 2, 4], f0_values: [100, 150, 120] },
                spectral_features: {
                    times: [0, 2, 4],
                    frequencies: [0, 22050], // Simpler frequencies for testing
                    spectrogram: [
                        [0.1, 0.2, 0.3],
                        [0.2, 0.5, 0.4],
                        [0.1, 0.3, 0.2]
                    ],
                    spectral_centroid: [[1000], [1200], [1100]],
                    spectral_bandwidth: [[500], [600], [550]],
                    spectral_rolloff: [[2000], [3000], [2500]],
                    spectral_flatness: [[0.1], [0.8], [0.3]], // New flatness data
                    rms: [[0.1], [0.5], [0.2]],
                },
                timbral_features: {
                    mfccs: [
                        [0.5, -0.2, 0.1, -0.3, 0.2, -0.1, 0.0, 0.4, -0.2, 0.1, 0.3, 0.2, -0.1], // 13 MFCC values
                        [0.8, 0.1, 0.3, 0.5, -0.2, 0.1, 0.0, 0.2, -0.1, 0.3, 0.5, 0.4, -0.3],
                        [0.6, 0.0, -0.2, 0.1, 0.4, -0.3, 0.2, 0.1, 0.0, -0.1, -0.2, 0.3, 0.1]
                    ],
                    chroma_stft: [
                        [0.1, 0, 0, 0, 0, 0.5, 0, 0, 0, 0.7, 0, 0],
                        [0, 0, 0, 0.6, 0, 0, 0, 0, 0, 0, 0, 0],
                        [0.2, 0, 0, 0, 0, 0, 0, 0, 0, 0.4, 0, 0],
                    ]
                },
                temporal_features: {
                    onsets: [1.5, 3.5],
                    beats: [0.5, 1.0, 1.5, 2.0],
                    tempo: 90, // Unique tempo for this stem
                }
            }
        }
    };

    test('constructor initializes correctly', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        expect(visualizer.canvas).toBe(mockCanvas);
        expect(visualizer.data).toBe(mockData);
        expect(visualizer.instrumentOrder).toEqual(['bass']);
        expect(mockCanvas.getContext).toHaveBeenCalledWith('2d');
    });

    test('update draws columns for all active instruments', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawInstrumentColumn = jest.fn();
        visualizer.update(2.5);
        expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 800, 600);
        expect(visualizer.drawInstrumentColumn).toHaveBeenCalledTimes(1);
    });

    test('drawInstrumentColumn uses stem-specific tempo and draws blob with flatness and mfccs', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawTempoLines = jest.fn();
        visualizer.drawBlob = jest.fn();
        visualizer.drawChromaHalo = jest.fn();
        visualizer.drawTemporalEffects = jest.fn();

        const stemData = mockData.stem_analyses.bass;
        const columnX = 100;
        const columnWidth = 200;
        const currentTime = 2;
        visualizer.currentTime = currentTime;

        visualizer.drawInstrumentColumn(columnX, columnWidth, 'bass', stemData);

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
            expect.any(Array), // frequencies
            expect.any(Array) // MFCCs
        );
    });

    test('drawBlobSimple is called when f0 is null', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawBlob = jest.fn();
        visualizer.drawBlobSimple = jest.fn();

        const stemDataWithNoF0 = { ...mockData.stem_analyses.bass, f0_data: { times: [0, 2, 4], f0_values: [null, null, null] } };
        const columnX = 100;
        const columnWidth = 200;
        visualizer.currentTime = 1;
        visualizer.drawInstrumentColumn(columnX, columnWidth, 'bass', stemDataWithNoF0);

        expect(visualizer.drawBlob).not.toHaveBeenCalled();
        expect(visualizer.drawBlobSimple).toHaveBeenCalled();
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

    test('drawMfccTexture draws a polygon based on MFCCs', () => {
        const visualizer = new HarmonicVisualizer(mockCanvas, mockData);
        visualizer.drawMfccTexture(400, 300, 50, mockData.stem_analyses.bass.timbral_features.mfccs[0]);
        expect(mockCtx.save).toHaveBeenCalled();
        expect(mockCtx.clip).toHaveBeenCalled();
        expect(mockCtx.beginPath).toHaveBeenCalled();
        expect(mockCtx.fill).toHaveBeenCalled();
        expect(mockCtx.restore).toHaveBeenCalled();
    });
});
