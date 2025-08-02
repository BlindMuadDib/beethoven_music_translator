// --- Fundamental Frequency Tracker ---

/**
 * A pure function to find the F0 value for a specific instrument at a given time.
 * @param {Array<number|null>}f0Values - Array of F0 values
 * @param {Array,number.|null>}timesArray - Array of corresponding times.
 * @param {number} currentTime - The current time in seconds.
 * @param {number} timeIntervalThreshold - The tolerance for matching a time point.
 * @returns {number|null} - The F0 value, or null if not found.
 */
export function getF0ValueAtTime(f0Values, timesArray, currentTime, timeIntervalThreshold) {
    if (!f0Values || !timesArray || timesArray.length === 0 || f0Values.length !== timesArray.length) return null;

    // Efficient search for the index corresponding to currentTime
    // For simplicity, linear scan; for performance, binary search (if timesArray is sorted)
    let bestMatchIndex = -1;
    let minDiff = Infinity;

    for (let i = 0; i < timesArray.length; i++) {
        const diff = Math.abs(timesArray[i] - currentTime);
        if (diff < minDiff) {
            minDiff = diff;
            bestMatchIndex = i;
        }
    }
    if (bestMatchIndex !== -1 && minDiff <= timeIntervalThreshold) {
        return f0Values[bestMatchIndex]; // This can be null if F0 was not detected
    }
    return null; // No data point close enough or f0 is null
}

// A shared utility function for finding volume value at a specific time via interpolation
function getInterpolatedValue(data, currentTime) {
    if (!data || data.length === 0) return null;
    for (let i = 0; i < data.length - 1; i++) {
        const [t1, v1] = data[i];
        const [t2, v2] = data[i + 1];
        if (currentTime >= t1 && currentTime <= t2) {
            const timeDiff = t2 - t1;
            if (timeDiff === 0) return v1;
            const fraction = (currentTime - t1) / timeDiff;
            return v1 + fraction * (v2 - v1);
        }
    }
    if (currentTime < data[0][0]) return data[0][1];
    if (currentTime > data[data.length - 1][0]) return data[data.length - 1][1];
    return null;
}

export class F0Tracker {
    constructor(canvas, f0AnalysisData, instrumentVolumeData) {
        if (!canvas) throw new Error ("F0 canvas not provided!");
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.f0Data = f0AnalysisData || {};
        // --- Configuration ---
        this.config = {
            instrumentColors: { bass: 'purple', guitar: 'blue', other: 'orange', piano: 'green', vocals: 'red', default: 'grey' },
            activeInstruments: ['bass', 'guitar', 'other', 'piano', 'vocals'],
            legendWidth: 80, // px. for instrument names and Y-axis labels
            yAxisTicks: 4, // Number of F0 value lables on Y-axis
            defaultF0Min: 50, // Hz
            defaultF0Max: 1200, // Hz
            minRadius: 4, // Minimum visible radius for the ball
            baseDrawingPadding: 5, // Small buffer to avoid labels/balls being on the edge.
        };

        // --- State ---
        // Store calculated min/max for consistent drawing
        this.drawingF0Min = this.config.defaultF0Min;
        this.drawingF0Max = this.config.defaultF0Max;

        // --- Process and normalize intrument volume data ---
        this.volumeData = this.processIntrumentVolume(instrumentVolumeData);

        this.update(0); // Initial draw
    }

    processIntrumentVolume(instrumentVolumeData) {
        if (!instrumentVolumeData) return {};
        const processedData = {};
        for (const instrument of this.config.activeInstruments) {
            const data = instrumentVolumeData[instrument]?.rms_values;
            if (!data || data.length === 0) continue;

            const values = data.map(d => d[1]);
            const minRms = Math.min(...values);
            const maxRms = Math.max(...values);
            const range = maxRms - minRms;

            processedData[instrument] = {
                minRms, maxRms, // Store for debugging if needed
                values: data.map(([time, value]) => [time, range > 0 ? (value - minRms) / range : 0]),
            };
        }
        return processedData;
    }

