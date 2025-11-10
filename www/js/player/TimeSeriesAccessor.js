/**
 * Manages a large time-series dataset by fetching it in chunks
 * and providing fast, indexed access to the loaded data.
 */
export class TimeSeriesAccessor {
    /**
     * @param {string|Array} source - The base URL to fetch NDJSON data
     * chunks or a raw array.
     * @param {number} totalElements - The total number of elements
     * expected in the full dataset.
     * @param {number} [chunkSize=500] - The number of elements to fetch per request.
     */
    constructor(source, totalElements, chunkSize = 500) {
        if (totalElements === undefined || totalElements < 0) {
            throw new RangeError("Invalid totalElements provided to TimeSeriesAccessor");
        }
        this.totalElements = totalElements;
        this.chunkSize = chunkSize;
        this.timePerFrame = 512 / 22050;

        this.chunks = new Map(); // Stores loaded data chunks (Map<chunkIndex, dataArray>)
        this.requests = new Map(); // Track in-flight requests to prevent re-fetching
        this.times = new Array(totalElements).fill(null); // Pre-allocated array to store timestamps for seeking

        // --- Differentiate between a URL source and a raw string source ---
        if (typeof source === 'string' && source.startsWith('/api/')) {
            this.isUrlSource = true;
            this.streamUrl = source;
        } else {
            this.isUrlSource = false;
            let data = [];
            if (Array.isArray(source)) {
                data = source;
            } else if (typeof source === 'string') {
                try {
                    const parsed = JSON.parse(source);
                    if (Array.isArray(parsed)) {
                        data = parsed;
                    }
                } catch (error) {
                    console.error("TimeSeriesAccessor Error: Failed to parse non-API string source as JSON.");
                }
            }

            this.chunks.set(0, data);
            data.forEach((item, i) => {
                if (item && i < this.totalElements) {
                    this.times[i] = item.onset_time ?? item.time; // Handle both drum and harmonic keys
                }
            });
        }
    }

    /**
     * Ensures that the data for a given time is loaded, fetching if if
     * necessary.
     * @param {number} time - The time in seconds to ensure data for.
     * @returns {Promise<void>}
     */
    async ensureDataForTime(time) {
        if (!this.isUrlSource) return Promise.resolve(); // Don't fetch for raw string data

        const targetIndex = this._getIndexForTime(time);
        const chunkIndex = Math.floor(targetIndex / this.chunkSize);

        if (!this.chunks.has(chunkIndex) && !this.requests.has(chunkIndex)) {
            // This returns a promise, allowing callers to await if needed
            return this._fetchChunk(chunkIndex);
        }
        return Promise.resolve();
    }

    /**
     * Checks if data for a given time is already loaded in memory.
     * @param {number} time - The time in seconds.
     * @returns {boolean}
     */
    isDataAvailableForTime(time) {
        const targetIndex = this._getIndexForTime(time);
        const chunkIndex = Math.floor(targetIndex / this.chunkSize);
        return this.chunks.has(chunkIndex);
    }

    /**
     * Retrieves a single data element for a specific time.
     * @param {number} time - The time in seconds to get data for.
     * @returns {Array<number> | null} The parsed data object or null if not loaded.
     */
    getElementAtTime(time) {
        const index = this._findClosestIndexBinary(time);
        return this.getElementAtIndex(index);
    }

    getElementAtIndex(index) {
        if (index < 0 || index >= this.totalElements) return null;
        const chunkIndex = Math.floor(index / this.chunkSize);
        const IndexInChunk = index % this.chunkSize;
        const chunk = this.chunks.get(chunkIndex);

        return chunk?.[IndexInChunk] ?? null;
    }

    /**
     * Fetches a specific chunk of data from the backend.
     * @private
     */
    _fetchChunk(chunkIndex) {
        if (chunkIndex < 0 || (chunkIndex * this.chunkSize) >= this.totalElements) {
            return Promise.resolve();
        }
        // If there's already a request for this chunk, return the existing promise
        if (this.requests.has(chunkIndex)) {
            return this.requests.get(chunkIndex);
        }

        const start = chunkIndex * this.chunkSize;
        const end = Math.min(start + this.chunkSize, this.totalElements);

        // Append query parameters correctly, checking if some already exist
        const separator = this.streamUrl.includes('?') ? '&' : '?';
        const url = `${this.streamUrl}${separator}start=${start}&end=${end}`;

        const promise = fetch(url)
            .then(response => {
                if (!response.ok) throw new Error(`Failed to fetch chunk ${chunkIndex}`);
                return response.text();
            })
            .then(ndjsonString => {
                if (!ndjsonString) return; // Handle empty response
                const lines = ndjsonString.trim().split('\n').map(JSON.parse);
                this.chunks.set(chunkIndex, lines);

                // Populate the times array for binary search
                lines.forEach((item, i) => {
                    const globalIndex = start + i;
                    if (item && typeof item.time !== 'undefined' && globalIndex < this.times.length) {
                        this.times[globalIndex] = item.time;
                    }
                });
            })
            .catch(error => {
                console.error(`Error fetching chunk ${chunkIndex}:`, error);
            })
            .finally(() => {
                this.requests.delete(chunkIndex);
            });

        this.requests.set(chunkIndex, promise);
        return promise;
    }

    _getIndexForTime(time) {
        return Math.min(this.totalElements - 1, Math.max(0, Math.floor(time / this.timePerFrame)));
    }

    /**
     * Uses a binary search algorithm to find the index of the element
     * closest to the given time. This is optimized for potentially sparse,
     * partially loaded time arrays.
     * @param {number} time - The target time.
     * @return {number} The closest index.
     * @private
     */
    _findClosestIndexBinary(targetTime) {
        let low = 0;
        let high = this.times.length - 1;
        let closestIndex = 0;
        let minDiff = Infinity;

        // Find the last non-null index to set a realistic search boundary
        let lastKnownTimeIndex = -1;
        for (let i = this.times.length - 1; i >= 0; i--) {
            if (this.times[i] !== null){
                lastKnownTimeIndex = i;
                break;
            }
        }
        if(lastKnownTimeIndex === -1) return 0; // No times loaded yet

        high = lastKnownTimeIndex;

        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            const midTime = this.times[mid];

            if (midTime === null) { // This part of the array is not populated yet
                high = mid - 1;
                continue;
            }

            const diff = Math.abs(midTime - targetTime);

            if (diff < minDiff) {
                minDiff = diff;
                closestIndex = mid;
            }

            if (midTime < targetTime) {
                low = mid + 1;
            } else if (midTime > targetTime) {
                high = mid - 1;
            } else {
                return mid; // Exact match found
            }
        }
        return closestIndex;
    }
}
