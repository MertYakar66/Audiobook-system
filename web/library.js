/**
 * Scriptum Library
 *
 * Homepage with sidebar navigation, book management,
 * and aggregated highlights/notes from all books.
 */

// Converted books catalog — books that have been processed with readalong
const CONVERTED_BOOKS = [
    {
        id: "the-intelligent-investor",
        path: "../output/readalong/The-Intelligent-Investor",
        title: "The Intelligent Investor",
        author: "Benjamin Graham",
        cover: "../output/readalong/The-Intelligent-Investor/cover.jpg",
        totalDuration: 79196,
        chapterCount: 22,
        addedDate: "2025-02-05"
    }
];

// Uploaded books (not yet converted) — detected from input folder
const UPLOADED_BOOKS = [
    // Example entry:
    // {
    //     id: "common-stocks",
    //     title: "Common Stocks and Uncommon Profits",
    //     author: "Philip Fisher",
    //     filename: "Common-Stocks-and-Uncommon-Profits.pdf",
    //     addedDate: "2025-02-05"
    // }
];

class ScriptumLibrary {
    constructor() {
        this.convertedBooks = [];
        this.uploadedBooks = [...UPLOADED_BOOKS];
        this.highlights = [];
        this.notes = [];
        this.currentView = 'converted';
        this.layout = 'grid';

        this.init();
    }

    async init() {
        this.loadBookData();
        await this.loadConvertedBooks();
        this.updateCounts();
        this.renderCurrentView();
        this.bindEvents();
        this.loadTheme();

        // Open the books section by default
        document.querySelector('[data-section="books"]').classList.add('open');
    }

    // ==================== DATA LOADING ====================

    async loadConvertedBooks() {
        for (const catalog of CONVERTED_BOOKS) {
            try {
                const response = await fetch(`${catalog.path}/manifest.json`);
                if (response.ok) {
                    const manifest = await response.json();
                    this.convertedBooks.push({
                        ...catalog,
                        title: manifest.title || catalog.title,
                        author: manifest.author || catalog.author,
                        totalDuration: manifest.totalDuration || catalog.totalDuration,
                        chapterCount: manifest.chapterCount || catalog.chapterCount,
                        chapters: manifest.chapters || []
                    });
                } else {
                    this.convertedBooks.push(catalog);
                }
            } catch (e) {
                console.warn(`Could not load manifest for ${catalog.id}`, e);
                this.convertedBooks.push(catalog);
            }
        }
    }

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

    getBookProgress(bookId) {
        try {
            const saved = localStorage.getItem(`readalong-progress-${bookId}`);
            if (saved) return JSON.parse(saved);
        } catch (e) { /* ignore */ }
        return null;
    }

    getProgressPercent(book) {
        const progress = this.getBookProgress(book.id);
        if (!progress) return 0;
        const chapterDuration = book.totalDuration / (book.chapterCount || 1);
        const totalListened = (progress.chapter * chapterDuration) + progress.position;
        return Math.min(100, (totalListened / book.totalDuration) * 100);
    }

    // ==================== RENDERING ====================

    updateCounts() {
        document.getElementById('converted-count').textContent = this.convertedBooks.length;
        document.getElementById('uploaded-count').textContent = this.uploadedBooks.length;
        document.getElementById('notes-count').textContent =
            this.highlights.length + this.notes.length;
    }

    renderCurrentView() {
        // Hide all views
        document.querySelectorAll('.content-view').forEach(v => v.classList.remove('active'));

        // Show target view
        const viewEl = document.getElementById(`view-${this.currentView}`);
        if (viewEl) viewEl.classList.add('active');

        // Update page title
        const titles = {
            'converted': 'Library',
            'uploaded': 'Uploaded Books',
            'all-notes': 'Highlights & Notes'
        };
        document.getElementById('page-title').textContent = titles[this.currentView] || 'Library';

        // Render content
        switch (this.currentView) {
            case 'converted':
                this.renderConvertedBooks();
                break;
            case 'uploaded':
                this.renderUploadedBooks();
                break;
            case 'all-notes':
                this.renderAllNotes();
                break;
        }
    }

