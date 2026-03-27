// main app that brings all the front-end pieces together

import { TimeSeriesAccessor } from './player/TimeSeriesAccessor.js';
import { calculateTotalFrames } from './utils.js';

const APP_VERSION = '0.1.3';

/**
 * Helper to validate Semantic Versioning compatibility.
 * Accepts x.y.z. Returns true if Major (x) and Minor (y) match.
 */
function isVersionCompatible(fileVersion, currentVersion) {
    // Legacy support for early versions without version control
    if (!fileVersion) {
        console.warn("File has no version tag. Assuming LEGACY support.")
        return true;
    }

    const [fMajor, fMinor] = fileVersion.split('.').map(Number);
    const [cMajor, cMinor] = currentVersion.split('.').map(Number);

    // Check strict equality for Major and Minor
    if (fMajor !== cMajor) return false;
    if (fMinor !== cMinor) return false;

    // Patch version (index 2) is ignored for compatibility
    return true;
}

/**
 * Orchestrates the Tutorial Mode.
 */
async function startTutorial(ui, playerDependencies, api, onExit) {
    try {
        ui.updateUIVisibility('player');

        // Define exit handler
        const handleExit = () => {
            // 1. Force the audio player to stop
            const audioPlayer = document.getElementById('audio-player');
            if (audioPlayer) {
                audioPlayer.pause();
                audioPlayer.currentTime = 0; // Reset to start
                audioPlayer.src = ""; // Unload the tutorial audio file
            }

            // 2. Hide UI
            ui.hideTutorialOverlay();

            // 3. Execute external exit callback (which swaps views back to Upload)
            if (onExit) onExit();
        };

        // Show overlay immediately
        ui.showTutorialOverlay(handleExit);

        const tutorialData = await api.fetchTutorialData();

        // --- DATA HYRDATION ---
        // The visualizers expect 'stream_accessor' (Harmonic) and
        // 'hits_accessor' (Drum) to be instances of TimeSeriesAccessor.
        // We must create them manually here.

        const { TimeSeriesAccessor } = playerDependencies;

        // 1. Hydrate Harmonic Data
        if (tutorialData.harmonic_analysis?.stem_analyses) {
            for (const stemName in tutorialData.harmonic_analysis.stem_analyses) {
                const stem = tutorialData.harmonic_analysis.stem_analyses[stemName];
                // The Python script puts the array in 'frames'
                if (stem.frames && Array.isArray(stem.frames)) {
                    stem.stream_accessor = new TimeSeriesAccessor(stem.frames, stem.frames.length);
                }
            }
        }

        // 2. Hydrate Drum Data
        if (tutorialData.drum_analysis?.hits) {
            const hits = tutorialData.drum_analysis.hits;
            tutorialData.drum_analysis.hits_accessor = new TimeSeriesAccessor(hits, hits.length);
        }

        // Init player with the hyrdated data
        playerDependencies.initPlayer(tutorialData, handleExit, playerDependencies);

    } catch (e) {
        console.warn("Could not load tutorial:", e);
        // If tutorial fails, just exit it
        if (onExit) onExit();
    }
}

/**
 * Handles the form submission by orchestrating API and UI calls.
 * This function now accepts its dependencies as arguments.
 * @param {Event} event
 * @param {object} ui - The UI module dependency.
 * @param {object} api - The API module dependency.
 * @param {object} playerDependencies - The Player module dependency.
 */
