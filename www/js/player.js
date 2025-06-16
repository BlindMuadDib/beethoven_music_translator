/**
 * Initializes the entire player UI, including all sub-modules.
 * This is the main entry point for the player feature.
 * @param {object} resultData - The `result` object from the API response.
 * @param {function} onStopAndReset - Callback for when the user wants to go back to the upload screen.
 * @param {object} dependencies - An object containing the required modules/classes.
 */
export function initPlayer(resultData, onStopAndReset, dependencies) {
    try {
        // 1. Define dependencies
        const { setupAudioPlayer, LyricTracker, F0Tracker } = dependencies;

        // 2. Find all the necessary DOM elements
        const audioPlayer = document.getElementById('audio-player');
        const lyricCanvas = document.getElementById('lyric-canvas');
        const f0Canvas = document.getElementById('f0-canvas');

        if (!audioPlayer || !lyricCanvas || !f0Canvas) {
            console.error("One or more player components are missing from the DOM.");
            return;
        }

        // 3. Create new instances of the trackers
        const lyricTracker = new LyricTracker(lyricCanvas, resultData.mapped_result);
        const f0Tracker = new F0Tracker(f0Canvas, resultData.f0_analysis);

        // 4. Set up the audio player controls, passing the reset callback
        setupAudioPlayer(audioPlayer, resultData, { onStopAndReset });

        // 5. Set up the main "heartbeat" listener
        audioPlayer.addEventListener('timeupdate', () => {
            const currentTime = audioPlayer.currentTime;
            // Update each tracker with the new time
            if (lyricTracker && f0Tracker) {
                lyricTracker.update(currentTime);
                f0Tracker.update(currentTime);
            }
        });
    } catch (error) {
        // This will print any error from the Initialization to the browser console.
        console.error("! FATAL: Failed to initialize the player UI.", error);
        const statusMessage = document.getElementById('status-message');
        if (statusMessage) {
            statusMessage.textContent = `Player Error: ${error.message}. Please refresh and try again.`;
            statusMessage.style.display = 'block';
            statusMessage.style.color = 'red';
        }
    }
}
