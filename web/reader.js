/**
 * Read-Along Reader - Enhanced Version
 *
 * Synchronized audio-text playback with:
 * - Sentence highlighting and tap-to-seek
 * - Bookmarks and notes
 * - Search inside book
 * - Sleep timer
 * - Progress persistence
 * - Offline support (PWA)
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

        // Bookmarks and Notes
        this.bookmarks = [];
        this.notes = [];
        this.highlights = [];

        // Sleep timer
        this.sleepTimer = null;
        this.sleepTimerEnd = null;
        this.sleepTimerMode = null; // 'minutes' or 'chapter'

        // Selection for notes
        this.selectedText = null;
        this.selectedSentenceId = null;

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

        // Book catalog for URL-based loading
        this.booksCatalog = {
            'the-intelligent-investor': '../output/readalong/the-intelligent-investor'
        };

        // Initialize
        this.bindEvents();
        this.loadSettings();

        // Check for book in URL
        this.checkUrlForBook();
    }

    /**
     * Check URL for book parameter and load it
     */
    async checkUrlForBook() {
        const params = new URLSearchParams(window.location.search);
        const bookId = params.get('book');

        if (bookId && this.booksCatalog[bookId]) {
            await this.loadBookFromPath(this.booksCatalog[bookId]);
        }
    }

    /**
     * Load book from server path
     */
    async loadBookFromPath(basePath) {
        try {
            this.showLoading(true);

            // Fetch manifest
            const manifestResponse = await fetch(`${basePath}/manifest.json`);
            if (!manifestResponse.ok) throw new Error('Book not found');
            this.bookData = await manifestResponse.json();

            // Fetch timing data
            const timingResponse = await fetch(`${basePath}/${this.bookData.timing}`);
            if (timingResponse.ok) {
                this.timingData = await timingResponse.json();
            }

            // Fetch text data
            const textResponse = await fetch(`${basePath}/${this.bookData.text}`);
            if (textResponse.ok) {
                this.textData = await textResponse.json();
            }

            // Store base path for audio files
            this.audioBasePath = basePath;

            // Load bookmarks and notes for this book
            this.loadBookData();

            // Initialize reader
            this.initializeReader();

        } catch (error) {
            console.error('Error loading book:', error);
            this.showToast('Error loading book: ' + error.message);
            this.showLoading(false);
        }
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

        // Book selection (if elements exist - for backwards compatibility)
        const selectBookBtn = document.getElementById('select-book-btn');
        const folderInput = document.getElementById('folder-input');
        if (selectBookBtn && folderInput) {
            selectBookBtn.addEventListener('click', () => {
                folderInput.click();
            });
            folderInput.addEventListener('change', (e) => {
                this.handleFolderSelect(e.target.files);
            });
        }

        // Bookmarks panel
        document.getElementById('menu-btn').addEventListener('click', () => {
            document.getElementById('bookmarks-panel').classList.toggle('open');
        });
        document.getElementById('close-bookmarks').addEventListener('click', () => {
            document.getElementById('bookmarks-panel').classList.remove('open');
        });

        // Add bookmark button
        document.getElementById('bookmark-btn').addEventListener('click', () => {
            this.addBookmark();
        });

        // Search
        document.getElementById('search-btn').addEventListener('click', () => {
            this.openSearchModal();
        });
        document.getElementById('close-search').addEventListener('click', () => {
            this.closeSearchModal();
        });
        document.getElementById('search-submit').addEventListener('click', () => {
            this.performSearch();
        });
        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // Sleep timer
        document.getElementById('sleep-timer-btn').addEventListener('click', () => {
            this.openSleepTimerModal();
        });
        document.getElementById('close-sleep-timer').addEventListener('click', () => {
            this.closeSleepTimerModal();
        });
        document.querySelectorAll('.timer-options button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const minutes = e.target.dataset.minutes;
                this.setSleepTimer(minutes);
            });
        });

        // Notes modal
        document.getElementById('close-notes').addEventListener('click', () => {
            this.closeNotesModal();
        });
        document.getElementById('save-note').addEventListener('click', () => {
            this.saveNote();
        });
        document.getElementById('highlight-only').addEventListener('click', () => {
            this.addHighlight();
        });

        // Text selection for notes
        document.addEventListener('mouseup', (e) => {
            if (e.target.closest('.text-content')) {
                this.handleTextSelection();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));

        // Close menus on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.speed-control')) {
                document.getElementById('speed-menu').classList.remove('show');
            }
            if (!e.target.closest('.side-panel') && !e.target.closest('#menu-btn')) {
                document.getElementById('bookmarks-panel').classList.remove('open');
            }
        });

        // Close modals on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('open');
                }
            });
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
            this.showToast('No manifest.json found. Please select a processed book folder.');
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
                if (name.endsWith('.wav') || name.endsWith('.mp3') || name.endsWith('.m4a')) {
                    this.audioFiles[name] = file;
                }
            }

            // Load bookmarks and notes for this book
            this.loadBookData();

            // Initialize reader
            this.initializeReader();

        } catch (error) {
            console.error('Error loading book:', error);
            this.showToast('Error loading book: ' + error.message);
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

        // Load saved progress or first chapter
        const savedProgress = this.getSavedProgress();
        if (savedProgress) {
            this.loadChapter(savedProgress.chapter, savedProgress.position);
            this.showToast('Resumed from where you left off');
        } else {
            this.loadChapter(0);
        }

        // Render bookmarks
        this.renderBookmarks();
        this.renderNotes();
    }

    /**
     * Load a specific chapter
     */
    async loadChapter(chapterIndex, startPosition = 0) {
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

        // Check if loading from URL (audioBasePath) or from folder (audioFiles)
        if (this.audioBasePath) {
            // URL-based loading
            this.audio.src = `${this.audioBasePath}/audio/${audioFileName}`;

            // Wait for audio to load then seek
            this.audio.addEventListener('loadedmetadata', () => {
                if (startPosition > 0) {
                    this.audio.currentTime = startPosition;
                }
            }, { once: true });
        } else if (this.audioFiles && this.audioFiles[audioFileName]) {
            // Folder-based loading
            const audioUrl = URL.createObjectURL(this.audioFiles[audioFileName]);
            this.audio.src = audioUrl;

            // Wait for audio to load then seek
            this.audio.addEventListener('loadedmetadata', () => {
                if (startPosition > 0) {
                    this.audio.currentTime = startPosition;
                }
            }, { once: true });
        }

        // Reset progress
        this.progressFill.style.width = '0%';
        this.progressHandle.style.left = '0%';
        this.currentTimeEl.textContent = '0:00';

        // Update bookmark markers
        this.updateBookmarkMarkers();

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

                // Check if has note or highlight
                if (this.notes.some(n => n.sentenceId === sentence.id)) {
                    sentenceEl.classList.add('has-note');
                }
                if (this.highlights.some(h => h.sentenceId === sentence.id)) {
                    sentenceEl.classList.add('highlighted');
                }

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

        // Save progress periodically
        this.saveProgress();

        // Check sleep timer
        this.checkSleepTimer();
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

        // Remove active class from all
        document.querySelectorAll('.sentence.active').forEach(el => {
            el.classList.remove('active');
        });

        // Update played state
        document.querySelectorAll('.sentence.played').forEach(el => {
            el.classList.remove('played');
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
        // Check if sleep timer is set to end of chapter
        if (this.sleepTimerMode === 'chapter') {
            this.cancelSleepTimer();
            this.showToast('Sleep timer ended');
            return;
        }

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
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.tagName === 'SELECT') return;

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
            case 'KeyB':
                this.addBookmark();
                break;
            case 'KeyF':
                if (event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    this.openSearchModal();
                }
                break;
        }
    }

    // ==================== BOOKMARKS ====================

    /**
     * Add a bookmark at current position
     */
    addBookmark() {
        if (!this.bookData) return;

        const chapter = this.timingData.chapters[this.currentChapter];
        const currentTime = this.audio.currentTime;
        const currentEntry = chapter.entries[this.currentSentenceIndex] || {};

        const bookmark = {
            id: Date.now().toString(),
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            chapterTitle: chapter.title,
            time: currentTime,
            text: currentEntry.text || '',
            createdAt: new Date().toISOString()
        };

        this.bookmarks.push(bookmark);
        this.saveBookData();
        this.renderBookmarks();
        this.updateBookmarkMarkers();
        this.showToast('Bookmark added');

        // Flash the bookmark button
        document.getElementById('bookmark-btn').classList.add('active');
        setTimeout(() => {
            document.getElementById('bookmark-btn').classList.remove('active');
        }, 500);
    }

    /**
     * Remove a bookmark
     */
    removeBookmark(id) {
        this.bookmarks = this.bookmarks.filter(b => b.id !== id);
        this.saveBookData();
        this.renderBookmarks();
        this.updateBookmarkMarkers();
        this.showToast('Bookmark removed');
    }

    /**
     * Jump to a bookmark
     */
    jumpToBookmark(bookmark) {
        if (bookmark.chapter !== this.currentChapter) {
            this.loadChapter(bookmark.chapter, bookmark.time);
        } else {
            this.audio.currentTime = bookmark.time;
        }
        if (!this.isPlaying) {
            this.audio.play();
        }
        document.getElementById('bookmarks-panel').classList.remove('open');
    }

    /**
     * Render bookmarks list
     */
    renderBookmarks() {
        const container = document.getElementById('bookmarks-list');
        const bookBookmarks = this.bookmarks.filter(b => b.bookId === this.bookData?.bookId);

        if (bookBookmarks.length === 0) {
            container.innerHTML = '<p class="empty-message">No bookmarks yet. Click the bookmark button while listening to add one.</p>';
            return;
        }

        container.innerHTML = bookBookmarks.map(b => `
            <div class="bookmark-item" data-id="${b.id}">
                <button class="bookmark-delete" onclick="event.stopPropagation(); reader.removeBookmark('${b.id}')">Delete</button>
                <div class="bookmark-time">${this.formatTime(b.time)}</div>
                <div class="bookmark-chapter">${b.chapterTitle}</div>
                <div class="bookmark-text">"${b.text.substring(0, 60)}${b.text.length > 60 ? '...' : ''}"</div>
            </div>
        `).join('');

        // Add click handlers
        container.querySelectorAll('.bookmark-item').forEach(item => {
            item.addEventListener('click', () => {
                const bookmark = this.bookmarks.find(b => b.id === item.dataset.id);
                if (bookmark) this.jumpToBookmark(bookmark);
            });
        });
    }

    /**
     * Update bookmark markers on progress bar
     */
    updateBookmarkMarkers() {
        const container = document.getElementById('bookmark-markers');
        const chapterBookmarks = this.bookmarks.filter(
            b => b.bookId === this.bookData?.bookId && b.chapter === this.currentChapter
        );
        const duration = this.audio.duration || 1;

        container.innerHTML = chapterBookmarks.map(b => {
            const percent = (b.time / duration) * 100;
            return `<div class="bookmark-marker" style="left: ${percent}%"></div>`;
        }).join('');
    }

    // ==================== NOTES ====================

    /**
     * Handle text selection for notes
     */
    handleTextSelection() {
        const selection = window.getSelection();
        const text = selection.toString().trim();

        if (text.length > 0) {
            // Find the sentence element
            let node = selection.anchorNode;
            while (node && !node.classList?.contains('sentence')) {
                node = node.parentNode;
            }

            if (node && node.classList?.contains('sentence')) {
                this.selectedText = text;
                this.selectedSentenceId = node.dataset.id;
                this.openNotesModal(text);
            }
        }
    }

    /**
     * Open notes modal
     */
    openNotesModal(text) {
        document.getElementById('selected-text-preview').textContent = `"${text}"`;
        document.getElementById('note-input').value = '';
        document.getElementById('notes-modal').classList.add('open');
    }

    /**
     * Close notes modal
     */
    closeNotesModal() {
        document.getElementById('notes-modal').classList.remove('open');
        window.getSelection().removeAllRanges();
    }

    /**
     * Save a note
     */
    saveNote() {
        const noteText = document.getElementById('note-input').value.trim();
        if (!noteText && !this.selectedText) return;

        const note = {
            id: Date.now().toString(),
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            sentenceId: this.selectedSentenceId,
            selectedText: this.selectedText,
            note: noteText,
            createdAt: new Date().toISOString()
        };

        this.notes.push(note);
        this.saveBookData();
        this.renderNotes();
        this.closeNotesModal();

        // Update sentence styling
        const el = document.querySelector(`[data-id="${this.selectedSentenceId}"]`);
        if (el) el.classList.add('has-note');

        this.showToast('Note saved');
    }

    /**
     * Add highlight only (no note text)
     */
    addHighlight() {
        if (!this.selectedSentenceId) return;

        const highlight = {
            id: Date.now().toString(),
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            sentenceId: this.selectedSentenceId,
            text: this.selectedText,
            createdAt: new Date().toISOString()
        };

        this.highlights.push(highlight);
        this.saveBookData();
        this.closeNotesModal();

        // Update sentence styling
        const el = document.querySelector(`[data-id="${this.selectedSentenceId}"]`);
        if (el) el.classList.add('highlighted');

        this.showToast('Highlight added');
    }

    /**
     * Remove a note
     */
    removeNote(id) {
        const note = this.notes.find(n => n.id === id);
        if (note) {
            const el = document.querySelector(`[data-id="${note.sentenceId}"]`);
            if (el) el.classList.remove('has-note');
        }
        this.notes = this.notes.filter(n => n.id !== id);
        this.saveBookData();
        this.renderNotes();
        this.showToast('Note removed');
    }

    /**
     * Render notes list
     */
    renderNotes() {
        const container = document.getElementById('notes-list');
        const bookNotes = this.notes.filter(n => n.bookId === this.bookData?.bookId);

        if (bookNotes.length === 0) {
            container.innerHTML = '<p class="empty-message">No notes yet. Select text to add a note.</p>';
            return;
        }

        container.innerHTML = bookNotes.map(n => `
            <div class="note-item" data-id="${n.id}">
                <button class="note-delete" onclick="event.stopPropagation(); reader.removeNote('${n.id}')">Delete</button>
                <div class="note-text">"${n.selectedText.substring(0, 50)}${n.selectedText.length > 50 ? '...' : ''}"</div>
                <div class="note-content">${n.note}</div>
            </div>
        `).join('');

        // Add click handlers to jump to note location
        container.querySelectorAll('.note-item').forEach(item => {
            item.addEventListener('click', () => {
                const note = this.notes.find(n => n.id === item.dataset.id);
                if (note) {
                    if (note.chapter !== this.currentChapter) {
                        this.loadChapter(note.chapter);
                    }
                    setTimeout(() => {
                        const el = document.querySelector(`[data-id="${note.sentenceId}"]`);
                        if (el) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            el.classList.add('active');
                            setTimeout(() => el.classList.remove('active'), 2000);
                        }
                    }, 500);
                    document.getElementById('bookmarks-panel').classList.remove('open');
                }
            });
        });
    }

    // ==================== SEARCH ====================

    /**
     * Open search modal
     */
    openSearchModal() {
        document.getElementById('search-modal').classList.add('open');
        document.getElementById('search-input').focus();
    }

    /**
     * Close search modal
     */
    closeSearchModal() {
        document.getElementById('search-modal').classList.remove('open');
        document.getElementById('search-input').value = '';
        document.getElementById('search-results').innerHTML = '<p class="empty-message">Enter a search term above.</p>';
        // Remove search highlights
        document.querySelectorAll('.sentence.search-match').forEach(el => {
            el.classList.remove('search-match');
        });
    }

    /**
     * Perform search across all chapters
     */
    performSearch() {
        const query = document.getElementById('search-input').value.trim().toLowerCase();
        if (!query) return;

        const results = [];

        this.textData.chapters.forEach((chapter, chapterIndex) => {
            chapter.paragraphs.forEach(paragraph => {
                paragraph.sentences.forEach(sentence => {
                    if (sentence.text.toLowerCase().includes(query)) {
                        results.push({
                            chapter: chapterIndex,
                            chapterTitle: this.timingData.chapters[chapterIndex].title,
                            sentenceId: sentence.id,
                            text: sentence.text,
                            query: query
                        });
                    }
                });
            });
        });

        this.renderSearchResults(results, query);
    }

    /**
     * Render search results
     */
    renderSearchResults(results, query) {
        const container = document.getElementById('search-results');

        if (results.length === 0) {
            container.innerHTML = '<p class="empty-message">No results found.</p>';
            return;
        }

        const countHtml = `<div class="search-count">${results.length} result${results.length > 1 ? 's' : ''} found</div>`;

        const resultsHtml = results.slice(0, 50).map(r => {
            const highlightedText = r.text.replace(
                new RegExp(`(${this.escapeRegex(query)})`, 'gi'),
                '<mark>$1</mark>'
            );
            return `
                <div class="search-result-item" data-chapter="${r.chapter}" data-sentence="${r.sentenceId}">
                    <div class="search-result-chapter">${r.chapterTitle}</div>
                    <div class="search-result-text">${highlightedText}</div>
                </div>
            `;
        }).join('');

        container.innerHTML = countHtml + resultsHtml;

        // Add click handlers
        container.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const chapter = parseInt(item.dataset.chapter);
                const sentenceId = item.dataset.sentence;
                this.jumpToSearchResult(chapter, sentenceId, query);
            });
        });
    }

    /**
     * Jump to search result
     */
    jumpToSearchResult(chapter, sentenceId, query) {
        // Remove old highlights
        document.querySelectorAll('.sentence.search-match').forEach(el => {
            el.classList.remove('search-match');
        });

        if (chapter !== this.currentChapter) {
            this.loadChapter(chapter);
            setTimeout(() => this.highlightSearchResult(sentenceId), 500);
        } else {
            this.highlightSearchResult(sentenceId);
        }

        this.closeSearchModal();
    }

    /**
     * Highlight and scroll to search result
     */
    highlightSearchResult(sentenceId) {
        const el = document.querySelector(`[data-id="${sentenceId}"]`);
        if (el) {
            el.classList.add('search-match');
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Also seek audio to this sentence
            this.seekToSentence(sentenceId);
        }
    }

    /**
     * Escape regex special characters
     */
    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // ==================== SLEEP TIMER ====================

    /**
     * Open sleep timer modal
     */
    openSleepTimerModal() {
        document.getElementById('sleep-timer-modal').classList.add('open');
    }

    /**
     * Close sleep timer modal
     */
    closeSleepTimerModal() {
        document.getElementById('sleep-timer-modal').classList.remove('open');
    }

    /**
     * Set sleep timer
     */
    setSleepTimer(value) {
        this.cancelSleepTimer();

        if (value === '0') {
            this.showToast('Sleep timer cancelled');
            this.closeSleepTimerModal();
            return;
        }

        if (value === 'chapter') {
            this.sleepTimerMode = 'chapter';
            this.showToast('Will stop at end of chapter');
            document.getElementById('sleep-timer-display').textContent = 'End of chapter';
            document.getElementById('sleep-timer-btn').classList.add('active');
        } else {
            const minutes = parseInt(value);
            this.sleepTimerMode = 'minutes';
            this.sleepTimerEnd = Date.now() + minutes * 60 * 1000;
            this.showToast(`Sleep timer set for ${minutes} minutes`);
            document.getElementById('sleep-timer-btn').classList.add('active');
        }

        this.closeSleepTimerModal();
    }

    /**
     * Check and update sleep timer
     */
    checkSleepTimer() {
        if (!this.sleepTimerEnd && this.sleepTimerMode !== 'chapter') return;

        if (this.sleepTimerMode === 'minutes') {
            const remaining = Math.max(0, this.sleepTimerEnd - Date.now());
            const minutes = Math.floor(remaining / 60000);
            const seconds = Math.floor((remaining % 60000) / 1000);

            document.getElementById('sleep-timer-display').textContent =
                `${minutes}:${seconds.toString().padStart(2, '0')}`;

            if (remaining <= 0) {
                this.audio.pause();
                this.cancelSleepTimer();
                this.showToast('Sleep timer ended');
            }
        }
    }

    /**
     * Cancel sleep timer
     */
    cancelSleepTimer() {
        this.sleepTimerEnd = null;
        this.sleepTimerMode = null;
        document.getElementById('sleep-timer-display').textContent = '';
        document.getElementById('sleep-timer-btn').classList.remove('active');
    }

    // ==================== PROGRESS PERSISTENCE ====================

    /**
     * Save current progress
     */
    saveProgress() {
        if (!this.bookData) return;

        const progress = {
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            position: this.audio.currentTime,
            updatedAt: Date.now()
        };

        localStorage.setItem(`readalong-progress-${this.bookData.bookId}`, JSON.stringify(progress));
    }

    /**
     * Get saved progress for current book
     */
    getSavedProgress() {
        if (!this.bookData) return null;

        try {
            const saved = localStorage.getItem(`readalong-progress-${this.bookData.bookId}`);
            if (saved) {
                const progress = JSON.parse(saved);
                // Only use if less than 30 days old
                if (Date.now() - progress.updatedAt < 30 * 24 * 60 * 60 * 1000) {
                    return progress;
                }
            }
        } catch (e) {
            console.warn('Could not load progress:', e);
        }
        return null;
    }

    // ==================== DATA PERSISTENCE ====================

    /**
     * Load book-specific data (bookmarks, notes)
     */
    loadBookData() {
        try {
            const saved = localStorage.getItem('readalong-bookdata');
            if (saved) {
                const data = JSON.parse(saved);
                this.bookmarks = data.bookmarks || [];
                this.notes = data.notes || [];
                this.highlights = data.highlights || [];
            }
        } catch (e) {
            console.warn('Could not load book data:', e);
        }
    }

    /**
     * Save book-specific data
     */
    saveBookData() {
        const data = {
            bookmarks: this.bookmarks,
            notes: this.notes,
            highlights: this.highlights
        };
        localStorage.setItem('readalong-bookdata', JSON.stringify(data));
    }

    // ==================== SETTINGS ====================

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

    // ==================== UTILITIES ====================

    /**
     * Format time in M:SS or H:MM:SS
     */
    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';

        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
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
     * Show toast notification
     */
    showToast(message) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.add('show');

        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reader = new ReadAlongReader();
});
