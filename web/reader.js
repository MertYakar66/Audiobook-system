/**
 * Read-Along Reader - Enhanced Edition
 *
 * Synchronized audio-text playback with sentence highlighting,
 * page viewer for original documents, bookmarks, and more.
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
        this.currentPage = 1;
        this.totalPages = 0;
        this.pageZoom = 1.0;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.autoScroll = true;
        this.fontSize = 18;
        this.lineHeight = 1.7;
        this.highlightStyle = 'background';
        this.sleepTimer = null;
        this.sleepTimeRemaining = 0;
        this.bookmarks = [];
        this.splitView = false;
        this.audioFiles = {};
        this.pageFiles = {};

        // DOM Elements
        this.initElements();

        // Initialize
        this.bindEvents();
        this.loadSettings();
    }

    initElements() {
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
        this.chapterTitleDisplay = document.getElementById('chapter-title-display');
        this.pagePanel = document.getElementById('page-panel');
        this.pageImage = document.getElementById('page-image');
        this.pageIndicator = document.getElementById('page-indicator');
        this.splitContainer = document.getElementById('split-container');
        this.sleepTimerValue = document.getElementById('sleep-timer-value');
    }

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
            this.audio.currentTime = Math.min(this.audio.duration || 0, this.audio.currentTime + 30);
        });

        // Progress bar
        this.progressBar.addEventListener('click', (e) => this.seekTo(e));
        this.progressBar.addEventListener('mousedown', (e) => this.startDragging(e));

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
            if (this.timingData && this.currentChapter < this.timingData.chapters.length - 1) {
                this.loadChapter(this.currentChapter + 1);
            }
        });

        // Settings panel
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

        // Line spacing
        document.querySelectorAll('.spacing-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setLineSpacing(parseFloat(e.target.dataset.spacing)));
        });

        // Theme
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setTheme(e.currentTarget.dataset.theme));
        });

        // Highlight style
        document.getElementById('highlight-style').addEventListener('change', (e) => {
            this.setHighlightStyle(e.target.value);
        });

        // Auto-scroll toggle
        document.getElementById('auto-scroll').addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
            this.saveSettings();
        });

        // Reset settings
        document.getElementById('reset-settings').addEventListener('click', () => this.resetSettings());

        // View mode toggle (split view)
        document.getElementById('view-mode-btn').addEventListener('click', () => this.toggleSplitView());

        // Page navigation
        document.getElementById('page-prev').addEventListener('click', () => this.prevPage());
        document.getElementById('page-next').addEventListener('click', () => this.nextPage());
        document.getElementById('page-zoom-in').addEventListener('click', () => this.zoomPage(0.2));
        document.getElementById('page-zoom-out').addEventListener('click', () => this.zoomPage(-0.2));

        // Bookmarks
        document.getElementById('bookmark-btn').addEventListener('click', () => this.showBookmarkModal());
        document.getElementById('save-bookmark').addEventListener('click', () => this.saveBookmark());
        document.getElementById('cancel-bookmark').addEventListener('click', () => this.hideBookmarkModal());

        // Sleep timer
        document.getElementById('sleep-timer').addEventListener('click', () => this.showSleepModal());
        document.querySelectorAll('.sleep-options button').forEach(btn => {
            btn.addEventListener('click', (e) => this.setSleepTimer(parseInt(e.target.dataset.minutes)));
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
            if (!e.target.closest('.settings-panel') && !e.target.closest('#settings-btn')) {
                document.getElementById('settings-panel').classList.remove('open');
            }
        });

        // Modal close on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.add('hidden');
                }
            });
        });
    }

    async handleFolderSelect(files) {
        const fileMap = {};
        for (const file of files) {
            const relativePath = file.webkitRelativePath || file.name;
            const fileName = relativePath.split('/').pop();
            fileMap[fileName] = file;

            // Also store with path for nested files
            if (relativePath.includes('/')) {
                const parts = relativePath.split('/');
                if (parts.length >= 2) {
                    const subPath = parts.slice(1).join('/');
                    fileMap[subPath] = file;
                }
            }
        }

        const manifestFile = fileMap['manifest.json'];
        if (!manifestFile) {
            this.showToast('No manifest.json found. Please select a processed book folder.', 'error');
            return;
        }

        try {
            this.showLoading(true);

            // Read manifest
            const manifestText = await this.readFile(manifestFile);
            this.bookData = JSON.parse(manifestText);

            // Read timing data
            const timingFile = fileMap[this.bookData.timing] || fileMap['timing.json'];
            if (timingFile) {
                const timingText = await this.readFile(timingFile);
                this.timingData = JSON.parse(timingText);
            }

            // Read text data
            const textFile = fileMap[this.bookData.text] || fileMap['text.json'];
            if (textFile) {
                const textText = await this.readFile(textFile);
                this.textData = JSON.parse(textText);
            }

            // Read pages data if available
            if (this.bookData.hasOriginalPages || this.bookData.pages) {
                const pagesFile = fileMap[this.bookData.pages] || fileMap['pages.json'];
                if (pagesFile) {
                    const pagesText = await this.readFile(pagesFile);
                    this.pagesData = JSON.parse(pagesText);
                }
            }

            // Store audio files reference
            this.audioFiles = {};
            this.pageFiles = {};

            for (const [name, file] of Object.entries(fileMap)) {
                if (name.endsWith('.wav') || name.endsWith('.mp3') || name.endsWith('.m4a')) {
                    this.audioFiles[name] = file;
                }
                if (name.endsWith('.jpg') || name.endsWith('.png') || name.endsWith('.jpeg')) {
                    this.pageFiles[name] = file;
                }
            }

            // Load bookmarks for this book
            this.loadBookmarks();

            // Initialize reader
            this.initializeReader();

        } catch (error) {
            console.error('Error loading book:', error);
            this.showToast('Error loading book: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    initializeReader() {
        // Update header
        this.bookTitle.textContent = this.bookData.title;
        this.bookAuthor.textContent = this.bookData.author;

        // Populate chapter select
        this.chapterSelect.innerHTML = '';
        this.timingData.chapters.forEach((chapter, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = `${index + 1}. ${chapter.title}`;
            this.chapterSelect.appendChild(option);
        });

        // Setup page viewer if pages available
        if (this.pagesData) {
            this.totalPages = this.pagesData.total_pages || this.pagesData.total_images || 0;
            if (this.totalPages > 0) {
                document.getElementById('view-mode-btn').style.display = 'flex';
            }
        }

        // Show reader view
        document.getElementById('empty-state').classList.remove('active');
        document.getElementById('reader-view').style.display = 'block';
        document.getElementById('player').style.display = 'block';

        // Restore last position if available
        const lastPosition = this.getLastPosition();
        if (lastPosition) {
            this.loadChapter(lastPosition.chapter);
            setTimeout(() => {
                this.audio.currentTime = lastPosition.time;
            }, 500);
        } else {
            this.loadChapter(0);
        }

        this.showToast(`Loaded: ${this.bookData.title}`, 'success');
    }

    async loadChapter(chapterIndex) {
        if (!this.timingData || chapterIndex < 0 || chapterIndex >= this.timingData.chapters.length) {
            return;
        }

        this.currentChapter = chapterIndex;
        this.currentSentenceIndex = -1;

        const chapter = this.timingData.chapters[chapterIndex];
        const textChapter = this.textData.chapters[chapterIndex];

        // Update chapter select
        this.chapterSelect.value = chapterIndex;

        // Update navigation buttons
        document.getElementById('prev-chapter').disabled = chapterIndex === 0;
        document.getElementById('next-chapter').disabled = chapterIndex === this.timingData.chapters.length - 1;

        // Update chapter title display
        this.chapterTitleDisplay.textContent = chapter.title;

        // Render text
        this.renderText(textChapter);

        // Load audio
        const audioFileName = chapter.audioFile.split('/').pop();
        const audioFile = this.audioFiles[audioFileName] || this.audioFiles[`audio/${audioFileName}`];

        if (audioFile) {
            const audioUrl = URL.createObjectURL(audioFile);
            this.audio.src = audioUrl;
        }

        // Reset progress
        this.progressFill.style.width = '0%';
        this.progressHandle.style.left = '0%';
        this.currentTimeEl.textContent = '0:00';

        // Scroll to top
        this.textContent.scrollTop = 0;
    }

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

                sentenceEl.addEventListener('click', () => {
                    this.seekToSentence(sentence.id);
                });

                paraEl.appendChild(sentenceEl);
            });

            this.textContent.appendChild(paraEl);
        });
    }

    onTimeUpdate() {
        const currentTime = this.audio.currentTime;
        const duration = this.audio.duration || 0;

        // Update progress bar
        if (duration > 0) {
            const percent = (currentTime / duration) * 100;
            this.progressFill.style.width = `${percent}%`;
            this.progressHandle.style.left = `${percent}%`;
        }

        // Update time display
        this.currentTimeEl.textContent = this.formatTime(currentTime);

        // Save position
        this.savePosition();

        // Find and highlight current sentence
        this.highlightCurrentSentence(currentTime);

        // Update sleep timer display
        if (this.sleepTimer) {
            this.updateSleepTimerDisplay();
        }
    }

    highlightCurrentSentence(currentTime) {
        if (!this.timingData) return;

        const chapter = this.timingData.chapters[this.currentChapter];
        if (!chapter) return;

        const entries = chapter.entries;

        let currentIndex = -1;
        for (let i = 0; i < entries.length; i++) {
            if (currentTime >= entries[i].start && currentTime < entries[i].end) {
                currentIndex = i;
                break;
            }
            if (currentTime < entries[i].start) {
                currentIndex = i > 0 ? i - 1 : -1;
                break;
            }
        }

        if (currentIndex === -1 && entries.length > 0 && currentTime >= entries[entries.length - 1].start) {
            currentIndex = entries.length - 1;
        }

        if (currentIndex !== this.currentSentenceIndex) {
            this.currentSentenceIndex = currentIndex;
            this.updateHighlighting();
        }
    }

    updateHighlighting() {
        if (!this.timingData) return;

        const chapter = this.timingData.chapters[this.currentChapter];
        if (!chapter) return;

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
                    if (this.autoScroll && this.isPlaying) {
                        this.scrollToElement(el);
                    }
                } else if (index < this.currentSentenceIndex) {
                    el.classList.add('played');
                }
            }
        });
    }

    scrollToElement(element) {
        const container = this.textContent;
        const elementRect = element.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();

        if (elementRect.top < containerRect.top + 100 || elementRect.bottom > containerRect.bottom - 100) {
            const scrollTop = element.offsetTop - container.offsetTop - (container.clientHeight / 3);
            container.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
            });
        }
    }

    seekToSentence(sentenceId) {
        if (!this.timingData) return;

        const chapter = this.timingData.chapters[this.currentChapter];
        const entry = chapter.entries.find(e => e.id === sentenceId);

        if (entry) {
            this.audio.currentTime = entry.start;
            if (!this.isPlaying) {
                this.audio.play();
            }
        }
    }

    seekTo(event) {
        const rect = this.progressBar.getBoundingClientRect();
        const percent = (event.clientX - rect.left) / rect.width;
        const duration = this.audio.duration || 0;
        this.audio.currentTime = Math.max(0, Math.min(duration, percent * duration));
    }

    startDragging(e) {
        e.preventDefault();

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

    togglePlay() {
        if (this.audio.paused) {
            this.audio.play();
        } else {
            this.audio.pause();
        }
    }

    updatePlayState(playing) {
        this.isPlaying = playing;
        this.playIcon.style.display = playing ? 'none' : 'block';
        this.pauseIcon.style.display = playing ? 'block' : 'none';
    }

    onChapterEnd() {
        if (this.timingData && this.currentChapter < this.timingData.chapters.length - 1) {
            this.loadChapter(this.currentChapter + 1);
            setTimeout(() => this.audio.play(), 100);
        } else {
            this.showToast('Book finished!');
        }
    }

    onAudioLoaded() {
        this.totalTimeEl.textContent = this.formatTime(this.audio.duration);
    }

    // Page Viewer
    toggleSplitView() {
        if (!this.pagesData || this.totalPages === 0) {
            this.showToast('No document pages available');
            return;
        }

        this.splitView = !this.splitView;

        if (this.splitView) {
            this.pagePanel.classList.remove('hidden');
            this.splitContainer.classList.add('split-view');
            this.loadPage(1);
        } else {
            this.pagePanel.classList.add('hidden');
            this.splitContainer.classList.remove('split-view');
        }

        this.saveSettings();
    }

    async loadPage(pageNum) {
        if (!this.pagesData || pageNum < 1 || pageNum > this.totalPages) return;

        this.currentPage = pageNum;
        this.pageIndicator.textContent = `Page ${pageNum} / ${this.totalPages}`;

        const pageInfo = this.pagesData.pages ? this.pagesData.pages[pageNum - 1] : this.pagesData.images[pageNum - 1];
        if (!pageInfo) return;

        const fileName = pageInfo.file.split('/').pop();
        const pageFile = this.pageFiles[fileName] || this.pageFiles[pageInfo.file];

        if (pageFile) {
            const url = URL.createObjectURL(pageFile);
            this.pageImage.src = url;
            this.pageImage.style.transform = `scale(${this.pageZoom})`;
        }
    }

    prevPage() {
        if (this.currentPage > 1) {
            this.loadPage(this.currentPage - 1);
        }
    }

    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.loadPage(this.currentPage + 1);
        }
    }

    zoomPage(delta) {
        this.pageZoom = Math.max(0.5, Math.min(3, this.pageZoom + delta));
        this.pageImage.style.transform = `scale(${this.pageZoom})`;
    }

    // Bookmarks
    showBookmarkModal() {
        document.getElementById('bookmark-modal').classList.remove('hidden');
        document.getElementById('bookmark-note').value = '';
        document.getElementById('bookmark-note').focus();
    }

    hideBookmarkModal() {
        document.getElementById('bookmark-modal').classList.add('hidden');
    }

    saveBookmark() {
        const note = document.getElementById('bookmark-note').value.trim();
        const chapter = this.timingData.chapters[this.currentChapter];

        const bookmark = {
            id: Date.now(),
            chapter: this.currentChapter,
            chapterTitle: chapter.title,
            time: this.audio.currentTime,
            note: note,
            created: new Date().toISOString()
        };

        this.bookmarks.push(bookmark);
        this.saveBookmarks();
        this.renderBookmarks();
        this.hideBookmarkModal();
        this.showToast('Bookmark saved!', 'success');
    }

    deleteBookmark(id) {
        this.bookmarks = this.bookmarks.filter(b => b.id !== id);
        this.saveBookmarks();
        this.renderBookmarks();
    }

    goToBookmark(bookmark) {
        this.loadChapter(bookmark.chapter);
        setTimeout(() => {
            this.audio.currentTime = bookmark.time;
        }, 100);
        document.getElementById('settings-panel').classList.remove('open');
    }

    renderBookmarks() {
        const list = document.getElementById('bookmarks-list');

        if (this.bookmarks.length === 0) {
            list.innerHTML = '<p class="no-bookmarks">No bookmarks yet</p>';
            return;
        }

        list.innerHTML = this.bookmarks.map(b => `
            <div class="bookmark-item" onclick="reader.goToBookmark(${JSON.stringify(b).replace(/"/g, '&quot;')})">
                <div class="bookmark-info">
                    <div class="bookmark-chapter">${b.chapterTitle}</div>
                    <div class="bookmark-time">${this.formatTime(b.time)}</div>
                    ${b.note ? `<div class="bookmark-note">${b.note}</div>` : ''}
                </div>
                <button class="bookmark-delete" onclick="event.stopPropagation(); reader.deleteBookmark(${b.id})">×</button>
            </div>
        `).join('');
    }

    loadBookmarks() {
        if (!this.bookData) return;
        const key = `bookmarks_${this.bookData.bookId}`;
        try {
            this.bookmarks = JSON.parse(localStorage.getItem(key) || '[]');
        } catch (e) {
            this.bookmarks = [];
        }
        this.renderBookmarks();
    }

    saveBookmarks() {
        if (!this.bookData) return;
        const key = `bookmarks_${this.bookData.bookId}`;
        localStorage.setItem(key, JSON.stringify(this.bookmarks));
    }

    // Sleep Timer
    showSleepModal() {
        document.getElementById('sleep-modal').classList.remove('hidden');
    }

    hideSleepModal() {
        document.getElementById('sleep-modal').classList.add('hidden');
    }

    setSleepTimer(minutes) {
        this.hideSleepModal();

        if (this.sleepTimer) {
            clearInterval(this.sleepTimer);
            this.sleepTimer = null;
        }

        if (minutes === 0) {
            this.sleepTimeRemaining = 0;
            this.sleepTimerValue.textContent = '';
            this.showToast('Sleep timer cancelled');
            return;
        }

        this.sleepTimeRemaining = minutes * 60;
        this.showToast(`Sleep timer set for ${minutes} minutes`, 'success');

        this.sleepTimer = setInterval(() => {
            this.sleepTimeRemaining--;
            this.updateSleepTimerDisplay();

            if (this.sleepTimeRemaining <= 0) {
                this.audio.pause();
                clearInterval(this.sleepTimer);
                this.sleepTimer = null;
                this.sleepTimerValue.textContent = '';
                this.showToast('Sleep timer - pausing playback');
            }
        }, 1000);
    }

    updateSleepTimerDisplay() {
        if (this.sleepTimeRemaining > 0) {
            const mins = Math.floor(this.sleepTimeRemaining / 60);
            const secs = this.sleepTimeRemaining % 60;
            this.sleepTimerValue.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        }
    }

    // Settings
    setSpeed(speed) {
        this.playbackSpeed = speed;
        this.audio.playbackRate = speed;
        document.getElementById('speed-value').textContent = `${speed}x`;
        document.getElementById('speed-menu').classList.remove('show');

        document.querySelectorAll('#speed-menu button').forEach(btn => {
            btn.classList.toggle('active', parseFloat(btn.dataset.speed) === speed);
        });

        this.saveSettings();
    }

    setFontSize(size) {
        this.fontSize = Math.max(12, Math.min(28, size));
        document.documentElement.style.setProperty('--font-size', `${this.fontSize}px`);
        document.getElementById('font-size-value').textContent = `${this.fontSize}px`;
        this.saveSettings();
    }

    setLineSpacing(spacing) {
        this.lineHeight = spacing;
        document.documentElement.style.setProperty('--line-height', spacing);

        document.querySelectorAll('.spacing-btn').forEach(btn => {
            btn.classList.toggle('active', parseFloat(btn.dataset.spacing) === spacing);
        });

        this.saveSettings();
    }

    setTheme(theme) {
        document.body.dataset.theme = theme;
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
        this.saveSettings();
    }

    setHighlightStyle(style) {
        this.highlightStyle = style;
        document.body.dataset.highlight = style;
        this.saveSettings();
    }

    resetSettings() {
        this.setFontSize(18);
        this.setLineSpacing(1.7);
        this.setTheme('light');
        this.setSpeed(1.0);
        this.setHighlightStyle('background');
        this.autoScroll = true;
        document.getElementById('auto-scroll').checked = true;
        this.saveSettings();
        this.showToast('Settings reset to defaults');
    }

    handleKeyboard(event) {
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (event.code) {
            case 'Space':
                event.preventDefault();
                this.togglePlay();
                break;
            case 'ArrowLeft':
                if (event.shiftKey) {
                    if (this.currentChapter > 0) this.loadChapter(this.currentChapter - 1);
                } else {
                    this.audio.currentTime = Math.max(0, this.audio.currentTime - 5);
                }
                break;
            case 'ArrowRight':
                if (event.shiftKey) {
                    if (this.timingData && this.currentChapter < this.timingData.chapters.length - 1) {
                        this.loadChapter(this.currentChapter + 1);
                    }
                } else {
                    this.audio.currentTime = Math.min(this.audio.duration || 0, this.audio.currentTime + 5);
                }
                break;
            case 'ArrowUp':
                event.preventDefault();
                this.setSpeed(Math.min(2, this.playbackSpeed + 0.25));
                break;
            case 'ArrowDown':
                event.preventDefault();
                this.setSpeed(Math.max(0.5, this.playbackSpeed - 0.25));
                break;
            case 'KeyB':
                this.showBookmarkModal();
                break;
            case 'KeyP':
                if (this.pagesData) this.toggleSplitView();
                break;
            case 'Escape':
                document.getElementById('settings-panel').classList.remove('open');
                document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
                break;
        }
    }

    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hrs > 0) {
            return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    showLoading(show) {
        document.getElementById('loading-state').classList.toggle('active', show);
        document.getElementById('empty-state').classList.toggle('active', !show);
    }

    showToast(message, type = '') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    // Persistence
    saveSettings() {
        localStorage.setItem('readalong-settings', JSON.stringify({
            fontSize: this.fontSize,
            lineHeight: this.lineHeight,
            theme: document.body.dataset.theme || 'light',
            highlightStyle: this.highlightStyle,
            speed: this.playbackSpeed,
            autoScroll: this.autoScroll,
            splitView: this.splitView,
        }));
    }

    loadSettings() {
        try {
            const settings = JSON.parse(localStorage.getItem('readalong-settings') || '{}');

            if (settings.fontSize) this.setFontSize(settings.fontSize);
            if (settings.lineHeight) this.setLineSpacing(settings.lineHeight);
            if (settings.theme) this.setTheme(settings.theme);
            if (settings.highlightStyle) {
                this.setHighlightStyle(settings.highlightStyle);
                document.getElementById('highlight-style').value = settings.highlightStyle;
            }
            if (settings.speed) this.setSpeed(settings.speed);
            if (settings.autoScroll !== undefined) {
                this.autoScroll = settings.autoScroll;
                document.getElementById('auto-scroll').checked = this.autoScroll;
            }
        } catch (e) {
            console.warn('Could not load settings:', e);
        }
    }

    savePosition() {
        if (!this.bookData) return;
        const key = `position_${this.bookData.bookId}`;
        localStorage.setItem(key, JSON.stringify({
            chapter: this.currentChapter,
            time: this.audio.currentTime
        }));
    }

    getLastPosition() {
        if (!this.bookData) return null;
        const key = `position_${this.bookData.bookId}`;
        try {
            return JSON.parse(localStorage.getItem(key));
        } catch (e) {
            return null;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reader = new ReadAlongReader();
});
