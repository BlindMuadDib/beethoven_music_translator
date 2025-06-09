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
        // If timesArray is sorted, we can potentially break early
        if (timesArray[i] > currentTime && minDiff <= timeIntervalThreshold) {
            break;
        }
    }

    if (bestMatchIndex !== -1 && minDiff <= timeIntervalThreshold) {
        return f0Values[bestMatchIndex]; // This can be null if F0 was not detected
    }
    return null; // No data point close enough or f0 is null
}

export class F0Tracker {
    // --- Configuration ---
    config = {
        instrumentColors: { bass: 'purple', guitar: 'blue', other: 'orange', piano: 'green', vocals: 'red', default: 'grey' },
        activeInstruments: ['vocals', 'guitar', 'bass', 'piano', 'other'], // Desired display order
        ballRadius: 6,
        legendWidth: 80, // px. for instrument names and Y-axis labels
        yAxisTicks: 4, // Number of F0 value lables on Y-axis
        defaultF0Min: 50, // Hz
        defaultF0Max: 1200 // Hz
    };

    // --- State ---
    ctx = null;
    f0Data = {};
    canvas = null;
    // Store calculated min/max for consistent drawing
    drawingF0Min = this.config.defaultF0Min;
    drawingF0Max = this.config.defaultF0Max;

    constructor(canvas, f0AnalysisData) {
        if (!canvas) throw new Error ("F0 canvas not provided!");
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.f0Data = f0AnalysisData || {};
        this.canvas.width = canvas.offsetWidth;
        this.canvas.height = canvas.offsetHeight;
        this.update(0); // Initial draw
    }

    /**
     * Draws the state of the F0 tracker for a given time.
     * @param {number} currentTime
     */
    update(currentTime) {
        if (!this.ctx || !this.f0Data) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const f0Min = this.drawingF0Min;
        const f0Max = this.drawingF0Max;
        const drawAreaWidth = this.canvas.width - this.config.legendWidth;
        const drawAreaHeight = this.canvas.height - 20; // Padding at top/bottom for labels
        const yOffset = 10; // Start drawing Y-axis from this offset

        const numInstruments = this.config.activeInstruments.length;
        // Calculate horizontal spacing for balls within the drawAreaWidth
        const ballHorizontalSpacing = drawAreaWidth / (numInstruments > 1 ? numInstruments : 2); // Avoid division by 1 if only one instrument

        this.config.activeInstruments.forEach((instrumentName, index) => {
            const instrumentData = this.f0Data[instrumentName];

            // Draw Y-axis labels (F0 values)
            this.ctx.fillStyle = 'black';
            this.ctx.font = '10px sans-serif';
            this.ctx.textAlign = 'right';
            for (let i = 0; i < this.config.yAxisTicks; i++) {
                const val = f0Min + (i / (this.config.yAxisTicks - 1)) * (f0Max - f0Min);
                // Scale value to Y position: 0 Hz at bottom, max Hz at top of drawAreaHeight
                const yPos = yOffset + drawAreaHeight - ((val - f0Min) / (f0Max - f0Min) * drawAreaHeight);

                this.ctx.fillText(val.toFixed(0) + "Hz", this.config.legendWidth - 10, yPos + 3); // +3 for text alignment, Hz for clarity
                // Draw light horizontal grid lines
                this.ctx.strokeStyle = '#eee';
                this.ctx.beginPath();
                this.ctx.moveTo(this.config.legendWidth, yPos);
                this.ctx.lineTo(this.canvas.width, yPos);
                this.ctx.stroke();
            }

            // Draw instrument F0 balls and legend
            this.config.activeInstruments.forEach((instrumentName, index) => {
                const instrumentDataArray = this.f0Data[instrumentName];

                if (instrumentDataArray && instrumentDataArray.times && instrumentDataArray.f0_values) {
                    const timeInterval = instrumentDataArray.time_interval || this.f0Data.time_interval || 0.2; // Get specific or global time-interval
                    const currentF0 = getF0ValueAtTime(instrumentDataArray.f0_values, instrumentDataArray.times, currentTime, timeInterval);

                    // Draw Legend Text (instrument name)
                    this.ctx.textAlign = 'left';
                    this.ctx.fillText(instrumentName, 5, yOffset + 15 + index * 15); // Stagger legend items

                    if (currentF0 !== null && currentF0 >= f0Min && currentF0 <= f0Max) {
                        // Position ball horizontally
                        const ballX = this.config.legendWidth + (index * ballHorizontalSpacing) + (ballHorizontalSpacing / 2);
                        const normalizedY = (currentF0 - f0Min) / (f0Max - f0Min);
                        // Position ball vertically based on F0 value
                        const ballY = yOffset + drawAreaHeight - (normalizedY * drawAreaHeight);

                        this.ctx.beginPath();
                        this.ctx.arc(ballX, ballY, this.config.ballRadius, 0, Math.PI * 2);
                        const ballColor = this.config.instrumentColors[instrumentName] || this.config.instrumentColors.default;
                        this.ctx.fillStyle = ballColor;
                        this.ctx.fill();
                        this.ctx.closePath();
                    }
                } else {
                    // Draw legend even if data is missing
                    this.ctx.fillStyle = this.config.instrumentColors.default;
                    this.ctx.textAlign = 'left';
                    this.ctx.fillText(instrumentName + " (no data)", 5, yOffset + 15 + index * 15);
                }
            })
        });
    }
}
