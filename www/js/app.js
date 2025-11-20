// main app that brings all the front-end pieces together

import { TimeSeriesAccessor } from './player/TimeSeriesAccessor.js';
import { calculateTotalFrames } from './utils.js';

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

    try {
        ui.setSubmitButtonDisabled(true);
        ui.showStatusMessage('Uploading files...');
        ui.updateUIVisibility('status');

        const form = document.getElementById('translate-form');
        const formData = new FormData(form);

        const jobStartData = await api.submitJob(formData);
        ui.showStatusMessage('Processing... This may take several minutes.');

        const finalResult = await api.pollJobStatus(
            jobStartData.job_id, ui.showStatusMessage
        );

        // This is the ONLY place we interact with the player module
        playerDependencies.initPlayer(finalResult.result, () => {
            // This is the onStopAndReset callback function.
            // It tells the UI module what to do.
            ui.updateUIVisibility('upload');
            ui.setSubmitButtonDisabled(false);
        }, playerDependencies);

        // player.render(finalResult.result);
        ui.updateUIVisibility('player');

    } catch (error) {
        console.error("Form submission failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'An unknown error occurred.'}`);
        ui.setSubmitButtonDisabled(false);
    }
}

/**
 * Handles the upload of a pre-generated .mtr (zip) file.
 * This function bypasses the API and constructs the final data object locally.
 * @param {File} mtrFile = The .mtr (zip) file.
 * @param {File} audioFile = The .wav audio file.
 * @param {object} ui - The UI module dependency.
 * @param {object} playerDependencies - The Player module dependency.
 */
export async function handleLocalFileSubmit(mtrFile, audioFile, ui, playerDependencies) {
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

    try {
        ui.setSubmitButtonDisabled(true);
        ui.showStatusMessage('Loading local file...');
        ui.updateUIVisibility('status');

        const jszip = new JSZip();
        const zip = await jszip.loadAsync(mtrFile);

        // 1. Parse the main result.json file
        const resultText = await zip.file('result.json').async('string');
        const finalResult = JSON.parse(resultText);

        // 2. Load audio from the separate file and create a local Blob URL
        finalResult.audio_url = URL.createObjectURL(audioFile);

        // 3. Load the static harmonic data
        const staticText = await zip.file('harmonic_static.json').async('string');
        const staticData = JSON.parse(staticText);

        // 4. Re-create the logic from api.js's prepareFinalData
        const finalHarmonicData = {
            full_track_analysis: staticData.full_track_analysis,
            stem_analyses: {},
        };

        const trackDuration = staticData.full_track_analysis?.duration;
        if (typeof trackDuration !== 'number') {
            throw new Error("Static data did not provide a valid duration.");
        }
        const totalFrames = calculateTotalFrames(trackDuration);

        // 5. Load each NDJSON stream and create Accessors
        if (staticData.stem_analyses) {
            for (const instrument in staticData.stem_analyses) {
                const stemStaticData = staticData.stem_analyses[instrument];

                // Get the .ndjson filename from result.json or static data
                // Assuming it's stored in static data for this example
                // e.g., "streams/vocals.ndjson"
                const ndjsonFilename = stemStaticData.stream_file_path;

                if (!ndjsonFilename) {
                    console.warn(`No stream file path for $(instrument)`);
                    continue;
                }

                const ndjsonString = await zip.file(ndjsonFilename).async('string');
                // Parse the entire NDJSON string into an array
                const ndjsonData = ndjsonString.trim().split('\n').map(JSON.parse);

                // Pass the *full array* to the TimeSeriesAccessor.
                // Its constructor already supports this!
                const accessor = new TimeSeriesAccessor(ndjsonData, ndjsonData.length);

                finalHarmonicData.stem_analyses[instrument] = {
                    temporal_features: stemStaticData,
                    stream_accessor: accessor,
                };
            }
        }

        // 6. Create Accessor for Drum Hits (which are already in result.json)
        if (finalResult.drum_analysis?.hits && Array.isArray(finalResult.drum_analysis.hits)) {
            const hits = finalResult.drum_analysis.hits;
            finalResult.drum_analysis.hits_accessor = new TimeSeriesAccessor(hits, hits.length);
        }

        // 7. Assign the constructed data
        finalResult.harmonic_analysis = finalHarmonicData;

        console.log("Local file processed successfully:", finalResult);

        // 8. Initialize the player
        playerDependencies.initPlayer(finalResult, () => {
            ui.updateUIVisibility('upload');
            ui.setSubmitButtonDisabled(false);
            // Revoke the local URL to free up memory
            URL.revokeObjectURL(finalResult.audio_url);
        }, playerDependencies);

        ui.updateUIVisibility('player');

    } catch (error) {
        console.error("Local file submission failed:", error);
        ui.showStatusMessage(`Error: ${error.message || 'Could not read file.'}`);
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
            handleLocalFileSubmit(mtrFile, audioFile, ui, playerDependencies);

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

