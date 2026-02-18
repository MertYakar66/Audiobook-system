/**
 * Scriptum Read Only Reader
 *
 * Renders structured text from text.json with:
 * - Chapter navigation
 * - Tool-first annotation: pick a tool, then click sentences
 * - Multi-color sentence highlighting
 * - Notes on selected text
 * - Eraser tool to remove highlights
 * - Persistent annotations (localStorage)
 * - Progress tracking (chapter + scroll)
 * - Export annotations as markdown
 */

// Book registry — maps URL ?book= param to text data path
const BOOK_SOURCES = {
    "the-intelligent-investor": {
        textPath: "../output/readalong/the-intelligent-investor",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    },
    "the-intelligent-investor-text": {
        textPath: "../output/readalong/the-intelligent-investor",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    }
};

// Highlight colors
const HIGHLIGHT_COLORS = [
    { name: 'yellow', color: '#fff59d' },
    { name: 'green', color: '#c8e6c9' },
    { name: 'blue', color: '#bbdefb' },
    { name: 'pink', color: '#f8bbd9' },
    { name: 'orange', color: '#ffcc80' }
];

class TextReader {
    constructor() {
        this.bookId = null;
        this.bookInfo = null;
        this.textData = null;
        this.currentChapter = 0;

        // Annotations
        this.highlights = [];
        this.notes = [];
        this.selectedHighlightColor = 'yellow';

        // Active tool: null, 'highlight', 'note', 'eraser'
        this.activeTool = null;

        this.init();
    }

    async init() {
        var params = new URLSearchParams(window.location.search);
        this.bookId = params.get('book');

        if (!this.bookId || !BOOK_SOURCES[this.bookId]) {
            this.showError('Book not found.');
            return;
        }

        this.bookInfo = BOOK_SOURCES[this.bookId];
        document.getElementById('book-title').textContent = this.bookInfo.title;
        document.title = this.bookInfo.title + ' - Scriptum';

        this.loadAnnotations();
        this.bindEvents();
        await this.loadBook();
    }

    // ==================== LOADING ====================

    async loadBook() {
        try {
            var resp = await fetch(this.bookInfo.textPath + '/text.json');
            if (!resp.ok) throw new Error('Could not load text data');
            this.textData = await resp.json();

            // Populate chapter selector
            var select = document.getElementById('chapter-select');
            this.textData.chapters.forEach(function(ch, i) {
                var opt = document.createElement('option');
                opt.value = i;
                opt.textContent = ch.title || ('Chapter ' + (i + 1));
                select.appendChild(opt);
            });

            // Hide loading, show text
            document.getElementById('loading-state').style.display = 'none';
            document.getElementById('text-content').style.display = 'block';

            // Restore saved progress or load first chapter
            var saved = this.restoreProgress();
            if (saved && saved.chapter < this.textData.chapters.length) {
                this.loadChapter(saved.chapter, saved.scrollTop);
            } else {
                this.loadChapter(0);
            }

        } catch (e) {
            console.error('Load error:', e);
            this.showError(e.message);
        }
    }

    // ==================== CHAPTER RENDERING ====================

