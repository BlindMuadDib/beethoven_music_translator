/**
 * @class DrumTracker
 * @description Manages the visualization of drum analysis data on an
 * HTML canvas. It maps different drum types to specific shapes and
 * visual properties, creating a dynamic representation of the drum
 * track.
 */
export class DrumTracker {
    /**
     * @param {HTMLCanvasElement} canvas - The canvas element to draw on.
     * @param {Array} drumAnalysis - The drum_analysis data from the API.
     */
    constructor(canvas, drumAnalysis) {
        if (!canvas || !(canvas instanceof HTMLCanvasElement)) {
            throw new Error("A valid canvas element must be provided.");
        }
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        // Assume tempo is part of the analysis data. Default to
        // 120 if not present.
        this.tempo = drumAnalysis?.tempo || 120;
        this.drumHits = drumAnalysis?.hits || [];
        this.lastTime = -1;

        // Constants for visualization
        this.config = {
            yAxisMap: {
                // Higher number means lower on the Y-axis
                'kick': 0.9,
                'tom': 0.75,
                'snare': 0.6,
                'cowbell': 0.35,
                'hihat': 0.25,
                'cymbal': 0.15,
                'other': 0.5,
            },
            shapes: {
                'kick': 'hexagon',
                'tom': 'pentagon', // General for all toms
                'snare': 'circle',
                'cowbell': 'rectangle',
                'hihat': 'triangle', // General for all hihats
                'cymbal': 'trapezoid', // General for all cymbals
                'other': 'square',
            },
            maxSize: 1000, // Max size of a shape
            yAxisPitchRange: 0.1, // How much pitch can affect Y-pos
            staticXPosition: 0.25, // Shapes appear 25% of the way across the canvas
        };

        // Add properties for tooltip handling
        this.hoveredHit = null;
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseout', this.handleMouseOut.bind(this));

        console.log('[DrumTracker] Initialized with', this.drumHits.length, 'drum hits.');

        // Use a ResizeObserver to handle canvas resizing automatically
        const resizeObserver = new ResizeObserver(() => this.resizeCanvas());
        resizeObserver.observe(this.canvas);

        this.resizeCanvas();
    }

    /**
     * Resizes the canvas's drawing surface to match its displayed
     * size. This is crucial for preventing stretched or misaligned
     * drawings.
     */
    resizeCanvas() {
        const { width, height } = this.canvas.getBoundingClientRect();
        this.canvas.width = width;
        this.canvas.height = height;
        this.draw();
    }

    /**
     * Updates the visualization to the given time.
     * @param {number} currentTime - The current playback time in seconds.
     */
    update(currentTime) {
        // Only redraw if the time has changed significantly
        if (Math.abs(currentTime - this.lastTime) > 1 / 60) { // 60 FPS
            this.lastTime = currentTime;
            this.draw(currentTime);
        }
    }

    /**
     * Clears and redraws the entire canvas.
     * @param {number} currentTime - The current playback time to highlight
     */
    draw(currentTime = this.lastTime) {
        const { width, height } = this.canvas;
        // Clear the canvas
        this.ctx.clearRect(0, 0, width, height);

        // 1. Draw background tempo lines first
        this.drawTempoLines(currentTime, width, height);
        this.drawNowLine(width, height);

        // 2. Filter for currently active drum hits
        const visibleHits = this.drumHits.filter(hit =>
            currentTime >= hit.onset_time && currentTime < (hit.onset_time + hit.duration)
        );

        // 3. Draw the shapes
        visibleHits.forEach(hit => {
            const xPos = width * this.config.staticXPosition;
            const yPos = this.getYPosition(hit) * height;
            const color = this.getColor(hit);
            const size = this.getSize(hit, currentTime);
            const shape = this.getShape(hit.drum_category, hit.drum_type);

            if (size > 1) {
                // 1. Draw the main colored shape.
                // To achieve an "oil and water" effect where colors overlap
                // but don't mix, we draw each shape with partial
                // transparency.
                this.ctx.globalAlpha = 0.85;
                this.drawShape(xPos, yPos, size, shape, color);

                // Create a decaying flash for the moment the drum
                // is struck
                const flashDuration = 0.15;
                const timeSinceOnset = currentTime - hit.onset_time;

                if (timeSinceOnset >= 0 && timeSinceOnset < flashDuration) {
                    // Calculate brightness (alpha) based on how long
                    // ago the hit was. it starts at 1.0 (full bright)
                    // and fades to 0.
                    const flashAlpha = 1.0 - (timeSinceOnset / flashDuration);

                    // Apply the calculated alpha and draw the flash
                    this.ctx.globalAlpha = flashAlpha;
                    this.drawShape(xPos, yPos, size * .2, shape, '#FFFFFF');
                }
            }
        });

        // 4. Reset alpha for tooltips and legend, and draw UI elements
        this.ctx.globalAlpha = 1.0;
        this.drawLegend();
        this.drawTooltip();
    }