export async function handleFormSubmit(event, ui, api, playerDependencies) {
    event.preventDefault();

    // 1. Check Preferences
    const disableTutorial = localStorage.getItem('beethoven_disable_tutorial') === 'true';

    // State to track if result is ready while tutorial plays
    let jobResult = null;
    let isTutorialActive = !disableTutorial;

    // Helper to transition to the actual result
    const loadResultToPlayer = (result) => {
        ui.hideTutorialOverlay();
        ui.updateUIVisibility('player');

        playerDependencies.initPlayer(result, () => {
            ui.updateUIVisibility('upload');
            ui.setSubmitButtonDisabled(false);
            ui.toggleDownloadButton(false);
        }, playerDependencies);

        // Check for downloads
        if (result.drum_analysis?.hits_accessor && result.harmonic_analysis?.full_track_analysis) {
            ui.setupDownloadButton(() => api.triggerMtrDownload(result.job_id)); // passed via result usually
            ui.toggleDownloadButton(true);
        }
    };

    try {
        ui.setSubmitButtonDisabled(true);

        // 2. Start Tutorial (if enabled)
        if (isTutorialActive) {
            // Define what happens when user clicks "Exit Tutorial"
            const onTutorialExit = () => {
                isTutorialActive = false;
                if (jobResult) {
                    // If result is ready, load it immediately
                    loadResultToPlayer(jobResult);
                } else {
                    // If not ready, show status screen
                    ui.updateUIVisibility('status');
                }
            };

            await startTutorial(ui, playerDependencies, api, onTutorialExit);
        } else {
            ui.showStatusMessage('Uploading files...');
            ui.updateUIVisibility('status');
        }

        // 3. Start API Job (in background)
        const form = document.getElementById('translate-form');
        const formData = new FormData(form);
        const jobStartData = await api.submitJob(formData);

        if (!isTutorialActive) {
            ui.showStatusMessage('Processing... This may take several minutes.');
        }

        // 4. Poll for result
        const finalResult = await api.pollJobStatus(
            jobStartData.job_id,
            (status) => {
                if (!isTutorialActive) ui.showStatusMessage(status);
            }
        );

        // Store result
        jobResult = finalResult.result;
        // Inject job_id for download button later
        jobResult.job_id = jobStartData.job_id;

        // 5. Handle completion
        if (isTutorialActive) {
            // If tutorial is still running, update the overlay to show "Ready"
            ui.updateTutorialStatus('ready', () => {
                // Force exit tutorial logic, which will trigger loadResultToPlayer
                isTutorialActive = false;
                loadResultToPlayer(jobResult);
            });
        } else {
            // Normal flow
            loadResultToPlayer(jobResult);
        }

    } catch (error) {
        console.error("Form submission failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'An unknown error occurred.'}`);
        ui.setSubmitButtonDisabled(false);
        // Revert UI to status context on error
        ui.updateUIVisibility('status');
    }
}

/**
 * Handles the upload of a pre-generated .mtr (zip) file.
 * This function bypasses the API and constructs the final data object locally.
 * @param {File} mtrFile = The .mtr (zip) file.
 * @param {File} audioFile = The .wav audio file.
 * @param {object} ui - The UI module dependency.
 * @param {object} playerDependencies - The Player module dependency.
 * @param {object} api - The API module dependency (for tutorial loading).
 */
export async function handleLocalFileSubmit(mtrFile, audioFile, ui, playerDependencies, api) {
    if (!mtrFile || !audioFile) {
        console.warn("Local file submission called without both files.");
        return;
    }

    // JSZip must be loaded on the page
    if (typeof JSZip === 'undefined') {
        console.error("JSZip library not loaded.");
        ui.showStatusMessage("Error: File processing library is missing.");
        return;
    }

    // Check Preferences
    const disableTutorial = localStorage.getItem('beethoven_disable_tutorial') === 'true';
    let isTutorialActive = !disableTutorial;
    let localResult = null;

    // Helper to transition
    const loadResultToPlayer = (result) => {
        ui.hideTutorialOverlay();
        ui.updateUIVisibility('player');

        playerDependencies.initPlayer(result, () => {
            ui.updateUIVisibility('upload');
            ui.setSubmitButtonDisabled(false);
            if (result.audio_url) URL.revokeObjectURL(result.audio_url);
        }, playerDependencies);
    };

    try {
        ui.setSubmitButtonDisabled(true);
        ui.toggleDownloadButton(false);

        // 1. Start Tutorial (if enabled)
        if (isTutorialActive) {
            const onTutorialExit = () => {
                isTutorialActive = false;
                if (localResult) {
                    loadResultToPlayer(localResult);
                } else {
                    ui.updateUIVisibility('status');
                }
            };
            // Note: We need to pass 'ui' and 'playerDependencies' to
            // startTutorial. Assuming startTutorial is availble in this scope
            await startTutorial(ui, playerDependencies, api, onTutorialExit);
        } else {
            ui.showStatusMessage('Loading local file...');
            ui.updateUIVisibility('status');
        }

        // 2. Process File (Parallel)
        const jszip = new JSZip();
        const zip = await jszip.loadAsync(mtrFile);

        // Check if result.json exists before reading
        const resultFile = zip.file('result.json');
        if (!resultFile) {
            throw new Error("Invalid .mtr file: 'result.json' not found in the zip root.");
        }

        // Parse the main result.json file
        const resultText = await resultFile.async('string');
        const finalResult = JSON.parse(resultText);

        // --- VERSION CHECK ---
        const fileVersion = finalResult.app_version;
        if (!isVersionCompatible(fileVersion, APP_VERSION)) {
            throw new Error(`Version mismatch. File version: ${fileVersion || 'Unknown'}, App version: ${APP_VERSION}. Please use a compatible file.`);
        }
        console.log(`File version ${fileVersion} verified against App version ${APP_VERSION}`);

        // 3. Load audio from the separate file and create a local Blob URL
        finalResult.audio_url = URL.createObjectURL(audioFile);

        // Check if harmonic_static.json exists
        const harmonicStaticFile = zip.file('harmonic_static.json');
        if (!harmonicStaticFile) {
            throw new Error("Invalid .mtr file: 'harmonic_static.json' not found.");
        }

        // 4. Load the static harmonic data
        const staticText = await harmonicStaticFile.async('string');
        const staticData = JSON.parse(staticText);

        // 5. Re-create the logic from api.js's prepareFinalData
        const finalHarmonicData = {
            full_track_analysis: staticData.full_track_analysis,
            stem_analyses: {},
        };

        const trackDuration = staticData.full_track_analysis?.duration;
        if (typeof trackDuration !== 'number') {
            throw new Error("Static data did not provide a valid duration.");
        }
        const totalFrames = calculateTotalFrames(trackDuration);

        // 6. Load each NDJSON stream and create Accessors
        if (staticData.stem_analyses) {
            for (const instrument in staticData.stem_analyses) {
                const stemStaticData = staticData.stem_analyses[instrument];

                // Get the .ndjson filename from result.json
                const ndjsonFilename = finalResult.harmonic_analysis?.streaming_urls?.[instrument];

                if (!ndjsonFilename) {
                    console.warn(`No stream file path for $(instrument)`);
                    continue;
                }

                const zipStreamFile = zip.file(ndjsonFilename);
                if (zipStreamFile) {
                    const ndjsonString = await zipStreamFile.async('string');
                    // Parse the entire NDJSON string into an array
                    const ndjsonData = ndjsonString.trim().split('\n').map(JSON.parse);

                    // Pass the *full array* to the TimeSeriesAccessor.
                    const accessor = new TimeSeriesAccessor(ndjsonData, ndjsonData.length);

                    finalHarmonicData.stem_analyses[instrument] = {
                        temporal_features: stemStaticData,
                        stream_accessor: accessor,
                    };
                } else {
                    console.warn(`Stream file ${ndjsonFilename} missing from .mtr zip.`);
                }
            }
        }

        // 7. Create Accessor for Drum Hits (which are already in result.json)
        if (finalResult.drum_analysis?.hits && Array.isArray(finalResult.drum_analysis.hits)) {
            const hits = finalResult.drum_analysis.hits;
            finalResult.drum_analysis.hits_accessor = new TimeSeriesAccessor(hits, hits.length);
        }

        // 8. Assign the constructed data
        finalResult.harmonic_analysis = finalHarmonicData;
        localResult = finalResult; // Store result for tutorial callback

        console.log("Local file processed successfully:", finalResult);

        // 9. Handle Completion / Transition
        if (isTutorialActive) {
            // If tutorial is still running, update the overlay to show "Ready"
            ui.updateTutorialStatus('ready', () => {
                // Force exit tutorial logic, which will trigger loadResultToPlayer
                isTutorialActive = false;
                loadResultToPlayer(localResult);
            });
        } else {
            // Normal flow
            loadResultToPlayer(localResult);
        }

    } catch (error) {
        console.error("Local file submission failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'Could not read file.'}`);
        ui.setSubmitButtonDisabled(false);
        // Revert UI to upload/status so user isn't stuck on a broken player screen
        ui.updateUIVisibility('status');
    }
}

/**
 * Handles playing a song selected from the library.
 * It is structured very similarly to the local file submit handler,
 * but fetches the MTR buffer from the library endpoint instead.
 * @param {object} song - The song object from the library containing metadata and URLs.
 * @param {object} ui - The UI dependency.
 * @param {object} player - The Player dependency.
 * @param {object} api - The API dependency.
 */
export async function handleLibrarySongLoad(song, ui, player, api) {
    try {
        ui.updateUIVisibility('status');
        ui.showStatusMessage(`Loading ${song.title} from library...`);

        // Fetch MTR array buffer from backend
        const response = await fetch(song.mtr_url);
        if (!response.ok) {
            throw new Error(`Failed to fetch translation for ${song.title}`);
        }
        const mtrBuffer = await response.arrayBuffer();

        const zip = new JSZip();
        await zip.loadAsync(mtrBuffer);

        // 1. Validate version from result.json
        let finalResult = null;
        const resultZipEntry = zip.file('result.json');

        if (resultZipEntry) {
            const resultString = await resultZipEntry.async('string');
            finalResult = JSON.parse(resultString);

            const fileVersion = finalResult.app_version;
            if (!isVersionCompatible(fileVersion, APP_VERSION)) {
                throw new Error(`Version mismatch. File version: ${fileVersion || 'Unknown'}, App version: ${APP_VERSION}. Please use a compatible file.`);
            }
            console.log(`File version ${fileVersion} verified against App version ${APP_VERSION}`);
        } else {
            throw new Error('result.json is required but not found in .mtr file.');
        }

        // 2. Fetch the static Harmonic JSON file
        const staticZipEntry = zip.file('harmonic_static.json');
        let staticData = null;
        if (staticZipEntry) {
            const staticString = await staticZipEntry.async('string');
            staticData = JSON.parse(staticString);
        } else {
            console.warn("No 'harmonic_static.json' found. Harmonic visualizations may not be available.");
        }

        // 3. Assemble Harmonic Feature and Temporal Feature structs
        const finalHarmonicData = {
            full_track_analysis: staticData?.full_track_analysis || {},
            stem_analyses: {},
        };

        const trackDuration = finalHarmonicData.full_track_analysis?.duration;
        if (!trackDuration) {
            console.warn("Could not find full track duration. Accessors will fallback to item lengths.");
        }
        const totalFrames = calculateTotalFrames(trackDuration);

        // 4. Load each NDJSON stream
        if (staticData && staticData.stem_analyses) {
            for (const instrument in staticData.stem_analyses) {
                const stemStaticData = staticData.stem_analyses[instrument];
                const ndjsonFilename = finalResult.harmonic_analysis?.streaming_urls?.[instrument];

                if (!ndjsonFilename) {
                    console.warn(`No stream file path for ${instrument}`);
                    continue;
                }

                const zipStreamFile = zip.file(ndjsonFilename);
                if (zipStreamFile) {
                    const ndjsonString = await zipStreamFile.async('string');
                    const ndjsonData = ndjsonString.trim().split('\n').map(JSON.parse);
                    const accessor = new TimeSeriesAccessor(ndjsonData, ndjsonData.length);

                    finalHarmonicData.stem_analyses[instrument] = {
                        temporal_features: stemStaticData,
                        stream_accessor: accessor,
                    };
                } else {
                    console.warn(`Stream file ${ndjsonFilename} missing from .mtr zip.`);
                }
            }
        }

        // 5. Create Accessor for Drum Hits
        if (finalResult.drum_analysis?.hits && Array.isArray(finalResult.drum_analysis.hits)) {
            const hits = finalResult.drum_analysis.hits;
            finalResult.drum_analysis.hits_accessor = new TimeSeriesAccessor(hits, hits.length);
        }

        finalResult.harmonic_analysis = finalHarmonicData;
        finalResult.audio_url = song.audio_url; // Library uses direct URL, not an ObjectURL!

        console.log(`Library song loaded successfully: ${song.title}`);

        // 6. Init the player directly, no need for complex tutorial callbacks
        ui.updateUIVisibility('player');
        // Disable download button for library songs
        ui.toggleDownloadButton(false);
        player.initPlayer(finalResult, () => console.log('Library song ended'), player);

    } catch (error) {
        console.error("Library song load failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'Could not load song.'}`);
        ui.setSubmitButtonDisabled(false);
    }
}

/**
 * Main application initializer.
 * It accepts dependencies and sets up the event listener.
 * @param {object} ui - The UI module dependency.
 * @param {HTMLElement} formElement - The form to attach the listener to.
 * @param {object} api - The API module dependency.
 * @param {object} player - The Player module dependency.
 */
export async function init(ui, api, playerDependencies, formElement) {
    ui.cacheDOMElements();

    // Check auth status first and update the UI accordingly
    try {
        const authStatus = await api.checkAuthStatus();
        ui.updateAuthUI(authStatus);
    } catch (e) {
        // If the auth check itself fails, proceed is if logged out.
        console.error("Failed to initialize auth status:", e);
        ui.updateAuthUI({ isAuthenticated: false });
    }

    ui.updateUIVisibility('upload');

    // Library Navigation Button Listener
    const libraryBtn = document.getElementById('library-btn');
    if (libraryBtn) {
        libraryBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                ui.updateUIVisibility('status');
                ui.showStatusMessage('Fetching library catalog...');
                const libraryData = await api.fetchLibrary();
                const container = document.getElementById('library-ui-container');
                ui.renderLibrary(libraryData, container, (song) => {
                    handleLibrarySongLoad(song, ui, playerDependencies, api);
                });
                ui.updateUIVisibility('library');
            } catch (error) {
                console.error("Failed to load library:", error);
                ui.showStatusMessage('Error fetching library. Please try again later.');
            }
        });
    }

    // Tutorial Button Listener
    const tutorialBtn = document.getElementById('tutorial-btn');
    if (tutorialBtn) {
        tutorialBtn.addEventListener('click', () => {
            // Pass a simple exit callback that returns to upload screen
            startTutorial(ui, playerDependencies, api, () => {
                ui.hideTutorialOverlay();
                ui.updateUIVisibility('upload');
            });
        });
    }

    // Preference Listener
    const prefCheckbox = document.getElementById('disable-auto-tutorial');
    if (prefCheckbox) {
        // Init state from storage
        const isDisabled = localStorage.getItem('beethoven_disable_tutorial') === 'true';
        prefCheckbox.checked = isDisabled;

        prefCheckbox.addEventListener('change', (e) => {
            localStorage.setItem('beethoven_disable_tutorial', String(e.target.checked));
        });
    }

    // Listener for back-end processing
    if (formElement) {
        // We bind the dependencies to handleFormSubmit so they are available when the event fires.
        const boundHandler = (event) => handleFormSubmit(event, ui, api, playerDependencies);
        formElement.addEventListener('submit', boundHandler);
    } else {
        console.error("Form element not found for init");
    }

    // Listener for local file processing
    const localFileInput = document.getElementById('local-file-input');
    const localAudioInput = document.getElementById('local-audio-input');

    // This handler will check if both files are ready
    const localFileHandler = () => {
        const mtrFile = localFileInput?.files[0];
        const audioFile = localAudioInput?.files[0];

        if (mtrFile && audioFile) {
            // Both files are present, call the processor
            handleLocalFileSubmit(mtrFile, audioFile, ui, playerDependencies, api);

            // Clear the inputs so the user can upload a new set
            localFileInput.value = null;
            localAudioInput.value = null;
        }
    };

    if (localFileInput) {
        localFileInput.addEventListener('change', localFileHandler);
    } else {
        console.warn("Local file input (#local-file-input) not found.");
    }

    if (localAudioInput) {
        localAudioInput.addEventListener('change', localFileHandler);
    } else {
        console.warn("Local audio input (#local-audio-input) not found.");
    }
}

