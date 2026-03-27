// This file only worries about the DOM.

// A central place to hold references to UI elements
const uiElements = {};

/**
 * Finds and stores all necessary DOM elements in the ui object.
 * This should only be called once by the main app initializer.
 */
export function cacheDOMElements() {
    uiElements.uploadUI = document.getElementById('upload-ui-container');
    uiElements.playerUI = document.getElementById('player-ui-container');
    uiElements.statusMessage = document.getElementById('status-message');
    uiElements.submitButton = document.getElementById('submit-button');
    uiElements.localFileInput = document.getElementById('local-file-input');
    uiElements.localAudioInput = document.getElementById('local-audio-input');
    uiElements.loggedInView = document.getElementById('logged-in-view');
    uiElements.loggedOutView = document.getElementById('logged-out-view');
    uiElements.userGreeting = document.getElementById('user-greeting');
    uiElements.downloadContainer = document.getElementById('download-container');
    uiElements.downloadMtrBtn = document.getElementById('download-mtr-btn');
    uiElements.libraryUI = document.getElementById('library-ui-container');
    uiElements.libraryBtn = document.getElementById('library-btn');
    uiElements.libraryList = document.getElementById('library-songs-list');
    // Tutorial Elements
    uiElements.tutorialOverlay = document.getElementById('tutorial-overlay');
    uiElements.tutorialStatus = document.getElementById('tutorial-status-text');
    uiElements.skipTutorialBtn = document.getElementById('skip-tutorial-btn');
    uiElements.viewResultBtn = document.getElementById('view-result-btn');
}

/**
 * Updates the navigation bar to show either login/register or logout/user info
 * @param {object} authStatus - The authentication status object from the API.
 * e.g., { isAuthenticated: boolean, user?: { email: string } }
 */
export function updateAuthUI(authStatus) {
    const { loggedInView, loggedOutView, userGreeting } = uiElements;

    if (!loggedInView || !loggedOutView || !userGreeting) {
        console.error("Authentication UI elements not found in the DOM.");
        return;
    }

    if (authStatus && authStatus.isAuthenticated) {
        // User is logged in, show their view
        loggedInView.style.display = 'flex';
        loggedOutView.style.display = 'none';
        userGreeting.textContent = `Welcome, ${authStatus.user?.email || 'User'}`;

    } else {
        // User is logged out, show the default view
        loggedInView.style.display = 'none';
        loggedOutView.style.display = 'flex';
    }
}

/**
 * Controls which main UI container is visible.
 * @param {'upload' | 'player' | 'status'} visibleSection - The UI to show.
 */
export function updateUIVisibility(visibleSection) {
    const { uploadUI, playerUI, statusMessage, libraryUI } = uiElements;

    // Hide everything first.
    if (uploadUI) uploadUI.style.display = 'none';
    if (playerUI) playerUI.style.display = 'none';
    if (statusMessage) statusMessage.style.display = 'none';
    if (libraryUI) libraryUI.style.display = 'none';

    // Now, show only the one requested.
    if (visibleSection === 'upload' && uploadUI) {
        uploadUI.style.display = 'block';
    } else if (visibleSection === 'player' && playerUI) {
        playerUI.style.display = 'flex';
    } else if (visibleSection === 'status' && statusMessage) {
        // Also show the main upload container so the status is in context
        if (uploadUI) uploadUI.style.display = 'block';
        statusMessage.style.display = 'block';
    } else if (visibleSection === 'library' && libraryUI) {
        libraryUI.style.display = 'block';
    }
}

/**
 * Updates the text content of the status message area.
 * @param {string | {status: string, progress_stage?: string}} message - The message to display.
 */
export function showStatusMessage(message) {
    if (!uiElements.statusMessage) return;

    let statusText = '';
    if (typeof message === 'string') {
        statusText = message;
    } else if (typeof message === 'object' && message.status) {
        // Handle the progressData object from pollJobStatus
        statusText = `Status: ${message.status} - ${message.progress_stage || '...'}`;
    }

    uiElements.statusMessage.textContent = statusText;
}

/**
 * Enables or disables the submit button.
 * @param {boolean} isDisabled - True to disable, false to enable.
 */
export function setSubmitButtonDisabled(isDisabled) {
    if (uiElements.submitButton) {
        uiElements.submitButton.disabled = isDisabled;
    }
}

/**
 * Sets up the click handler for the MTR download button.
 * @param {Function} onClickCallback - The function to call when clicked.
 */
export function setupDownloadButton(onClickCallback) {
    if (uiElements.downloadMtrBtn) {
        // Remove old listeners by assigning a new one
        uiElements.downloadMtrBtn.onclick = onClickCallback;
    }
}