    drawTempoLines(currentTime, width, height) {
        this.ctx.save();
        const beatsPerSecond = this.tempo / 60;
        const timePerBeat = 1 / beatsPerSecond;
        const pixelsPerBeat = 150; // How far apart each beat line is

        // Calculate the starting offset to make the lines scroll
        const scrollOffset = (currentTime % timePerBeat) / timePerBeat * pixelsPerBeat;

        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;

        for (let x = -scrollOffset; x < width; x += pixelsPerBeat) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, height);
            this.ctx.stroke();
        }
        this.ctx.restore();
    }

    drawNowLine(width, height) {
        this.ctx.save();
        const x = width * this.config.staticXPosition;
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(x, 0);
        this.ctx.lineTo(x, height);
        this.ctx.stroke();
        this.ctx.restore();
    }

    // --- Helper Methods ---

    /**
     * Calculates the Y position of a drum hit.
     * It starts with a base position for the drum type and adjusts
     * it based on frequency data.
     * @param {object} hit - The drum hit object.
     * @returns {number} A value from 0.0 (top) to 1.0 (bottom).
     */
    getYPosition(hit) {
        const baseKey = this.config.yAxisMap[hit.drum_type] !== undefined
                        ? hit.drum_type
                        : (this.config.yAxisMap[hit.drum_category] !== undefined
                            ? hit.drum_category
                            : 'other');

        const basePos = this.config.yAxisMap[baseKey] || 0.5;

        // Weighted average of spectral centroid and dominant
        // frequency for pitch adjustment
        const weightedPitch = (hit.spectral_centroid * 0.8) + (hit.dominant_frequency * 0.2);

        // Normalize the pitch value. Let's assume a practical range
        // of 0-4000Hz. A lower pitch should push the shape down
        // (increase Y), and a higher pitch should push the shape up
        // (decrease Y). Normalize to roughly -0.5 to 0.5
        const pitchFactor = (weightedPitch - 2000) / 4000;

        const pitchOffset = pitchFactor * this.config.yAxisPitchRange;

        return Math.max(0, Math.min(1, basePos - pitchOffset));
    }

    /**
     * Calculates the color of a drum hit based on spectral
     * properties. Uses HSL color space for intuitive manipulation.
     * - Hue is determined by spectral rolloff (brighter sounds ->
     * cooler colors).
     * - Saturation and Lightness are determined by spectral flux
     * (sharper sounds -> more intense color).
     * @param {object} hit - The drum hit object.
     * @returns {string} An HSL color string
     */
    getColor(hit) {
        // Rolloff -> Hue (e.g., 500Hz-8000Hz mapped to 0-240 degrees:
        // Red to Blue)
        const hue = Math.max(0, Math.min(240, 240 * ((hit.spectral_rolloff - 500) / 7500)));

        // Flux -> Saturation (e.g., 0.0-1.0 mapped to 70-100% saturation)
        const saturation = 70 + (Math.min(1, hit.spectral_flux / 1.0) * 30);

        // Fixed lightness for vibrancy
        const lightness = 60;

        return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    }

    /**
     * Calculates the current size of a shape based on volume and decay.
     * @param {object} hit - The drum hit object.
     * @param {number} currentTime - The current playback time.
     * @returns {number} The radius/size of the shape.
     */
    getSize(hit, currentTime) {
        const timeSinceOnset = currentTime - hit.onset_time;
        let decayFactor = 1.0;

        // Only apply decay for hits with a noticeable duration (e.g., cymbals)
        if (hit.duration > 0.15 && timeSinceOnset > 0) {
            decayFactor = Math.max(0, 1 - (timeSinceOnset / hit.duration));
        }

        return this.config.maxSize * hit.relative_volume * decayFactor;
    }

    /**
     * Determines the shape based on drum_category and drum_type.
     * Prioritizes drum_category, then drum_type, then 'unknown'
     * @param {string} drumCategory - The drum category (e.g., 'snare').
     * @param {string} drumType - The specific drum type (e.g. 'closed_band').
     * @returns {string} The name of the shape (e.g., 'circle').
     */
    getShape(drumCategory, drumType) {
        // Prioritizes specific category mappings
        if (drumCategory && this.config.shapes[drumCategory]) {
            return this.config.shapes[drumCategory];
        }
        // Fallback to drumType if it's a known general type that
        // might be explicitly mapped (though current config uses
        // categories primarily).
        if (drumType && this.config.shapes[drumType]) {
            return this.config.shapes[drumType];
        }
        // General category specific logic if `drumCategory` is
        // 'other' but `drumType` is not 'unknown'. This handles
        // cases like `drum_category: 'other', drum_type: 'cowbell'`
        if (drumCategory === 'other' && drumType && drumType !== 'unknown') {
            if (drumType.includes('cowbell')) return this.config.shapes.cowbell;
        }

        // Fallback for general groupings or unknown
        if (drumCategory.includes('tom')) return this.config.shapes.tom;
        if (drumCategory.includes('cymbal') && drumType.includes('hihat')) return this.config.shapes.hihat;
        else if (drumCategory.includes('cymbal')) return this.config.shapes.cymbal;

        // Final fallback
        return this.config.shapes.unknown || 'square';
    }

    /**
     * Draws a specific polygon or shape on the canvas.
     * @param {number} x - Center X coordinate.
     * @param {number} y - Center Y coordinate.
     * @param {number} size - The size (radius) of the shape.
     * @param {number} shape - The name of the shape to draw.
     * @param {number} color - The fill color for the shape.
     */
    drawShape(x, y, size, shape, color) {
        this.ctx.save();

        // Glow effect
        this.ctx.shadowColor = color;
        this.ctx.shadowBlur = 15;

        this.ctx.fillStyle = color;
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();

        const radius = size / 2;

        switch (shape) {
            case 'circle':
                this.ctx.arc(x, y, radius, 0, 2 * Math.PI);
                break;
            case 'square':
                this.ctx.rect(x - radius, y - radius, size, size);
                break;
            case 'triangle':
                this.ctx.moveTo(x, y - radius);
                this.ctx.lineTo(x - radius, y + radius);
                this.ctx.lineTo(x + radius, y + radius);
                this.ctx.closePath();
                break;
            case 'hexagon':
                this.drawPolygon(x, y, 6, radius);
                break;
            case 'pentagon':
                this.drawPolygon(x, y, 5, radius);
                break;
            case 'trapezoid':
                this.ctx.moveTo(x - radius, y - radius / 2);
                this.ctx.lineTo(x + radius, y - radius / 2);
                this.ctx.lineTo(x + radius * 0.7, y + radius / 2);
                this.ctx.lineTo(x - radius * 0.7, y + radius / 2);
                break;
            case 'rectangle':
                this.ctx.rect(x - radius, y - radius / 2, size, radius);
                break;
        }

        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.stroke();
        this.ctx.restore();
    }

    /**
     * Helper to draw a regular polygon
     * @param {number} x - Center X coordinate.
     * @param {number} y - Center Y coordinate.
     * @param {number} sides - Number of sides.
     * @param {number} radius - The radius of the polygon.
     */
    drawPolygon(x, y, sides, radius) {
        const angleStep = (2 * Math.PI) / sides;
        // Start at the top point
        let angle = -Math.PI / 2;

        this.ctx.moveTo(x + radius * Math.cos(angle), y + radius * Math.sin(angle));
        for (let i = 0; i < sides; i++) {
            angle += angleStep;
            this.ctx.lineTo(x + radius * Math.cos(angle), y + radius * Math.sin(angle));
        }
    }

    /**
     * Draws a static legend on the canvas.
     */
    drawLegend() {
        const legendWidth = 140;
        const legendX = this.canvas.width - legendWidth - 15;
        const legendY = 15;
        const itemHeight = 25;
        const items = Object.keys(this.config.shapes);
        const legendHeight = (items.length * itemHeight) + 25;

        // Draw background box for the legend
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.roundRect(legendX, legendY, legendWidth, legendHeight, 5);
        this.ctx.fill();
        this.ctx.stroke();

        // Legend Title
        this.ctx.fillStyle = '#FFFFFF'; // White text
        this.ctx.font = 'bold 12px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Instrument Key', legendX + legendWidth / 2, legendY + 18);

        // Legend Items
        this.ctx.font = '11px sans-serif';
        this.ctx.textAlign = 'left';
        items.forEach((key, index) => {
            const shape = this.config.shapes[key];
            const yPos = legendY + 30 + (index * itemHeight);
            const xPos = legendX + 20;

            const displayName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            this.drawShape(xPos, yPos, 15, shape, 'hsl(0, 0%, 80)'); // Draw a neutral colored shape

            // Reset fillStyle for the text after drawing the shape
            this.ctx.fillStyle = '#FFFFFF';
            this.ctx.fillText(displayName, xPos + 20, yPos + 4);
        });
    }

    /**
     * Draws a tooltip if a drum hit is being hovered over.
     */
    drawTooltip() {
        if (!this.hoveredHit) return;

        const hit = this.hoveredHit;
        // Position tooltip relative to the shape's last drawn position
        const x = this.hoveredHit.lastX + 15;
        const y = this.hoveredHit.lastY;

        const lines = [
            `Category: ${hit.drum_category?.replace(/_/g, ' ') || 'N/A'}`,
            `  └ Confidence: ${(hit.category_confidence * 100).toFixed(1)}%`,
            `Type: ${hit.drum_type?.replace(/_/g, ' ') || 'N/A'}`,
            `  └ Confidence: ${(hit.type_confidence * 100).toFixed(1)}%`,
        ];

        // Add qualifier line only if it's not 'no_qualifier' or undefined
        if (hit.qualifier && hit.qualifier !== 'no_qualifier') {
            lines.push(`Qualifier: ${hit.qualifier.replace(/_/g, ' ') || 'N/A'}`);
            lines.push(`  └ Confidence: ${(hit.qualifier_confidence * 100).toFixed(1)}%`);
        }

        this.ctx.font = `13px sans-serif`;
        let maxTextWidth = 0;
        lines.forEach(line => {
            maxTextWidth = Math.max(maxTextWidth, this.ctx.measureText(line).width);
        });

        const boxWidth = maxTextWidth + 20;
        const boxHeight = (lines.length * 18) + 10;

        if (y + boxHeight > this.canvas.height) {
            y = this.canvas.height - boxHeight;
        }

        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        this.ctx.fillRect(x, y, boxWidth, boxHeight);

        this.ctx.fillStyle = 'white';
        lines.forEach((line, index) => {
            this.ctx.fillText(line, x + 10, y + 20 + (index * 18));
        });
    }

    /**
     * Handles the mouse move event to detect hovering over shapes.
     * @param {MouseEvent} e - The mouse event.
     */
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const currentTime = this.lastTime;
        const visibleHits = this.drumHits.filter(hit => {
            const timeSinceOnset = currentTime - hit.onset_time;
            return timeSinceOnset >= 0 && timeSinceOnset < hit.duration;
        });

        // Find the topmost hit under the cursor
        this.hoveredHit = null;
        for (const hit of visibleHits.reverse()) { // Reverse to check topmost first
            const size = this.getSize(hit, currentTime);
            const x = this.config.staticXPosition * this.canvas.width;
            const y = this.getYPosition(hit) * this.canvas.height;

            // Simple bounding box collision detection
            if (mouseX >= x - size/2 && mouseX <= x + size/2 &&
                mouseY >= y - size/2 && mouseY <= y + size/2) {
                this.hoveredHit = hit;
                this.hoveredHit.lastX = x;
                this.hoveredHit.lastY = y;
                break;
            }
        }

        // Redraw is handled by the main update loop, but we can
        // trigger one if needed
        // this.draw();
    }

    /**
     * Clears the tooltip when the mouse leaves the canvas.
     */
    handleMouseOut() {
        this.hoveredHit = null;
    }
}
