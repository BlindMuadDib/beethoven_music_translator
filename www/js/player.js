/**
 * This is the Player module, responsible for buffering data into the UI
 * as well as orchestrating the visualizer components.
 */

// A buffer manager to load the NDJSON arrays into the browser in chunks and
// avoid an OOM or SIGILL error. The NDJSON files can reach ~1.5GB for ~90s
// of audio.
function createBufferManager(visualizer, audioPlayer) {
    let intervalId = null;
    let queue = [];
    let isRunning = false; // Flag to track state
    const accessors = Object.values(visualizer.streamAccessors);
    if (accessors.length === 0) return { start: () => {}, stop: () => {} };

    // --- USER UPLOAD CHECK ---
    // If the accessors are not URL-based, the data is already in memory.
    // No buffering is needed.
    if (accessors[0] && !accessors[0].isUrlSource) {
        console.log('[BufferManager] Data is pre-loaded. Buuffering disabled.');
        // Still return timePerFrame as it's used by the 'seeked' event
        return { start: () => {}, stop: () => {}, timePerFrame: accessors[0].timePerFrame };
    }

    // Assume all accessors have the same chunking properties
    const totalChunks = Math.ceil(accessors[0].totalElements / accessors[0].chunkSize);
    const timePerFrame = accessors[0].timePerFrame;

    // The worker function, now interval-driven
    const worker = async () => {
        // Process up to a few chunks at a time to not overload the network/browser
        const chunksToFetch = queue.splice(0, 3);
        if (chunksToFetch.length === 0) {
            console.log(`[BufferManager] Queue empty. Stopping worker.`);
            stop();
            return;
        }

        const fetchPromises = chunksToFetch.map(chunkIndex => {
            console.log(`[BufferManager] Fetching chunk ${chunkIndex}...`);
            return Promise.all(accessors.map(acc => acc._fetchChunk(chunkIndex)));
        });

        await Promise.all(fetchPromises);
        console.log(`[BufferManager] Chunks ${chunksToFetch} loaded.`);
    };

    function start(startChunk = 0) {
        if (isRunning) {
            console.log('[BufferManager] Already running. Skipping start.');
            return; // Already running
        }
        console.log(`[BufferManager] Starting...`);

        isRunning = true;
        // The queue will be populated with all chunks from the startChunk to
        // the end
        queue = Array.from({length: totalChunks - startChunk}, (_, i) => i + startChunk);
        console.log(`[BufferManager] Queued chunks from ${startChunk}. Total in queue: ${queue.length}`);
        // Start the worker on an interval
        intervalId = setInterval(worker, 500);

    }

    function stop() {
        if (!isRunning) {
            console.log('[BufferManager] Already stopped.Skipping stop.');
            return;
        }
        console.log(`[BufferManager] Stopping...`);
        clearInterval(intervalId);
        intervalId = null;
        isRunning = false;
        queue = [];
    }

    return { start, stop, timePerFrame };
}

/**
 * Initializes the entire player UI, including all sub-modules.
 * This is the main entry point for the player feature.
 * @param {object} resultData - The `result` object from the API response.
 * @param {function} onStopAndReset - Callback for when the user wants to go back to the upload screen.
 * @param {object} dependencies - An object containing the required modules/classes.
 * @param {Function} dependencies.LyricTracker - The LyricTracker class
 * @param {Function} dependencies.HarmonicVisualizer - The HarmonicVisualizer class
 * @param {Function} dependencies.VolumeTracker - The VolumeTracker class
 * @param {Function} dependencies.DrumTracker - The DrumTracker class
 * @param {Function} dependencies.setupAudioPlayer - The setupAudioPlayer function
 */
