import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Import functions from the module to be tested
import {
    updateUIVisibility,
    cacheDOMElements,
    showStatusMessage,
    setSubmitButtonDisabled,
    updateAuthUI,
    toggleDownloadButton,
    setupDownloadButton,
    showTutorialOverlay,
    hideTutorialOverlay,
    updateTutorialStatus,
    renderLibrary
} from '../www/js/ui.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('UI Module', () => {
    let uploadUI, playerUI, statusMessage, downloadContainer, downloadBtn;
    let tutorialOverlay, tutorialStatus, skipBtn, viewResultsBtn;

    beforeEach(() => {
        // Load the DOM from index.html before each test
        const html = fs.readFileSync(path.resolve(__dirname, '../www/index.html'), 'utf8');
        document.body.innerHTML = html;
        // Cache the elements after loading the new DOM
        cacheDOMElements();
        uploadUI = document.getElementById('upload-ui-container');
        playerUI = document.getElementById('player-ui-container');
        statusMessage = document.getElementById('status-message');
        downloadContainer = document.getElementById('download-container');
        downloadBtn = document.getElementById('download-mtr-btn');
        tutorialOverlay = document.getElementById('tutorial-overlay');
        tutorialStatus = document.getElementById('tutorial-status-text');
        skipBtn = document.getElementById('skip-tutorial-btn');
        viewResultsBtn = document.getElementById('view-result-btn');
    });

    describe('updateAuthUI', () => {
        let loggedInView, loggedOutView, userGreeting;

        beforeEach(() => {
            // Get references to the specific auth elements
            loggedInView = document.getElementById('logged-in-view');
            loggedOutView = document.getElementById('logged-out-view');
            userGreeting = document.getElementById('user-greeting');
        });

        test('should show logged-in view and user email when authenticated', () => {
            const authStatus = { isAuthenticated: true, user: { email: 'test@example.com' } };
            updateAuthUI(authStatus);

            expect(loggedInView.style.display).toBe('flex');
            expect(loggedOutView.style.display).toBe('none');
            expect(userGreeting.textContent).toBe('Welcome, test@example.com');
        });

        test('should show logged-out view when not authenticated', () => {
            const authStatus = { isAuthenticated: false };
            updateAuthUI(authStatus);

            expect(loggedInView.style.display).toBe('none');
            expect(loggedOutView.style.display).toBe('flex');
        });

        test('should handle a missing user email gracefully', () => {
            // Case where user object exists but email is missing
            const authStatus = { isAuthenticated: true, user: {} };
            updateAuthUI(authStatus);

            expect(loggedInView.style.display).toBe('flex');
            expect(userGreeting.textContent).toBe('Welcome, User');
        });

        test('should default to logged-out view for null or invalid input', () => {
            updateAuthUI(null);

            expect(loggedInView.style.display).toBe('none');
            expect(loggedOutView.style.display).toBe('flex');
        });
    });

    describe('Visibility Toggles', () => {
        test('updateUIVisibility should only show the "upload" container', () => {
            updateUIVisibility('upload');
            expect(uploadUI.style.display).toBe('block');
            expect(playerUI.style.display).toBe('none');
            expect(statusMessage.style.display).toBe('none');
        });

        test('updateUIVisibility should only show the "player" container', () => {
            updateUIVisibility('player');
            expect(uploadUI.style.display).toBe('none');
            expect(playerUI.style.display).toBe('flex');
            expect(statusMessage.style.display).toBe('none');
        });

        test('updateUIVisibility should only show the "status" message and "upload" container', () => {
            updateUIVisibility('status');
            expect(uploadUI.style.display).toBe('block');
            expect(playerUI.style.display).toBe('none');
            expect(statusMessage.style.display).toBe('block');
        });

        test('toggleDownloadButton should show/hide the download container', () => {
            toggleDownloadButton(true);
            expect(downloadContainer.style.display).toBe('block');

            toggleDownloadButton(false);
            expect(downloadContainer.style.display).toBe('none');
        });
    });

    describe('Interactions & Messaging', () => {
        test('showStatusMessage should display a simple string', () => {
            const message = 'Test message';
            showStatusMessage(message);
            expect(statusMessage.textContent).toBe(message);
        });

        test('showStatusMessage should format a progress object correctly', () => {
            const progress = { status: 'started', progress_stage: 'separating_audio' };
            showStatusMessage(progress);
            expect(statusMessage.textContent).toBe('Status: started - separating_audio');
        });

        test('setSubmitButtonDisabled should disable and enable the button', () => {
            const submitButton = document.getElementById('submit-button');

            setSubmitButtonDisabled(true);
            expect(submitButton.disabled).toBe(true);

            setSubmitButtonDisabled(false);
            expect(submitButton.disabled).toBe(false);
        });

        test('setupDownloadButton should attach a click listener', () => {
            const mockCallback = jest.fn();
            setupDownloadButton(mockCallback);

            downloadBtn.click();
            expect(mockCallback).toHaveBeenCalledTimes(1);
        });
    });

    describe('Tutorial Overlay', () => {
        test('showTutorialOverlay should display the overlay and bind exit callback', () => {
            const mockExit = jest.fn();

            showTutorialOverlay(mockExit);

            expect(tutorialOverlay.style.display).toBe('block');
            expect(viewResultsBtn.style.display).toBe('none'); // Should be hidden initially
            expect(tutorialStatus.textContent).toContain('Demonstrating');

            // Re-fetch the button because the function replaces the DOM node
            const activeSkipBtn = document.getElementById('skip-tutorial-btn');

            // Verify click listener
            activeSkipBtn.click();
            expect(mockExit).toHaveBeenCalled();
        });

        test('hideTutorialOverlay should hide the container', () => {
            tutorialOverlay.style.display = 'block';
            hideTutorialOverlay();
            expect(tutorialOverlay.style.display).toBe('none');
        });

        test('updateTutorialStatus should show "Ready" state and bind result callback', () => {
            const mockResultClick = jest.fn();

            // First show it to set initial state
            showTutorialOverlay(jest.fn());

            // Update status
            updateTutorialStatus('ready', mockResultClick);

            expect(tutorialStatus.textContent).toContain('Translation Completed');

            // Re-fetch the button because the function replaces the DOM node
            const activeViewResultBtn = document.getElementById('view-result-btn');
            expect(activeViewResultBtn.style.display).toBe('inline-block');

            // Verify result button listener
            activeViewResultBtn.click();
            expect(mockResultClick).toHaveBeenCalled();
        });
    });

    describe('Library View', () => {
        let libraryContainer;

        beforeEach(() => {
            libraryContainer = document.createElement('div');
            libraryContainer.id = 'library-ui-container';
            document.body.appendChild(libraryContainer);
        });

        afterEach(() => {
            document.body.removeChild(libraryContainer);
        });

        test('renderLibrary should generate sorted library UI grouped by artist', () => {
            const mockSongs = [
                { artist: 'Zebra', title: 'Song 2', audio_url: '2.wav' },
                { artist: 'Aardvark', title: 'Song 1', audio_url: '1.wav' },
                { artist: 'Zebra', title: 'Song 3', audio_url: '3.wav' }
            ];
            const mockCallback = jest.fn();

            renderLibrary(mockSongs, libraryContainer, mockCallback);

            const headings = libraryContainer.querySelectorAll('h3');
            expect(headings.length).toBe(2);
            expect(headings[0].textContent).toContain('Aardvark');
            expect(headings[1].textContent).toContain('Zebra');

            const songs = libraryContainer.querySelectorAll('.library-song-item');
            expect(songs.length).toBe(3);
            expect(songs[0].textContent).toContain('Song 1');
            expect(songs[1].textContent).toContain('Song 2');
            expect(songs[2].textContent).toContain('Song 3');

            const disclaimer = libraryContainer.querySelector('.library-disclaimer');
            expect(disclaimer).not.toBeNull();
            expect(disclaimer.textContent).toContain('All songs in this library are shared under Creative Commons licensing or explicit permission of the copyright owner.');

            songs[0].click();
            expect(mockCallback).toHaveBeenCalledWith(mockSongs[1]); // Aardvark - Song 1
        });

        test('renderLibrary should use CSS classes instead of inline styles for theme consistency', () => {
            const mockSongs = [
                { artist: 'Zebra', title: 'Song 2', audio_url: '2.wav' }
            ];
            const mockCallback = jest.fn();

            renderLibrary(mockSongs, libraryContainer, mockCallback);

            const headings = libraryContainer.querySelectorAll('h3');
            expect(headings[0].classList.contains('library-artist-header')).toBe(true);
            expect(headings[0].style.borderBottom).toBe(''); // Aesthetic styles should be removed

            const lists = libraryContainer.querySelectorAll('ul');
            expect(lists[0].classList.contains('library-artist-list')).toBe(true);
            expect(lists[0].style.listStyleType).toBe(''); // Aesthetic styles should be removed

            const songs = libraryContainer.querySelectorAll('.library-song-item');
            expect(songs[0].style.background).toBe(''); // Should not have hardcoded background
            expect(songs[0].style.backgroundColor).toBe(''); // Should not be inline
            expect(songs[0].style.borderRadius).toBe('');
            expect(songs[0].onmouseover).toBeNull(); // Hover styling should be handled natively by CSS :hover
        });
    });
});
