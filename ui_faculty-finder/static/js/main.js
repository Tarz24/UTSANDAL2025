// ===== UI FACULTY FINDER MAIN JAVASCRIPT =====

// Variabel global (jika diperlukan di scope global)
// Sebaiknya dibungkus dalam objek atau IIFE untuk menghindari polusi global scope
const UIFacultyFinder = {
    searchTimeout: null,
    currentPage: 1,
    currentQuery: '',
    currentFilters: {},
    searchHistory: [],
    isGridView: false, // Default ke list view

    // DOM Elements (ambil di dalam fungsi yang relevan atau initializeApp)
    // searchForm: null, /* document.getElementById('searchForm') */
    // ...dan seterusnya

    initializeApp: function() {
        // this.searchForm = document.getElementById('searchForm'); // Contoh pengambilan elemen
        this.initializeEventListeners();
        this.loadSearchHistory(); // Muat riwayat pencarian
        this.initializeViewPreference(); // Muat preferensi tampilan (list/grid)
        
        // Panggil fungsi inisialisasi spesifik halaman jika ada
        if (document.body.classList.contains('page-index') && typeof this.initializeIndexPage === 'function') {
            this.initializeIndexPage();
        }
        if (document.body.classList.contains('page-search') && typeof this.initializeSearchPage === 'function') {
            this.initializeSearchPage();
        }
        if (document.body.classList.contains('page-faculty-detail') && typeof this.initializeFacultyDetailPage === 'function') {
            this.initializeFacultyDetailPage();
        }
        
        this.initializeTooltipsAndPopovers();
        console.log("UI Faculty Finder Initialized");
    },

    initializeEventListeners: function() {
        const self = this; // Simpan referensi 'this'

        // Search form submission (jika ada form utama di banyak halaman)
        const mainSearchForm = document.querySelector('form[action*="search"]'); // Selector lebih umum
        if (mainSearchForm) {
            mainSearchForm.addEventListener('submit', function(e) {
                const searchInput = this.querySelector('input[name="q"]');
                if (searchInput && searchInput.value.trim()) {
                    self.addToSearchHistory(searchInput.value.trim());
                }
                // Tidak perlu preventDefault jika ingin form submit biasa ke halaman search
            });
        }
        
        // Quick tag clicks (jika ada di banyak halaman)
        document.addEventListener('click', function(e) {
            if (e.target.matches('.quick-tags .badge, .search-suggestions .btn-sm')) { // Selector lebih spesifik
                e.preventDefault();
                const query = e.target.textContent.trim();
                // Arahkan ke halaman search dengan query
                window.location.href = e.target.href || `/search?q=${encodeURIComponent(query)}`;
            }
        });
    },

    // Fungsi untuk inisialisasi halaman index
    initializeIndexPage: function() {
        const searchInput = document.getElementById('mainSearch');
        const suggestionsContainer = document.getElementById('searchSuggestions');
        if (searchInput && suggestionsContainer) {
            this.initializeSearchSuggestions(searchInput, suggestionsContainer, 'selectSuggestionHomepage');
        }
    },

    // Fungsi untuk inisialisasi halaman search
    initializeSearchPage: function() {
        const searchInput = document.getElementById('searchInput'); // ID di halaman search
        // const suggestionsContainer = ... // Jika ada suggestions di halaman search
        // if (searchInput && suggestionsContainer) {
        //     this.initializeSearchSuggestions(searchInput, suggestionsContainer, 'selectSuggestionSearchPage');
        // }
        
        this.initializeViewToggle();
        this.initializeFilterAutoSubmit();
        this.initializeSearchHighlighting();
    },
    
    // Fungsi untuk inisialisasi halaman detail fakultas
    initializeFacultyDetailPage: function() {
        this.initializeCardAnimations(); // Animasi card saat scroll
        // Event listener untuk tombol share, print, dll sudah inline di HTML atau bisa dipindah ke sini
    },


    initializeSearchSuggestions: function(inputElement, containerElement, selectCallbackName) {
        const self = this;
        if (!inputElement || !containerElement) return;

        let suggestionTimeout;
        inputElement.addEventListener('input', function() {
            clearTimeout(suggestionTimeout);
            const query = this.value.trim();

            if (query.length < 2) {
                containerElement.innerHTML = '';
                containerElement.style.display = 'none';
                return;
            }

            suggestionTimeout = setTimeout(() => {
                fetch(`/api/suggestions?q=${encodeURIComponent(query)}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok for suggestions.');
                        return response.json();
                    })
                    .then(data => {
                        if (data.suggestions && data.suggestions.length > 0) {
                            const html = data.suggestions
                                .map(suggestion =>
                                    `<div class="suggestion-item" 
                                          onclick="${selectCallbackName}('${self.escapeHtml(suggestion)}')"
                                          role="button" 
                                          tabindex="0">
                                        ${self.escapeHtml(suggestion)}
                                     </div>`
                                )
                                .join('');
                            containerElement.innerHTML = html;
                            containerElement.style.display = 'block';
                        } else {
                            containerElement.innerHTML = '';
                            containerElement.style.display = 'none';
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching suggestions:', error);
                        containerElement.innerHTML = '';
                        containerElement.style.display = 'none';
                    });
            }, 350); // Delay sedikit lebih lama
        });

        // Hide suggestions when clicking outside
        document.addEventListener('click', function(e) {
            if (!inputElement.contains(e.target) && !containerElement.contains(e.target)) {
                containerElement.innerHTML = '';
                containerElement.style.display = 'none';
            }
        });
    },
    
    // Definisikan fungsi callback selectSuggestion di scope global agar bisa dipanggil dari HTML
    // atau panggil method dari UIFacultyFinder
    selectSuggestion: function(suggestion, inputElementId, formElement) {
        const searchInput = document.getElementById(inputElementId);
        const suggestionsContainer = searchInput ? searchInput.parentNode.querySelector('.suggestions-container') : null;
        
        if (searchInput) {
            searchInput.value = suggestion;
        }
        if (suggestionsContainer) {
            suggestionsContainer.innerHTML = '';
            suggestionsContainer.style.display = 'none';
        }
        if (formElement) { // Jika formElement adalah string ID
           const form = document.getElementById(formElement) || searchInput.closest('form');
           if(form) form.submit();
        } else if (searchInput) { // Fallback ke closest form
            searchInput.closest('form').submit();
        }
    },


    loadSearchHistory: function() {
        try {
            const history = localStorage.getItem('facultySearchHistory');
            if (history) {
                this.searchHistory = JSON.parse(history);
            }
        } catch (error) {
            console.error('Failed to load search history:', error);
            this.searchHistory = [];
        }
    },

    addToSearchHistory: function(query) {
        if (!query || this.searchHistory.includes(query)) return;
        this.searchHistory.unshift(query);
        if (this.searchHistory.length > 10) { // Simpan 10 item terakhir
            this.searchHistory = this.searchHistory.slice(0, 10);
        }
        try {
            localStorage.setItem('facultySearchHistory', JSON.stringify(this.searchHistory));
        } catch (error) {
            console.error('Failed to save search history:', error);
        }
    },
    
    initializeViewPreference: function() {
        // Cek jika ada preferensi di localStorage atau dari server (misal via data attribute di body)
        const storedView = localStorage.getItem('searchViewGrid');
        if (storedView !== null) {
            this.isGridView = JSON.parse(storedView);
        }
        // Terapkan class awal ke body atau container hasil pencarian
        const searchResultsDiv = document.getElementById('searchResults');
        if (searchResultsDiv) {
            if (this.isGridView) {
                searchResultsDiv.classList.add('grid-view');
                searchResultsDiv.classList.remove('list-view');
                if(document.getElementById('gridView')) document.getElementById('gridView').checked = true;
            } else {
                searchResultsDiv.classList.add('list-view');
                searchResultsDiv.classList.remove('grid-view');
                if(document.getElementById('listView')) document.getElementById('listView').checked = true;
            }
        }
    },

    initializeViewToggle: function() {
        const self = this;
        const listViewBtn = document.getElementById('listView');
        const gridViewBtn = document.getElementById('gridView');
        const searchResultsDiv = document.getElementById('searchResults');

        function setView(isGrid) {
            self.isGridView = isGrid;
            if (searchResultsDiv) {
                searchResultsDiv.classList.toggle('grid-view', isGrid);
                searchResultsDiv.classList.toggle('list-view', !isGrid);
            }
            try { // Simpan preferensi ke localStorage
                localStorage.setItem('searchViewGrid', JSON.stringify(isGrid));
            } catch (e) { console.error("Error saving view preference to localStorage", e); }
            
            // Jika ingin simpan ke server juga (contoh dari search.html)
            // fetch("{{ url_for('set_search_view') }}", { ... });
        }

        if (listViewBtn) {
            listViewBtn.addEventListener('change', function() { if (this.checked) setView(false); });
        }
        if (gridViewBtn) {
            gridViewBtn.addEventListener('change', function() { if (this.checked) setView(true); });
        }
    },

    initializeFilterAutoSubmit: function() {
        const filterSelects = document.querySelectorAll('form.search-form select[name="type"], form.search-form select[name="sort"]');
        filterSelects.forEach(select => {
            select.addEventListener('change', function() {
                this.closest('form').submit();
            });
        });
    },

    initializeSearchHighlighting: function() {
        // Ambil query dari URL atau data attribute jika ada
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');
        const searchResultsDiv = document.getElementById('searchResults');

        if (query && searchResultsDiv) {
            const terms = query.toLowerCase().split(' ').filter(term => term.length > 1);
            if (terms.length > 0) {
                const regex = new RegExp('(' + terms.map(term => this.escapeRegex(term)).join('|') + ')', 'gi');
                const textNodesToHighlight = searchResultsDiv.querySelectorAll('.card-title a, .card-text, .programs-preview .badge, .breadcrumb-preview small');
                
                textNodesToHighlight.forEach(node => {
                    this._walkAndHighlightTextNodes(node, regex);
                });
            }
        }
    },
    
    _walkAndHighlightTextNodes: function(node, regex) { // Helper internal
        if (node.nodeType === Node.TEXT_NODE) {
            const parent = node.parentNode;
            // Hindari highlighting di dalam <mark> atau script/style tags
            if (parent && parent.tagName && parent.tagName.toLowerCase() === 'mark') return;
            if (parent && parent.tagName && (parent.tagName.toLowerCase() === 'script' || parent.tagName.toLowerCase() === 'style')) return;

            const text = node.nodeValue;
            const newHtml = text.replace(regex, '<mark class="bg-warning p-0">$1</mark>');
            if (newHtml !== text) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newHtml;
                const newNodes = Array.from(tempDiv.childNodes);
                newNodes.forEach(newNode => parent.insertBefore(newNode, node));
                parent.removeChild(node);
            }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            // Jangan masuk ke dalam tag tertentu seperti script, style, atau mark
            if (node.tagName.toLowerCase() === 'script' || node.tagName.toLowerCase() === 'style' || node.tagName.toLowerCase() === 'mark') {
                return;
            }
            for (let i = 0; i < node.childNodes.length; i++) {
                this._walkAndHighlightTextNodes(node.childNodes[i], regex);
            }
        }
    },

    initializeCardAnimations: function() {
        const animatedCards = document.querySelectorAll('.faculty-detail-card, .similar-card, .stats-card, .faculty-card, .feature-card, .process-step-card');
        if (animatedCards.length > 0 && 'IntersectionObserver' in window) {
            const observerOptions = {
                root: null,
                rootMargin: '0px 0px -50px 0px',
                threshold: 0.1
            };
            const observer = new IntersectionObserver((entries, obs) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-in'); // Gunakan class dari style.css
                        obs.unobserve(entry.target);
                    }
                });
            }, observerOptions);
            animatedCards.forEach(card => observer.observe(card));
        } else {
            animatedCards.forEach(card => card.classList.add('animate-in')); // Fallback
        }
    },

    initializeTooltipsAndPopovers: function() {
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
            const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
            popoverTriggerList.map(function (popoverTriggerEl) {
                return new bootstrap.Popover(popoverTriggerEl);
            });
        }
    },
    
    // Utility functions
    escapeHtml: function(text) {
        if (text === null || typeof text === 'undefined') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    escapeRegex: function(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
};

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    UIFacultyFinder.initializeApp();
});

// Expose selectSuggestion globally if needed by inline HTML onclick,
// atau modifikasi HTML untuk memanggil UIFacultyFinder.selectSuggestion(...)
function selectSuggestionHomepage(suggestion) {
    UIFacultyFinder.selectSuggestion(suggestion, 'mainSearch');
}
function selectSuggestionSearchPage(suggestion) { // Jika ada ID berbeda di halaman search
    UIFacultyFinder.selectSuggestion(suggestion, 'searchInput');
}

// Fungsi global dari faculty.html (share, print, notification) bisa dipindahkan ke UIFacultyFinder
// atau dibiarkan global jika hanya spesifik untuk halaman tersebut.
// Untuk notifikasi, bisa dibuat method di UIFacultyFinder.
UIFacultyFinder.showNotification = function(message, type = 'info', duration = 3500) {
    const alertsContainer = document.querySelector('.alerts-container'); // Pastikan ada di base.html
    if (!alertsContainer) {
        console.warn("Alerts container not found for notification.");
        // Fallback ke alert standar jika container tidak ada
        alert(`${type.toUpperCase()}: ${message}`);
        return;
    }
    
    const alertId = `alert-${Date.now()}`; // ID unik untuk alert
    const alertDiv = document.createElement('div');
    alertDiv.id = alertId;
    alertDiv.className = `alert alert-${type} alert-dismissible fade show shadow-sm`;
    alertDiv.setAttribute('role', 'alert');
    
    alertDiv.innerHTML = `
        ${this.escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertsContainer.appendChild(alertDiv);
    
    const bsAlert = new bootstrap.Alert(alertDiv); // Inisialisasi Bootstrap alert
    
    setTimeout(() => {
        // Cek lagi apakah alert masih ada sebelum close
        const currentAlert = document.getElementById(alertId);
        if(currentAlert) {
            bsAlert.close();
        }
    }, duration);
}

// Pindahkan fungsi global dari faculty.html ke sini jika ingin lebih terstruktur
function shareURL() {
    if (navigator.share) {
        navigator.share({
            title: document.title,
            text: document.querySelector('meta[name="description"]')?.content || `Info dari ${document.title}`,
            url: window.location.href
        }).catch(err => {
            console.warn('Native share failed, falling back:', err);
            fallbackShare();
        });
    } else {
        fallbackShare();
    }
}

function fallbackShare() {
    const url = window.location.href;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(() => {
            UIFacultyFinder.showNotification('URL berhasil disalin ke clipboard!', 'success');
        }).catch((err) => {
            console.warn('Clipboard write failed, prompting user:', err);
            promptCopyURL(url);
        });
    } else {
        promptCopyURL(url);
    }
}

function promptCopyURL(url) {
    let modalElement = document.getElementById('shareModal');
    if (!modalElement) {
        modalElement = document.createElement('div');
        modalElement.innerHTML = `
            <div class="modal fade" id="shareModal" tabindex="-1" aria-labelledby="shareModalLabel" aria-hidden="true">
              <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                  <div class="modal-header">
                    <h5 class="modal-title" id="shareModalLabel">Salin URL</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                  </div>
                  <div class="modal-body">
                    <p>Salin tautan di bawah ini untuk dibagikan:</p>
                    <input type="text" class="form-control" value="${url}" readonly id="shareUrlInputModal">
                  </div>
                  <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Tutup</button>
                    <button type="button" class="btn btn-primary" onclick="copyShareUrlInputModal()">Salin</button>
                  </div>
                </div>
              </div>
            </div>
        `;
        document.body.appendChild(modalElement);
    }
    const shareModalInput = document.getElementById('shareUrlInputModal');
    if(shareModalInput) shareModalInput.value = url; // Update URL setiap kali modal muncul
    
    const shareModalInstance = new bootstrap.Modal(document.getElementById('shareModal'));
    shareModalInstance.show();
}

function copyShareUrlInputModal(){ // Fungsi khusus untuk tombol salin di modal
    const input = document.getElementById('shareUrlInputModal');
    input.select();
    input.setSelectionRange(0, 99999);
    try {
        document.execCommand('copy');
        UIFacultyFinder.showNotification('URL berhasil disalin!', 'success');
        const modalInstance = bootstrap.Modal.getInstance(document.getElementById('shareModal'));
        if(modalInstance) modalInstance.hide();
    } catch (err) {
        UIFacultyFinder.showNotification('Gagal menyalin. Salin secara manual.', 'danger');
    }
}


function exportPDF() {
    UIFacultyFinder.showNotification('Fitur export PDF belum tersedia. Gunakan fungsi Cetak (Print) dari browser Anda dan pilih "Save as PDF".', 'info', 7000);
}


// Akhir dari UIFacultyFinder Object