    loadChapter(index, scrollTop) {
        if (!this.textData || index < 0 || index >= this.textData.chapters.length) return;

        this.currentChapter = index;
        var chapter = this.textData.chapters[index];

        // Update nav
        document.getElementById('chapter-select').value = index;
        document.getElementById('prev-chapter').disabled = index === 0;
        document.getElementById('next-chapter').disabled = index === this.textData.chapters.length - 1;

        // Build lookup maps for annotations
        var highlightMap = new Map();
        for (var h of this.highlights) {
            if (h.chapter === index) highlightMap.set(h.sentenceId, h);
        }
        var noteMap = new Map();
        for (var n of this.notes) {
            if (n.chapter === index) noteMap.set(n.sentenceId, n);
        }
        var colorMap = new Map();
        for (var c of HIGHLIGHT_COLORS) {
            colorMap.set(c.name, c.color);
        }

        // Build DOM
        var fragment = document.createDocumentFragment();

        chapter.paragraphs.forEach(function(paragraph) {
            var pEl = document.createElement('p');
            pEl.className = 'paragraph';
            pEl.dataset.id = paragraph.id;

            paragraph.sentences.forEach(function(sentence) {
                var span = document.createElement('span');
                span.className = 'sentence';
                span.dataset.id = sentence.id;
                span.textContent = sentence.text + ' ';

                // Apply saved highlight
                var hl = highlightMap.get(sentence.id);
                if (hl) {
                    span.classList.add('highlighted');
                    span.dataset.highlightColor = hl.color;
                    var bgColor = colorMap.get(hl.color);
                    if (bgColor) span.style.backgroundColor = bgColor;
                }

                // Apply saved note indicator
                if (noteMap.has(sentence.id)) {
                    span.classList.add('has-note');
                }

                pEl.appendChild(span);
            });

            fragment.appendChild(pEl);
        });

        var textContent = document.getElementById('text-content');
        textContent.innerHTML = '';
        textContent.appendChild(fragment);

        // Scroll to saved position or top
        var content = document.getElementById('content');
        if (scrollTop && scrollTop > 0) {
            requestAnimationFrame(function() { content.scrollTop = scrollTop; });
        } else {
            content.scrollTop = 0;
        }

        this.saveProgress();
    }

    // ==================== TOOL MANAGEMENT ====================

    setActiveTool(toolName) {
        // Toggle off if same tool clicked again
        if (this.activeTool === toolName) {
            this.activeTool = null;
        } else {
            this.activeTool = toolName;
        }

        // Update button states
        document.querySelectorAll('.tool-btn').forEach(function(btn) {
            btn.classList.remove('active');
        });
        if (this.activeTool) {
            var activeBtn = document.getElementById('tool-' + this.activeTool);
            if (activeBtn) activeBtn.classList.add('active');
        }

        // Update body class for cursor
        document.body.classList.remove('tool-highlight', 'tool-note', 'tool-eraser');
        if (this.activeTool) {
            document.body.classList.add('tool-' + this.activeTool);
        }
    }

    handleSentenceClick(sentenceEl) {
        if (!this.activeTool) return;

        var sentenceId = sentenceEl.dataset.id;
        var sentenceText = sentenceEl.textContent.trim();

        if (this.activeTool === 'highlight') {
            this.addHighlight(sentenceId, sentenceText, sentenceEl);
        } else if (this.activeTool === 'note') {
            this.openNoteModal(sentenceId, sentenceText);
        } else if (this.activeTool === 'eraser') {
            this.eraseHighlight(sentenceId, sentenceEl);
        }
    }

    // ==================== HIGHLIGHTING ====================

    addHighlight(sentenceId, sentenceText, el) {
        var chapter = this.textData.chapters[this.currentChapter];
        var highlight = {
            id: Date.now().toString(),
            bookId: this.bookId,
            chapter: this.currentChapter,
            chapterTitle: chapter.title || ('Chapter ' + (this.currentChapter + 1)),
            sentenceId: sentenceId,
            text: sentenceText,
            color: this.selectedHighlightColor,
            createdAt: new Date().toISOString()
        };

        // Remove existing highlight on same sentence (replace with new color)
        this.highlights = this.highlights.filter(function(h) { return h.sentenceId !== sentenceId; });
        this.highlights.push(highlight);
        this.saveAnnotations();
        this.renderHighlightsList();

        // Apply to DOM
        el.classList.add('highlighted');
        el.dataset.highlightColor = this.selectedHighlightColor;
        var colorObj = HIGHLIGHT_COLORS.find(function(c) { return c.name === highlight.color; });
        if (colorObj) el.style.backgroundColor = colorObj.color;

        // Flash feedback
        el.classList.add('flash');
        setTimeout(function() { el.classList.remove('flash'); }, 900);
        this.showToast('Highlighted in ' + this.selectedHighlightColor);
    }

    eraseHighlight(sentenceId, el) {
        var existing = this.highlights.find(function(h) { return h.sentenceId === sentenceId; });
        if (!existing) {
            this.showToast('No highlight to remove');
            return;
        }

        el.classList.remove('highlighted');
        el.style.backgroundColor = '';
        delete el.dataset.highlightColor;

        this.highlights = this.highlights.filter(function(h) { return h.sentenceId !== sentenceId; });
        this.saveAnnotations();
        this.renderHighlightsList();
        this.showToast('Highlight removed');
    }