    /**
     * Draws the state of the F0 tracker for a given time.
     * @param {number} currentTime
     */
    update(currentTime) {
        if (!this.ctx || !this.f0Data) return;

        // This ensures we have the correct size once the browser has rendered it
        if (this.canvas.width !== this.canvas.offsetWidth || this.canvas.height !== this.canvas.offsetHeight) {
            this.canvas.width = this.canvas.offsetWidth;
            this.canvas.height = this.canvas.offsetHeight;
        }

        // If width or height is still 0, don't try to draw
        if (!this.canvas.width || !this.canvas.height) {
            return;
        }

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        const drawAreaWidth = this.canvas.width - this.config.legendWidth;
        const numInstruments = this.config.activeInstruments.length;
        // Calculate horizontal spacing for balls within the drawAreaWidth
        const instrumentSpacing = drawAreaWidth / (numInstruments > 1 ? numInstruments : 2); // Avoid division by 1 if only one instrument
        const maxRadiusThisFrame = Math.max(this.config.minRadius, instrumentSpacing / 2);

        this.drawYAxis(maxRadiusThisFrame)

        this.config.activeInstruments.forEach((instrumentName, index) => {
            const instrumentF0Data = this.f0Data[instrumentName];
            this.drawLegend(instrumentName, index);
            if (!instrumentF0Data?.times) return;

            const currentF0 = getF0ValueAtTime(instrumentF0Data.f0_values, instrumentF0Data.times, currentTime, instrumentF0Data.time_interval || 0.1);
            if (currentF0 !== null && currentF0 >= this.drawingF0Min && currentF0 <= this.drawingF0Max) {
                // Default Volume if no data
                let normalizedVolume = 0.5;
                const instrumentVolumeData = this.volumeData[instrumentName];
                if (instrumentVolumeData) {
                    const vol = getInterpolatedValue(instrumentVolumeData.values, currentTime);
                    if (vol !== null) {
                        normalizedVolume = vol;
                    }
                }
                // Position ball horizontally
                const ballX = this.config.legendWidth + (index * instrumentSpacing) + (instrumentSpacing / 2);
                this.drawBall(instrumentName, ballX, currentF0, normalizedVolume, instrumentSpacing);
            }
        });
    }

    drawBall(instrument, x, f0, normalizedVolume, spacing) {
        // Calculate the maximum possible radius for any ball given current spacing
        const maxRadiusThisFrame = Math.max(this.config.minRadius, spacing / 2);
        // Use this to determine the consistent vertical offset
        const totalVerticalOffset = maxRadiusThisFrame + this.config.baseDrawingPadding;
        const effectiveCanvasHeight = this.canvas.height - (2 * totalVerticalOffset)

        // Map F0 to Y coordinate within the effective drawing height
        // Invert Y-axis: higher F0 should be lower Y value (closer to top)
        const y = totalVerticalOffset + (effectiveCanvasHeight - ((f0 - this.drawingF0Min) / (this.drawingF0Max - this.drawingF0Min)) * effectiveCanvasHeight);

        // Ensure spacing is a number to prevent NaN
        const validSpacing = typeof spacing === 'number' ? spacing : 10;
        const currentBallMaxRadius = (validSpacing / 2);
        // Ensure maxRadius is greater than minRadius before calculating range
        const radiusRange = Math.max(0, currentBallMaxRadius - this.config.minRadius);
        const radius = this.config.minRadius + (normalizedVolume * radiusRange);
        console.log(`[F0Tracker] Drawing ball for ${instrument}: F0=${f0.toFixed(1)}, Vol=${normalizedVolume.toFixed(2)}, Radius=${radius.toFixed(2)}`);

        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.fillStyle = this.config.instrumentColors[instrument] || this.config.instrumentColors.default;
        this.ctx.fill();
        this.ctx.closePath();
    }

    drawYAxis(maxRadiusForAxis) {
        const f0Min = this.drawingF0Min;
        const f0Max = this.drawingF0Max;

        const totalVerticalOffset = maxRadiusForAxis + this.config.baseDrawingPadding; // Start drawing Y-axis from this offset
        const drawAreaHeight = this.canvas.height - (2 * totalVerticalOffset); // Padding at top/bottom for labels

        // Draw Y-axis labels (F0 values) one time
        this.ctx.fillStyle = 'black';
        this.ctx.font = '10px sans-serif';
        this.ctx.textAlign = 'right';
        for (let i = 0; i < this.config.yAxisTicks; i++) {
            const val = f0Min + (i / (this.config.yAxisTicks - 1)) * (f0Max - f0Min);
            // Scale value to Y position: 0 Hz at bottom, max Hz at top of drawAreaHeight
            const yPos = totalVerticalOffset + drawAreaHeight - ((val - f0Min) / (f0Max - f0Min) * drawAreaHeight);

            this.ctx.fillText(val.toFixed(0) + "Hz", this.config.legendWidth - 10, yPos + 3); // +3 for text alignment, Hz for clarity
            // Draw light horizontal grid lines
            this.ctx.strokeStyle = '#eee';
            this.ctx.beginPath();
            this.ctx.moveTo(this.config.legendWidth, yPos);
            this.ctx.lineTo(this.canvas.width, yPos);
            this.ctx.stroke();
        }
    }

    drawLegend(instrumentName, index) {
        const yOffset = 10;
        const instrumentData = this.f0Data[instrumentName];
        this.ctx.textAlign = 'left';
        this.ctx.fillStyle = this.config.instrumentColors[instrumentName] || this.config.instrumentColors.default;
        const legendText = instrumentData ? instrumentName : `${instrumentName} (no data)`;
        this.ctx.fillText(legendText, 5, yOffset + 15 + index * 15);
    }
}

