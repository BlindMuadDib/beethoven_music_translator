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
    let canvas, mockCtx;

    beforeEach(() => {
        // Mock the canvas and its context
        mockCtx = {
            clearRect: jest.fn(),
            fillText: jest.fn(),
            measureText:jest.fn(text=> ({ width: text.length * 10 })),
            beginPath: jest.fn(),
            arc: jest.fn(),
            fill: jest.fn(),
            closePath: jest.fn(),
        };
        canvas = {
            getContext: jest.fn().mockReturnValue(mockCtx),
            offsetWidth: 500,
            offsetHeight: 100,
        };
    });

    const lyricData = [{
        line_text: 'hello world',
        words: [
            { word: 'hello', start: 0.5, end: 1.0 },
            { word: 'world', start: 1.2, end: 1.8 },
        ],
        line_start_time: 0.5,
        line_end_time: 1.8
    }]

    test('update() should draw the current line of text', () => {
        const tracker = new LyricTracker(canvas, lyricData);
        tracker.update(0.7);

        // Check that it cleared the canvas and draws the words
        expect(mockCtx.clearRect).toHaveBeenCalled();
        expect(mockCtx.fillText).toHaveBeenCalledWith('hello', expect.any(Number), expect.any(Number));
        expect(mockCtx.fillText).toHaveBeenCalledWith('world', expect.any(Number), expect.any(Number));
    });

    test('update() should draw the bouncing call on the active word', () => {
        const tracker = new LyricTracker(canvas, lyricData);
        tracker.update(1.5); // Call the update method
        // Assert that the ball drawing function is called
        expect(mockCtx.arc).toHaveBeenCalled();
    });

    test('update() should handle time between words', () => {
        const tracker = new LyricTracker(canvas, lyricData);
        // This time is between "hello" and "world"
        tracker.update(1.1);

        // Assert that the text is still drawn
        expect(mockCtx.fillText).toHaveBeenCalled();
        // Assert that the ball is still drawn (in the "in-between" state)
        expect(mockCtx.arc).toHaveBeenCalled();
    });
});
