import { jest, describe, test, expect, beforeEach } from '@jest/globals';
import { setupAudioPlayer } from '../www/js/player/audio-player.js'

describe('Audio Player Module', () => {
    let audioPlayer;
    let playPauseButton;
    let stopButton;

    beforeEach(() => {
        // Create a mock DOM for the player controls
        document.body.innerHTML = `
            <div>
                <p id="song-title"></p>
                <p id="song-metadata"></p>
                <button id="player-play-pause"></button>
                <button id="player-stop"></button>
                <button id="player-rewind"></button>
                <button id="player-ffwd"></button>
                <input type="range" id="volume-control" />
            </div>
        `;

        // Create a mock audio element with mock methods
        audioPlayer = {
            scr: '',
            paused: true,
            currentTime: 0,
            play: jest.fn().mockImplementation(() => {
                audioPlayer.paused = false;
                // Manually trigger onplay event for testing
                audioPlayer.onplay();
            }),
            pause: jest.fn().mockImplementation(() => {
                audioPlayer.paused = true;
                // Manually trigger onpause event for testing
                audioPlayer.onpause();
            }),
            // Mock event handlers so we can assign to them
            onplay: null,
            onpause: null,
            onended: null,
            onvolumechange: null,
        };

        playPauseButton = document.getElementById('player-play-pause');
        stopButton = document.getElementById('player-stop');
    });

    test('should set the audio source correctly', () => {
        const mockResult = {
            audio_url: 'http://test.com/audio.wav',
            original_filename: 'MySong.wav'
        };

        setupAudioPlayer(audioPlayer, mockResult);

        expect(audioPlayer.src).toBe(mockResult.audio_url);
        expect(document.getElementById('song-title').textContent).toBe('MySong');
    });

    test('play/pause button should call the correct audio methods', () => {
        setupAudioPlayer(audioPlayer, { audio_url: '' });

        // Initial state is paused, so first click should play
        playPauseButton.click();
        expect(audioPlayer.play).toHaveBeenCalledTimes(1);
        expect(playPauseButton.textContent).toBe('Pause');

        // Now it's playing, so second click should pause
        playPauseButton.click();
        expect(audioPlayer.pause).toHaveBeenCalledTimes(1);
        expect(playPauseButton.textContent).toBe('Play');
    });

    test('stop button should call onStopAndReset callback if confirmed', () => {
        const onStopMock = jest.fn();
        // Mock the window.confirm function to always return true (user clicked "OK")
        jest.spyOn(window, 'confirm').mockReturnValue(true);

        setupAudioPlayer(audioPlayer, { audio_url: '' }, { onStopAndReset: onStopMock });

        stopButton.click();

        // Check that our callback was called
        expect (onStopMock).toHaveBeenCalledTimes(1);
        // Check that the audio was paused
        expect(audioPlayer.pause).toHaveBeenCalled();
    });
});
