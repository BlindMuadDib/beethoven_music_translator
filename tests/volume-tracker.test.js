import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import { VolumeTracker } from '../www/js/player/volume-tracker.js';

describe('VolumeTracker (Overall RMS)', () => {
    let canvas, ctx, overallRmsData;

    beforeEach(() => {
        // Set up the DOM with a canvas element
        document.body.innerHTML = '<canvas id="overall-volume-canvas" width="100" height="400"></canvas>';
        canvas = document.getElementById('overall-volume-canvas');
        ctx = canvas.getContext('2d');
        overallRmsData = [[0.0, 0.1], [0.1, 0.5], [0.2, 0.2]]; //min: 0.1, max: 0.5
    });

    test('constructor should initialize correctly', () => {
        const tracker = new VolumeTracker('overall-volume-canvas');
        expect(tracker.canvas).toBe(canvas);
        expect(tracker.normalizedData).toBeNull();
    });

    test('setData should process and normalize only overall_rms data', () => {
        const tracker = new VolumeTracker('overall-volume-canvas');
        tracker.setData(overallRmsData);

        expect(tracker.normalizedData).not.toBeNull();
        expect(tracker.normalizedData.values.length).toBe(3);
        // Normalization: 0.1 -> 0, 0.5 -> 1, 0.2 -> 0.25
        expect(tracker.normalizedData.values[0][1]).toBe(0);
        expect(tracker.normalizedData.values[1][1]).toBe(1);
        expect(tracker.normalizedData.values[2][1]).toBe(0.25);
    });

    test('update should call draw with the correct interpolated volume level', () => {
        const tracker = new VolumeTracker('overall-volume-canvas');
        tracker.setData(overallRmsData);
        const drawSpy = jest.spyOn(tracker, 'draw');

        tracker.update(0.15); // Time between 2nd and 3rd points

        expect(drawSpy).toHaveBeenCalled();
        const normalizedVolume = drawSpy.mock.calls[0][0];
        // interpolated between 1 and 0.25 -> should be 0.625
        expect(normalizedVolume).toBeCloseTo(0.625);
    });

    test('draw should clear canvas, draw legend, and draw the volume bar', () => {
        const tracker = new VolumeTracker('overall-volume-canvas');
        const clearRectSpy = jest.spyOn(tracker.ctx, 'clearRect');
        const fillTextSpy = jest.spyOn(tracker.ctx, 'fillText');
        const fillRectSpy = jest.spyOn(tracker.ctx, 'fillRect');

        tracker.draw(0.75); // Draw with 75% volume

        expect(clearRectSpy).toHaveBeenCalledWith(0, 0, canvas.width, canvas.height);
        expect(fillTextSpy).toHaveBeenCalledWith(expect.stringContaining('Relative Volume'), expect.any(Number), expect.any(Number));

        expect(fillRectSpy).toHaveBeenCalled();
        const barHeight = canvas.height * 0.75;
        const yPosition = canvas.height - barHeight;
        // Check if fillRect was called with the correct y-position and height
        expect(fillRectSpy).toHaveBeenCalledWith(expect.any(Number), yPosition, expect.any(Number), barHeight);
        expect(tracker.ctx.fillStyle.toUpperCase()).toBe('#8A2BE2');
    });
});
