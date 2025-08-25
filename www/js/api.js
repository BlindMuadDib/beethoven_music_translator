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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
    }

    return response.json();
}

/**
 * Polls the results endpoint until the job is finished or fails,
 * and upon completion, fetches the final harmonic data from its URL,
 * returning a single, complete result object.
 * Provides updates on the current processing stage
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

                    // Check for the harmonic analysis URL.
                    const harmonicUrl = data.result?.harmonic_analysis?.results_url;

                    if (harmonicUrl) {
                        console.log(`Job finished. Fetching harmonic data from ${harmonicUrl}...`);
                        try {
                            // Fetch the detailed harmonic data from the provided URL.
                            const harmonicResponse = await fetch(`/${harmonicUrl}`);
                            if (!harmonicResponse.ok) {
                                throw new Error(`Failed to fetch harmonic data. Status: ${harmonicResponse.status}`);
                            }
                            const harmonicData = await harmonicResponse.json();

                            // Replace the URL object with the actual data.
                            data.result.harmonic_analysis = harmonicData;

                            console.log("Harmonic data fetched and merged successfully.");
                            resolve(data); // Resolve with the complete, merged data.

                        } catch (fetchError) {
                            console.error("Could not fetch harmonic data:", fetchError);
                            // Reject the promise if the secondary fetch fails.
                            reject(fetchError);
                        }
                    } else {
                        // If there is no URL, resolve the data as-is.
                        resolve(data);
                    }
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    reject(new Error(data.message || 'The job failed.'));
                }
            } catch (error) {
                clearInterval(interval);
                reject(error);
            }
        }, 5000); // Poll every 5 seconds (adjust as needed)
    });
}

/**
 * Sends a request to the backend to delete a processed audio file.
 * @param {string} filename - The unique filename of the audio to delete.
 * @returns {Promise<void>}
 */
export async function deleteAudioFile(filename) {
    // We don't need to do anything with the response unless an error occurs.
    const response = await fetch(`/api/cleanup/${filename}`, {
        method: 'DELETE',
    });

    if (!response.ok) {
        // Log an error but don't block the user from navigating away.
        console.error(`Failed to delete audio file ${filename} on the server.`);
    }
}
