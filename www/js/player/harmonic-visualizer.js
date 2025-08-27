// --- Harmonic Visualizer ---
// This module contains the main logic for drawing all the harmonic
// analysis data onto a canvas. It replaces the functionality of the
// old F0Tracker.

/**
 * A helper function to find the value for a given time via linear
 * interpolation.
 * @param {Array<Array<number>>} data - An array of [time, value] pairs.
 * @param {number} currentTime - The current time in seconds.
 * @returns {number|null} - The interpolated value, or null if out of bounds.
 */
function getInterpolatedValue(data, currentTime) {
    if (!data || data.length === 0) return null;
    if (currentTime < data[0][0]) return data[0][1];
    if (currentTime > data[data.length - 1][0]) return data[data.length - 1][1];

    for (let i = 0; i < data.length -1; i++) {
        const t1 = data[i][0];
        const v1 = data[i][1];
        const t2 = data[i + 1][0];
        const v2 = data[i + 1][1];

        if (currentTime >= t1 && currentTime <= t2) {
            const timeDiff = t2 -t1;
            if (timeDiff === 0) return v1;
            const fraction = (currentTime - t1) / timeDiff;
            return v1 + fraction * (v2 - v1);
        }
    }
    return null;
}

/**
 * A helper function to find the closest data index for a given time.
 * @param {Array<numer>}  times - An array of time stamps.
 * @param {number} currentTime - The current time in seconds.
 * @returns {number} - The index of the closest time, or 0 if out of bounds.
 */
function getClosestDataIndex(times, currentTime) {
    if (!times || times.length === 0) return 0;
    let index = times.findIndex(t => t > currentTime);
    return Math.max(0, index - 1);
}

/**
 * The main class for visualizing harmonic analysis data on a canvas.
 */
export class HarmonicVisualizer {
    /**
     * @param {HTMLCanvasElement} canvas - The canvas element to draw on.
     * @param {object} harmonicData - The full harmonic analysis data object.
     */
    constructor(canvas, harmonicData) {
        if (!canvas) throw new Error("Canvas element not provided.");
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.data = harmonicData;

        // Configuration and state
        this.config = {
            // Colors are generated dynamically based on spectral features
            baseSaturation: 80, // %
            baseLightness: 50, // %
            minRadius: 10,
            maxRadiusRatio: 0.45, // Max radius is 45% of column width
            minPadding: 10, // px, padding around the drawing area
            onsetItemDecay: 200, // ms for onset flash to fade
            beatItemDecay: 300, // ms for beat square to fade
            f0BallSizeRatio: 0.51, // F0 ball is 51% of the blob's max radius
            f0BallColor: 'gray',
            columnGap: 20, // px between columns
            // For interpolation and mapping
            spectralRolloffMax: 10000, // Hz, an educated guess for normalization
            spectralBandwidthMax: 5000, // Hz
            rmsMax: 1, // A guess for max RMS to normalize volume
            tempoLinePixelsPerBeat: 150, // px
            chromaRingWidth: 10, // px
        };

        //Dynamic state to track
        this.currentTime = 0;
        this.minimizedInstruments = [];
        this.instrumentOrder = Object.keys(this.data.stem_analyses);

        // Keep track of recent onsets and beats for visualization
        this.onsets = {};
        this.beats = {};

        // Initial drawing to set up the canvas
        this.resize();
        this.update(0);
    }

    /**
     * Resizes the canvas to match its displayed size.
     */
    resize() {
        if (this.canvas.width !== this.canvas.offsetWidth || this.canvas.height !== this.canvas.offsetHeight) {
            this.canvas.width = this.canvas.offsetWidth;
            this.canvas.height = this.canvas.offsetHeight;
        }
    }

    /**
     * Updates and draws the visualizer for the current time.
     * @param {number} currentTime - The current time in seconds.
     */
    update(currentTime) {
        this.resize();
        this.currentTime = currentTime;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const activeInstruments = this.instrumentOrder.filter(inst => !this.minimizedInstruments.includes(inst));
        const totalWidth = this.canvas.width;
        const columnWidth = (totalWidth - (this.config.columnGap * (activeInstruments.length - 1))) / activeInstruments.length;

        activeInstruments.forEach((instrumentName, index) => {
            const stemData = this.data.stem_analyses[instrumentName];
            if (!stemData) return;

            const columnX = (columnWidth + this.config.columnGap) * index;

            // Draw all the visual components for this instrument at the current time
            this.drawInstrumentColumn(
                columnX,
                columnWidth,
                instrumentName,
                stemData
            );
        });
    }

