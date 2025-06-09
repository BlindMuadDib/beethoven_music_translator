import { describe, test, expect, beforeEach } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Import functions from the module to be tested
import { updateUIVisibility, cacheDOMElements } from '../www/js/ui.js';

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
});