export function initPlayer(resultData, onStopAndReset, dependencies) {
    let bufferManager;

    try {
        console.log('[Player] Initializing with data:', resultData)

        // Ensure dependencies are provided and valid
        if (!dependencies || typeof dependencies.LyricTracker !== 'function' ||
            typeof dependencies.HarmonicVisualizer !== 'function' ||
            typeof dependencies.VolumeTracker !== 'function' ||
            typeof dependencies.DrumTracker !== 'function' ||
            typeof dependencies.setupAudioPlayer !== 'function') {
            throw new Error("Missing or invalid dependencies provided to initPlayer. Check LyricTracker, HarmonicVisualizer, VolumeTracker, DrumTracker, setupAudioPlayer.")
        }

        // Destructure directly using the class names as they are provided by main.js
        const {
            LyricTracker,
            HarmonicVisualizer,
            VolumeTracker,
            DrumTracker,
            setupAudioPlayer,
        } = dependencies;

        // Find all the necessary DOM elements
        const audioPlayer = document.getElementById('audio-player');
        const lyricCanvas = document.getElementById('lyric-canvas');
        const harmonicCanvas = document.getElementById('harmonic-canvas');
        const overallVolumeCanvas = document.getElementById('overall-volume-canvas');
        const drumCanvas = document.getElementById('drum-canvas');
        const statusMessageEl = document.getElementById('status-message');

        if (!audioPlayer || !lyricCanvas || !harmonicCanvas || !overallVolumeCanvas || !drumCanvas || !statusMessageEl) {
            console.error("One or more player components are missing from the DOM.");
            throw new Error("Missing player UI elements for initialization.")
        }

        console.log('[Player] Setting up audio player...')
        // Pass onStopAndReset to clean up buffer resources
        const cleanupAndReset = () => {
            console.log("Stopping player and cleaning up resources...");
            if (bufferManager) bufferManager.stop();
            onStopAndReset();
        };
        setupAudioPlayer(audioPlayer, resultData, { onStopAndReset: cleanupAndReset });

        // Create new instances of the trackers
        console.log('[Player] Initializing LyricTracker...')
        const lyricTracker = new LyricTracker(lyricCanvas, resultData.mapped_result);

        console.log('[Player] Initializing HarmonicVisualizer...')
        const harmonicVisualizer = new HarmonicVisualizer(harmonicCanvas, resultData.harmonic_analysis);

        // Volume Tracker gets ONLY the overall song volume data
        console.log('[Player] Initializing VolumeTracker...')
        const volumeTracker = new VolumeTracker('overall-volume-canvas');
        volumeTracker.setData(resultData.harmonic_analysis.full_track_analysis);

        console.log('[Player] Initializing DrumTracker...')
        const drumTracker = new DrumTracker(drumCanvas, resultData.drum_analysis);

        bufferManager = createBufferManager(harmonicVisualizer, audioPlayer);
        // Start buffering immediately for a fluid user experience
        bufferManager.start();

        audioPlayer.addEventListener('play', () => {
            // Ensure buffering is active when playing
            bufferManager.start();
        });

        audioPlayer.addEventListener('seeked', () => {
            console.log(`[Player] Seek detected. Restarting buffer at ${audioPlayer.currentTime}s.`);
            const startingChunk = Math.floor(audioPlayer.currentTime / bufferManager.timePerFrame);
            bufferManager.stop();
            bufferManager.start(startingChunk);
        });

        // Set up the main "heartbeat" listener
        audioPlayer.addEventListener('timeupdate', async () => {
            const currentTime = audioPlayer.currentTime;

            // Check if data is ready, if not, pause and wait for it
            if (!harmonicVisualizer.isDataAvailableForTime(currentTime)) {
                audioPlayer.pause();
                harmonicVisualizer.isBuffering = true;
                harmonicVisualizer.update(currentTime); // Show buffering message

                // Wait for the specific data chunk needed to continue
                await harmonicVisualizer.ensureDataForTime(currentTime);

                harmonicVisualizer.isBuffering = false;
                // Resume playback only if the user hasn't manually paused
                const playPauseButton = document.getElementById('player-play-pause');
                if (audioPlayer.paused && playPauseButton && playPauseButton.textContent.includes('Play')) {
                    // Do nothing, user has manually paused
                } else if (audioPlayer.paused) {
                    audioPlayer.play();
                }
            }

            // Update each tracker with the new time
            lyricTracker?.update(currentTime);
            harmonicVisualizer?.update(currentTime);
            volumeTracker?.update(currentTime);
            drumTracker?.update(currentTime);
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
