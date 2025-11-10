// This file only worries about the DOM.

// A central place to hold references to UI elements
const uiElements = {};

/**
 * Finds and stores all necessary DOM elements in the ui object.
 * This should only be called once by the main app initializer.
 */
export function cacheDOMElements(){
    uiElements.uploadUI = document.getElementById('upload-ui-container');
    uiElements.playerUI = document.getElementById('player-ui-container');
    uiElements.statusMessage = document.getElementById('status-message');
    uiElements.submitButton = document.getElementById('submit-button');
    uiElements.loggedInView = document.getElementById('logged-in-view');
    uiElements.loggedOutView = document.getElementById('logged-out-view');
    uiElements.userGreeting = document.getElementById('user-greeting');
    uiElements.accessCodeContainer = document.getElementById('access-code-container');
    uiElements.accessCodeInput = document.getElementById('access_code');
}

/**
 * Updates the navigation bar to show either login/register or logout/user info
 * @param {object} authStatus - The authentication status object from the API.
 * e.g., { isAuthenticated: boolean, user?: { email: string } }
 */
export function updateAuthUI(authStatus) {
    const { loggedInView, loggedOutView, userGreeting, accessCodeContainer, accessCodeInput } = uiElements;

    if (!loggedInView || !loggedOutView || !userGreeting || !accessCodeInput) {
        console.error("Authentication UI elements not found in the DOM.");
        return;
    }

    if (authStatus && authStatus.isAuthenticated) {
        // User is logged in, show their view
        loggedInView.style.display = 'flex';
        loggedOutView.style.display = 'none';
        userGreeting.textContent = `Welcome, ${authStatus.user?.email || 'User'}`;

        if (accessCodeContainer) accessCodeContainer.style.display = 'none';
        accessCodeInput.required = false;

    } else {
        // User is logged out, show the default view
        loggedInView.style.display = 'none';
        loggedOutView.style.display = 'flex';

        if (accessCodeContainer) accessCodeContainer.style.display = 'block';
        accessCodeInput.required = true;
    }
}

/**
 * Controls which main UI container is visible.
 * @param {'upload' | 'player' | 'status'} visibleSection - The UI to show.
 */
export function updateUIVisibility(visibleSection) {
    const { uploadUI, playerUI, statusMessage } = uiElements;

    // Hide everything first.
    if (uploadUI) uploadUI.style.display = 'none';
    if (playerUI) playerUI.style.display = 'none';
    if (statusMessage) statusMessage.style.display = 'none';

    // Now, show only the one requested.
    if (visibleSection === 'upload' && uploadUI) {
        uploadUI.style.display = 'block';
    } else if (visibleSection === 'player' && playerUI) {
        playerUI.style.display = 'flex'
    } else if (visibleSection === 'status' && statusMessage) {
        // Also show the main upload container so the status is in context
        if (uploadUI) uploadUI.style.display = 'block';
        statusMessage.style.display = 'block';
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
