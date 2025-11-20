/**
 * Manages a large spectrogram array stored as a raw string, allowing for
 * on-demand parsing of individual time-slices to avoid memory overload.
 */
export class SpectrogramAccessor {
    /**
     * @param {string} spectrogramString - The raw string content of the
     * spectrogram array, e.g., "[[...],[...]]".
     */
    constructor(spectrogramString) {
        // Trim the outer brackets `[` and `]` to work with the inner content.
        this.dataString = spectrogramString.substring(1, spectrogramString.length - 1);
        this.slices = [];
    }

    /**
     * Lazily finds and parses a single time-slice (a column) from the
     * spectrogram string.
     * @param {number} sliceIndex - The index of the time-slice to retrieve.
     * @returns {Array<number> | null} The parsed array of numbers for that
     * slice, or null.
     */
    getSlice(sliceIndex) {
        // Return from cache if already parsed
        if (this.slices[sliceIndex]) {
            return this.slices[sliceIndex];
        }

        // This parser finds the desired slice regardless of the order.
        let depth = 0;
        let start = -1;
        let currentSlice = 0;

        // ALWAYS start searching from the beginning of the string.
        for (let i = 0; i < this.dataString.length; i++) {
            const char = this.dataString[i];
            if (char === '[') {
                if (depth === 0) { // Found the start of a potential slice
                    if (currentSlice === sliceIndex) {
                        start = i;
                    }
                }
                depth++;
            } else if (char === ']') {
                depth--;
                if (depth === 0 && currentSlice === sliceIndex) {
                    const sliceStr = this.dataString.substring(start, i + 1);
                    try {
                        const parsedSlice = JSON.parse(sliceStr);
                        this.slices[sliceIndex] = parsedSlice; // Cache the result
                        this.index = i + 1; // Start next search from here
                        return parsedSlice;
                    } catch (e) {
                        console.error(`Failed to parse spectrogram slice at index ${sliceIndex}`, e);
                        return null;
                    }
                }
                currentSlice++; // Move to the next slice
            }
        }
        return null; // Index out of bounds
    }
}
