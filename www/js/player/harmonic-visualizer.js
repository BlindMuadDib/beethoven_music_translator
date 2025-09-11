// --- Harmonic Visualizer ---
// This module contains the main logic for drawing all the harmonic
// analysis data onto a canvas. It replaces the functionality of the
// old F0Tracker.

import { TimeSeriesAccessor } from "./TimeSeriesAccessor.js";

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
    return Math.max(0, index === -1 ? times.length - 1 : index - 1);
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
        this.axisContainer = document.getElementById('frequency-axis');
        this.chromaKeyContainer = document.getElementById('chroma-key');
        this.isBuffering = false;

        // Create accessors for each instrument's stream
        this.streamAccessors = {};
        if (this.data && this.data.stem_analyses) {
            for (const instrumentName in this.data.stem_analyses) {
                const stemData = this.data.stem_analyses[instrumentName];
                if (stemData && stemData.stream_accessor) {
                    this.streamAccessors[instrumentName] = stemData.stream_accessor;
                }
            }
        }

        // Pre-fetch the first chunk of data for immediate playback
        Object.values(this.streamAccessors).forEach(accessor => accessor.ensureDataForTime(0));

        // Configuration and state
        this.config = {
            // Colors are generated dynamically based on spectral features
            baseSaturation: 80, // %
            baseLightness: 50, // %
            minBlobWidth: 5,
            maxBlobWidthRatio: 1,
            blobWidthScale: 3, // Multiplier to make blobs thicker and more visible
            minPadding: 10, // px, padding around the drawing area
            onsetItemDecay: 100, // ms for onset flash to fade
            beatItemDecay: 100, // ms for beat square to fade
            f0BallSizeRatio: 0.51, // F0 ball is 51% of the blob's max radius
            f0BallColor: 'gray',
            columnGap: 2, // px between columns
            // For interpolation and mapping
            spectralRolloffMax: 10000, // Hz, an educated guess for normalization
            spectralBandwidthMax: 5000, // Hz
            rmsMax: 1, // A guess for max RMS to normalize volume
            tempoLinePixelsPerBeat: 150, // px
            chromaRingWidth: 10, // px
            labelFont: '14px sans-serif'
        };

        //Dynamic state to track
        this.currentTime = 0;
        this.minimizedInstruments = [];
        this.instrumentOrder = this.data.stem_analyses ? Object.keys(this.data.stem_analyses) : [];

        // Add a ResizeObserver to automatically handle canvas sizing and redraws.
        const resizeObserver = new ResizeObserver(() => this.resize());
        resizeObserver.observe(this.canvas);

        // Initial drawing to set up the canvas
        this.drawFrequencyAxis();
        this.drawChromaKey();
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
        // Redraw with current time whenever the size changes
        this.drawFrequencyAxis();
        this.drawChromaKey();
        this.update(this.currentTime);
    }

    /**
     * Updates and draws the visualizer for the current time.
     * @param {number} currentTime - The current time in seconds.
     */
    update(currentTime) {
        if (this.canvas.width === 0 || this.canvas.height === 0) {
            return; // Don't draw if the canvas isn't visible
        }

        this.currentTime = currentTime;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.isBuffering) {
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            this.ctx.font = '18px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('Buffering visuals...', this.canvas.width / 2, this.canvas.height / 2);
            return;
        }

        const activeInstruments = this.instrumentOrder.filter(inst => !this.minimizedInstruments.includes(inst));
        if (activeInstruments.length === 0) return;

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
            this.drawInstrumentLabel(instrumentName, columnX, columnWidth);
        });
    }

    /**
     * Checks if data for a specific time is available for all instruments.
     * @param {number} time - The time in seconds.
     * @returns {boolean} - True if all data is loaded.
     */
    isDataAvailableForTime(time) {
        for (const instrumentName in this.streamAccessors) {
            if (!this.streamAccessors[instrumentName].isDataAvailableForTime(time)) {
                return false;
            }
        }
        return true;
    }

    /**
     * Ensures data for a specific time is loaded for all instruments.
     * @param {number} time - The time in seconds.
     * @returns {Promise<void>} - A proimise that resolves when all data is loaded.
     */
    ensureDataForTime(time) {
        const promises = Object.values(this.streamAccessors)
            .map(accessor => accessor.ensureDataForTime(time));
        return Promise.all(promises);
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

        // Retrieve the data
        const accessor = this.streamAccessors[instrumentName];
        if (!accessor) return; // Don't draw if there's no stream data

        const timeSlice = accessor.getElementAtTime(this.currentTime);
        if (!timeSlice) {
            // Data for this time isn't loaded yet. Could draw a loading indicator here.
            return;
        }

        // Extract features from the parsed time slice
        const {
            f0_data: f0,
            rms,
            spectral_centroid: spectralCentroid,
            spectral_bandwidth: spectralBandwidth,
            spectral_rolloff: spectralRolloff,
            spectral_flatness: spectralFlatness,
            frequencies,
            spectrogram: spectrogramSlice,
            chroma_stft: chromaStft,
            mfccs,
        } = timeSlice;

        // Draw moving tempo lines first
        this.drawTempoLines(x, width, stemData.temporal_features.tempo);

        // --- Visualization Logic ---
        // Calculate the color (Hue, Saturation, Lightness)
        const hue = this.mapValueToHue(spectralRolloff, this.config.spectralRolloffMax);
        const saturation = this.mapValueToSaturation(spectralBandwidth, this.config.spectralBandwidthMax);
        const lightness = this.config.baseLightness;
        const color = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.8)`;

        // Calculate the size and position of the blob
        const maxBlobWidth = width * this.config.maxBlobWidthRatio;
        const blobWidth = this.mapValueToBlobWidth(rms, maxBlobWidth);
        const centerX = x + width / 2;
        const centerY = this.canvas.height / 2;

        // Draw the main blob using spectrogram and spectral data
        if (f0 && f0 > 0) {
            this.drawBlob(
                centerX,
                blobWidth,
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
                blobWidth,
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
        this.drawChromaHoops(centerX, centerY, blobWidth, chromaStft);

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
    mapValueToLogNormalizedY(frequency, minFreq = 20, maxFreq = 20000) {
        if (frequency <= minFreq) return 0;
        if (frequency >= maxFreq) return 1;

        const logMin = Math.log(minFreq);
        const logMax = Math.log(maxFreq);
        const logFreq = Math.log(frequency);

        return (logFreq - logMin) / (logMax - logMin);
    }

    /**
     * Maps an RMS value to a radius for the blob.
     * @param {number} rms - The Root Mean Square value (volume).
     * @param {number} maxBlobWidth - The maximum possible width for this column.
     * @returns {number} - The width of the blob's peak amplitude.
     */
    mapValueToBlobWidth(rms, maxRadius) {
        const normalizedRms = Math.min(1, Math.max(0, rms / this.config.rmsMax));
        return Math.max(this.config.minBlobWidth, normalizedRms * maxRadius);
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
        const normalizedF0 = this.mapValueToLogNormalizedY(f0, frequencies);
        const f0_y = this.canvas.height - (normalizedF0 * this.canvas.height);

        // Find y-position for spectral centroid
        const normalizedCentroid = this.mapValueToLogNormalizedY(spectralCentroid, frequencies);
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
        const normalizedCentroid = this.mapValueToLogNormalizedY(spectralCentroid, frequencies);
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
        if (!Array.isArray(spectrogram) || spectrogram.length === 0) return;

        const randomness = flatness * 50; // Randomness increases with flatness
        const maxAmplitude = Math.max(...spectrogram) || 1;

        // Use a static seed for consistent jitter per time step
        const seed = Math.floor(this.currentTime * 100);
        const rand = (s) => {
            s = Math.sin(s) * 10000;
            return s - Math.floor(s);
        };

        // Draw the bottom point
        const firstFreqY = this.canvas.height - (this.mapValueToLogNormalizedY(frequencies[0]) * this.canvas.height)
        this.ctx.moveTo(x, firstFreqY);

        // Draw the left side of the blob (from bottom to top)
        for (let i = 0; i < spectrogram.length; i++) {
            const freq = frequencies[i];
            const amplitude = spectrogram[i];
            const normalizedY = this.mapValueToLogNormalizedY(freq);
            const currentY = this.canvas.height - (normalizedY * this.canvas.height);

            const amplitudeRadius = radius * (amplitude / maxAmplitude);
            const jitter = (rand(seed + i) - 0.5) * 2 * randomness;
            let finalRadius = (amplitudeRadius + jitter) * this.config.blobWidthScale;
            finalRadius = Math.min(radius, finalRadius); // Clamp to maxBlobWidth

            this.ctx.lineTo(x - finalRadius, currentY);
        }

        // Draw the right side of the blob (from top to bottom)
        for (let i = spectrogram.length - 1; i >= 0; i--) {
            const freq = frequencies[i];
            const amplitude = spectrogram[i];
            const normalizedY = this.mapValueToLogNormalizedY(freq);
            const currentY = this.canvas.height - (normalizedY * this.canvas.height);

            const amplitudeRadius = radius * (amplitude / maxAmplitude);
            const jitter = (rand(seed + i) - 0.5) * 2 * randomness;
            let finalRadius = (amplitudeRadius + jitter) * this.config.blobWidthScale;
            finalRadius = Math.min(radius, finalRadius); // Clamp to maxBlobWidth

            this.ctx.lineTo(x + finalRadius, currentY);
        }

    }

    /**
     * Draws a polygon texture inside the blob based on all 13 MFCCs.
     * @param {number} x - Center x-coordinate.
     * @param {number} y - Center y-coordinate.
     * @param {number} radius - Base radius of the texture.
     * @param {Array<number>} mfccs - The 20 MFCC coefficients.
     */
    drawMfccTexture(x, y, radius, mfccs) {
        if (!mfccs || mfccs.length < 13) return;

        this.ctx.save();
        this.ctx.clip(); // Constrain the drawing to the blob's shape

        const maxMfcc = Math.max(...mfccs.map(Math.abs)) || 1;
        const numShapes = 8 + Math.round(Math.abs(mfccs[0]) / maxMfcc * 12); // Between 8 and 20 shapes

        for (let j = 0; j < numShapes; j++) {
            this.ctx.globalAlpha = 0.2 + (j / numShapes) * 0.3; // Fade out to create depth

            const shapeRadius = radius * (0.1 + Math.abs(mfccs[j % 20]) / maxMfcc * 0.8);
            const rotation = mfccs[(j + 2) % 20] * Math.PI;
            const offsetX = x + (mfccs[(j + 2) % 20] / maxMfcc) * (radius * 0.4);
            const offsetY = y + (mfccs[(j + 3) % 20] / maxMfcc) * (radius * 0.4);
            const hue = (mfccs[(j + 6) % 20] / maxMfcc) * 360;

            this.ctx.beginPath();
            const shapeType = j % 4;

            if (shapeType !== 3) {
                this.ctx.fillStyle = `hsla(${hue}, 80%, 70%, 0.7)`;
            }

            switch (shapeType) {
                case 0: { // Polygon
                    const numVertices = 3 + Math.round(Math.abs(mfccs[(j + 4) % 20] / maxMfcc) * 5);
                    for (let i = 0; i < numVertices; i++) {
                        const angle = (Math.PI * 2 / numVertices) * i + rotation;
                        const px = offsetX + shapeRadius * Math.cos(angle);
                        const py = offsetY + shapeRadius * Math.sin(angle);
                        if (i === 0) this.ctx.moveTo(px, py);
                        else this.ctx.lineTo(px, py);
                    }
                    this.ctx.closePath();
                    this.ctx.fill();
                    break;
                }
                case 1: { // Polygram (Star)
                    const points = 3 + Math.round(Math.abs(mfccs[(j + 4) % 20] / maxMfcc) * 4);
                    const pointiness = 0.4 + Math.abs(mfccs[( j + 5) % 20] / maxMfcc) * 0.5;
                    this.drawPolygram(offsetX, offsetY, shapeRadius, points, pointiness, rotation);
                    this.ctx.fill();
                    break;
                }
                case 2: { // Ellipse
                    const ellipseRx = shapeRadius;
                    const ellipseRy = shapeRadius * (0.3 + Math.abs(mfccs[(j + 4) % 20] / maxMfcc) * 0.7);
                    this.ctx.ellipse(offsetX, offsetY, ellipseRx, ellipseRy, rotation, 0, Math.PI * 2);
                    this.ctx.fill();
                    break;
                }
                case 3: { // Line
                    const endX = offsetX + Math.cos(rotation) * shapeRadius * 2;
                    const endY = offsetY + Math.sin(rotation) * shapeRadius * 2;
                    this.ctx.moveTo(offsetX - (endX - offsetX), offsetY - (endY - offsetY));
                    this.ctx.lineTo(endX, endY);
                    this.ctx.lineWidth = 1 + Math.abs(mfccs[(j + 4) % 20] / maxMfcc) * 4;
                    const hue = (mfccs[(j + 6) % 20] / maxMfcc) * 360;
                    this.ctx.strokeStyle = `hsla(${hue}, 80%, 70%, 0.7)`;
                    this.ctx.stroke();
                    break;
                }
            }
        }

        this.ctx.restore();
    }

    /**
     * Draws a polygram (star) shape.
     * @param {number} x - Center x-coordinate
     * @param {number} y - Center y-coordinate
     * @param {number} radius - Outer radius
     * @param {number} sides - Number of points
     * @param {number} pointiness - How sharp the points are (0-1)
     * @param {number} rotation - Rotation in radians
     */
    drawPolygram(x, y, radius, sides, pointiness = 0.5, rotation = 0) {
        const angleStep = Math.PI / sides;
        this.ctx.beginPath();
        for (let i = 0; i < 2 * sides; i++) {
            const r = (i % 2 === 0) ? radius : radius * pointiness;
            const angle = i * angleStep + rotation
            const px = x + r * Math.cos(angle);
            const py = y + r * Math.sin(angle);
            if (i === 0) this.ctx.moveTo(px, py);
            else this.ctx.lineTo(px, py);
        }
        this.ctx.closePath();
    }

    /**
     * Draws a 12-segment ring around the blob for chroma STFT visualization.
     * @param {number} x - Center x-coordinate.
     * @param {number} y - Center y-coordinate.
     * @param {number} blobWidth - The width of the blob (inner ring).
     * @param {Array<number>} chromaStft - The 12-element chroma vector.
     */
    drawChromaHoops(x, y, blobWidth, chromaStft) {
        if (!chromaStft || chromaStft.length !== 12) return;

        const hoopRadiusX = blobWidth + this.config.chromaRingWidth; // Ellipse width
        const hoopRadiusY = 8; // Ellipse height (constant for 3D effect)
        const availableHeight = this.canvas.height * 0.8;
        const verticalSpacing = availableHeight / 12; // Space between hoops

        for (let i = 0; i < 12; i++) {
            const chromaValue = chromaStft[i];
            if (chromaValue < 0.1) continue; // Don't draw faint hoops

            // Distribute hoops vertically around the center
            const hoopY = (this.canvas.height / 2) + (i - 5.5) * verticalSpacing;
            const opacity = Math.min(1, chromaValue * 1.5);

            this.ctx.strokeStyle = `hsla(${i * 30}, 100%, 70%, ${opacity})`; // Give each note a unique color
            this.ctx.lineWidth = 2 + (chromaValue * 3); // Stronger notes are thicker
            this.ctx.beginPath();
            this.ctx.ellipse(x, hoopY, hoopRadiusX, hoopRadiusY, 0, 0, 2 * Math.PI);
            this.ctx.stroke();
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
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
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
        const onsets = stemData.temporal_features.onsets || [];
        const beats = stemData.temporal_features.beats || [];

        // Handle Onsets
        onsets.forEach(onsetTime => {
            const timeDiff = analysisTimeMs - (onsetTime * 1000);
            if (timeDiff >= 0 && timeDiff <= this.config.onsetTimeDecay) {
                const opacity = 1 - (timeDiff / this.config.onsetItemDecay);
                this.ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
                this.ctx.fillRect(x - (width * 0.05), this.canvas.height / 2 - width / 2, width * 0.1, width);
            }
        });

        // Handle Beats
        beats.forEach(beatTime => {
            const timeDiff = analysisTimeMs - (beatTime * 1000);
            if (timeDiff >= 0 && timeDiff <= this.config.beatItemDecay) {
                const opacity = 1 - (timeDiff / this.config.beatItemDecay);
                this.ctx.fillStyle = `rgba(200, 200, 200, ${opacity})`;
                const squareSize = width * 0.2;
                this.ctx.fillRect(x - squareSize/2, this.canvas.height / 2 - squareSize/2, squareSize, squareSize);
            }
        });
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

    /**
     * Draws the instrument name label at the top of a column.
     * @param {string} name - The name of the instrument
     * @param {number} x - The x-coordinate of the column.
     * @param {number} width - The width of the column.
     */
    drawInstrumentLabel(name, x, width) {
        this.ctx.fillStyle = '#ccc';
        this.ctx.font = this.config.labelFont;
        this.ctx.textAlign = 'center';
        this.ctx.fillText(name, x + width / 2, 20);
    }

    drawFrequencyAxis() {
        if (!this.axisContainer) return;
        this.axisContainer.innerHTML = '';
        const frequencies = [65.41, 130.81, 261.63, 523.25, 1046.50, 2093.00, 4186.01]; // C2 to C8
        const labels = ['C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'];

        frequencies.forEach((freq, i) => {
            const normalizedY = this.mapValueToLogNormalizedY(freq);
            const yPos = (1 - normalizedY) * 100; // a percentage from the top

            const labelEl = document.createElement('div');
            labelEl.textContent = labels[i];
            labelEl.style.position = 'absolute';
            labelEl.style.top = `${yPos}%`;
            labelEl.style.right = '5px'; // Position inside the axis container
            labelEl.style.transform = 'translateY(-50%)'; // Center verically
            labelEl.style.color = '#ccc';
            labelEl.style.fontSize = '12px';
            this.axisContainer.appendChild(labelEl);
        });
    }

    drawChromaKey() {
        if (!this.chromaKeyContainer) return;
        this.chromaKeyContainer.innerHTML = '';
        const notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        const availableHeight = this.canvas.height * 0.8;
        const verticalSpacing = availableHeight / 12;

        notes.forEach((note, i) => {
            const yPos = (this.canvas.height / 2) + (i - 5.5) * verticalSpacing;
            if (yPos < 0 || yPos > this.canvas.height) return; // Don't draw if off-canvas

            const labelEl = document.createElement('div');
            labelEl.textContent = note;
            labelEl.style.position = 'absolute';
            labelEl.style.top = `${yPos}px`;
            labelEl.style.left = '5px';
            labelEl.style.transform = 'translateY(-50%)';
            labelEl.style.color = `hsl(${i * 30}, 100%, 70%)`;
            labelEl.style.fontSize = '12px';
            this.chromaKeyContainer.appendChild(labelEl);
        });
    }
}