    removeHighlight(id) {
        var highlight = this.highlights.find(function(h) { return h.id === id; });
        if (highlight) {
            var el = document.querySelector('[data-id="' + highlight.sentenceId + '"]');
            if (el) {
                el.classList.remove('highlighted');
                el.style.backgroundColor = '';
                delete el.dataset.highlightColor;
            }
        }
        this.highlights = this.highlights.filter(function(h) { return h.id !== id; });
        this.saveAnnotations();
        this.renderHighlightsList();
        this.showToast('Highlight removed');
    }

    // ==================== NOTES ====================

    openNoteModal(sentenceId, sentenceText) {
        this._pendingNoteSentenceId = sentenceId;
        this._pendingNoteSentenceText = sentenceText;
        document.getElementById('selected-text-preview').textContent = '"' + sentenceText + '"';
        document.getElementById('note-input').value = '';
        document.getElementById('note-modal').classList.add('open');
        document.getElementById('note-input').focus();
    }

    closeNoteModal() {
        document.getElementById('note-modal').classList.remove('open');
        this._pendingNoteSentenceId = null;
        this._pendingNoteSentenceText = null;
    }

    saveNote() {
        var noteText = document.getElementById('note-input').value.trim();
        if (!noteText && !this._pendingNoteSentenceText) return;

        var sentenceId = this._pendingNoteSentenceId;
        var selectedText = this._pendingNoteSentenceText;

        var chapter = this.textData.chapters[this.currentChapter];
        var note = {
            id: Date.now().toString(),
            bookId: this.bookId,
            chapter: this.currentChapter,
            chapterTitle: chapter.title || ('Chapter ' + (this.currentChapter + 1)),
            sentenceId: sentenceId,
            selectedText: selectedText,
            note: noteText,
            color: this.selectedHighlightColor,
            createdAt: new Date().toISOString()
        };

        this.notes.push(note);
        this.saveAnnotations();
        this.renderNotesList();
        this.closeNoteModal();

        // Mark sentence
        var el = document.querySelector('[data-id="' + sentenceId + '"]');
        if (el) el.classList.add('has-note');

        this.showToast('Note saved');
    }

    addHighlightOnly() {
        // Highlight the sentence from the note modal context
        if (this._pendingNoteSentenceId) {
            var el = document.querySelector('[data-id="' + this._pendingNoteSentenceId + '"]');
            if (el) {
                this.addHighlight(this._pendingNoteSentenceId, this._pendingNoteSentenceText, el);
            }
        }
        this.closeNoteModal();
    }

    removeNote(id) {
        var note = this.notes.find(function(n) { return n.id === id; });
        if (note) {
            var el = document.querySelector('[data-id="' + note.sentenceId + '"]');
            if (el) el.classList.remove('has-note');
        }
        this.notes = this.notes.filter(function(n) { return n.id !== id; });
        this.saveAnnotations();
        this.renderNotesList();
        this.showToast('Note removed');
    }

    // ==================== SIDEBAR ====================

    openSidebar() {
        document.getElementById('sidebar').classList.add('open');
        document.getElementById('sidebar-overlay').classList.add('open');
        this.renderHighlightsList();
        this.renderNotesList();
    }

    closeSidebar() {
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebar-overlay').classList.remove('open');
    }

