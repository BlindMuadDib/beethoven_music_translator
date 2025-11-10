import { describe, test, expect, beforeEach } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Import functions from the module to be tested
import {
    updateUIVisibility,
    cacheDOMElements,
    showStatusMessage,
    setSubmitButtonDisabled,
    updateAuthUI
} from '../www/js/ui.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('UI Module', () => {
    let uploadUI, playerUI, statusMessage;

    beforeEach(() => {
        // Load the DOM from index.html before each test
        const html = fs.readFileSync(path.resolve(__dirname, '../www/index.html'), 'utf8');
       document.body.innerHTML = html;
       // Cache the elements after loading the new DOM
       cacheDOMElements();
       uploadUI = document.getElementById('upload-ui-container');
       playerUI = document.getElementById('player-ui-container');
       statusMessage = document.getElementById('status-message');
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
});
