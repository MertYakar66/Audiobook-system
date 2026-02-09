/**
 * Scriptum Text Reader
 *
 * Read-only DOCX reader with:
 * - Client-side DOCX parsing (mammoth.js)
 * - Chapter detection and navigation
 * - Text highlighting and notes
 * - Shared progress with Read & Listen reader
 */

// Book registry — maps bookId to source file
const BOOK_SOURCES = {
    "the-intelligent-investor": {
        sourceFile: "../input/The Intelligent Investor.docx",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    }
};

class TextReader {
    constructor() {
        this.bookId = null;
        this.bookInfo = null;
        this.chapters = [];
        this.currentChapter = 0;
        this.highlights = [];
        this.notes = [];
        this.fontSize = 18;
        this.selectedText = '';
        this.selectedRange = null;

        this.init();
    }

    async init() {
        // Get book from URL
        const params = new URLSearchParams(window.location.search);
        this.bookId = params.get('book');

        if (!this.bookId || !BOOK_SOURCES[this.bookId]) {
            this.showError('Book not found. Please select a book from the library.');
            return;
        }

        this.bookInfo = BOOK_SOURCES[this.bookId];
        document.getElementById('book-title').textContent = this.bookInfo.title;
        document.getElementById('book-author').textContent = this.bookInfo.author;
        document.title = `${this.bookInfo.title} - Scriptum`;

        this.loadBookData();
        this.loadTheme();
        this.loadFontSize();
        this.bindEvents();

        await this.loadDocument();
    }

    // ==================== DOCUMENT LOADING ====================

    async loadDocument() {
        try {
            const response = await fetch(this.bookInfo.sourceFile);
            if (!response.ok) {
                throw new Error(`Could not fetch document (${response.status})`);
            }

            const arrayBuffer = await response.arrayBuffer();

            if (typeof mammoth === 'undefined') {
                throw new Error('Document parser not loaded. Please check your internet connection.');
            }

            const result = await mammoth.convertToHtml(
                { arrayBuffer: arrayBuffer },
                {
                    styleMap: [
                        "p[style-name='Heading 1'] => h1:fresh",
                        "p[style-name='Heading 2'] => h2:fresh",
                        "p[style-name='Heading 3'] => h3:fresh",
                        "p[style-name='Title'] => h1:fresh"
                    ]
                }
            );

            this.parseChapters(result.value);
            this.buildChapterSelect();
            this.restoreProgress();
            this.renderChapter();

            document.getElementById('loading-state').style.display = 'none';
            document.getElementById('text-view').style.display = 'block';

        } catch (e) {
            console.error('Failed to load document:', e);
            this.showError(e.message);
        }
    }

    parseChapters(html) {
        const container = document.createElement('div');
        container.innerHTML = html;

        const children = Array.from(container.childNodes);
        this.chapters = [];
        let currentChapter = { title: 'Introduction', content: '' };

        for (const node of children) {
            if (node.nodeType === Node.ELEMENT_NODE &&
                /^H[12]$/i.test(node.tagName)) {
                // Save previous chapter if it has content
                if (currentChapter.content.trim()) {
                    this.chapters.push(currentChapter);
                }
                // Start new chapter
                currentChapter = {
                    title: node.textContent.trim(),
                    content: node.outerHTML
                };
            } else {
                const outerHtml = node.nodeType === Node.ELEMENT_NODE
                    ? node.outerHTML
                    : (node.textContent.trim() ? `<p>${node.textContent}</p>` : '');
                currentChapter.content += outerHtml;
            }
        }

        // Push last chapter
        if (currentChapter.content.trim()) {
            this.chapters.push(currentChapter);
        }

        // If no chapters detected, treat entire content as one chapter
        if (this.chapters.length === 0) {
            this.chapters.push({ title: 'Full Text', content: html });
        }
    }

    buildChapterSelect() {
        const select = document.getElementById('chapter-select');
        select.innerHTML = this.chapters.map((ch, i) =>
            `<option value="${i}">${ch.title}</option>`
        ).join('');
    }

    // ==================== CHAPTER RENDERING ====================

    renderChapter() {
        const textView = document.getElementById('text-view');
        textView.innerHTML = this.chapters[this.currentChapter].content;
        textView.style.fontSize = this.fontSize + 'px';

        // Update nav
        document.getElementById('chapter-select').value = this.currentChapter;
        document.getElementById('prev-chapter').disabled = this.currentChapter === 0;
        document.getElementById('next-chapter').disabled = this.currentChapter >= this.chapters.length - 1;

        // Scroll to top
        document.querySelector('.reader-content').scrollTop = 0;

        // Re-apply highlights for this chapter
        this.applyHighlights();

        // Save progress
        this.saveProgress();
    }

