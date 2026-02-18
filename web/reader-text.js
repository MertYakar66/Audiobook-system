/**
 * Scriptum PDF Reader
 *
 * Renders original PDF pages using PDF.js.
 * Shares reading progress with the Read & Listen reader.
 * Page-level annotation system (notes + highlights).
 */

// Book registry
const BOOK_SOURCES = {
    "the-intelligent-investor": {
        pdfFile: "../input/PDFs/The Intelligent Investor.pdf",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    },
    "the-intelligent-investor-text": {
        pdfFile: "../input/PDFs/The Intelligent Investor.pdf",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    }
};

// PDF.js CDN (jsdelivr mirrors npm pdfjs-dist)
const PDFJS_CDN = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.269/build";

// Highlight colors
const HIGHLIGHT_COLORS = [
    { name: 'yellow', color: '#fff59d' },
    { name: 'green', color: '#c8e6c9' },
    { name: 'blue', color: '#bbdefb' },
    { name: 'pink', color: '#f8bbd9' },
    { name: 'orange', color: '#ffcc80' }
];

class PDFReader {
    constructor() {
        this.bookId = null;
        this.bookInfo = null;
        this.pdfDoc = null;
        this.totalPages = 0;
        this.currentPage = 1;
        this.renderedPages = new Set();
        this.renderScale = 1.5;
        this.observer = null;
        this._scrollThrottleTimer = null;

        // Annotations
        this.notes = [];
        this.highlights = [];
        this.selectedColor = 'yellow';

        this.init();
    }

    async init() {
        const params = new URLSearchParams(window.location.search);
        this.bookId = params.get('book');

        if (!this.bookId || !BOOK_SOURCES[this.bookId]) {
            this.showError('Book not found.');
            return;
        }

        this.bookInfo = BOOK_SOURCES[this.bookId];
        document.getElementById('book-title').textContent = this.bookInfo.title;
        document.title = `${this.bookInfo.title} - Scriptum`;

        this.loadAnnotations();
        this.bindEvents();
        await this.loadPDF();
    }

    async loadPDF() {
        try {
            // Load PDF.js library
            const pdfjsLib = await import(`${PDFJS_CDN}/pdf.min.mjs`);
            pdfjsLib.GlobalWorkerOptions.workerSrc = `${PDFJS_CDN}/pdf.worker.min.mjs`;

            const loadingTask = pdfjsLib.getDocument(this.bookInfo.pdfFile);
            this.pdfDoc = await loadingTask.promise;
            this.totalPages = this.pdfDoc.numPages;

            // Update UI
            document.getElementById('page-indicator').textContent = `1 / ${this.totalPages}`;
            const slider = document.getElementById('page-slider');
            slider.max = this.totalPages;
            slider.value = 1;

            // Create page placeholders
            this.createPagePlaceholders();

            // Restore saved progress
            this.restoreProgress();

            // Show the viewer
            document.getElementById('loading-state').style.display = 'none';
            document.getElementById('pages-container').style.display = 'flex';

            // Set up intersection observer for lazy rendering
            this.setupLazyRendering();

            // Render first visible pages in parallel
            const pagesToRender = [];
            for (let i = this.currentPage; i <= Math.min(this.currentPage + 2, this.totalPages); i++) {
                pagesToRender.push(this.renderPage(i));
            }
            await Promise.all(pagesToRender);

            // Scroll to saved page
            this.scrollToPage(this.currentPage);

            // Apply page indicators for annotations
            this._applyAllPageIndicators();

        } catch (e) {
            console.error('PDF load error:', e);
            this.showError(`Could not load PDF: ${e.message}`);
        }
    }

    createPagePlaceholders() {
        const container = document.getElementById('pages-container');
        container.innerHTML = '';

        for (let i = 1; i <= this.totalPages; i++) {
            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.id = `page-${i}`;
            wrapper.dataset.page = i;

            // Create canvas with estimated dimensions
            const canvas = document.createElement('canvas');
            canvas.width = 612 * this.renderScale;
            canvas.height = 792 * this.renderScale;
            canvas.style.width = `${612}px`;
            canvas.style.height = `${792}px`;
            wrapper.appendChild(canvas);
            container.appendChild(wrapper);
        }
    }

