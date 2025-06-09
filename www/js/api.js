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
 * Polls the results endpoint until the job is finished or fails.
 * Provides updates on the current processing stage
 * @param {string} job_id - The ID of the job to poll, returned by back-end after initial job submission.
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
                    return reject(new Error(`Error fetching results. Status: ${response.status}`));
                }

                const data = await response.json();

                // Call the progress callback to update the UI
                if (typeof onProgress === 'function') {
                    onProgress(data);
                }

                if (data.status === 'finished') {
                    clearInterval(interval);
                    resolve(data); // Resolve the promise with the final data
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
