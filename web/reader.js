/**
 * Read-Along Reader
 *
 * Synchronized audio-text playback with sentence highlighting.
 * Supports tap-to-seek, auto-scroll, and multiple themes.
 */

class ReadAlongReader {
    constructor() {
        // State
        this.bookData = null;
        this.timingData = null;
        this.textData = null;
        this.currentChapter = 0;
        this.currentSentenceIndex = -1;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.autoScroll = true;
        this.fontSize = 18;

        // DOM Elements
        this.audio = document.getElementById('audio');
        this.textContent = document.getElementById('text-content');
        this.playPauseBtn = document.getElementById('play-pause');
        this.playIcon = document.getElementById('play-icon');
        this.pauseIcon = document.getElementById('pause-icon');
        this.progressBar = document.getElementById('progress-bar');
        this.progressFill = document.getElementById('progress-fill');
        this.progressHandle = document.getElementById('progress-handle');
        this.currentTimeEl = document.getElementById('current-time');
        this.totalTimeEl = document.getElementById('total-time');
        this.chapterSelect = document.getElementById('chapter-select');
        this.bookTitle = document.getElementById('book-title');
        this.bookAuthor = document.getElementById('book-author');

        // Initialize
        this.bindEvents();
        this.loadSettings();
    }

    /**
     * Bind all event listeners
     */
    bindEvents() {
        // Audio events
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('loadedmetadata', () => this.onAudioLoaded());
        this.audio.addEventListener('ended', () => this.onChapterEnd());
        this.audio.addEventListener('play', () => this.updatePlayState(true));
        this.audio.addEventListener('pause', () => this.updatePlayState(false));

        // Play/Pause
        this.playPauseBtn.addEventListener('click', () => this.togglePlay());

        // Skip buttons
        document.getElementById('skip-back').addEventListener('click', () => {
            this.audio.currentTime = Math.max(0, this.audio.currentTime - 10);
        });
        document.getElementById('skip-forward').addEventListener('click', () => {
            this.audio.currentTime = Math.min(this.audio.duration, this.audio.currentTime + 30);
        });

        // Progress bar
        this.progressBar.addEventListener('click', (e) => this.seekTo(e));
        this.progressBar.addEventListener('mousedown', () => this.startDragging());

        // Speed control
        document.getElementById('speed-btn').addEventListener('click', () => {
            document.getElementById('speed-menu').classList.toggle('show');
        });
        document.querySelectorAll('#speed-menu button').forEach(btn => {
            btn.addEventListener('click', (e) => this.setSpeed(parseFloat(e.target.dataset.speed)));
        });

        // Chapter navigation
        this.chapterSelect.addEventListener('change', (e) => {
            this.loadChapter(parseInt(e.target.value));
        });
        document.getElementById('prev-chapter').addEventListener('click', () => {
            if (this.currentChapter > 0) this.loadChapter(this.currentChapter - 1);
        });
        document.getElementById('next-chapter').addEventListener('click', () => {
            if (this.currentChapter < this.timingData.chapters.length - 1) {
                this.loadChapter(this.currentChapter + 1);
            }
        });

        // Settings
        document.getElementById('settings-btn').addEventListener('click', () => {
            document.getElementById('settings-panel').classList.add('open');
        });
        document.getElementById('close-settings').addEventListener('click', () => {
            document.getElementById('settings-panel').classList.remove('open');
        });

        // Font size
        document.getElementById('font-decrease').addEventListener('click', () => {
            this.setFontSize(this.fontSize - 2);
        });
        document.getElementById('font-increase').addEventListener('click', () => {
            this.setFontSize(this.fontSize + 2);
        });

        // Theme
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setTheme(e.target.dataset.theme));
        });

        // Auto-scroll toggle
        document.getElementById('auto-scroll').addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
            this.saveSettings();
        });

        // Book selection
        document.getElementById('select-book-btn').addEventListener('click', () => {
            document.getElementById('folder-input').click();
        });
        document.getElementById('folder-input').addEventListener('change', (e) => {
            this.handleFolderSelect(e.target.files);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));

        // Close menus on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.speed-control')) {
                document.getElementById('speed-menu').classList.remove('show');
            }
        });
    }

    /**
     * Handle folder selection
     */
    async handleFolderSelect(files) {
        const fileMap = {};
        for (const file of files) {
            fileMap[file.name] = file;
        }

        // Look for manifest.json
        const manifestFile = fileMap['manifest.json'];
        if (!manifestFile) {
            alert('No manifest.json found. Please select a processed book folder.');
            return;
        }

        try {
            this.showLoading(true);

            // Read manifest
            const manifestText = await this.readFile(manifestFile);
            this.bookData = JSON.parse(manifestText);

            // Read timing data
            const timingFile = fileMap[this.bookData.timing];
            if (timingFile) {
                const timingText = await this.readFile(timingFile);
                this.timingData = JSON.parse(timingText);
            }

            // Read text data
            const textFile = fileMap[this.bookData.text];
            if (textFile) {
                const textText = await this.readFile(textFile);
                this.textData = JSON.parse(textText);
            }

            // Store audio files reference
            this.audioFiles = {};
            for (const [name, file] of Object.entries(fileMap)) {
                if (name.endsWith('.wav') || name.endsWith('.mp3')) {
                    this.audioFiles[name] = file;
                }
            }

            // Initialize reader
            this.initializeReader();

        } catch (error) {
            console.error('Error loading book:', error);
            alert('Error loading book: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Read file as text
     */
    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    /**
     * Initialize the reader with loaded book data
     */
    initializeReader() {
        // Update header
        this.bookTitle.textContent = this.bookData.title;
        this.bookAuthor.textContent = this.bookData.author;

        // Populate chapter select
        this.chapterSelect.innerHTML = '';
        this.timingData.chapters.forEach((chapter, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = chapter.title;
            this.chapterSelect.appendChild(option);
        });

        // Show reader view
        document.getElementById('empty-state').classList.remove('active');
        document.getElementById('reader-view').style.display = 'block';
        document.getElementById('player').style.display = 'block';

        // Load first chapter
        this.loadChapter(0);
    }

    /**
     * Load a specific chapter
     */
    async loadChapter(chapterIndex) {
        this.currentChapter = chapterIndex;
        this.currentSentenceIndex = -1;

        const chapter = this.timingData.chapters[chapterIndex];
        const textChapter = this.textData.chapters[chapterIndex];

        // Update chapter select
        this.chapterSelect.value = chapterIndex;

        // Update navigation buttons
        document.getElementById('prev-chapter').disabled = chapterIndex === 0;
        document.getElementById('next-chapter').disabled = chapterIndex === this.timingData.chapters.length - 1;

        // Render text
        this.renderText(textChapter);

        // Load audio
        const audioFileName = chapter.audioFile.split('/').pop();
        if (this.audioFiles[audioFileName]) {
            const audioUrl = URL.createObjectURL(this.audioFiles[audioFileName]);
            this.audio.src = audioUrl;
        }

        // Reset progress
        this.progressFill.style.width = '0%';
        this.progressHandle.style.left = '0%';
        this.currentTimeEl.textContent = '0:00';

        // Scroll to top
        this.textContent.scrollTop = 0;
    }

    /**
     * Render text content with sentence spans
     */
    renderText(chapterData) {
        this.textContent.innerHTML = '';

        chapterData.paragraphs.forEach(paragraph => {
            const paraEl = document.createElement('p');
            paraEl.className = 'paragraph';
            paraEl.dataset.id = paragraph.id;

            paragraph.sentences.forEach(sentence => {
                const sentenceEl = document.createElement('span');
                sentenceEl.className = 'sentence';
                sentenceEl.dataset.id = sentence.id;
                sentenceEl.textContent = sentence.text + ' ';

                // Click to seek
                sentenceEl.addEventListener('click', () => {
                    this.seekToSentence(sentence.id);
                });

                paraEl.appendChild(sentenceEl);
            });

            this.textContent.appendChild(paraEl);
        });
    }

    /**
     * Handle audio time updates
     */
    onTimeUpdate() {
        const currentTime = this.audio.currentTime;
        const duration = this.audio.duration || 0;

        // Update progress bar
        const percent = (currentTime / duration) * 100;
        this.progressFill.style.width = `${percent}%`;
        this.progressHandle.style.left = `${percent}%`;

        // Update time display
        this.currentTimeEl.textContent = this.formatTime(currentTime);

        // Find and highlight current sentence
        this.highlightCurrentSentence(currentTime);
    }

    /**
     * Find and highlight the sentence at current time
     */
    highlightCurrentSentence(currentTime) {
        const chapter = this.timingData.chapters[this.currentChapter];
        const entries = chapter.entries;

        // Find current sentence
        let currentIndex = -1;
        for (let i = 0; i < entries.length; i++) {
            if (currentTime >= entries[i].start && currentTime < entries[i].end) {
                currentIndex = i;
                break;
            }
            // If between sentences, highlight the upcoming one
            if (currentTime < entries[i].start) {
                currentIndex = i > 0 ? i - 1 : -1;
                break;
            }
        }

        // Handle end of chapter
        if (currentIndex === -1 && entries.length > 0 && currentTime >= entries[entries.length - 1].start) {
            currentIndex = entries.length - 1;
        }

        // Update highlighting if changed
        if (currentIndex !== this.currentSentenceIndex) {
            this.currentSentenceIndex = currentIndex;
            this.updateHighlighting();
        }
    }

    /**
     * Update sentence highlighting
     */
    updateHighlighting() {
        const chapter = this.timingData.chapters[this.currentChapter];
        const entries = chapter.entries;

        // Remove all highlights
        document.querySelectorAll('.sentence.active, .sentence.played').forEach(el => {
            el.classList.remove('active', 'played');
        });

        // Apply new highlights
        entries.forEach((entry, index) => {
            const el = document.querySelector(`[data-id="${entry.id}"]`);
            if (el) {
                if (index === this.currentSentenceIndex) {
                    el.classList.add('active');
                    // Auto-scroll
                    if (this.autoScroll && this.isPlaying) {
                        this.scrollToElement(el);
                    }
                } else if (index < this.currentSentenceIndex) {
                    el.classList.add('played');
                }
            }
        });
    }

    /**
     * Scroll to element smoothly
     */
    scrollToElement(element) {
        const container = this.textContent;
        const elementRect = element.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();

        // Check if element is out of view
        if (elementRect.top < containerRect.top + 100 || elementRect.bottom > containerRect.bottom - 100) {
            const scrollTop = element.offsetTop - container.offsetTop - (container.clientHeight / 3);
            container.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
            });
        }
    }

    /**
     * Seek to a specific sentence
     */
    seekToSentence(sentenceId) {
        const chapter = this.timingData.chapters[this.currentChapter];
        const entry = chapter.entries.find(e => e.id === sentenceId);

        if (entry) {
            this.audio.currentTime = entry.start;
            if (!this.isPlaying) {
                this.audio.play();
            }
        }
    }

    /**
     * Handle progress bar click
     */
    seekTo(event) {
        const rect = this.progressBar.getBoundingClientRect();
        const percent = (event.clientX - rect.left) / rect.width;
        this.audio.currentTime = percent * this.audio.duration;
    }

    /**
     * Start dragging progress handle
     */
    startDragging() {
        const onMouseMove = (e) => {
            const rect = this.progressBar.getBoundingClientRect();
            const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            this.progressFill.style.width = `${percent * 100}%`;
            this.progressHandle.style.left = `${percent * 100}%`;
        };

        const onMouseUp = (e) => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            this.seekTo(e);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    /**
     * Toggle play/pause
     */
    togglePlay() {
        if (this.audio.paused) {
            this.audio.play();
        } else {
            this.audio.pause();
        }
    }

    /**
     * Update play button state
     */
    updatePlayState(playing) {
        this.isPlaying = playing;
        this.playIcon.style.display = playing ? 'none' : 'block';
        this.pauseIcon.style.display = playing ? 'block' : 'none';
    }

    /**
     * Handle chapter end
     */
    onChapterEnd() {
        // Auto-advance to next chapter
        if (this.currentChapter < this.timingData.chapters.length - 1) {
            this.loadChapter(this.currentChapter + 1);
            this.audio.play();
        }
    }

    /**
     * Handle audio loaded
     */
    onAudioLoaded() {
        this.totalTimeEl.textContent = this.formatTime(this.audio.duration);
    }

    /**
     * Set playback speed
     */
    setSpeed(speed) {
        this.playbackSpeed = speed;
        this.audio.playbackRate = speed;
        document.getElementById('speed-value').textContent = `${speed}x`;
        document.getElementById('speed-menu').classList.remove('show');

        // Update active button
        document.querySelectorAll('#speed-menu button').forEach(btn => {
            btn.classList.toggle('active', parseFloat(btn.dataset.speed) === speed);
        });

        this.saveSettings();
    }

    /**
     * Set font size
     */
    setFontSize(size) {
        this.fontSize = Math.max(12, Math.min(32, size));
        document.documentElement.style.setProperty('--font-size', `${this.fontSize}px`);
        document.getElementById('font-size-value').textContent = `${this.fontSize}px`;
        this.saveSettings();
    }

    /**
     * Set theme
     */
    setTheme(theme) {
        document.body.dataset.theme = theme;
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
        this.saveSettings();
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboard(event) {
        // Ignore if in input field
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT') return;

        switch (event.code) {
            case 'Space':
                event.preventDefault();
                this.togglePlay();
                break;
            case 'ArrowLeft':
                this.audio.currentTime = Math.max(0, this.audio.currentTime - 5);
                break;
            case 'ArrowRight':
                this.audio.currentTime = Math.min(this.audio.duration, this.audio.currentTime + 5);
                break;
            case 'ArrowUp':
                event.preventDefault();
                if (this.currentChapter > 0) this.loadChapter(this.currentChapter - 1);
                break;
            case 'ArrowDown':
                event.preventDefault();
                if (this.currentChapter < this.timingData.chapters.length - 1) {
                    this.loadChapter(this.currentChapter + 1);
                }
                break;
        }
    }

    /**
     * Format time in M:SS
     */
    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Show/hide loading state
     */
    showLoading(show) {
        document.getElementById('loading-state').classList.toggle('active', show);
        document.getElementById('empty-state').classList.toggle('active', !show);
    }

    /**
     * Save settings to localStorage
     */
    saveSettings() {
        localStorage.setItem('readalong-settings', JSON.stringify({
            fontSize: this.fontSize,
            theme: document.body.dataset.theme || 'light',
            speed: this.playbackSpeed,
            autoScroll: this.autoScroll,
        }));
    }

    /**
     * Load settings from localStorage
     */
    loadSettings() {
        try {
            const settings = JSON.parse(localStorage.getItem('readalong-settings') || '{}');

            if (settings.fontSize) this.setFontSize(settings.fontSize);
            if (settings.theme) this.setTheme(settings.theme);
            if (settings.speed) this.setSpeed(settings.speed);
            if (settings.autoScroll !== undefined) {
                this.autoScroll = settings.autoScroll;
                document.getElementById('auto-scroll').checked = this.autoScroll;
            }
        } catch (e) {
            console.warn('Could not load settings:', e);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reader = new ReadAlongReader();
});
