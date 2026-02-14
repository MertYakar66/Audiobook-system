/**
 * Read-Along Reader - Professional Edition
 *
 * Synchronized audio-text playback with:
 * - Sentence highlighting and tap-to-seek
 * - Professional bookmarks and notes
 * - Multi-color highlighting
 * - Search inside book
 * - Sleep timer
 * - Progress persistence with resume
 * - Mobile-optimized with touch gestures
 * - Offline support (PWA)
 */

class ReadAlongReader {
    constructor() {
        // State
        this.bookData = null;
        this.timingData = null;
        this.textData = null;
        this.pagesData = null;
        this.currentChapter = 0;
        this.currentSentenceIndex = -1;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.autoScroll = true;
        this.fontSize = 18;

        // Page viewer state
        this.currentPage = 1;
        this.totalPages = 0;
        this.pageZoom = 1.0;
        this.splitView = false;
        this.pageFiles = {};

        // Bookmarks and Notes
        this.bookmarks = [];
        this.notes = [];
        this.highlights = [];

        // Highlight colors
        this.highlightColors = [
            { name: 'yellow', color: '#fff59d' },
            { name: 'green', color: '#c8e6c9' },
            { name: 'blue', color: '#bbdefb' },
            { name: 'pink', color: '#f8bbd9' },
            { name: 'orange', color: '#ffcc80' }
        ];
        this.selectedHighlightColor = 'yellow';

        // Sleep timer
        this.sleepTimer = null;
        this.sleepTimerEnd = null;
        this.sleepTimerMode = null; // 'minutes' or 'chapter'

        // Selection for notes
        this.selectedText = null;
        this.selectedSentenceId = null;
        this.selectionRange = null;

        // Mobile/touch state
        this.isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        this.touchStartX = 0;
        this.touchStartY = 0;
        this.wakeLock = null;

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

        // Page viewer DOM elements
        this.splitContainer = document.getElementById('split-container');
        this.pagePanel = document.getElementById('page-panel');
        this.pageViewBtn = document.getElementById('page-view-btn');
        this.pageImage = document.getElementById('page-image');
        this.pageIndicator = document.getElementById('page-indicator');
        this.pageZoomValue = document.getElementById('page-zoom-value');
        this.pagePrevBtn = document.getElementById('page-prev');
        this.pageNextBtn = document.getElementById('page-next');
        this.pageZoomInBtn = document.getElementById('page-zoom-in');
        this.pageZoomOutBtn = document.getElementById('page-zoom-out');

        // Book catalog for URL-based loading
        this.booksCatalog = {
            'the-intelligent-investor': '../output/readalong/The-Intelligent-Investor'
        };

        // Initialize
        this.bindEvents();
        this.loadSettings();
        this.setupMobileFeatures();
        this.createSelectionToolbar();

        // Check for book in URL
        this.checkUrlForBook();
    }

    /**
     * Setup mobile-specific features
     */
    setupMobileFeatures() {
        if (this.isMobile) {
            document.body.classList.add('mobile-device');

            // Request wake lock when playing
            this.audio.addEventListener('play', () => this.requestWakeLock());
            this.audio.addEventListener('pause', () => this.releaseWakeLock());

            // Touch gestures for page viewer
            const pageViewer = document.getElementById('page-viewer');
            if (pageViewer) {
                pageViewer.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: true });
                pageViewer.addEventListener('touchend', (e) => this.handleTouchEnd(e), { passive: true });
            }

