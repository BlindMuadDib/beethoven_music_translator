import { TimeSeriesAccessor } from './player/TimeSeriesAccessor.js'
import { calculateTotalFrames } from './utils.js';

/**
 * Handles the form submission.
 * @param {FormData} formData - The form data to submit.
 * @param {string} accessCode - The user's access code.
 * @returns {Promise<object>} - A promise that resolves to the job initiation data.
 */
export async function submitJob(formData, accessCode) {
    const response = await fetch(`/api/translate?access_code=${accessCode}`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        // Handle cases where error response is not JSON
        const errorData = await response.json().catch(() => ({
            error: `HTTP error! Status: ${response.status}`
        }));
        throw new Error(errorData.error);
    }

    return response.json();
}

/**
 * Polls the results endpoint until the job is finished or fails,
 * and upon completion prepares the final data structure.
 * Provides updates on the current processing stage.
 * @param {string} job_id - The ID of the job to poll, returned by back-end after initial job submission.
 * @param {function} onProgress - A callback function for progress updates.
 * @returns {Promise<object>} - A promise that resolves to the final job result data.
 */
export function pollJobStatus(job_id, onProgress) {
    return new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/results/${job_id}`);

            // Check for non-JSON responses or network errors first
                if (!response.ok) {
                    // Stop polling on server error
                    clearInterval(interval);
                    reject(new Error(`Error fetching results. Status: ${response.status}`));
                    return;
                }

                const data = await response.json();

                // Call the progress callback to update the UI
                if (typeof onProgress === 'function') {
                    onProgress(data);
                }

                if (data.status === 'finished') {
                    clearInterval(interval);
                    console.log("Job finished. Fetching and preparing all data...")

                    const finalResult = await prepareFinalData(data.result);
                    resolve({ ...data, result: finalResult }); // Resolve with enhanced result

                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    reject(new Error(data.message || 'The job failed.'));
                }
            } catch (error) {
                clearInterval(interval);
                const errorMessage = error instanceof Error ? error.message : String(error);
                reject(new Error(`Polling failed: ${errorMessage}`));
            }
        }, 5000); // Poll every 5 seconds (adjust as needed)
    });
}

/** Fetches static and streaming harmonic data and structures is for the
 * application.
 * @param {object} initialResult - The result object from the polling method.
 * @returns {Proimise<object>} The result object with harmonic data fully
 * resolved.
 */
async function prepareFinalData(initialResult) {
    // Fetch the static harmonic analysis file
    const harmonicInfo = initialResult.harmonic_analysis;
    if (!harmonicInfo || !harmonicInfo.static_results_url) {
        console.warn("No static harmonic results URL found.");
        return initialResult; // Return early if no harmonic data
    }

    const staticResponse = await fetch(`${harmonicInfo.static_results_url}`);
    if (!staticResponse.ok) {
        throw new Error("Failed to fetch static harmonic data.");
    }
    const staticData = await staticResponse.json();

    // Combine static and streaming data into the final structure
    const finalHarmonicData = {
        full_track_analysis: staticData.full_track_analysis,
        stem_analyses: {},
    };
    const initialFetchPromises = [];

    // Use the duration from the full track analysis as the canonical duration
    // for all stems.
    const trackDuration = staticData.full_track_analysis?.duration;
    if (typeof trackDuration !== 'number') {
        throw new Error("Full track analysis did not provide a valid duration.");
    }
    const totalFrames = calculateTotalFrames(trackDuration);

    if (staticData.stem_analyses) {
        for (const instrument in staticData.stem_analyses) {
            const stemStaticData = staticData.stem_analyses[instrument];
            if (stemStaticData && harmonicInfo.streaming_urls?.[instrument]) {
                const streamUrl = `/${harmonicInfo.streaming_urls[instrument]}`;
                const accessor = new TimeSeriesAccessor(streamUrl, totalFrames)

                finalHarmonicData.stem_analyses[instrument] = {
                    // Static data (tempo, beats, onsets) comes from the main JSON
                    temporal_features: stemStaticData,
                    // The raw NDJSON string is added for the visualizer to use
                    stream_accessor: accessor
                };

                // IMPORTANT: Kick off the fetch for the first chunk and add its promise to the array
                initialFetchPromises.push(accessor.ensureDataForTime(0));
            }
        }
    }

    // Process drum analysis data right away by passing the raw array into the
    // TimeSeriesAccessor
    if (initialResult.drum_analysis?.hits && Array.isArray(initialResult.drum_analysis.hits)) {
        const hits = initialResult.drum_analysis.hits;
        // Wrap the drum hits array in the TimeSeriesAccessor
        initialResult.drum_analysis.hits_accessor = new TimeSeriesAccessor(hits, hits.length);
    }

    console.log(`Waiting for initial data chunks for ${initialFetchPromises.length} instruments...`);
    await Promise.all(initialFetchPromises);
    console.log("Initial data chunks loaded.");

    initialResult.harmonic_analysis = finalHarmonicData;
    return initialResult;
}

/**
 * Sends a request to the backend to delete a processed audio file.
 * @param {string} filename - The unique filename of the audio to delete.
 * @returns {Promise<void>}
 */
export async function deleteAudioFile(filename) {
    try {
        // We don't need to do anything with the response unless an error occurs.
        const response = await fetch(`/api/cleanup/${filename}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            // Log an error but don't block the user from navigating away.
            console.error(`Failed to delete audio file ${filename} on the server.`);
        }
    } catch (error) {
        console.error(`Error during deletion of audio file ${filename}:`, error)
    }
}
