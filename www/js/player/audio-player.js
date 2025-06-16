// --- Audio Player ---

/**
 * Sets up the audio player controls and event listeners.
 * @param {HTMLAudioElement} audioplayer - The audio element.
 * @param {object} resultData - The full result data from the API.
 * @param {object} option - An object for callbacks.
 * @param {function} options.onStopAndReset - A function to call when the user stops and confirms.
 */

export function setupAudioPlayer(audioPlayer, resultData, options = {}) {
    if (!audioPlayer) throw new Error("Audio player element not provided!");

    const playPauseButton = document.getElementById('player-play-pause');
    const stopButton = document.getElementById('player-stop');
    const rewindButton = document.getElementById('player-rewind');
    const ffwdButton = document.getElementById('player-ffwd');
    const volumeControl = document.getElementById('volume-control');
    const songTitleElem = document.getElementById('song-title');

    // Ensure all elements exist before proceeding
    if (!playPauseButton || !stopButton || !songTitleElem) {
        console.error("One or more audio player UI elements are missing from the DOM.");
        return;
    }

    audioPlayer.src = resultData.audio_url;

    // --- Set Metadata ---
    let title = "Unknown Title";
    if (resultData.original_filename) {
        // Remove extension
        title = resultData.original_filename.replace(/\.[^/.]+$/, "");
    }

    songTitleElem.textContent = title;

    // --- Attach Event Listeners ---
    playPauseButton.onclick = () => {
        if (audioPlayer.paused) audioPlayer.play();
        else audioPlayer.pause();
    };


    audioPlayer.onplay = () => { playPauseButton.textContent = 'Pause'; };
    audioPlayer.onpause = () => { playPauseButton.textContent = 'Play'; };
    audioPlayer.onended = () => { playPauseButton.textContent = 'Play'; };

    stopButton.onclick = () => {
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        if (confirm("Stop playback and upload a different song?")) {
            // INVERSION OF CONTROL: Call the callback instead of touching the DOM element.
            if (typeof options.onStopAndReset === 'function') {
                options.onStopAndReset();
            }
        }
    };

    audioPlayer.onvolumechange = () => {
        volumeControl.value = audioPlayer.volume;
        // If volume is changed via browser's native controls to >0, unmuted it
        if (audioPlayer.volume > 0 && audioPlayer.muted) {
            audioPlayer.muted = false;
        }
    };

    rewindButton.onclick = () => { audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 5); };
    ffwdButton.onclick = () => { audioPlayer.currentTime = Math.min(audioPlayer.duration || 0, audioPlayer.currentTime + 5); };

    volumeControl.oninput = () => {
        audioPlayer.volume = parseFloat(volumeControl.value);
        audioPlayer.muted = (audioPlayer.volume === 0);
    };
}


