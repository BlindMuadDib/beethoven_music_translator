import * as ui from './ui.js';
import * as api from './api.js';
import { initPlayer } from './player.js';
import { setupAudioPlayer } from './player/audio-player.js';
import { LyricTracker } from './player/lyric-tracker.js';
import { F0Tracker } from './player/f0-tracker.js';
import { init as appInit } from './app.js';

// Find the root elements the app needs to start
const formElement = document.getElementById('translate-form');

// Assemble the dependencies into plain objects
const playerDependencies = {
    initPlayer,
    setupAudioPlayer,
    LyricTracker,
    F0Tracker,
};

// Start the application by injecting all real dependencies
appInit(ui, api, playerDependencies, formElement);
