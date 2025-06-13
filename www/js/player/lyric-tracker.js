// --- Lyric Tracker ---

/**
 * A pure function to find the index of the line that should be active at a given time.
 * @param {number} currentTime - The current time in seconds.
 * @param {Array<object>} - The index of the active line, or -1
 */
export function findCurrentLineIndex(currentTime, lines) {
    if (!lines || lines.length === 0) return -1;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lineStart = line.line_start_time !== null ? line.line_start_time : (line.words[0] && line.words[0].start !== null ? line.words[0].start : Infinity);
        const lineEnd = line.line_end_time !== null ? line.line_end_time : (line.words[line.words.length - 1] && line.words[line.words.length - 1].end !== null ? line.words[line.words.length - 1].end : -Infinity);

        if (currentTime >= lineStart && currentTime <= lineEnd) {
            return i;
        }
        // Handle transition to next line: display next line halfway between current line end and next line start
        const nextLine = lines[i + 1];
        if (nextLine) {
            const nextLineStart = nextLine.line_start_time !== null ? nextLine.line_start_time : (nextLine.words[0] && nextLine.words[0].start !== null ? nextLine.words[0].start : Infinity);
            if (currentTime > lineEnd && currentTime < nextLineStart) {
                const transitionPoint = lineEnd + (nextLineStart - lineEnd) / 2;
                if (currentTime >= transitionPoint) {
                    return i + 1;
                } else {
                    return i; // Still show current line before midpoint
                }
            }
        }
    }
    // If current time is before the very first line's start time
    if (lines[0] && currentTime < (lines[0].line_start_time !== null ? lines[0].line_start_time : (lines[0].words[0] && lines[0].words[0].start))) {
        return 0; // Show the first line
    }
    // If current time is after the very last line's end time
    if (lines[lines.length-1] && currentTime > (lines[lines.length-1].line_end_time !== null ? lines[lines.length-1].line_end_time : (lines[lines.length-1].words[lines[lines.length-1].words.length-1].end))) {
        return lines.length -1; // Show the last line
    }
    return -1; // No line active
}

export class LyricTracker {
    // --- Configuration ---
    config = {
        fontFamily: 'sans-serif',
        fontSize: 22,
        lineHeightPadding: 10,
        ballRadius: 7,
        ballColor: 'red',
        textColor: 'black',
        wordSpacing: 8
    };

    // --- State ---
    ctx = null;
    lyricData = [];
    currentLineIndex = -1;
    canvas = null;

    constructor(canvas, mappedLyrics) {
        if (!canvas) throw new Error("Lyric canvas not provided!");
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.lyricData = mappedLyrics || [];
        this.update(0);
    }

    /**
     * Draws the state of the lyrics for a given time.
     * This is the main "heartbeat" function called by the player
     * @param {number} currentTime - The current time of the audio player.
     */
    update(currentTime) {
        if (!this.ctx) return;

        // Check and set canvas dimensions on every update call
        if (this.canvas.width !== this.canvas.offsetWidth || this.canvas.height !== this.canvas.offsetHeight) {
            this.canvas.width = this.canvas.offsetWidth;
            this.canvas.height = this.canvas.offsetHeight;
        }

        // If width or height is still 0, don't try to draw
        if (!this.canvas.width || !this.canvas.height) {
            return;
        }

        if (!this.lyricData || this.lyricData.length === 0) {
            if (this.ctx) this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        const newIdx = findCurrentLineIndex(currentTime, this.lyricData);
        if (newIdx !== -1) {
            this.currentLineIndex = newIdx;
        } else if (this.currentLineIndex === -1 && this.lyricData.length > 0) { // Default to first line if nothing is selected
            this.currentLineIndex = 0;
        }

        if (this.currentLineIndex < 0 || this.currentLineIndex >= this.lyricData.length) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        const lineObj = this.lyricData[this.currentLineIndex];
        const lineTextToDisplay = lineObj.line_text || "";
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.font = `${this.config.fontSize}px ${this.config.fontFamily}`;
        this.ctx.fillStyle = this.config.textColor;
        this.ctx.textAlign = 'left'; // We will calculate center position

        // Calculate total width of the line to center it
        let totalLineWidth = 0;
        lineObj.words.forEach((wordObj, index) => {
            totalLineWidth += this.ctx.measureText(wordObj.word || "").width;
            if (index < lineObj.words.length - 1) {
                totalLineWidth += this.config.wordSpacing;
            }
        });

        let currentX = (this.canvas.width - totalLineWidth) / 2;
        const textY = (this.canvas.height / 2) + (this.config.fontSize / 3); // Approximate vertical center

        // Draw words of the current line
        lineObj.words.forEach(wordObj => {
            this.ctx.fillText(wordObj.word || "", currentX, textY);
            currentX += this.ctx.measureText(wordObj.word || "").width + this.config.wordSpacing;
        });

        // --- Bouncing Ball Logic ---
        let activeWord = null;
        let lastSpokenWord = null;

        // Find the currently spoken word and the last spoken word
        for (const word of lineObj.words) {
            if (word.start !== null && word.end !== null) {
                if (currentTime >= word.start && currentTime < word.end) {
                    activeWord = word;
                    // Found the active word, no need to look further
                    break;
                }
                if (currentTime >= word.end) {
                    lastSpokenWord = word;
                }
            }
        }

        const wordToFollow = activeWord || lastSpokenWord;

        if (wordToFollow) {
            // Find the X-position of the word to follow
            let ballX = (this.canvas.width - totalLineWidth) /2;
            for (const word of lineObj.words) {
                const wordWidth = this.ctx.measureText(word.word || "").width;
                if (word === wordToFollow) {
                    ballX += wordWidth / 2;
                    break;
                }
                ballX += wordWidth + this.config.wordSpacing;
            }

            const ballY = textY - this.config.fontSize - this.config.ballRadius;
            this.drawBall(ballX, ballY);
        }
    }

    drawBall(x, y) {
        if (!this.ctx) return;
        this.ctx.beginPath();
        this.ctx.arc(x, y, this.config.ballRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = this.config.ballColor;
        this.ctx.fill();
        this.ctx.closePath();
    }
}

