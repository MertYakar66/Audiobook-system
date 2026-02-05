/**
 * Read-Along Library
 * 
 * Displays available books with progress tracking.
 * Books are registered in the BOOKS_CATALOG.
 */

// Book catalog - add books here as they are processed
const BOOKS_CATALOG = [
    {
        id: "the-intelligent-investor",
        path: "../output/readalong/The-Intelligent-Investor",
        title: "The Intelligent Investor",
        author: "Benjamin Graham",
        cover: "../output/readalong/The-Intelligent-Investor/cover.jpg",
        totalDuration: 79196, // seconds
        chapterCount: 22
    }
];

class Library {
    constructor() {
        this.books = [];
        this.progress = {};

        this.init();
    }

    async init() {
        // Load saved progress
        this.loadProgress();

        // Load book data
        await this.loadBooks();

        // Render UI
        this.renderContinueReading();
        this.renderLibrary();

        // Bind events
        this.bindEvents();

        // Load theme
        this.loadTheme();
    }

    async loadBooks() {
        for (const catalog of BOOKS_CATALOG) {
            try {
                // Try to fetch manifest for dynamic data
                const response = await fetch(`${catalog.path}/manifest.json`);
                if (response.ok) {
                    const manifest = await response.json();
                    this.books.push({
                        ...catalog,
                        title: manifest.title || catalog.title,
                        author: manifest.author || catalog.author,
                        totalDuration: manifest.totalDuration || catalog.totalDuration,
                        chapterCount: manifest.chapterCount || catalog.chapterCount,
                        chapters: manifest.chapters || []
                    });
                } else {
                    // Use catalog data if manifest not found
                    this.books.push(catalog);
                }
            } catch (e) {
                console.warn(`Could not load manifest for ${catalog.id}`, e);
                this.books.push(catalog);
            }
        }

        document.getElementById('book-count').textContent =
            `${this.books.length} book${this.books.length !== 1 ? 's' : ''}`;
    }

    loadProgress() {
        try {
            // Load all progress from localStorage
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.startsWith('readalong-progress-')) {
                    const bookId = key.replace('readalong-progress-', '');
                    this.progress[bookId] = JSON.parse(localStorage.getItem(key));
                }
            }
        } catch (e) {
            console.warn('Could not load progress', e);
        }
    }

    getBookProgress(bookId) {
        return this.progress[bookId] || null;
    }

    getProgressPercent(book) {
        const progress = this.getBookProgress(book.id);
        if (!progress) return 0;

        // Calculate based on chapter and position
        const chapterDuration = book.totalDuration / (book.chapterCount || 1);
        const totalListened = (progress.chapter * chapterDuration) + progress.position;
        return Math.min(100, (totalListened / book.totalDuration) * 100);
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    }

    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    renderContinueReading() {
        const container = document.getElementById('continue-reading');
        const section = document.getElementById('continue-section');

        // Get books with progress
        const booksWithProgress = this.books.filter(book => this.getBookProgress(book.id));

        if (booksWithProgress.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';

        container.innerHTML = booksWithProgress.map(book => {
            const progress = this.getBookProgress(book.id);
            const percent = this.getProgressPercent(book);
            const chapterNum = progress.chapter + 1;
            const chapterTitle = book.chapters?.[progress.chapter]?.title || `Chapter ${chapterNum}`;

            return `
                <a href="reader.html?book=${book.id}" class="continue-card">
                    <img src="${book.cover}" alt="${book.title}" class="cover" 
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 300%22><rect fill=%22%23007bff%22 width=%22200%22 height=%22300%22/><text x=%22100%22 y=%22150%22 text-anchor=%22middle%22 font-size=%2240%22 fill=%22white%22>📖</text></svg>'">
                    <div class="info">
                        <h3 class="title">${book.title}</h3>
                        <p class="author">${book.author}</p>
                        <div class="progress-info">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${percent}%"></div>
                            </div>
                            <span class="progress-text">${Math.round(percent)}% completed</span>
                            <div class="chapter-info">📍 ${chapterTitle} • ${this.formatTime(progress.position)}</div>
                        </div>
                        <button class="continue-btn">
                            ▶ Continue Reading
                        </button>
                    </div>
                </a>
            `;
        }).join('');
    }

    renderLibrary() {
        const container = document.getElementById('library-grid');
        const emptyState = document.getElementById('empty-state');

        if (this.books.length === 0) {
            container.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        container.style.display = 'grid';
        emptyState.style.display = 'none';

        container.innerHTML = this.books.map(book => {
            const percent = this.getProgressPercent(book);

            return `
                <a href="reader.html?book=${book.id}" class="book-card">
                    <div class="cover-container">
                        <img src="${book.cover}" alt="${book.title}" class="cover"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 300%22><rect fill=%22%23007bff%22 width=%22200%22 height=%22300%22/><text x=%22100%22 y=%22150%22 text-anchor=%22middle%22 font-size=%2240%22 fill=%22white%22>📖</text></svg>'">
                        <span class="duration-badge">${this.formatDuration(book.totalDuration)}</span>
                        ${percent > 0 ? `
                            <div class="progress-overlay">
                                <div class="fill" style="width: ${percent}%"></div>
                            </div>
                        ` : ''}
                    </div>
                    <div class="book-info">
                        <h3 class="book-title">${book.title}</h3>
                        <p class="book-author">${book.author}</p>
                        <p class="book-chapters">${book.chapterCount} chapters</p>
                    </div>
                </a>
            `;
        }).join('');
    }

    bindEvents() {
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

        // Nav tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                if (tab.dataset.tab === 'continue') {
                    document.getElementById('continue-section').style.display = 'block';
                    document.getElementById('library-section').style.display = 'none';
                } else {
                    document.getElementById('continue-section').style.display =
                        this.books.some(b => this.getBookProgress(b.id)) ? 'block' : 'none';
                    document.getElementById('library-section').style.display = 'block';
                }
            });
        });

        // Close panel on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.settings-panel') && !e.target.closest('#settings-btn')) {
                document.getElementById('settings-panel').classList.remove('open');
            }
        });
    }

    setTheme(theme) {
        document.body.dataset.theme = theme;
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
        localStorage.setItem('readalong-theme', theme);
    }

    loadTheme() {
        const theme = localStorage.getItem('readalong-theme') || 'light';
        this.setTheme(theme);
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
    window.library = new Library();
});