    renderHighlightsList() {
        var container = document.getElementById('highlights-list');
        if (!container) return;

        this._updateTabBadges();
        var bookHighlights = this.highlights.filter(function(h) { return h.bookId === this.bookId; }.bind(this));

        if (bookHighlights.length === 0) {
            container.innerHTML =
                '<div class="empty-state">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="36" height="36">' +
                '<path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>' +
                '</svg>' +
                '<p>No highlights yet</p>' +
                '<span>Use the toolbar above, then click sentences</span>' +
                '</div>';
            return;
        }

        container.innerHTML = bookHighlights.map(function(h) {
            var colorObj = HIGHLIGHT_COLORS.find(function(c) { return c.name === h.color; }) || HIGHLIGHT_COLORS[0];
            var dateStr = this._formatDate(h.createdAt);
            var chTitle = h.chapterTitle || ('Chapter ' + (h.chapter + 1));
            var textPreview = h.text.length > 150 ? h.text.substring(0, 150) + '...' : h.text;
            return '<div class="annotation-card" data-id="' + h.id + '" style="border-left: 4px solid ' + colorObj.color + '">' +
                '<button class="annotation-delete" onclick="event.stopPropagation(); textReader.removeHighlight(\'' + h.id + '\')" title="Delete">&times;</button>' +
                '<div class="annotation-meta"><span class="annotation-chapter">' + chTitle + '</span></div>' +
                '<div class="annotation-quote" style="background: ' + colorObj.color + '; color: #1a1a2e;">"' + this._escapeHtml(textPreview) + '"</div>' +
                '<div class="annotation-date">' + dateStr + '</div>' +
                '</div>';
        }.bind(this)).join('');

        var self = this;
        container.querySelectorAll('.annotation-card').forEach(function(item) {
            item.addEventListener('click', function() {
                var h = self.highlights.find(function(h) { return h.id === item.dataset.id; });
                if (h) self._goToAnnotation(h.chapter, h.sentenceId);
            });
        });
    }

    renderNotesList() {
        var container = document.getElementById('notes-list');
        if (!container) return;

        this._updateTabBadges();
        var bookNotes = this.notes.filter(function(n) { return n.bookId === this.bookId; }.bind(this));

        if (bookNotes.length === 0) {
            container.innerHTML =
                '<div class="empty-state">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="36" height="36">' +
                '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
                '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>' +
                '</svg>' +
                '<p>No notes yet</p>' +
                '<span>Use the Note tool, then click a sentence</span>' +
                '</div>';
            return;
        }

        container.innerHTML = bookNotes.map(function(n) {
            var colorObj = HIGHLIGHT_COLORS.find(function(c) { return c.name === n.color; }) || HIGHLIGHT_COLORS[0];
            var dateStr = this._formatDate(n.createdAt);
            var chTitle = n.chapterTitle || ('Chapter ' + (n.chapter + 1));
            var textPreview = n.selectedText.length > 150 ? n.selectedText.substring(0, 150) + '...' : n.selectedText;
            return '<div class="annotation-card" data-id="' + n.id + '" style="border-left: 4px solid ' + colorObj.color + '">' +
                '<button class="annotation-delete" onclick="event.stopPropagation(); textReader.removeNote(\'' + n.id + '\')" title="Delete">&times;</button>' +
                '<div class="annotation-meta"><span class="annotation-chapter">' + chTitle + '</span></div>' +
                '<div class="annotation-quote">"' + this._escapeHtml(textPreview) + '"</div>' +
                '<div class="annotation-note-text">' + this._escapeHtml(n.note) + '</div>' +
                '<div class="annotation-date">' + dateStr + '</div>' +
                '</div>';
        }.bind(this)).join('');

        var self = this;
        container.querySelectorAll('.annotation-card').forEach(function(item) {
            item.addEventListener('click', function() {
                var n = self.notes.find(function(n) { return n.id === item.dataset.id; });
                if (n) self._goToAnnotation(n.chapter, n.sentenceId);
            });
        });
    }