    goToChapter(index) {
        if (index < 0 || index >= this.chapters.length) return;
        this.currentChapter = index;
        this.renderChapter();
    }

    // ==================== PROGRESS (shared with Read & Listen) ====================

    saveProgress() {
        const progress = {
            bookId: this.bookId,
            chapter: this.currentChapter,
            position: 0, // No audio position in read-only mode
            updatedAt: Date.now()
        };
        localStorage.setItem(`readalong-progress-${this.bookId}`, JSON.stringify(progress));
    }

    restoreProgress() {
        try {
            const saved = localStorage.getItem(`readalong-progress-${this.bookId}`);
            if (saved) {
                const progress = JSON.parse(saved);
                if (Date.now() - progress.updatedAt < 30 * 24 * 60 * 60 * 1000) {
                    if (progress.chapter < this.chapters.length) {
                        this.currentChapter = progress.chapter;
                    }
                }
            }
        } catch (e) {
            console.warn('Could not restore progress:', e);
        }
    }

    // ==================== HIGHLIGHTS & NOTES ====================

    loadBookData() {
        try {
            const saved = localStorage.getItem('readalong-bookdata');
            if (saved) {
                const data = JSON.parse(saved);
                this.highlights = data.highlights || [];
                this.notes = data.notes || [];
            }
        } catch (e) {
            console.warn('Could not load book data:', e);
        }
    }

    saveBookData() {
        const data = {
            bookmarks: [], // Preserved from Read & Listen
            highlights: this.highlights,
            notes: this.notes
        };

        // Preserve existing bookmarks from Read & Listen
        try {
            const existing = localStorage.getItem('readalong-bookdata');
            if (existing) {
                const parsed = JSON.parse(existing);
                data.bookmarks = parsed.bookmarks || [];
            }
        } catch (e) { /* ignore */ }

        localStorage.setItem('readalong-bookdata', JSON.stringify(data));
    }

    addHighlight(text, color) {
        const highlight = {
            id: `hl-${Date.now()}`,
            bookId: this.bookId,
            chapter: this.currentChapter,
            text: text,
            color: color,
            createdAt: new Date().toISOString()
        };

        this.highlights.push(highlight);
        this.saveBookData();
        this.applyHighlights();
        this.hideSelectionToolbar();
        this.showToast('Highlight added');
    }

    addNote(text, noteContent, color) {
        const note = {
            id: `note-${Date.now()}`,
            bookId: this.bookId,
            chapter: this.currentChapter,
            selectedText: text,
            note: noteContent,
            color: color || 'yellow',
            createdAt: new Date().toISOString()
        };

        this.notes.push(note);
        this.saveBookData();
        this.applyHighlights();
        this.showToast('Note saved');
    }

    removeHighlight(id) {
        this.highlights = this.highlights.filter(h => h.id !== id);
        this.saveBookData();
        this.renderChapter();
        this.renderHighlightsList();
        this.showToast('Highlight removed');
    }

    removeNote(id) {
        this.notes = this.notes.filter(n => n.id !== id);
        this.saveBookData();
        this.renderChapter();
        this.renderHighlightsList();
        this.showToast('Note removed');
    }

    applyHighlights() {
        const textView = document.getElementById('text-view');
        const chapterHighlights = this.highlights.filter(
            h => h.bookId === this.bookId && h.chapter === this.currentChapter
        );
        const chapterNotes = this.notes.filter(
            n => n.bookId === this.bookId && n.chapter === this.currentChapter
        );

        // Apply highlights by wrapping matched text
        const allMarks = [
            ...chapterHighlights.map(h => ({ text: h.text, color: h.color, id: h.id })),
            ...chapterNotes.map(n => ({ text: n.selectedText, color: n.color, id: n.id }))
        ];

        for (const mark of allMarks) {
            if (!mark.text) continue;
            const walker = document.createTreeWalker(textView, NodeFilter.SHOW_TEXT);
            let node;
            while ((node = walker.nextNode())) {
                const idx = node.textContent.indexOf(mark.text);
                if (idx >= 0) {
                    const range = document.createRange();
                    range.setStart(node, idx);
                    range.setEnd(node, idx + mark.text.length);

                    const span = document.createElement('span');
                    span.className = 'highlight';
                    span.dataset.color = mark.color;
                    span.dataset.id = mark.id;
                    range.surroundContents(span);
                    break; // Only first occurrence
                }
            }
        }
    }

