// import { setupAudioPlayer } from './player/audio-player.js';
// import { LyricTracker } from './player/lyric-tracker.js';
// import { F0Tracker } from './player/f0-tracker.js';
// import { VolumeTracker } from './player/volume-tracker.js';

/**
 * Initializes the entire player UI, including all sub-modules.
 * This is the main entry point for the player feature.
 * @param {object} resultData - The `result` object from the API response.
 * @param {function} onStopAndReset - Callback for when the user wants to go back to the upload screen.
 * @param {object} dependencies - An object containing the required modules/classes.
 * @param {Function} dependencies.LyricTracker - The LyricTracker class
 * @param {Function} dependencies.F0Tracker - The F0Tracker class
 * @param {Function} dependencies.VolumeTracker - The VolumeTracker class
 * @param {Function} dependencies.setupAudioPlayer - The setupAudioPlayer function
 */
export function initPlayer(resultData, onStopAndReset, dependencies) {
    try {
        console.log('[Player] Initializing with data:', resultData)

        // Ensure dependencies are provided and valid
        if (!dependencies || typeof dependencies.LyricTracker !== 'function' ||
            typeof dependencies.F0Tracker !== 'function' ||
            typeof dependencies.VolumeTracker !== 'function' ||
            typeof dependencies.setupAudioPlayer !== 'function') {
            throw new Error("Missing or invalid dependencies provided to initPlayer. Check LyricTracker, F0Tracker, VolumeTracker, setupAudioPlayer.")
        }

        // Destructure directly using the class names as they are provided by main.js
        const {
            LyricTracker,
            F0Tracker,
            VolumeTracker,
            setupAudioPlayer,
        } = dependencies;

        // 2. Find all the necessary DOM elements
        const audioPlayer = document.getElementById('audio-player');
        const lyricCanvas = document.getElementById('lyric-canvas');
        const f0Canvas = document.getElementById('f0-canvas');
        const overallVolumeCanvas = document.getElementById('overall-volume-canvas');

        if (!audioPlayer || !lyricCanvas || !f0Canvas || !overallVolumeCanvas) {
            console.error("One or more player components are missing from the DOM.");
            throw new Error("Missing player UI elements for initialization.")
        }

        console.log('[Player] Setting up audio player...')
        setupAudioPlayer(audioPlayer, resultData, { onStopAndReset });

        // 3. Create new instances of the trackers
        console.log('[Player] Initializing LyricTracker...')
        const lyricTracker = new LyricTracker(lyricCanvas, resultData.mapped_result);

        console.log('[Player] Initializing F0Tracker...')
        const f0Tracker = new F0Tracker(f0Canvas, resultData.f0_analysis, resultData.volume_analysis?.instruments);

        // 4. Volume Tracker gets ONLY the overall song volume data
        console.log('[Player] Initializing VolumeTracker...')
        const volumeTracker = new VolumeTracker('overall-volume-canvas');
        volumeTracker.setData(resultData.volume_analysis.overall_rms);

        // 5. Set up the main "heartbeat" listener
        audioPlayer.addEventListener('timeupdate', () => {
            const currentTime = audioPlayer.currentTime;
            // Update each tracker with the new time
            lyricTracker?.update(currentTime);
            f0Tracker?.update(currentTime);
            volumeTracker?.update(currentTime);
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