/** Toggles the visibility of the download button container.
 * @param {boolean} show - True to show, false to hide.
 */
export function toggleDownloadButton(show) {
    if (uiElements.downloadContainer) {
        uiElements.downloadContainer.style.display = show ? 'block' : 'none';
    }
}

/**
 * Shows the tutorial overlay bar and binds the Exit button.
 * @param {Function} onExitCallback - Function to run when user clicks "Exit Tutorial".
 */
export function showTutorialOverlay(onExitCallback) {
    if (!uiElements.tutorialOverlay) return;

    uiElements.tutorialOverlay.style.display = 'block';
    if (uiElements.tutorialStatus) {
        uiElements.tutorialStatus.textContent = " - Demonstrating visualization features...";
    }

    // Reset buttons
    if (uiElements.viewResultBtn) uiElements.viewResultBtn.style.display = 'none';

    if (uiElements.skipTutorialBtn) {
        // Clone to remove old listeners
        const newBtn = uiElements.skipTutorialBtn.cloneNode(true);
        uiElements.skipTutorialBtn.parentNode.replaceChild(newBtn, uiElements.skipTutorialBtn);
        uiElements.skipTutorialBtn = newBtn; // Update reference

        uiElements.skipTutorialBtn.onclick = (e) => {
            e.preventDefault();
            onExitCallback();
        };
    }
}

/**
 * Hides the tutorial overlay.
 */
export function hideTutorialOverlay() {
    if (uiElements.tutorialOverlay) {
        uiElements.tutorialOverlay.style.display = 'none';
    }
}

/**
 * Updates the tutorial overlay to indicate the real result is ready.
 * @param {'ready'} status - The status code (currently only 'ready' is used).
 * @param {Function} onResultClick - Function to run when user clicks "View Result".
 */
export function updateTutorialStatus(status, onResultClick) {
    if (status === 'ready') {
        if (uiElements.tutorialStatus) {
            uiElements.tutorialStatus.textContent = " - Translation Completed! Click to view.";
        }

        if (uiElements.viewResultBtn) {
            uiElements.viewResultBtn.style.display = 'inline-block';

            const newBtn = uiElements.viewResultBtn.cloneNode(true);
            uiElements.viewResultBtn.parentNode.replaceChild(newBtn, uiElements.viewResultBtn);
            uiElements.viewResultBtn = newBtn;

            uiElements.viewResultBtn.onclick = (e) => {
                e.preventDefault();
                onResultClick();
            };
        }
    }
}

/**
 * Renders the library screen with songs sorted and grouped by artist.
 * @param {Array} libraryData 
 * @param {HTMLElement} containerElement
 * @param {Function} onSongClick
 */
export function renderLibrary(libraryData, containerElement, onSongClick) {
    if (!containerElement) return;

    // Ensure the structure is pristine
    containerElement.innerHTML = `
        <h2>Creative Commons Library</h2>
        <p class="library-disclaimer">All songs in this library are shared under Creative Commons licensing or explicit permission of the copyright owner.</p>
        <div id="library-songs-list"></div>
    `;

    const listContainer = containerElement.querySelector('#library-songs-list');

    // Group by artist
    const byArtist = {};
    for (const song of libraryData) {
        const artist = song.artist || 'Unknown Artist';
        if (!byArtist[artist]) {
            byArtist[artist] = [];
        }
        byArtist[artist].push(song);
    }

    // Sort artists alphabetically
    const artists = Object.keys(byArtist).sort((a, b) => a.localeCompare(b));

    artists.forEach(artist => {
        const artistHeader = document.createElement('h3');
        artistHeader.textContent = artist + ' \u25BE'; // add down arrow
        artistHeader.className = 'library-artist-header';
        listContainer.appendChild(artistHeader);

        const ul = document.createElement('ul');
        ul.className = 'library-artist-list';
        ul.style.display = 'none'; // hidden by default

        artistHeader.onclick = () => {
            const isHidden = ul.style.display === 'none';
            ul.style.display = isHidden ? 'block' : 'none';
            artistHeader.textContent = artist + (isHidden ? ' \u25B4' : ' \u25BE'); // toggle arrow
        };

        // Sort songs by title
        byArtist[artist].sort((a, b) => a.title.localeCompare(b.title));

        byArtist[artist].forEach(song => {
            const li = document.createElement('li');
            li.className = 'library-song-item';

            li.textContent = song.title;

            li.onclick = () => onSongClick(song);

            ul.appendChild(li);
        });

        listContainer.appendChild(ul);
    });
}
