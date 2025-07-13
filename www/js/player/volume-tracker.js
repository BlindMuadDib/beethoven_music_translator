/**
 * A utility function to find a value from a time-series array via interpolation.
 * @param {Array<[number, number]>} data - The time-series data, e.g., [[time, value], ...].
 * @param {number} currentTime - The current time to find the value for.
 * @return {number | null} The interpolated value or null if out of bounds.
 */
function getInterpolatedValue(data, currentTime) {
    if (!data || data.length === 0) return null;

    // Find the two points surrounding the current time
    for (let i = 0; i < data.length - 1; i++) {
        const [t1, v1] = data[i];
        const [t2, v2] = data[i + 1];

        if (currentTime >= t1 && currentTime <= t2) {
            // Linear interpolation: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
            const timeDiff = t2 - t1;
            if (timeDiff === 0) return v1; // Avoid division by zero
            const fraction = (currentTime - t1) / timeDiff
            return v1 + fraction * (v2 - v1);
        }
    }
    return null; // currentTime is out of the data's time range
}


export class VolumeTracker {
    /**
     * Manages the visualization of the overall song volume.
     * @param {string} canvasId - The ID of the canvas element for the overall volume bar.
     */
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas with id $(canvasId} not found.`);
        }
        this.ctx = this.canvas.getContext('2d');
        this.normalizedData = null;
    }

    /**
     * Processes and normalizes the raw overall RMS data from the backend.
     * @param {Array<[number, number]>} overallRmsData - The overall_rms array from the API.
     */
    setData(overallRmsData) {
        if (!overallRmsData || overallRmsData.length === 0) {
            this.normalizedData = null;
            return;
        }

        const values = overallRmsData.map(d => d[1]);
        const minRms = Math.min(...values);
        const maxRms = Math.max(...values);
        const range = maxRms - minRms;

        this.normalizedData = {
            values: overallRmsData.map(([time, value]) => {
                const normalized = range > 0 ? (value - minRms) / range : 0;
                return [time, normalized];
            }),
        };
    }

    /**
     * Updates the visualization to the given time.
     * @param {number} currentTime - The current time of the audio playback.
     */
    update(currentTime) {
        if (!this.normalizedData) return;

        const currentVolume = getInterpolatedValue(this.normalizedData.values, currentTime);
        if (currentVolume !== null) {
            this.draw(currentVolume);
        }
    }

    /**
     * Draws the overall volume bar on the canvas.
     * @param {number} normalizedVolume - The current volume level, from 0 to 1.
     */
    draw(normalizedVolume) {
        const { width, height } = this.canvas;
        this.ctx.clearRect(0, 0, width, height);

        // --- Draw Legend ---
        this.ctx.fillStyle = 'white';
        this.ctx.font = '12px Arial';
        this.ctx.textAlign = 'center';
        // Simple text rotation for vertical display
        this.ctx.save();
        this.ctx.translate(width / 2, height / 2);
        this.ctx.rotate(-Math.PI / 2);
        this.ctx.fillText('Relative Volume of Song', 0, 0);
        this.ctx.restore();

        // --- Draw Volume Bar ---
        const barWidth = width * 0.5 // Make the bar 50% of the canvas width
        const barX = (width - barWidth) / 2;
        const barHeight = height * normalizedVolume;
        const barY = height - barHeight;

        this.ctx.fillStyle = '#8A2BE2';
        this.ctx.fillRect(barX, barY, barWidth, barHeight);
    }
}
