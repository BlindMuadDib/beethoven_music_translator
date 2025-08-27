import * as ui from './ui.js';
import * as api from './api.js';
import { initPlayer } from './player.js';
import { setupAudioPlayer } from './player/audio-player.js';
import { LyricTracker } from './player/lyric-tracker.js';
import { HarmonicVisualizer } from './player/harmonic-visualizer.js';
import { SpectrogramAccessor } from './player/SpectrogramAccessor.js';
import { VolumeTracker } from './player/volume-tracker.js';
import { DrumTracker } from './player/drum-tracker.js';
import { init as appInit } from './app.js';

// Find the root elements the app needs to start
const formElement = document.getElementById('translate-form');

// Assemble the dependencies into plain objects
const playerDependencies = {
    initPlayer,
    setupAudioPlayer,
    LyricTracker,
    HarmonicVisualizer,
    SpectrogramAccessor,
    VolumeTracker,
    DrumTracker,
};

// Start the application by injecting all real dependencies
appInit(ui, api, playerDependencies, formElement);