    setupLazyRendering() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const pageNum = parseInt(entry.target.dataset.page);
                    this.renderPage(pageNum);
                }
            });
        }, {
            root: document.getElementById('viewer'),
            rootMargin: '200px 0px'
        });

        document.querySelectorAll('.page-wrapper').forEach(el => {
            this.observer.observe(el);
        });

        // Track current page on scroll (throttled to avoid jank)
        document.getElementById('viewer').addEventListener('scroll', () => {
            if (!this._scrollThrottleTimer) {
                this._scrollThrottleTimer = requestAnimationFrame(() => {
                    this._scrollThrottleTimer = null;
                    this.updateCurrentPageFromScroll();
                });
            }
        }, { passive: true });
    }

    async renderPage(pageNum) {
        if (this.renderedPages.has(pageNum) || pageNum < 1 || pageNum > this.totalPages) return;
        this.renderedPages.add(pageNum);

        try {
            const page = await this.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: this.renderScale });

            const wrapper = document.getElementById(`page-${pageNum}`);
            const canvas = wrapper.querySelector('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${viewport.width / this.renderScale}px`;
            canvas.style.height = `${viewport.height / this.renderScale}px`;

            const ctx = canvas.getContext('2d');
            await page.render({ canvasContext: ctx, viewport: viewport }).promise;
        } catch (e) {
            console.warn(`Failed to render page ${pageNum}:`, e);
            this.renderedPages.delete(pageNum);
        }
    }

    updateCurrentPageFromScroll() {
        const viewer = document.getElementById('viewer');
        const viewerRect = viewer.getBoundingClientRect();
        const viewerCenter = viewerRect.top + viewerRect.height / 3;

        // Only check pages near the current page instead of all pages
        const startPage = Math.max(1, this.currentPage - 3);
        const endPage = Math.min(this.totalPages, this.currentPage + 3);
        let closestPage = this.currentPage;
        let closestDist = Infinity;

        for (let i = startPage; i <= endPage; i++) {
            const page = document.getElementById(`page-${i}`);
            if (!page) continue;
            const rect = page.getBoundingClientRect();
            const dist = Math.abs(rect.top - viewerCenter);
            if (dist < closestDist) {
                closestDist = dist;
                closestPage = i;
            }
        }

        // If closest is at boundary, expand search in that direction
        if (closestPage === startPage && startPage > 1) {
            const prevPage = document.getElementById(`page-${startPage - 1}`);
            if (prevPage) {
                const dist = Math.abs(prevPage.getBoundingClientRect().top - viewerCenter);
                if (dist < closestDist) closestPage = startPage - 1;
            }
        } else if (closestPage === endPage && endPage < this.totalPages) {
            const nextPage = document.getElementById(`page-${endPage + 1}`);
            if (nextPage) {
                const dist = Math.abs(nextPage.getBoundingClientRect().top - viewerCenter);
                if (dist < closestDist) closestPage = endPage + 1;
            }
        }

        if (closestPage !== this.currentPage) {
            this.currentPage = closestPage;
            document.getElementById('page-indicator').textContent = `${this.currentPage} / ${this.totalPages}`;
            document.getElementById('page-slider').value = this.currentPage;
            this.saveProgress();
        }
    }

    scrollToPage(pageNum) {
        const el = document.getElementById(`page-${pageNum}`);
        if (el) {
            el.scrollIntoView({ behavior: 'auto', block: 'start' });
        }
    }

    goToPage(pageNum) {
        pageNum = Math.max(1, Math.min(this.totalPages, pageNum));
        this.currentPage = pageNum;
        document.getElementById('page-indicator').textContent = `${pageNum} / ${this.totalPages}`;
        document.getElementById('page-slider').value = pageNum;
        this.scrollToPage(pageNum);
        this.renderPage(pageNum);
        this.saveProgress();
    }

    // ==================== PROGRESS (shared with Read & Listen) ====================

    saveProgress() {
        const progress = {
            bookId: this.bookId,
            chapter: 0,
            position: 0,
            page: this.currentPage,
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
                    if (progress.page && progress.page <= this.totalPages) {
                        this.currentPage = progress.page;
                    }
                }
            }
        } catch (e) {
            console.warn('Could not restore progress:', e);
        }
    }

    // ==================== ANNOTATIONS ====================

    loadAnnotations() {
        try {
            const saved = localStorage.getItem(`scriptum-pdf-annotations-${this.bookId}`);
            if (saved) {
                const data = JSON.parse(saved);
                this.notes = data.notes || [];
                this.highlights = data.highlights || [];
            }
        } catch (e) {
            console.warn('Could not load annotations:', e);
        }
    }

    saveAnnotations() {
        const data = {
            notes: this.notes,
            highlights: this.highlights
        };
        localStorage.setItem(`scriptum-pdf-annotations-${this.bookId}`, JSON.stringify(data));
    }

    addPageHighlight(page, color) {
        const highlight = {
            id: Date.now().toString(),
            bookId: this.bookId,
            page: page,
            color: color || this.selectedColor,
            createdAt: new Date().toISOString()
        };
        this.highlights.push(highlight);
        this.saveAnnotations();
        this._applyPageIndicator(page);
        this.renderHighlightsList();
        this.showToast(`Page ${page} marked in ${highlight.color}`);
    }

    addPageNote(page, noteText, color) {
        if (!noteText.trim()) return;
        const note = {
            id: Date.now().toString(),
            bookId: this.bookId,
            page: page,
            note: noteText.trim(),
            color: color || this.selectedColor,
            createdAt: new Date().toISOString()
        };
        this.notes.push(note);
        this.saveAnnotations();
        this._applyPageIndicator(page);
        this.renderNotesList();
        this.showToast(`Note added to page ${page}`);
    }

    removeNote(id) {
        const note = this.notes.find(n => n.id === id);
        this.notes = this.notes.filter(n => n.id !== id);
        this.saveAnnotations();
        if (note) this._applyPageIndicator(note.page);
        this.renderNotesList();
        this.showToast('Note removed');
    }

    removeHighlight(id) {
        const h = this.highlights.find(h => h.id === id);
        this.highlights = this.highlights.filter(h => h.id !== id);
        this.saveAnnotations();
        if (h) this._applyPageIndicator(h.page);
        this.renderHighlightsList();
        this.showToast('Highlight removed');
    }

    _applyPageIndicator(page) {
        const wrapper = document.getElementById(`page-${page}`);
        if (!wrapper) return;

        // Remove existing indicator
        const existing = wrapper.querySelector('.page-annotation-indicator');
        if (existing) existing.remove();

        // Check if this page has any annotations
        const pageNotes = this.notes.filter(n => n.page === page);
        const pageHighlights = this.highlights.filter(h => h.page === page);
        const total = pageNotes.length + pageHighlights.length;

        if (total > 0) {
            const color = pageHighlights.length > 0
                ? (HIGHLIGHT_COLORS.find(c => c.name === pageHighlights[0].color)?.color || '#fff59d')
                : '#6c5ce7';
            const indicator = document.createElement('div');
            indicator.className = 'page-annotation-indicator';
            indicator.style.setProperty('--indicator-color', color);
            indicator.title = `${total} annotation${total > 1 ? 's' : ''} on this page`;
            wrapper.appendChild(indicator);
        }
    }

    _applyAllPageIndicators() {
        const pages = new Set();
        this.notes.forEach(n => pages.add(n.page));
        this.highlights.forEach(h => pages.add(h.page));
        pages.forEach(p => this._applyPageIndicator(p));
    }

    renderNotesList() {
        const container = document.getElementById('pdf-notes-list');
        if (!container) return;

        this._updatePdfTabBadges();

        if (this.notes.length === 0) {
            container.innerHTML = `
                <div class="pdf-empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="36" height="36">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                    <p>No notes yet</p>
                    <span>Use the note button to add a note to the current page</span>
                </div>`;
            return;
        }

        container.innerHTML = this.notes.map(n => {
            const colorObj = HIGHLIGHT_COLORS.find(c => c.name === n.color) || HIGHLIGHT_COLORS[0];
            const dateStr = this._formatDate(n.createdAt);
            return `
                <div class="pdf-annotation-card" data-id="${n.id}" style="border-left: 4px solid ${colorObj.color}">
                    <button class="pdf-annotation-delete" onclick="event.stopPropagation(); pdfReader.removeNote('${n.id}')" title="Delete">×</button>
                    <div class="pdf-annotation-meta">
                        <span class="pdf-annotation-page">Page ${n.page}</span>
                    </div>
                    <div class="pdf-annotation-note">${n.note}</div>
                    <div class="pdf-annotation-date">${dateStr}</div>
                </div>`;
        }).join('');

        container.querySelectorAll('.pdf-annotation-card').forEach(item => {
            item.addEventListener('click', () => {
                const note = this.notes.find(n => n.id === item.dataset.id);
                if (note) {
                    this.goToPage(note.page);
                    this.closeSidebar();
                }
            });
        });
    }

    renderHighlightsList() {
        const container = document.getElementById('pdf-highlights-list');
        if (!container) return;

        this._updatePdfTabBadges();

        if (this.highlights.length === 0) {
            container.innerHTML = `
                <div class="pdf-empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="36" height="36">
                        <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                    </svg>
                    <p>No page marks yet</p>
                    <span>Use the highlight button to mark the current page</span>
                </div>`;
            return;
        }

        container.innerHTML = this.highlights.map(h => {
            const colorObj = HIGHLIGHT_COLORS.find(c => c.name === h.color) || HIGHLIGHT_COLORS[0];
            const dateStr = this._formatDate(h.createdAt);
            return `
                <div class="pdf-annotation-card" data-id="${h.id}" style="border-left: 4px solid ${colorObj.color}">
                    <button class="pdf-annotation-delete" onclick="event.stopPropagation(); pdfReader.removeHighlight('${h.id}')" title="Delete">×</button>
                    <div class="pdf-annotation-meta">
                        <span class="pdf-annotation-page">Page ${h.page}</span>
                        <span class="pdf-annotation-color-dot" style="background: ${colorObj.color}"></span>
                    </div>
                    <div class="pdf-annotation-date">${dateStr}</div>
                </div>`;
        }).join('');

        container.querySelectorAll('.pdf-annotation-card').forEach(item => {
            item.addEventListener('click', () => {
                const h = this.highlights.find(h => h.id === item.dataset.id);
                if (h) {
                    this.goToPage(h.page);
                    this.closeSidebar();
                }
            });
        });
    }

    _updatePdfTabBadges() {
        const counts = {
            'pdf-highlights': this.highlights.length,
            'pdf-notes': this.notes.length
        };
        document.querySelectorAll('.pdf-panel-tab').forEach(tab => {
            const name = tab.dataset.tab;
            const count = counts[name] || 0;
            let badge = tab.querySelector('.pdf-tab-badge');
            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'pdf-tab-badge';
                    tab.appendChild(badge);
                }
                badge.textContent = count;
            } else if (badge) {
                badge.remove();
            }
        });
    }

    exportAnnotations() {
        let content = `# Annotations\n\n`;
        content += `**${this.bookInfo.title}**\n`;
        content += `*By ${this.bookInfo.author}*\n\n`;
        content += `Exported: ${this._formatDate(new Date().toISOString())}\n\n---\n\n`;

        if (this.highlights.length > 0) {
            content += `## Page Marks (${this.highlights.length})\n\n`;
            this.highlights.forEach((h, i) => {
                content += `${i + 1}. Page ${h.page} (${h.color}) - ${this._formatDate(h.createdAt)}\n`;
            });
            content += '\n';
        }

        if (this.notes.length > 0) {
            content += `## Notes (${this.notes.length})\n\n`;
            this.notes.forEach((n, i) => {
                content += `${i + 1}. **Page ${n.page}:** ${n.note}\n`;
                content += `   *${this._formatDate(n.createdAt)}*\n\n`;
            });
        }

        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.bookInfo.title.replace(/[^a-z0-9]/gi, '_')}_annotations.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.showToast('Annotations exported');
    }

    _formatDate(isoString) {
        try {
            const d = new Date(isoString);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
                ' at ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        } catch {
            return isoString;
        }
    }

    // ==================== SIDEBAR ====================

    openSidebar() {
        document.getElementById('pdf-sidebar').classList.add('open');
        document.getElementById('pdf-sidebar-overlay')?.classList.add('open');
        this.renderNotesList();
        this.renderHighlightsList();
    }

    closeSidebar() {
        document.getElementById('pdf-sidebar').classList.remove('open');
        document.getElementById('pdf-sidebar-overlay')?.classList.remove('open');
    }

    openNoteModal() {
        document.getElementById('pdf-note-page-num').textContent = this.currentPage;
        document.getElementById('pdf-note-input').value = '';
        document.getElementById('pdf-notes-modal').classList.add('open');
        document.getElementById('pdf-note-input').focus();
    }

    closeNoteModal() {
        document.getElementById('pdf-notes-modal').classList.remove('open');
    }

    // ==================== EVENTS ====================

    bindEvents() {
        // Page navigation
        document.getElementById('prev-page').addEventListener('click', () => {
            this.goToPage(this.currentPage - 1);
        });

        document.getElementById('next-page').addEventListener('click', () => {
            this.goToPage(this.currentPage + 1);
        });

        document.getElementById('page-slider').addEventListener('input', (e) => {
            const page = parseInt(e.target.value);
            document.getElementById('page-indicator').textContent = `${page} / ${this.totalPages}`;
        });

        document.getElementById('page-slider').addEventListener('change', (e) => {
            this.goToPage(parseInt(e.target.value));
        });

        // Annotation buttons in header
        document.getElementById('pdf-sidebar-btn')?.addEventListener('click', () => {
            this.openSidebar();
        });

        document.getElementById('pdf-highlight-btn')?.addEventListener('click', () => {
            this.addPageHighlight(this.currentPage, this.selectedColor);
        });

        document.getElementById('pdf-note-btn')?.addEventListener('click', () => {
            this.openNoteModal();
        });

        // Sidebar
        document.getElementById('pdf-close-sidebar')?.addEventListener('click', () => {
            this.closeSidebar();
        });

        // Sidebar tabs
        document.querySelectorAll('.pdf-panel-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.pdf-panel-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const tabName = tab.dataset.tab;
                document.querySelectorAll('.pdf-tab-content').forEach(c => c.classList.remove('active'));
                document.getElementById(`${tabName}-tab`)?.classList.add('active');
            });
        });

        // Export
        document.getElementById('pdf-export-btn')?.addEventListener('click', () => {
            this.exportAnnotations();
        });

        // Note modal
        document.getElementById('pdf-close-note-modal')?.addEventListener('click', () => {
            this.closeNoteModal();
        });

        document.getElementById('pdf-save-note')?.addEventListener('click', () => {
            const text = document.getElementById('pdf-note-input').value;
            this.addPageNote(this.currentPage, text, this.selectedColor);
            this.closeNoteModal();
        });

        // Modal color picker
        document.querySelectorAll('.pdf-color-pick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.pdf-color-pick-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                this.selectedColor = btn.dataset.color;
            });
        });

        // Close modal on backdrop
        document.querySelectorAll('.pdf-modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.remove('open');
            });
        });

        // Close sidebar on overlay click
        document.getElementById('pdf-sidebar-overlay')?.addEventListener('click', () => {
            this.closeSidebar();
        });

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault();
                this.goToPage(this.currentPage - 1);
            } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault();
                this.goToPage(this.currentPage + 1);
            } else if (e.key === 'Home') {
                e.preventDefault();
                this.goToPage(1);
            } else if (e.key === 'End') {
                e.preventDefault();
                this.goToPage(this.totalPages);
            }
        });
    }

    // ==================== UTILITIES ====================

    showError(message) {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('error-state').style.display = 'flex';
        document.getElementById('error-message').textContent = message;
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
    window.pdfReader = new PDFReader();
});