    renderConvertedBooks() {
        const grid = document.getElementById('converted-grid');
        const empty = document.getElementById('converted-empty');

        if (this.convertedBooks.length === 0) {
            grid.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        grid.style.display = '';
        empty.style.display = 'none';

        if (this.layout === 'list') {
            grid.className = 'books-grid list-layout';
            grid.innerHTML = this.renderListHeader() +
                this.convertedBooks.map(book => this.renderBookListItem(book, true)).join('');
        } else {
            grid.className = 'books-grid';
            grid.innerHTML = this.convertedBooks.map(book => this.renderBookGridCard(book, true)).join('');
        }
    }

    renderUploadedBooks() {
        const grid = document.getElementById('uploaded-grid');
        const empty = document.getElementById('uploaded-empty');

        if (this.uploadedBooks.length === 0) {
            grid.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        grid.style.display = '';
        empty.style.display = 'none';

        if (this.layout === 'list') {
            grid.className = 'books-grid list-layout';
            grid.innerHTML = this.renderListHeader() +
                this.uploadedBooks.map(book => this.renderBookListItem(book, false)).join('');
        } else {
            grid.className = 'books-grid';
            grid.innerHTML = this.uploadedBooks.map(book => this.renderBookGridCard(book, false)).join('');
        }
    }

    renderBookGridCard(book, isConverted) {
        const percent = isConverted ? this.getProgressPercent(book) : 0;
        const coverError = `this.parentElement.innerHTML='<div class="cover-placeholder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></div>'`;

        const href = isConverted ? `reader.html?book=${book.id}` : '#';
        const duration = isConverted && book.totalDuration ? this.formatDuration(book.totalDuration) : '';

        return `
            <a href="${href}" class="book-card" ${!isConverted ? 'onclick="event.preventDefault()"' : ''}>
                <div class="cover-container">
                    ${book.cover
                        ? `<img src="${book.cover}" alt="${this.escapeHtml(book.title)}" class="cover" onerror="${coverError}">`
                        : `<div class="cover-placeholder">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
                                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                            </svg>
                        </div>`
                    }
                    ${duration ? `<span class="duration-badge">${duration}</span>` : ''}
                    ${percent > 0 ? `
                        <div class="progress-overlay">
                            <div class="progress-fill" style="width: ${percent}%"></div>
                        </div>
                    ` : ''}
                </div>
                <div class="book-info">
                    <div class="book-title">${this.escapeHtml(book.title)}</div>
                    ${book.author ? `<div class="book-author">${this.escapeHtml(book.author)}</div>` : ''}
                    ${isConverted && book.chapterCount ? `<div class="book-chapters">${book.chapterCount} chapters</div>` : ''}
                    ${!isConverted ? '<div class="book-status pending">Pending conversion</div>' : ''}
                </div>
            </a>
        `;
    }

    renderListHeader() {
        return `
            <div class="list-header">
                <span>Name</span>
                <span>Author</span>
                <span>Added</span>
            </div>
        `;
    }

    renderBookListItem(book, isConverted) {
        const href = isConverted ? `reader.html?book=${book.id}` : '#';
        const coverError = `this.parentElement.innerHTML='<div class="cover-placeholder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="20" height="20"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></div>'`;
        const dateStr = book.addedDate ? this.formatDate(book.addedDate) : '';

        return `
            <a href="${href}" class="book-card" ${!isConverted ? 'onclick="event.preventDefault()"' : ''}>
                <div class="cover-container">
                    ${book.cover
                        ? `<img src="${book.cover}" alt="${this.escapeHtml(book.title)}" class="cover" onerror="${coverError}">`
                        : `<div class="cover-placeholder">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="20" height="20">
                                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                            </svg>
                        </div>`
                    }
                </div>
                <div class="book-info">
                    <div class="book-title">${this.escapeHtml(book.title)}</div>
                    <div class="book-author">${this.escapeHtml(book.author || '')}</div>
                    <div class="book-date">${dateStr}</div>
                </div>
            </a>
        `;
    }

    renderAllNotes() {
        const list = document.getElementById('notes-list');
        const empty = document.getElementById('notes-empty');

        // Combine highlights and notes, sort by date (newest first)
        const allItems = [
            ...this.highlights.map(h => ({ ...h, type: 'highlight' })),
            ...this.notes.map(n => ({ ...n, type: 'note' }))
        ].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

        if (allItems.length === 0) {
            list.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        list.style.display = '';
        empty.style.display = 'none';

        list.innerHTML = allItems.map(item => {
            const book = this.findBookById(item.bookId);
            const bookTitle = book ? book.title : 'Unknown Book';
            const chapterTitle = this.getChapterTitle(book, item.chapter);
            const highlightText = item.type === 'highlight' ? item.text : item.selectedText;
            const noteText = item.type === 'note' ? item.note : '';
            const color = item.color || 'yellow';
            const date = new Date(item.createdAt).toLocaleDateString();

            return `
                <div class="note-card" data-color="${color}" data-book-id="${item.bookId}" data-chapter="${item.chapter}">
                    <div class="note-book-title">${this.escapeHtml(bookTitle)}</div>
                    <div class="note-highlight">${this.escapeHtml(highlightText)}</div>
                    ${noteText ? `<div class="note-user-text">${this.escapeHtml(noteText)}</div>` : ''}
                    <div class="note-chapter-ref">
                        <strong>${chapterTitle}</strong>
                    </div>
                    <div class="note-date">${date}</div>
                </div>
            `;
        }).join('');

        // Click to open book at that chapter
        list.querySelectorAll('.note-card').forEach(card => {
            card.addEventListener('click', () => {
                const bookId = card.dataset.bookId;
                const book = this.findBookById(bookId);
                if (book) {
                    window.location.href = `reader.html?book=${bookId}`;
                }
            });
        });
    }

    findBookById(bookId) {
        return this.convertedBooks.find(b => b.id === bookId) ||
               CONVERTED_BOOKS.find(b => b.id === bookId);
    }

    getChapterTitle(book, chapterIndex) {
        if (!book || chapterIndex === undefined) return '';

        // Try to get from loaded chapters data
        if (book.chapters && book.chapters[chapterIndex]) {
            const ch = book.chapters[chapterIndex];
            const title = ch.title || `Chapter ${chapterIndex + 1}`;
            return `Chapter ${chapterIndex + 1}: ${title}`;
        }

        return `Chapter ${chapterIndex + 1}`;
    }

    // ==================== EVENT BINDING ====================

    bindEvents() {
        // Sidebar section toggles
        document.querySelectorAll('.nav-section-toggle').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const section = toggle.closest('.nav-section');
                section.classList.toggle('open');
            });
        });