            // Swipe gestures for chapter navigation
            this.textContent.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: true });
            this.textContent.addEventListener('touchend', (e) => this.handleSwipeEnd(e), { passive: true });
        }
    }

    /**
     * Request screen wake lock for mobile
     */
    async requestWakeLock() {
        if ('wakeLock' in navigator && !this.wakeLock) {
            try {
                this.wakeLock = await navigator.wakeLock.request('screen');
                this.wakeLock.addEventListener('release', () => {
                    this.wakeLock = null;
                });
            } catch (err) {
                console.log('Wake lock request failed:', err);
            }
        }
    }

    /**
     * Release screen wake lock
     */
    releaseWakeLock() {
        if (this.wakeLock) {
            this.wakeLock.release();
            this.wakeLock = null;
        }
    }

    /**
     * Handle touch start
     */
    handleTouchStart(e) {
        this.touchStartX = e.touches[0].clientX;
        this.touchStartY = e.touches[0].clientY;
    }

    /**
     * Handle touch end for page swipe
     */
    handleTouchEnd(e) {
        if (!this.splitView) return;

        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        const deltaX = touchEndX - this.touchStartX;
        const deltaY = touchEndY - this.touchStartY;

        // Only handle horizontal swipes
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
            if (deltaX > 0) {
                this.prevPage();
            } else {
                this.nextPage();
            }
        }
    }

    /**
     * Handle swipe for chapter navigation
     */
    handleSwipeEnd(e) {
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        const deltaX = touchEndX - this.touchStartX;
        const deltaY = touchEndY - this.touchStartY;

        // Only handle significant horizontal swipes at edges
        if (Math.abs(deltaX) > 100 && Math.abs(deltaX) > Math.abs(deltaY) * 2) {
            // Swipe right from left edge = previous chapter
            if (deltaX > 0 && this.touchStartX < 50 && this.currentChapter > 0) {
                this.loadChapter(this.currentChapter - 1);
                this.showToast('Previous chapter');
            }
            // Swipe left from right edge = next chapter
            else if (deltaX < 0 && this.touchStartX > window.innerWidth - 50) {
                if (this.currentChapter < this.timingData.chapters.length - 1) {
                    this.loadChapter(this.currentChapter + 1);
                    this.showToast('Next chapter');
                }
            }
        }
    }

    /**
     * Create floating selection toolbar
     */
    createSelectionToolbar() {
        // Create toolbar element
        const toolbar = document.createElement('div');
        toolbar.id = 'selection-toolbar';
        toolbar.className = 'selection-toolbar';
        toolbar.innerHTML = `
            <div class="toolbar-colors">
                ${this.highlightColors.map(c =>
                    `<button class="color-btn" data-color="${c.name}" style="background: ${c.color}" title="Highlight ${c.name}"></button>`
                ).join('')}
            </div>
            <div class="toolbar-actions">
                <button class="toolbar-btn" id="toolbar-highlight" title="Highlight">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                    </svg>
                </button>
                <button class="toolbar-btn" id="toolbar-note" title="Add Note">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                </button>
                <button class="toolbar-btn" id="toolbar-copy" title="Copy">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                </button>
            </div>
        `;
        document.body.appendChild(toolbar);

        // Bind toolbar events
        toolbar.querySelectorAll('.color-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectedHighlightColor = btn.dataset.color;
                toolbar.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
            });
        });

        // Set default color
        toolbar.querySelector('.color-btn[data-color="yellow"]').classList.add('selected');

        document.getElementById('toolbar-highlight').addEventListener('click', (e) => {
            e.stopPropagation();
            this.addHighlightFromToolbar();
        });

        document.getElementById('toolbar-note').addEventListener('click', (e) => {
            e.stopPropagation();
            this.hideSelectionToolbar();
            if (this.selectedText) {
                this.openNotesModal(this.selectedText);
            }
        });

        document.getElementById('toolbar-copy').addEventListener('click', (e) => {
            e.stopPropagation();
            this.copySelectedText();
        });

        this.selectionToolbar = toolbar;
    }

    /**
     * Show selection toolbar near selection
     */
    showSelectionToolbar(x, y) {
        const toolbar = this.selectionToolbar;
        const toolbarWidth = 220;
        const toolbarHeight = 80;

        // Position toolbar above selection
        let posX = x - toolbarWidth / 2;
        let posY = y - toolbarHeight - 10;

        // Keep within viewport
        posX = Math.max(10, Math.min(posX, window.innerWidth - toolbarWidth - 10));
        posY = Math.max(10, posY);

        // If not enough space above, show below
        if (posY < 10) {
            posY = y + 20;
        }

        toolbar.style.left = `${posX}px`;
        toolbar.style.top = `${posY}px`;
        toolbar.classList.add('visible');
    }

    /**
     * Hide selection toolbar
     */
    hideSelectionToolbar() {
        if (this.selectionToolbar) {
            this.selectionToolbar.classList.remove('visible');
        }
    }

    /**
     * Add highlight from toolbar
     */
    addHighlightFromToolbar() {
        if (!this.selectedSentenceId || !this.bookData) return;

        const highlight = {
            id: Date.now().toString(),
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            sentenceId: this.selectedSentenceId,
            text: this.selectedText,
            color: this.selectedHighlightColor,
            createdAt: new Date().toISOString()
        };

        this.highlights.push(highlight);
        this.saveBookData();
        this.hideSelectionToolbar();
        this.renderHighlights();

        // Apply highlight style
        const el = document.querySelector(`[data-id="${this.selectedSentenceId}"]`);
        if (el) {
            el.classList.add('highlighted');
            el.dataset.highlightColor = this.selectedHighlightColor;
            const colorObj = this.highlightColors.find(c => c.name === this.selectedHighlightColor);
            if (colorObj) {
                el.style.backgroundColor = colorObj.color;
            }
        }

        window.getSelection().removeAllRanges();
        this.showToast(`Highlighted in ${this.selectedHighlightColor}`);
    }

    /**
     * Copy selected text to clipboard
     */
    async copySelectedText() {
        if (this.selectedText) {
            try {
                await navigator.clipboard.writeText(this.selectedText);
                this.showToast('Copied to clipboard');
            } catch (err) {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = this.selectedText;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                this.showToast('Copied to clipboard');
            }
        }
        this.hideSelectionToolbar();
        window.getSelection().removeAllRanges();
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

            // Load page data (for viewing original document pages)
            await this.loadPagesFromPath(basePath);

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

        // Panel tabs
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                // Update active tab
                document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Show corresponding content
                const tabName = tab.dataset.tab;
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                document.getElementById(`${tabName}-tab`).classList.add('active');
            });
        });

        // Export button
        document.getElementById('export-notes-btn')?.addEventListener('click', () => {
            this.exportNotesAndHighlights();
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
            // Hide selection toolbar when clicking outside
            if (!e.target.closest('.selection-toolbar') && !e.target.closest('.sentence')) {
                this.hideSelectionToolbar();
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

        // Page viewer controls
        if (this.pageViewBtn) {
            this.pageViewBtn.style.display = 'none'; // Hide until pages are loaded
            this.pageViewBtn.addEventListener('click', () => this.togglePageView());
        }
        if (this.pagePrevBtn) {
            this.pagePrevBtn.addEventListener('click', () => this.prevPage());
        }
        if (this.pageNextBtn) {
            this.pageNextBtn.addEventListener('click', () => this.nextPage());
        }
        if (this.pageZoomInBtn) {
            this.pageZoomInBtn.addEventListener('click', () => this.zoomPage(0.1));
        }
        if (this.pageZoomOutBtn) {
            this.pageZoomOutBtn.addEventListener('click', () => this.zoomPage(-0.1));
        }
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

        // Render bookmarks, notes, highlights
        this.renderBookmarks();
        this.renderNotes();
        this.renderHighlights();
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
        // Prefer MP3 for faster loading, fall back to WAV
        const mp3FileName = audioFileName.replace(/\.wav$/i, '.mp3');

        // Check if loading from URL (audioBasePath) or from folder (audioFiles)
        if (this.audioBasePath) {
            // Try MP3 first, fall back to WAV
            const mp3Url = `${this.audioBasePath}/audio/${mp3FileName}`;
            const wavUrl = `${this.audioBasePath}/audio/${audioFileName}`;

            this.audio.src = mp3Url;
            this.audio.addEventListener('error', () => {
                if (this.audio.src.endsWith('.mp3')) {
                    this.audio.src = wavUrl;
                }
            }, { once: true });

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

                // Check if has note
                const note = this.notes.find(n => n.sentenceId === sentence.id);
                if (note) {
                    sentenceEl.classList.add('has-note');
                }

                // Check if has highlight and apply color
                const highlight = this.highlights.find(h => h.sentenceId === sentence.id);
                if (highlight) {
                    sentenceEl.classList.add('highlighted');
                    sentenceEl.dataset.highlightColor = highlight.color || 'yellow';
                    const colorObj = this.highlightColors.find(c => c.name === (highlight.color || 'yellow'));
                    if (colorObj) {
                        sentenceEl.style.backgroundColor = colorObj.color;
                    }
                }

                // Click to seek (but not when selecting text)
                sentenceEl.addEventListener('click', (e) => {
                    // Only seek if not selecting text
                    if (!window.getSelection().toString().trim()) {
                        this.seekToSentence(sentence.id);
                    }
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
            if (this.audio.readyState >= 1) {
                // Audio metadata loaded, seek directly
                this.audio.currentTime = entry.start;
                if (!this.isPlaying) {
                    this.audio.play();
                }
            } else {
                // Audio not ready yet, wait for metadata then seek
                this.audio.addEventListener('loadedmetadata', () => {
                    this.audio.currentTime = entry.start;
                    this.audio.play();
                }, { once: true });
                this.audio.load();
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
        if (theme === 'dark') {
            document.body.removeAttribute('data-theme');
        } else {
            document.body.dataset.theme = theme;
        }
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
            case 'KeyP':
                this.togglePageView();
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
                this.selectionRange = selection.getRangeAt(0).cloneRange();

                // Get position for toolbar
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                const x = rect.left + rect.width / 2;
                const y = rect.top + window.scrollY;

                // Show floating toolbar instead of modal
                this.showSelectionToolbar(x, rect.top);
            }
        } else {
            // Hide toolbar if no selection
            setTimeout(() => {
                if (!window.getSelection().toString().trim()) {
                    this.hideSelectionToolbar();
                }
            }, 100);
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
     * Add highlight only (no note text) - from notes modal
     */
    addHighlight() {
        if (!this.selectedSentenceId || !this.bookData) return;

        const highlight = {
            id: Date.now().toString(),
            bookId: this.bookData.bookId,
            chapter: this.currentChapter,
            sentenceId: this.selectedSentenceId,
            text: this.selectedText,
            color: this.selectedHighlightColor,
            createdAt: new Date().toISOString()
        };

        this.highlights.push(highlight);
        this.saveBookData();
        this.closeNotesModal();
        this.renderHighlights();

        // Update sentence styling with color
        const el = document.querySelector(`[data-id="${this.selectedSentenceId}"]`);
        if (el) {
            el.classList.add('highlighted');
            el.dataset.highlightColor = this.selectedHighlightColor;
            const colorObj = this.highlightColors.find(c => c.name === this.selectedHighlightColor);
            if (colorObj) {
                el.style.backgroundColor = colorObj.color;
            }
        }

        this.showToast(`Highlighted in ${this.selectedHighlightColor}`);
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
                <div class="note-chapter">Chapter ${n.chapter + 1}</div>
                <div class="note-text">"${n.selectedText.substring(0, 80)}${n.selectedText.length > 80 ? '...' : ''}"</div>
                <div class="note-content">${n.note}</div>
                <div class="note-date">${new Date(n.createdAt).toLocaleDateString()}</div>
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

    /**
     * Render highlights list
     */
    renderHighlights() {
        const container = document.getElementById('highlights-list');
        if (!container) return;

        const bookHighlights = this.highlights.filter(h => h.bookId === this.bookData?.bookId);

        if (bookHighlights.length === 0) {
            container.innerHTML = '<p class="empty-message">No highlights yet. Select text to highlight.</p>';
            return;
        }

        container.innerHTML = bookHighlights.map(h => {
            const colorObj = this.highlightColors.find(c => c.name === (h.color || 'yellow'));
            const bgColor = colorObj ? colorObj.color : '#fff59d';
            return `
                <div class="highlight-item" data-id="${h.id}" style="border-left: 4px solid ${bgColor}">
                    <button class="highlight-delete" onclick="event.stopPropagation(); reader.removeHighlight('${h.id}')">Delete</button>
                    <div class="highlight-chapter">Chapter ${h.chapter + 1}</div>
                    <div class="highlight-text" style="background: ${bgColor}">"${h.text.substring(0, 100)}${h.text.length > 100 ? '...' : ''}"</div>
                    <div class="highlight-date">${new Date(h.createdAt).toLocaleDateString()}</div>
                </div>
            `;
        }).join('');

        // Add click handlers
        container.querySelectorAll('.highlight-item').forEach(item => {
            item.addEventListener('click', () => {
                const highlight = this.highlights.find(h => h.id === item.dataset.id);
                if (highlight) {
                    if (highlight.chapter !== this.currentChapter) {
                        this.loadChapter(highlight.chapter);
                    }
                    setTimeout(() => {
                        const el = document.querySelector(`[data-id="${highlight.sentenceId}"]`);
                        if (el) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            el.classList.add('flash');
                            setTimeout(() => el.classList.remove('flash'), 1500);
                        }
                    }, 500);
                    document.getElementById('bookmarks-panel').classList.remove('open');
                }
            });
        });
    }

    /**
     * Remove a highlight
     */
    removeHighlight(id) {
        const highlight = this.highlights.find(h => h.id === id);
        if (highlight) {
            const el = document.querySelector(`[data-id="${highlight.sentenceId}"]`);
            if (el) {
                el.classList.remove('highlighted');
                el.style.backgroundColor = '';
                delete el.dataset.highlightColor;
            }
        }
        this.highlights = this.highlights.filter(h => h.id !== id);
        this.saveBookData();
        this.renderHighlights();
        this.showToast('Highlight removed');
    }

    /**
     * Export notes and highlights
     */
    exportNotesAndHighlights() {
        if (!this.bookData) return;

        const bookNotes = this.notes.filter(n => n.bookId === this.bookData.bookId);
        const bookHighlights = this.highlights.filter(h => h.bookId === this.bookData.bookId);

        let content = `# Notes and Highlights\n`;
        content += `## ${this.bookData.title}\n`;
        content += `By ${this.bookData.author}\n`;
        content += `Exported: ${new Date().toLocaleDateString()}\n\n`;

        if (bookHighlights.length > 0) {
            content += `## Highlights (${bookHighlights.length})\n\n`;
            bookHighlights.forEach((h, i) => {
                content += `${i + 1}. "${h.text}"\n`;
                content += `   - Chapter ${h.chapter + 1}, ${new Date(h.createdAt).toLocaleDateString()}\n\n`;
            });
        }

        if (bookNotes.length > 0) {
            content += `## Notes (${bookNotes.length})\n\n`;
            bookNotes.forEach((n, i) => {
                content += `${i + 1}. "${n.selectedText}"\n`;
                content += `   Note: ${n.note}\n`;
                content += `   - Chapter ${n.chapter + 1}, ${new Date(n.createdAt).toLocaleDateString()}\n\n`;
            });
        }

        // Download as file
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.bookData.title.replace(/[^a-z0-9]/gi, '_')}_notes.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.showToast('Notes exported');
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

    // ==================== PAGE VIEWER ====================

    /**
     * Load pages data from server
     */
    async loadPagesFromPath(basePath) {
        try {
            const response = await fetch(`${basePath}/pages.json`);
            if (response.ok) {
                this.pagesData = await response.json();
                this.totalPages = this.pagesData.totalPages || 0;
                this.basePath = basePath;

                // Build page files map
                if (this.pagesData.pages) {
                    this.pagesData.pages.forEach(page => {
                        this.pageFiles[page.number] = `${basePath}/${page.file}`;
                    });
                }

                // Show page view button if pages are available
                if (this.pageViewBtn && this.totalPages > 0) {
                    this.pageViewBtn.style.display = '';
                    this.showToast(`${this.totalPages} original pages available`);
                }
            }
        } catch (e) {
            console.log('No pages data available');
        }
    }

    /**
     * Toggle split view for page viewer
     */
    togglePageView() {
        if (!this.pagesData || this.totalPages === 0) {
            this.showToast('No original pages available for this book');
            return;
        }

        this.splitView = !this.splitView;

        if (this.splitView) {
            this.pagePanel.classList.remove('hidden');
            this.splitContainer.classList.add('split-view');
            this.loadPage(this.currentPage);
            this.showToast('Page view enabled');
        } else {
            this.pagePanel.classList.add('hidden');
            this.splitContainer.classList.remove('split-view');
            this.showToast('Page view disabled');
        }

        this.saveSettings();
    }

    /**
     * Load a specific page
     */
    loadPage(pageNum) {
        if (pageNum < 1 || pageNum > this.totalPages) return;

        this.currentPage = pageNum;
        const pageFile = this.pageFiles[pageNum];

        if (pageFile) {
            this.pageImage.src = pageFile;
            this.pageImage.style.transform = `scale(${this.pageZoom})`;
        }

        this.updatePageIndicator();
        this.updatePageNavButtons();
    }

    /**
     * Go to previous page
     */
    prevPage() {
        if (this.currentPage > 1) {
            this.loadPage(this.currentPage - 1);
        }
    }

    /**
     * Go to next page
     */
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.loadPage(this.currentPage + 1);
        }
    }

    /**
     * Zoom page by delta
     */
    zoomPage(delta) {
        this.pageZoom = Math.max(0.5, Math.min(3.0, this.pageZoom + delta));
        this.pageImage.style.transform = `scale(${this.pageZoom})`;
        if (this.pageZoomValue) {
            this.pageZoomValue.textContent = `${Math.round(this.pageZoom * 100)}%`;
        }
    }

    /**
     * Update page indicator
     */
    updatePageIndicator() {
        if (this.pageIndicator) {
            this.pageIndicator.textContent = `Page ${this.currentPage} / ${this.totalPages}`;
        }
    }

    /**
     * Update page navigation buttons
     */
    updatePageNavButtons() {
        if (this.pagePrevBtn) {
            this.pagePrevBtn.disabled = this.currentPage <= 1;
        }
        if (this.pageNextBtn) {
            this.pageNextBtn.disabled = this.currentPage >= this.totalPages;
        }
    }

    // ==================== SETTINGS ====================

    /**
     * Save settings to localStorage
     */
    saveSettings() {
        localStorage.setItem('readalong-settings', JSON.stringify({
            fontSize: this.fontSize,
            theme: document.body.dataset.theme || 'dark',
            speed: this.playbackSpeed,
            autoScroll: this.autoScroll,
            splitView: this.splitView,
            pageZoom: this.pageZoom,
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
            if (settings.pageZoom) {
                this.pageZoom = settings.pageZoom;
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
