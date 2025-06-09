import { findCurrentLineIndex, LyricTracker } from '../www/js/player/lyric-tracker.js';
import { jest, describe, test, expect, beforeEach } from '@jest/globals';

// Test the PURE function
describe('findCurrentLineIndex', () => {
    const mockLines = [
    { line_text: 'Line 1', line_start_time: 0, line_end_time: 2 },
    { line_text: 'Line 2', line_start_time: 3, line_end_time: 5 },
    ];

    test('should return the correct index when time is within a line', () => {
        expect(findCurrentLineIndex(1.5, mockLines)).toBe(0);
        expect(findCurrentLineIndex(4.0, mockLines)).toBe(1);
    });

    test('should return line until midpoint between lines, then show next line', () => {
        expect(findCurrentLineIndex(2.49, mockLines)).toBe(0);
        expect(findCurrentLineIndex(2.5, mockLines)).toBe(1);
    });
});

// Test the CLASS
describe('LyricTracker', () => {
    let mockCanvas, mockCtx;

    beforeEach(() => {
        // Mock the canvas and its context
        mockCtx = {
            clearRect: jest.fn(),
            fillText: jest.fn(),
            beginPath: jest.fn(),
            arc: jest.fn(),
            fill: jest.fn(),
            closePath: jest.fn(),
        };
        mockCanvas = {
            getContext: () => mockCtx,
            width: 500,
            height: 100,
            offsetWidth: 500,
            offsetHeight: 100,
        };
    });

    test('constructor should initialize the canvas and context', () => {
        const tracker = new LyricTracker(mockCanvas, []);
        expect(tracker.canvas).toBe(mockCanvas);
        expect(tracker.ctx).toBe(mockCtx);
        // Check that it cleared the canvas on init
        expect(mockCtx.clearRect).toHaveBeenCalledWith(0, 0, 500, 100);
    });

    test('update method should call clearRect', () => {
        const tracker = new LyricTracker(mockCanvas, []);
        tracker.update(1.0); // Call the update method
        // clearRect is called once in constructor, once in update
        expect(mockCtx.clearRect).toHaveBeenCalledTimes(2);
    });
});