        // Sidebar sub-item navigation
        document.querySelectorAll('.nav-sub-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.nav-sub-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                this.currentView = item.dataset.view;
                this.renderCurrentView();

                // Close mobile sidebar
                document.querySelector('.sidebar').classList.remove('open');
                document.getElementById('sidebar-overlay').classList.remove('active');
            });
        });

        // View layout toggles
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view-toggle').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.layout = btn.dataset.layout;
                this.renderCurrentView();
            });
        });

        // Search
        document.getElementById('search-btn').addEventListener('click', () => {
            const bar = document.getElementById('search-bar');
            bar.style.display = bar.style.display === 'none' ? 'flex' : 'none';
            if (bar.style.display === 'flex') {
                document.getElementById('search-input').focus();
            }
        });

        document.getElementById('search-close').addEventListener('click', () => {
            document.getElementById('search-bar').style.display = 'none';
            document.getElementById('search-input').value = '';
            this.renderCurrentView();
        });

        document.getElementById('search-input').addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        // Sort
        document.getElementById('sort-converted').addEventListener('change', (e) => {
            this.sortBooks(e.target.value);
        });

        // Settings panel
        document.getElementById('settings-btn').addEventListener('click', () => {
            document.getElementById('settings-panel').classList.add('open');
        });

        document.getElementById('close-settings').addEventListener('click', () => {
            document.getElementById('settings-panel').classList.remove('open');
        });

        // Theme buttons
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setTheme(btn.dataset.theme);
            });
        });

        // Mobile sidebar
        document.getElementById('sidebar-toggle').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('open');
            document.getElementById('sidebar-overlay').classList.toggle('active');
        });

        document.getElementById('sidebar-overlay').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.remove('open');
            document.getElementById('sidebar-overlay').classList.remove('active');
        });

        // Export notes
        const exportBtn = document.getElementById('export-all-notes');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportAllNotes());
        }

        // Close settings on outside click
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('settings-panel');
            if (panel.classList.contains('open') &&
                !e.target.closest('.settings-panel-content') &&
                !e.target.closest('#settings-btn')) {
                panel.classList.remove('open');
            }
        });
    }

    // ==================== SEARCH ====================

    handleSearch(query) {
        query = query.toLowerCase().trim();
        if (!query) {
            this.renderCurrentView();
            return;
        }

        if (this.currentView === 'converted' || this.currentView === 'uploaded') {
            const books = this.currentView === 'converted' ? this.convertedBooks : this.uploadedBooks;
            const filtered = books.filter(b =>
                b.title.toLowerCase().includes(query) ||
                (b.author && b.author.toLowerCase().includes(query))
            );

            const gridId = this.currentView === 'converted' ? 'converted-grid' : 'uploaded-grid';
            const grid = document.getElementById(gridId);
            const isConverted = this.currentView === 'converted';

            if (filtered.length === 0) {
                grid.innerHTML = '<div class="empty-state"><h3>No results</h3></div>';
            } else if (this.layout === 'list') {
                grid.className = 'books-grid list-layout';
                grid.innerHTML = this.renderListHeader() +
                    filtered.map(b => this.renderBookListItem(b, isConverted)).join('');
            } else {
                grid.className = 'books-grid';
                grid.innerHTML = filtered.map(b => this.renderBookGridCard(b, isConverted)).join('');
            }
        } else if (this.currentView === 'all-notes') {
            const allItems = [
                ...this.highlights.map(h => ({ ...h, type: 'highlight' })),
                ...this.notes.map(n => ({ ...n, type: 'note' }))
            ];

            const filtered = allItems.filter(item => {
                const text = item.type === 'highlight' ? item.text : item.selectedText;
                const noteText = item.type === 'note' ? item.note : '';
                const book = this.findBookById(item.bookId);
                const bookTitle = book ? book.title : '';
                return text.toLowerCase().includes(query) ||
                       noteText.toLowerCase().includes(query) ||
                       bookTitle.toLowerCase().includes(query);
            });

            const list = document.getElementById('notes-list');
            if (filtered.length === 0) {
                list.innerHTML = '<div class="empty-state"><h3>No results</h3></div>';
            } else {
                list.innerHTML = filtered.map(item => {
                    const book = this.findBookById(item.bookId);
                    const bookTitle = book ? book.title : 'Unknown Book';
                    const chapterTitle = this.getChapterTitle(book, item.chapter);
                    const highlightText = item.type === 'highlight' ? item.text : item.selectedText;
                    const noteText = item.type === 'note' ? item.note : '';
                    const color = item.color || 'yellow';
                    const date = new Date(item.createdAt).toLocaleDateString();

                    return `
                        <div class="note-card" data-color="${color}">
                            <div class="note-book-title">${this.escapeHtml(bookTitle)}</div>
                            <div class="note-highlight">${this.escapeHtml(highlightText)}</div>
                            ${noteText ? `<div class="note-user-text">${this.escapeHtml(noteText)}</div>` : ''}
                            <div class="note-chapter-ref"><strong>${chapterTitle}</strong></div>
                            <div class="note-date">${date}</div>
                        </div>
                    `;
                }).join('');
            }
        }
    }

    // ==================== SORTING ====================

    sortBooks(sortKey) {
        const [field, direction] = sortKey.split('-');

        this.convertedBooks.sort((a, b) => {
            let valA, valB;
            if (field === 'name') {
                valA = a.title.toLowerCase();
                valB = b.title.toLowerCase();
            } else {
                valA = a.addedDate || '';
                valB = b.addedDate || '';
            }

            if (valA < valB) return direction === 'asc' ? -1 : 1;
            if (valA > valB) return direction === 'asc' ? 1 : -1;
            return 0;
        });

        this.renderConvertedBooks();
    }

    // ==================== EXPORT ====================

    exportAllNotes() {
        const allItems = [
            ...this.highlights.map(h => ({ ...h, type: 'highlight' })),
            ...this.notes.map(n => ({ ...n, type: 'note' }))
        ].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

        if (allItems.length === 0) {
            this.showToast('No notes to export');
            return;
        }

        let content = '# Scriptum - All Highlights & Notes\n';
        content += `Exported: ${new Date().toLocaleDateString()}\n\n`;

        // Group by book
        const grouped = {};
        allItems.forEach(item => {
            const book = this.findBookById(item.bookId);
            const bookTitle = book ? book.title : 'Unknown Book';
            if (!grouped[bookTitle]) grouped[bookTitle] = [];
            grouped[bookTitle].push(item);
        });

        Object.entries(grouped).forEach(([bookTitle, items]) => {
            content += `## ${bookTitle}\n\n`;
            items.forEach((item, i) => {
                const text = item.type === 'highlight' ? item.text : item.selectedText;
                const chapterTitle = this.getChapterTitle(
                    this.findBookById(item.bookId), item.chapter
                );
                content += `${i + 1}. "${text}"\n`;
                if (item.type === 'note' && item.note) {
                    content += `   Note: ${item.note}\n`;
                }
                content += `   - ${chapterTitle}\n\n`;
            });
        });

        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'scriptum_notes_export.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.showToast('Notes exported');
    }

    // ==================== THEME ====================

    setTheme(theme) {
        document.body.dataset.theme = theme === 'dark' ? '' : theme;
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

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hours > 0) return `${hours}h ${mins}m`;
        return `${mins}m`;
    }

    formatDate(dateStr) {
        const date = new Date(dateStr);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[date.getMonth()]} ${date.getDate()}`;
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
    window.scriptum = new ScriptumLibrary();
});