    /**
     * Draws the visual elements for a single instrument column.
     * @param {number} x - The x-coordinate of the column.
     * @param {number} width - The width of the column.
     * @param {string} instrumentName - The name of the instrument.
     * @param {object} stemData - The analysis data for the instrument.
     */
    drawInstrumentColumn(x, width, instrumentName, stemData) {
        const currentTime = this.currentTime;
        const analysisTimeMs = Math.floor(currentTime * 1000);

        // Draw moving tempo lines first
        this.drawTempoLines(x, width, stemData.temporal_features.tempo);

        // --- Data Retrieval & Interpolation ---
        const f0 = getInterpolatedValue(
            stemData.f0_data.f0_values.map((v, i) => [stemData.f0_data.times[i], v]),
            currentTime
        );

        // Use the common spectral times for all time-aligned features
        const specTimes = stemData.spectral_features.times;
        const specIndex = getClosestDataIndex(specTimes, currentTime);

        const rms = stemData.spectral_features.rms[0]?.[specIndex] || 0;
        const spectralCentroid = stemData.spectral_features.spectral_centroid?.[specIndex]?.[0] || 0;
        const spectralBandwidth = stemData.spectral_features.spectral_bandwidth?.[specIndex]?.[0] || 0;
        const spectralRolloff = stemData.spectral_features.spectral_rolloff?.[specIndex]?.[0] || 0;
        const spectralFlatness = stemData.spectral_features.spectral_flatness?.[specIndex]?.[0] || 0;

        // Use the accessor to get ONLY the current slice because spectrogram
        // data is immense
        const spectrogramAccessor = stemData.spectral_features.spectrogram;
        const spectrogramSlice = spectrogramAccessor ? spectrogramAccessor.getSlice(specIndex) : [];

        const frequencies = stemData.spectral_features.frequencies;
        const chromaStft = stemData.timbral_features.chroma_stft[specIndex] || [];
        const mfccs = stemData.timbral_features.mfccs[specIndex] || [];

        // --- Visualization Logic ---

        // Calculate the color (Hue, Saturation, Lightness)
        const hue = this.mapValueToHue(spectralRolloff, this.config.spectralRolloffMax);
        const saturation = this.mapValueToSaturation(spectralBandwidth, this.config.spectralBandwidthMax);
        const lightness = this.config.baseLightness;
        const color = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.8)`;

        // Calculate the size and position of the blob
        const maxRadius = width * this.config.maxRadiusRatio;
        const radius = this.mapValueToRadius(rms, maxRadius);
        const centerX = x + width / 2;
        const centerY = this.canvas.height / 2;

        // Draw the main blob using spectrogram and spectral data
        if (f0 && f0 > 0) {
            this.drawBlob(
                centerX,
                radius,
                color,
                f0,
                spectralCentroid,
                spectralBandwidth,
                spectralFlatness,
                spectrogramSlice,
                frequencies,
                mfccs
            );
        } else {
            // Draw a simple circle when no F0 is detected
            this.drawBlobSimple(
                centerX,
                radius,
                color,
                spectralCentroid,
                spectralBandwidth,
                spectralFlatness,
                spectrogramSlice,
                frequencies,
                mfccs
            );
        }

        // Draw the Chroma STFT halo
        this.drawChromaHalo(centerX, centerY, radius, chromaStft);

        // Draw the temporal effects (onsets & beats)
        this.drawTemporalEffects(centerX, width, stemData, analysisTimeMs);
    }

    /**
     * Maps a spectral roll-off value to a hue in HSL space.
     * @param {number} value - The spectral roll-off value.
     * @param {number} max - The max value for normalization.
     * @returns {number} - The hue value (0-360)
     */
    mapValueToHue(value, max) {
        // High roll-off (brighter) -> Blue/Violet (240-300)
        // Low roll-off (dull) -> Red/Orange (0-60)
        const normalized = Math.min(1, Math.max(0, value / max));
        return 240 - (normalized * 240); // 240 (blue) to 0 (red)
    }

    /**
     * Maps a spectral bandwidth value to a saturation in HSL space.
     * @param {number} value - The spectral bandwidth value.
     * @param {number} max - The max value for normalization.
     * @returns {number} - The saturation value (%).
     */
    mapValueToSaturation(value, max) {
        // High bandwidth (noisy) -> High saturation
        // Low bandwidth (pure) -> Low saturation
        const normalized = Math.min(1, Math.max(0, value / max));
        return this.config.baseSaturation * normalized + 20; // Ensure it's not completely gray
    }

    /**
     * Maps a frequency value to a normalized y-position (0-1).
     * @param {number} frequency - The frequency in Hz.
     * @param {Array<number>} frequencies - The frequency bins array.
     * @returns {number} - The normalized Y position (0 = top, 1 = bottom).
     */
    mapValueToNormalizedY(frequency, frequencies) {
        const minFreq = frequencies[0] || 0;
        const maxFreq = frequencies[frequencies.length - 1] || 22050;
        return (frequency - minFreq) / (maxFreq - minFreq);
    }

    /**
     * Maps an RMS value to a radius for the blob.
     * @param {number} rms - The Root Mean Square value (volume).
     * @param {number} maxRadius - The maximum possible radius for this column.
     * @returns {number} - The radius of the blob.
     */
    mapValueToRadius(rms, maxRadius) {
        const normalizedRms = Math.min(1, Math.max(0, rms / this.config.rmsMax));
        return Math.max(this.config.minRadius, normalizedRms * maxRadius);
    }

    /**
     * Draws the main blob for an instrument using spectrogram data
     * and mfccs.
     * @param {number} x - Center x-coordinate.
     * @param {number} radius - Radius of the blob.
     * @param {string} color - The HSLA color string.
     * @param {number} f0 - The fundamental frequency.
     * @param {number} spectralCentroid - The spectral centroid.
     * @param {number} spectralBandwidth - The spectral bandwidth.
     * @param {number} spectralFlatness - The spectral flatness
     * @param {Array<number>} spectrogram - Spectrogram data for the current time.
     * @param {Array<number>} frequencies - Frequency bins corresponding to the spectrogram.
     * @param {Array<number>} mfccs - MFCCs for internal animation.
     */
    drawBlob(x, radius, color, f0, spectralCentroid, spectralBandwidth, spectralFlatness, spectrogram, frequencies, mfccs) {
        // Find the y-position based on f0
        const normalizedF0 = this.mapValueToNormalizedY(f0, frequencies);
        const f0_y = this.canvas.height - (normalizedF0 * this.canvas.height);

        // Find y-position for spectral centroid
        const normalizedCentroid = this.mapValueToNormalizedY(spectralCentroid, frequencies);
        const centroid_y = this.canvas.height - (normalizedCentroid * this.canvas.height);

        this.ctx.beginPath();
        this.createDynamicPath(x, spectrogram, frequencies, radius, spectralFlatness)
        this.ctx.closePath();
        this.ctx.fillStyle = color;
        this.ctx.fill();

        // Draw the internal MFCC texture
        this.drawMfccTexture(x, centroid_y, radius, mfccs);

        // Draw the F0 ball on top
        this.drawF0Ball(x, f0_y, radius * this.config.f0BallSizeRatio, f0);
    }

    /**
     * Draw a vertical blob when no F0 is detected.
     * @param {number} x - Center x-coordinate.
     * @param {number} radius - Radius of the blob.
     * @param {string} color - The HSLA color string.
     * @param {number} spectralCentroid - The spectral centroid.
     * @param {number} spectralFlatness - The spectral flatness.
     * @param {Array<number>} spectrogram - Spectrogram data for the current time.
     * @param {Array<number>} frequencies - Frequency bins corresponding to the spectrogram.
     * @param {Array<number>} mfccs - MFCCs for internal animation.
     */
    drawBlobSimple(x, radius, color, spectralCentroid, spectralFlatness, spectrogram, frequencies, mfccs) {
        // Find y-position for spectral centroid
        const normalizedCentroid = this.mapValueToNormalizedY(spectralCentroid, frequencies);
        const centroid_y = this.canvas.height - (normalizedCentroid * this.canvas.height);

        this.ctx.beginPath();
        this.createDynamicPath(x, spectrogram, frequencies, radius, spectralFlatness);
        this.ctx.closePath();
        this.ctx.fillStyle = color;
        this.ctx.fill();

        // Draw the internal MFCC texture
        this.drawMfccTexture(x, centroid_y, radius, mfccs)
    }

    /**
     * Creates a dynamic path for the blob. High flatness results in a
     * jagged path.
     * @param {number} x - Center x-coordinate.
     * @param {Array<number>} spectrogram - Determines ebb and flow of blob.
     * @param {Array<number>} frequencies - The corresponding frequency bins.
     * @param {number} radius - Base radius.
     * @param {number} flatness - Spectral flatness value (0-1)
     */
    createDynamicPath(x, spectrogram, frequencies, radius, flatness) {
        if (!spectrogram || spectrogram.length === 0) return;

        const randomness = flatness * 50; // Randomness increases with flatness
        const maxAmplitude = Math.max(...spectrogram) || 1;

        // Use a static seed for consistent jitter per time step
        const seed = Math.floor(this.currentTime * 100);
        const rand = (s) => {
            s = Math.sin(s) * 10000;
            return s - Math.floor(s);
        };

        // Draw the bottom point
        this.ctx.moveTo(x, this.canvas.height - (this.mapValueToNormalizedY(frequencies[frequencies.length - 1], frequencies) * this.canvas.height));

        // Draw the right side of the blob (from top to bottom)
        for (let i = spectrogram.length - 1; i >= 0; i--) {
            const freq = frequencies[i];
            const amplitude = spectrogram[i];
            const normalizedY = this.mapValueToNormalizedY(freq, frequencies);
            const currentY = this.canvas.height - (normalizedY * this.canvas.height);

            const amplitudeRadius = radius * (amplitude / maxAmplitude);
            const jitter = (rand(seed + i) - 0.5) * 2 * randomness;
            const finalRadius = amplitudeRadius + jitter;

            this.ctx.lineTo(x + finalRadius, currentY);
        }

        // Draw the left side of the blob (from bottom to top)
        for (let i = 0; i < spectrogram.length; i++) {
            const freq = frequencies[i];
            const amplitude = spectrogram[i];
            const normalizedY = this.mapValueToNormalizedY(freq, frequencies);
            const currentY = this.canvas.height - (normalizedY * this.canvas.height);

            const amplitudeRadius = radius * (amplitude / maxAmplitude);
            const jitter = (rand(seed + i) - 0.5) * 2 * randomness;
            const finalRadius = amplitudeRadius + jitter;

            this.ctx.lineTo(x - finalRadius, currentY);
        }
    }

    /**
     * Draws a polygon texture inside the blob based on all 13 MFCCs.
     * @param {number} x - Center x-coordinate.
     * @param {number} y - Center y-coordinate.
     * @param {number} radius - Base radius of the texture.
     * @param {Array<number>} mfccs - The 13 MFCC coefficients.
     */
    drawMfccTexture(x, y, radius, mfccs) {
        if (!mfccs || mfccs.length < 13) return;

        this.ctx.save();
        this.ctx.clip(); // Constrain the drawing to the blob's shape

        const maxMfcc = Math.max(...mfccs.map(Math.abs)) || 1;
        const numShapes = 8 + Math.round(Math.abs(mfccs[0]) / maxMfcc * 12); // Between 8 and 20 shapes

        for (let j = 0; j < numShapes; j++) {
            this.ctx.globalAlpha = 0.1 + (j / numShapes * 0.1); // Fade out to create depth

            const shapeRadius = radius * (0.1 + Math.abs(mfccs[j % 13]) / maxMfcc * 0.9);
            const numVertices = 3 + Math.round(Math.abs(mfccs[(j + 1) % 13]) / maxMfcc * 7); // 3 to 10 vertices
            const rotation = mfccs[(j + 2) % 13] * Math.PI;
            const offsetX = x + Math.cos(j / numShapes * Math.PI * 2) * (radius * 0.5);
            const offsetY = y + Math.sin(j / numShapes * Math.PI * 2) * (radius * 0.5);

            this.ctx.beginPath();
            for (let i = 0; i < numVertices; i++) {
                const angle = (Math.PI * 2 / numVertices) * i + rotation;
                const px = offsetX + shapeRadius * Math.cos(angle);
                const py = offsetY + shapeRadius * Math.sin(angle);

                if (i === 0) {
                    this.ctx.moveTo(px, py);
                } else {
                    this.ctx.lineTo(px, py);
                }
            }
            this.ctx.closePath();
            this.ctx.fillStyle = `hsla(${this.mapValueToHue(mfccs[(j + 3) % 13], maxMfcc)}, 70%, 80%, 0.5)`;
            this.ctx.fill();
        }

        this.ctx.restore();
    }

    /**
     * Draws a 12-segment ring around the blob for chroma STFT visualization.
     * @param {number} x - Center x-coordinate.
     * @param {number} y - Center y-coordinate.
     * @param {number} radius - The radius of the blob (inner ring).
     * @param {Array<number>} chromaStft - The 12-element chroma vector.
     */
    drawChromaHalo(x, y, radius, chromaStft) {
        if (!chromaStft || chromaStft.length !== 12) return;

        const innerRadius = radius + 5;
        const outerRadius = innerRadius + this.config.chromaRingWidth;

        for (let i = 0; i < 12; i++) {
            const chromaValue = chromaStft[i];
            if (chromaValue > 0) {
                const startAngle = (Math.PI * 2) / 12 * i - Math.PI / 2;
                const endAngle = (Math.PI * 2) / 12 * (i + 1) - Math.PI / 2;

                const opacity = Math.min(1, chromaValue * 2); // Amplify for visibility
                this.ctx.fillStyle = `hsla(180, 100%, 80%, ${opacity})`; // A consistent color for all chromas

                this.ctx.beginPath();
                this.ctx.arc(x, y, outerRadius, startAngle, endAngle);
                this.ctx.arc(x, y, innerRadius, endAngle, startAngle, true);
                this.ctx.closePath();
                this.ctx.fill();
            }
        }
    }

    /**
     * Draws the F0 ball on top of the blob.
     * @param {number} x - Center x-coordinate.
     * @param {number} y - Center y-coordinate.
     * @param {number} radius - Radius of the F0 ball.
     * @param {number} f0 - The fundamental frequency value.
     */
    drawF0Ball(x, y, radius) {
        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.Pi * 2);
        this.ctx.fillStyle = this.config.f0BallColor;
        this.ctx.fill();
        this.ctx.closePath();
    }

    /** Draws the temporal effects like onsets and beats.
     * @param {number} x - Center x-coordinate of the column.
     * @param {number} width - Width of the column.
     * @param {object} stemData - The analysis data for the instrument.
     * @param {number} analysisTimeMs - The current time in milliseconds.
     */
    drawTemporalEffects(x, width, stemData, analysisTimeMs) {
        // Handle Onsets
        if (stemData.temporal_features.onsets) {
            for (const onsetTime of stemData.temporal_features.onsets) {
                const onsetMs = Math.round(onsetTime * 1000);
                const timeDiff = analysisTimeMs - onsetMs;
                if (timeDiff >= 0 && timeDiff <= this.config.onsetTimeDecay) {
                    const opacity = 1 - (timeDiff / this.config.onsetItemDecay);
                    this.ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
                    this.ctx.fillRect(x - (width * 0.05), this.canvas.height / 2 - width / 2, width * 0.1, width);
                }
            }
        }

        // Handle Beats
        if (stemData.temporal_features.beats) {
            for (const beatTime of stemData.temporal_features.beats) {
                const beatMs = Math.round(beatTime * 1000);
                const timeDiff = analysisTimeMs - beatMs;
                if (timeDiff >= 0 && timeDiff <= this.config.beatItemDecay) {
                    const opacity = 1 - (timeDiff / this.config.beatItemDecay);
                    this.ctx.fillStyle = `rgba(200, 200, 200, ${opacity})`;
                    const squareSize = width * 0.2;
                    this.ctx.fillRect(x - squareSize/2, this.canvas.height / 2 - squareSize/2, squareSize, squareSize);
                }
            }
        }
    }

    /**
     * Draws moving tempo lines for the entire canvas.
     * @param {number} columnX - The x-coordinate of the column.
     * @param {number} columnWidth - The width of the column.
     * @param {number} tempo - The tempo in BPM.
     */
    drawTempoLines(columnX, columnWidth, tempo) {
        this.ctx.save();
        const beatsPerSecond = tempo / 60;
        const timePerBeat = 1 / beatsPerSecond;
        const pixelsPerBeat = this.config.tempoLinePixelsPerBeat;

        const scrollOffset = (this.currentTime % timePerBeat) / timePerBeat * pixelsPerBeat;

        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;

        for (let x = columnX - scrollOffset; x < columnX + columnWidth; x += pixelsPerBeat) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.canvas.height);
            this.ctx.stroke();
        }
        this.ctx.restore();
    }
}
