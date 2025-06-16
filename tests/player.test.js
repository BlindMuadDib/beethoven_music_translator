import { jest, describe, test, expect } from '@jest/globals';
import { initPlayer } from '../www/js/player.js';
import { LyricTracker } from '../www/js/player/lyric-tracker.js';
import { F0Tracker } from '../www/js/player/f0-tracker.js';

describe('Player Facade Integration)', () => {

    test('initPlayer should correctly update real trackers on audio timeupdate event', () => {
        // Arrange: Create mock dependencies
        const mockSetupAudioPlayer = jest.fn();

        // Assemble the dependencies object, matching the shape initPlayer expects
        const mockDependencies = {
            setupAudioPlayer: mockSetupAudioPlayer,
            LyricTracker: LyricTracker,
            F0Tracker: F0Tracker,
        };

        // Set up the required DOM
        document.body.innerHTML = `
            <audio id="audio-player"></audio>
            <canvas id="lyric-canvas" width="600" height="150"></canvas>
            <canvas id="f0-canvas" width="600" height="300"></canvas>
        `;
        const audioEl = document.getElementById('audio-player');

        // Capture the function passed to addEventListener
        let timeUpdateCallback;
        jest.spyOn(audioEl, 'addEventListener').mockImplementation((event, callback) => {
            if (event === 'timeupdate') {
                timeUpdateCallback = callback;
            }
        });

        const mockResultData = {
            mapped_result: [{
                line_text: 'example line',
                words: [
                    {word: 'example', start: 0.01, end: 0.02},
                    {word: 'line', start: 0.02, end: 0.03},
                ],
                line_start_time: 0.01,
                line_end_time: 0.03
            }],
            f0_analysis: {
                vocals: {
                    times: [0.01, 0.02, 0.03],
                    f0_values: [220.0, 220.1, 220.5],
                    time_interval: 0.01
                },
                bass: {
                    times: [0.01, 0.02, 0.03],
                    f0_values: [110.0, null, 110.2],
                    time_interval: 0.01
                },
            },
            audio_url: 'fake.wav',
            original_filename: 'fake.wav'
        };

        // Spy on the update methods of the REAL classes' prototypes
        const lyricUpdateSpy = jest.spyOn(LyricTracker.prototype, 'update');
        const f0UpdateSpy = jest.spyOn(F0Tracker.prototype, 'update');

        // ACT: Call initPlayer and PASS IN the single mocked dependencies object
        initPlayer(mockResultData, jest.fn(), mockDependencies);

        // Simulate a timeupdate event from the browser
        audioEl.currentTime = .03
        timeUpdateCallback();

        // Assert: The update methods on the real instances should have been called
        expect(lyricUpdateSpy).toHaveBeenCalledWith(0.03);
        expect(f0UpdateSpy).toHaveBeenCalledWith(0.03);
    });
});
