/**
 * Scriptum PDF Reader
 *
 * Renders original PDF pages using PDF.js.
 * Shares reading progress with the Read & Listen reader.
 */

// Book registry
const BOOK_SOURCES = {
    "the-intelligent-investor": {
        pdfFile: "../input/PDFs/The Intelligent Investor.pdf",
        title: "The Intelligent Investor",
        author: "Benjamin Graham"
    }
};

// PDF.js worker
const PDFJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379";

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

            // Render first visible pages
            await this.renderPage(this.currentPage);
            if (this.currentPage + 1 <= this.totalPages) {
                await this.renderPage(this.currentPage + 1);
            }

            // Scroll to saved page
            this.scrollToPage(this.currentPage);

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

        // Track current page on scroll
        document.getElementById('viewer').addEventListener('scroll', () => {
            this.updateCurrentPageFromScroll();
        });
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

        const pages = document.querySelectorAll('.page-wrapper');
        let closestPage = 1;
        let closestDist = Infinity;

        for (const page of pages) {
            const rect = page.getBoundingClientRect();
            const dist = Math.abs(rect.top - viewerCenter);
            if (dist < closestDist) {
                closestDist = dist;
                closestPage = parseInt(page.dataset.page);
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
        // Map page to approximate chapter for Read & Listen compatibility
        // Store page number in position field for precise restore
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

    // ==================== EVENTS ====================

    bindEvents() {
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

        // Keyboard
        document.addEventListener('keydown', (e) => {
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