    renderHighlightsList() {
        const list = document.getElementById('highlights-list');
        const bookHighlights = this.highlights.filter(h => h.bookId === this.bookId);
        const bookNotes = this.notes.filter(n => n.bookId === this.bookId);

        const allItems = [
            ...bookHighlights.map(h => ({ ...h, type: 'highlight' })),
            ...bookNotes.map(n => ({ ...n, type: 'note', text: n.selectedText }))
        ].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

        if (allItems.length === 0) {
            list.innerHTML = '<p class="empty-message">No highlights yet. Select text to highlight.</p>';
            return;
        }

        list.innerHTML = allItems.map(item => {
            const chapterTitle = this.chapters[item.chapter]?.title || `Chapter ${item.chapter + 1}`;
            return `
                <div class="highlight-item" data-color="${item.color}" data-chapter="${item.chapter}" data-id="${item.id}">
                    <button class="hl-delete" data-id="${item.id}" data-type="${item.type}">&times;</button>
                    <div class="hl-text">"${this.escapeHtml(item.text)}"</div>
                    ${item.type === 'note' && item.note ? `<div class="hl-note">${this.escapeHtml(item.note)}</div>` : ''}
                    <div class="hl-meta">${chapterTitle}</div>
                </div>
            `;
        }).join('');

        // Click to navigate to chapter
        list.querySelectorAll('.highlight-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.hl-delete')) return;
                const chapter = parseInt(el.dataset.chapter);
                this.goToChapter(chapter);
                document.getElementById('highlights-panel').classList.remove('open');
            });
        });

        // Delete buttons
        list.querySelectorAll('.hl-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                const type = btn.dataset.type;
                if (type === 'note') this.removeNote(id);
                else this.removeHighlight(id);
            });
        });
    }

    // ==================== SELECTION TOOLBAR ====================

    showSelectionToolbar() {
        const selection = window.getSelection();
        if (!selection.rangeCount || selection.isCollapsed) return;

        this.selectedText = selection.toString().trim();
        if (!this.selectedText) return;

        this.selectedRange = selection.getRangeAt(0).cloneRange();

        const rect = selection.getRangeAt(0).getBoundingClientRect();
        const toolbar = document.getElementById('selection-toolbar');
        toolbar.style.display = 'flex';
        toolbar.style.left = Math.max(10, rect.left + rect.width / 2 - toolbar.offsetWidth / 2) + 'px';
        toolbar.style.top = (rect.top - toolbar.offsetHeight - 10 + window.scrollY) + 'px';

        // If toolbar goes above viewport, show below
        if (rect.top - toolbar.offsetHeight - 10 < 0) {
            toolbar.style.top = (rect.bottom + 10 + window.scrollY) + 'px';
        }
    }

    hideSelectionToolbar() {
        document.getElementById('selection-toolbar').style.display = 'none';
        this.selectedText = '';
        this.selectedRange = null;
    }

    // ==================== EVENTS ====================

    bindEvents() {
        // Chapter navigation
        document.getElementById('prev-chapter').addEventListener('click', () => {
            this.goToChapter(this.currentChapter - 1);
        });

        document.getElementById('next-chapter').addEventListener('click', () => {
            this.goToChapter(this.currentChapter + 1);
        });

        document.getElementById('chapter-select').addEventListener('change', (e) => {
            this.goToChapter(parseInt(e.target.value));
        });

        // Text selection → show toolbar
        document.getElementById('text-view').addEventListener('mouseup', () => {
            setTimeout(() => this.showSelectionToolbar(), 10);
        });

        document.getElementById('text-view').addEventListener('touchend', () => {
            setTimeout(() => this.showSelectionToolbar(), 300);
        });

        // Hide toolbar on click outside
        document.addEventListener('mousedown', (e) => {
            if (!e.target.closest('.selection-toolbar') && !e.target.closest('.text-view')) {
                this.hideSelectionToolbar();
            }
        });

        // Highlight color buttons
        document.querySelectorAll('.highlight-color').forEach(btn => {
            btn.addEventListener('click', () => {
                if (this.selectedText) {
                    this.addHighlight(this.selectedText, btn.dataset.color);
                    window.getSelection().removeAllRanges();
                }
            });
        });

        // Add note button
        document.getElementById('add-note-btn').addEventListener('click', () => {
            if (this.selectedText) {
                document.getElementById('note-preview').textContent = `"${this.selectedText}"`;
                document.getElementById('note-input').value = '';
                document.getElementById('note-modal').style.display = 'flex';
                document.getElementById('note-input').focus();
                this.hideSelectionToolbar();
            }
        });

        // Note modal
        document.getElementById('save-note').addEventListener('click', () => {
            const noteText = document.getElementById('note-input').value.trim();
            if (this.selectedText) {
                this.addNote(this.selectedText, noteText, 'yellow');
                document.getElementById('note-modal').style.display = 'none';
                window.getSelection().removeAllRanges();
            }
        });

        document.getElementById('highlight-only').addEventListener('click', () => {
            if (this.selectedText) {
                this.addHighlight(this.selectedText, 'yellow');
                document.getElementById('note-modal').style.display = 'none';
                window.getSelection().removeAllRanges();
            }
        });

        document.getElementById('close-note-modal').addEventListener('click', () => {
            document.getElementById('note-modal').style.display = 'none';
        });

        // Highlights panel
        document.getElementById('highlights-btn').addEventListener('click', () => {
            this.renderHighlightsList();
            document.getElementById('highlights-panel').classList.toggle('open');
        });

        document.getElementById('close-highlights').addEventListener('click', () => {
            document.getElementById('highlights-panel').classList.remove('open');
        });

        // Settings
        document.getElementById('settings-btn').addEventListener('click', () => {
            const panel = document.getElementById('settings-panel');
            panel.style.display = 'block';
            setTimeout(() => panel.classList.add('open'), 10);
        });

        document.getElementById('close-settings').addEventListener('click', () => {
            const panel = document.getElementById('settings-panel');
            panel.classList.remove('open');
            setTimeout(() => { panel.style.display = 'none'; }, 300);
        });

        // Font size
        document.getElementById('font-decrease').addEventListener('click', () => {
            this.setFontSize(Math.max(12, this.fontSize - 2));
        });

        document.getElementById('font-increase').addEventListener('click', () => {
            this.setFontSize(Math.min(32, this.fontSize + 2));
        });

        // Theme
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setTheme(btn.dataset.theme);
            });
        });

        // Reading progress on scroll
        document.querySelector('.reader-content').addEventListener('scroll', () => {
            this.updateReadingProgress();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

            if (e.key === 'ArrowLeft') {
                this.goToChapter(this.currentChapter - 1);
            } else if (e.key === 'ArrowRight') {
                this.goToChapter(this.currentChapter + 1);
            } else if (e.key === 'Escape') {
                this.hideSelectionToolbar();
                document.getElementById('highlights-panel').classList.remove('open');
                document.getElementById('settings-panel').classList.remove('open');
                document.getElementById('note-modal').style.display = 'none';
            }
        });
    }

    // ==================== READING PROGRESS ====================

    updateReadingProgress() {
        const content = document.querySelector('.reader-content');
        const scrollTop = content.scrollTop;
        const scrollHeight = content.scrollHeight - content.clientHeight;
        const progress = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
        document.getElementById('reading-progress-fill').style.width = progress + '%';
    }

    // ==================== SETTINGS ====================

    setFontSize(size) {
        this.fontSize = size;
        document.getElementById('text-view').style.fontSize = size + 'px';
        document.getElementById('font-size-value').textContent = size + 'px';
        localStorage.setItem('scriptum-reader-fontsize', size);
    }

    loadFontSize() {
        const saved = localStorage.getItem('scriptum-reader-fontsize');
        if (saved) {
            this.fontSize = parseInt(saved);
            document.getElementById('font-size-value').textContent = this.fontSize + 'px';
        }
    }

    setTheme(theme) {
        if (theme === 'dark') {
            document.body.removeAttribute('data-theme');
        } else {
            document.body.dataset.theme = theme;
        }
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
        localStorage.setItem('scriptum-theme', theme);
    }

    loadTheme() {
        const theme = localStorage.getItem('scriptum-theme') || 'dark';
        this.setTheme(theme);
    }

    // ==================== UTILITIES ====================

    showError(message) {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('error-state').style.display = 'flex';
        document.getElementById('error-message').textContent = message;
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    showToast(message) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.textReader = new TextReader();
});