    _goToAnnotation(chapter, sentenceId) {
        if (chapter !== this.currentChapter) {
            this.loadChapter(chapter);
        }
        this.closeSidebar();
        setTimeout(function() {
            var el = document.querySelector('[data-id="' + sentenceId + '"]');
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.classList.add('flash');
                setTimeout(function() { el.classList.remove('flash'); }, 1500);
            }
        }, 300);
    }

    _updateTabBadges() {
        var self = this;
        var counts = {
            highlights: this.highlights.filter(function(h) { return h.bookId === self.bookId; }).length,
            notes: this.notes.filter(function(n) { return n.bookId === self.bookId; }).length
        };
        document.querySelectorAll('.panel-tab').forEach(function(tab) {
            var name = tab.dataset.tab;
            var count = counts[name] || 0;
            var badge = tab.querySelector('.tab-badge');
            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'tab-badge';
                    tab.appendChild(badge);
                }
                badge.textContent = count;
            } else if (badge) {
                badge.remove();
            }
        });
    }

    // ==================== EXPORT ====================

    exportAnnotations() {
        var content = '# Notes and Highlights\n\n';
        content += '**' + this.bookInfo.title + '**\n';
        content += '*By ' + this.bookInfo.author + '*\n\n';
        content += 'Exported: ' + this._formatDate(new Date().toISOString()) + '\n\n---\n\n';

        var bookHighlights = this.highlights.filter(function(h) { return h.bookId === this.bookId; }.bind(this));
        var bookNotes = this.notes.filter(function(n) { return n.bookId === this.bookId; }.bind(this));

        if (bookHighlights.length > 0) {
            content += '## Highlights (' + bookHighlights.length + ')\n\n';
            bookHighlights.forEach(function(h, i) {
                var chTitle = h.chapterTitle || ('Chapter ' + (h.chapter + 1));
                content += (i + 1) + '. > "' + h.text + '"\n\n';
                content += '   *' + chTitle + ' | ' + this._formatDate(h.createdAt) + '*\n\n';
            }.bind(this));
        }

        if (bookNotes.length > 0) {
            content += '## Notes (' + bookNotes.length + ')\n\n';
            bookNotes.forEach(function(n, i) {
                var chTitle = n.chapterTitle || ('Chapter ' + (n.chapter + 1));
                content += (i + 1) + '. > "' + n.selectedText + '"\n\n';
                content += '   **Note:** ' + n.note + '\n\n';
                content += '   *' + chTitle + ' | ' + this._formatDate(n.createdAt) + '*\n\n';
            }.bind(this));
        }

        var blob = new Blob([content], { type: 'text/markdown' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = this.bookInfo.title.replace(/[^a-z0-9]/gi, '_') + '_notes.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.showToast('Annotations exported');
    }

    // ==================== PERSISTENCE ====================

    saveAnnotations() {
        var data = { highlights: this.highlights, notes: this.notes };
        localStorage.setItem('scriptum-annotations-' + this.bookId, JSON.stringify(data));
    }

    loadAnnotations() {
        try {
            var saved = localStorage.getItem('scriptum-annotations-' + this.bookId);
            if (saved) {
                var data = JSON.parse(saved);
                this.highlights = data.highlights || [];
                this.notes = data.notes || [];
            }
        } catch (e) {
            console.warn('Could not load annotations:', e);
        }
    }

    saveProgress() {
        var content = document.getElementById('content');
        var progress = {
            chapter: this.currentChapter,
            scrollTop: content ? content.scrollTop : 0,
            updatedAt: Date.now()
        };
        localStorage.setItem('scriptum-progress-' + this.bookId, JSON.stringify(progress));
    }

    restoreProgress() {
        try {
            var saved = localStorage.getItem('scriptum-progress-' + this.bookId);
            if (saved) {
                var progress = JSON.parse(saved);
                if (Date.now() - progress.updatedAt < 30 * 24 * 60 * 60 * 1000) {
                    return progress;
                }
            }
        } catch (e) {
            console.warn('Could not restore progress:', e);
        }
        return null;
    }

    // ==================== EVENTS ====================

    bindEvents() {
        var self = this;

        // Chapter navigation
        document.getElementById('chapter-select').addEventListener('change', function(e) {
            self.loadChapter(parseInt(e.target.value));
        });
        document.getElementById('prev-chapter').addEventListener('click', function() {
            if (self.currentChapter > 0) self.loadChapter(self.currentChapter - 1);
        });
        document.getElementById('next-chapter').addEventListener('click', function() {
            if (self.textData && self.currentChapter < self.textData.chapters.length - 1) {
                self.loadChapter(self.currentChapter + 1);
            }
        });

        // Tool buttons
        document.querySelectorAll('.tool-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                self.setActiveTool(btn.dataset.tool);
            });
        });

        // Color buttons in toolbar
        document.querySelectorAll('.tool-color').forEach(function(btn) {
            btn.addEventListener('click', function() {
                self.selectedHighlightColor = btn.dataset.color;
                document.querySelectorAll('.tool-color').forEach(function(b) { b.classList.remove('selected'); });
                btn.classList.add('selected');
                // Also update the modal color picker
                document.querySelectorAll('.color-pick-btn').forEach(function(b) { b.classList.remove('selected'); });
                var modalBtn = document.querySelector('.color-pick-btn[data-color="' + btn.dataset.color + '"]');
                if (modalBtn) modalBtn.classList.add('selected');
            });
        });

        // Sentence clicks (tool-first pattern)
        document.getElementById('text-content').addEventListener('click', function(e) {
            var sentenceEl = e.target.closest('.sentence');
            if (sentenceEl && self.activeTool) {
                e.preventDefault();
                self.handleSentenceClick(sentenceEl);
            }
        });

        // Sidebar
        document.getElementById('sidebar-btn').addEventListener('click', function() {
            self.openSidebar();
        });
        document.getElementById('close-sidebar').addEventListener('click', function() {
            self.closeSidebar();
        });
        document.getElementById('sidebar-overlay').addEventListener('click', function() {
            self.closeSidebar();
        });

        // Sidebar tabs
        document.querySelectorAll('.panel-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.panel-tab').forEach(function(t) { t.classList.remove('active'); });
                tab.classList.add('active');
                var tabName = tab.dataset.tab;
                document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
                var target = document.getElementById(tabName + '-tab');
                if (target) target.classList.add('active');
            });
        });

        // Export
        document.getElementById('export-btn').addEventListener('click', function() {
            self.exportAnnotations();
        });

        // Note modal
        document.getElementById('close-note-modal').addEventListener('click', function() {
            self.closeNoteModal();
        });
        document.getElementById('save-note').addEventListener('click', function() {
            self.saveNote();
        });
        document.getElementById('highlight-only').addEventListener('click', function() {
            self.addHighlightOnly();
        });

        // Modal color picker
        document.querySelectorAll('.color-pick-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.color-pick-btn').forEach(function(b) { b.classList.remove('selected'); });
                btn.classList.add('selected');
                self.selectedHighlightColor = btn.dataset.color;
                // Sync toolbar colors
                document.querySelectorAll('.tool-color').forEach(function(b) { b.classList.remove('selected'); });
                var toolBtn = document.querySelector('.tool-color[data-color="' + btn.dataset.color + '"]');
                if (toolBtn) toolBtn.classList.add('selected');
            });
        });

        // Close modal on backdrop
        document.querySelectorAll('.modal').forEach(function(modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) modal.classList.remove('open');
            });
        });

        // Save progress on scroll (debounced)
        var scrollTimer = null;
        document.getElementById('content').addEventListener('scroll', function() {
            if (scrollTimer) clearTimeout(scrollTimer);
            scrollTimer = setTimeout(function() { self.saveProgress(); }, 1000);
        }, { passive: true });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

            // Escape to deactivate tool
            if (e.key === 'Escape') {
                self.setActiveTool(null);
                self.activeTool = null;
                return;
            }

            if (e.key === 'ArrowLeft') {
                if (self.currentChapter > 0) self.loadChapter(self.currentChapter - 1);
            } else if (e.key === 'ArrowRight') {
                if (self.textData && self.currentChapter < self.textData.chapters.length - 1) {
                    self.loadChapter(self.currentChapter + 1);
                }
            }

            // Tool shortcuts: h = highlight, n = note, e = eraser
            if (e.key === 'h') self.setActiveTool('highlight');
            else if (e.key === 'n') self.setActiveTool('note');
            else if (e.key === 'e') self.setActiveTool('eraser');
        });
    }

    // ==================== UTILITIES ====================

    showError(message) {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('error-state').style.display = 'flex';
        document.getElementById('error-message').textContent = message;
    }

    showToast(message) {
        var toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(function() { toast.classList.remove('show'); }, 3000);
    }

    _formatDate(isoString) {
        try {
            var d = new Date(isoString);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
                ' at ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        } catch (e) {
            return isoString;
        }
    }

    _escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    window.textReader = new TextReader();
});
