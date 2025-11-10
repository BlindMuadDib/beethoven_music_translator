/**
 * Calculates the total number of frames (time slices) for a given duration.
 * These values must match the backend analysis settings in analysis_functions.py
 * @param {number} duration - The duration of the audio in seconds
 * @returns {number} The total number of frames.
 */
export function calculateTotalFrames(duration) {
    // Ensure duration is a valid number before calculation
    if (typeof duration !== 'number' || !isFinite(duration) || duration < 0) {
        return 0;
    }
    const sr = 22050;
    const hop_length = 512;
    return Math.floor((duration * sr) / hop_length) + 1;
}
