// ===== UI FACULTY FINDER MAIN JAVASCRIPT =====

// Global variables
let searchTimeout;
let currentPage = 1;
let totalResults = 0;
let currentQuery = '';
let currentFilters = {};
let searchHistory = [];
let isGridView = false;

// DOM Elements
const searchForm = document.getElementById('searchForm');
const searchInput = document.getElementById('searchQuery');
const searchResults = document.getElementById('searchResults');
const loadingSpinner = document.getElementById('loadingSpinner');
const searchStats = document.getElementById('searchStats');
const suggestionsContainer = document.getElementById('suggestions');
const filterForm = document.getElementById('filterForm');
const viewToggle = document.getElementById('viewToggle');
const paginationContainer = document.getElementById('pagination');

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// App initialization
function initializeApp() {
    initializeEventListeners();
    initializeSearchSuggestions();
    initializeQuickTags();
    initializeFilters();
    loadSearchHistory();
    initializeAnimations();
    
    // Load initial data if on search page
    if (window.location.pathname.includes('search')) {
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');
        if (query) {
            searchInput.value = query;
            performSearch(query);
        }
    }
}

// Event Listeners
function initializeEventListeners() {
    // Search form submission
    if (searchForm) {
        searchForm.addEventListener('submit', handleSearchSubmit);
    }
    
    // Real-time search input
    if (searchInput) {
        searchInput.addEventListener('input', handleSearchInput);
        searchInput.addEventListener('focus', showSuggestions);
        searchInput.addEventListener('blur', hideSuggestions);
    }
    
    // Filter form changes
    if (filterForm) {
        filterForm.addEventListener('change', handleFilterChange);
    }
    
    // View toggle
    if (viewToggle) {
        viewToggle.addEventListener('click', toggleView);
    }
    
    // Quick tag clicks
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('quick-tag')) {
            e.preventDefault();
            const query = e.target.textContent.trim();
            searchInput.value = query;
            performSearch(query);
        }
    });
    
    // Suggestion clicks
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('suggestion-item')) {
            const query = e.target.textContent.trim();
            searchInput.value = query;
            performSearch(query);
            hideSuggestions();
        }
    });
    
    // Faculty card hover effects
    document.addEventListener('mouseenter', function(e) {
        if (e.target.classList.contains('faculty-card')) {
            addHoverEffect(e.target);
        }
    }, true);
    
    document.addEventListener('mouseleave', function(e) {
        if (e.target.classList.contains('faculty-card')) {
            removeHoverEffect(e.target);
        }
    }, true);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// Search handling
function handleSearchSubmit(e) {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (query) {
        performSearch(query);
        addToSearchHistory(query);
    }
}

function handleSearchInput(e) {
    const query = e.target.value.trim();
    
    // Clear previous timeout
    clearTimeout(searchTimeout);
    
    // Show suggestions after delay
    searchTimeout = setTimeout(() => {
        if (query.length >= 2) {
            showSearchSuggestions(query);
        } else {
            hideSuggestions();
        }
    }, 300);
}

function performSearch(query, page = 1, filters = {}) {
    currentQuery = query;
    currentPage = page;
    currentFilters = filters;
    
    showLoadingState();
    
    // Build search parameters
    const params = new URLSearchParams({
        q: query,
        page: page,
        ...filters
    });
    
    // Make API request
    fetch(`/api/search?${params}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
            updateSearchStats(data);
            updatePagination(data);
            updateURL(query, page, filters);
        })
        .catch(error => {
            console.error('Search error:', error);
            showErrorMessage('Terjadi kesalahan saat mencari. Silakan coba lagi.');
        })
        .finally(() => {
            hideLoadingState();
        });
}

// Search suggestions
function initializeSearchSuggestions() {
    // Load common search terms
    fetch('/api/suggestions/common')
        .then(response => response.json())
        .then(data => {
            window.commonSuggestions = data.suggestions || [];
        })
        .catch(error => console.error('Failed to load suggestions:', error));
}

function showSearchSuggestions(query) {
    if (!suggestionsContainer) return;
    
    // Get suggestions from various sources
    const suggestions = getSuggestions(query);
    
    if (suggestions.length === 0) {
        hideSuggestions();
        return;
    }
    
    // Create suggestions HTML
    const suggestionsHTML = suggestions.map(suggestion => 
        `<div class="suggestion-item">${escapeHtml(suggestion)}</div>`
    ).join('');
    
    suggestionsContainer.innerHTML = suggestionsHTML;
    suggestionsContainer.style.display = 'block';
}

function getSuggestions(query) {
    const suggestions = [];
    const lowerQuery = query.toLowerCase();
    
    // Add from common suggestions
    if (window.commonSuggestions) {
        window.commonSuggestions.forEach(suggestion => {
            if (suggestion.toLowerCase().includes(lowerQuery)) {
                suggestions.push(suggestion);
            }
        });
    }
    
    // Add from search history
    searchHistory.forEach(historyItem => {
        if (historyItem.toLowerCase().includes(lowerQuery) && 
            !suggestions.includes(historyItem)) {
            suggestions.push(historyItem);
        }
    });
    
    // Limit to 5 suggestions
    return suggestions.slice(0, 5);
}

function showSuggestions() {
    if (suggestionsContainer && searchInput.value.trim().length >= 2) {
        suggestionsContainer.style.display = 'block';
    }
}

function hideSuggestions() {
    setTimeout(() => {
        if (suggestionsContainer) {
            suggestionsContainer.style.display = 'none';
        }
    }, 200);
}

// Results display
function displaySearchResults(data) {
    if (!searchResults) return;
    
    const results = data.results || [];
    
    if (results.length === 0) {
        showNoResults();
        return;
    }
    
    // Set view class
    searchResults.className = `search-results ${isGridView ? 'grid-view' : 'list-view'}`;
    
    // Generate results HTML
    const resultsHTML = results.map(faculty => createFacultyCard(faculty)).join('');
    searchResults.innerHTML = resultsHTML;
    
    // Add animations
    animateResults();
}

function createFacultyCard(faculty) {
    const programs = faculty.programs ? faculty.programs.slice(0, 3) : [];
    const programBadges = programs.map(program => 
        `<span class="badge bg-secondary me-1 mb-1">${escapeHtml(program)}</span>`
    ).join('');
    
    const morePrograms = faculty.programs && faculty.programs.length > 3 ? 
        ` <span class="badge bg-light text-dark">+${faculty.programs.length - 3} lainnya</span>` : '';
    
    return `
        <div class="result-item card mb-3 fade-in-up">
            <div class="card-body">
                <div class="row">
                    <div class="col-md-8">
                        <h5 class="card-title">
                            <a href="/faculty/${faculty.id}" class="text-decoration-none">
                                ${escapeHtml(faculty.name)}
                            </a>
                        </h5>
                        <p class="text-muted mb-2">
                            <i class="fas fa-university me-1"></i>
                            ${escapeHtml(faculty.department)}
                        </p>
                        ${faculty.research_areas ? `
                            <p class="card-text">
                                <small class="text-muted">
                                    <i class="fas fa-microscope me-1"></i>
                                    ${escapeHtml(faculty.research_areas.slice(0, 100))}...
                                </small>
                            </p>
                        ` : ''}
                        <div class="programs-preview">
                            ${programBadges}${morePrograms}
                        </div>
                    </div>
                    <div class="col-md-4 text-md-end">
                        <div class="result-score mb-2">
                            <span class="badge bg-primary">
                                <i class="fas fa-star me-1"></i>
                                ${Math.round(faculty.score * 100)}% match
                            </span>
                        </div>
                        <div class="result-meta">
                            ${faculty.email ? `
                                <div class="mb-1">
                                    <small class="text-muted">
                                        <i class="fas fa-envelope me-1"></i>
                                        ${escapeHtml(faculty.email)}
                                    </small>
                                </div>
                            ` : ''}
                            ${faculty.phone ? `
                                <div class="mb-1">
                                    <small class="text-muted">
                                        <i class="fas fa-phone me-1"></i>
                                        ${escapeHtml(faculty.phone)}
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function showNoResults() {
    if (!searchResults) return;
    
    searchResults.innerHTML = `
        <div class="no-results text-center">
            <i class="fas fa-search fa-3x mb-3"></i>
            <h4>Tidak ada hasil ditemukan</h4>
            <p class="text-muted">Coba gunakan kata kunci yang berbeda atau periksa ejaan Anda.</p>
            <div class="search-tips mt-4">
                <h6>Tips pencarian:</h6>
                <ul class="list-unstyled">
                    <li><i class="fas fa-check text-success me-1"></i> Gunakan kata kunci yang lebih umum</li>
                    <li><i class="fas fa-check text-success me-1"></i> Periksa ejaan kata kunci</li>
                    <li><i class="fas fa-check text-success me-1"></i> Coba kombinasi kata yang berbeda</li>
                    <li><i class="fas fa-info text-info me-1"></i> Gunakan filter untuk mempersempit pencarian</li>
                </ul>
            </div>
        </div>
    `;
}

// Filters handling
function initializeFilters() {
    // Load filter options
    loadFilterOptions();
}

function loadFilterOptions() {
    // Load departments
    fetch('/api/departments')
        .then(response => response.json())
        .then(data => {
            populateFilterSelect('departmentFilter', data.departments);
        })
        .catch(error => console.error('Failed to load departments:', error));
    
    // Load programs
    fetch('/api/programs')
        .then(response => response.json())
        .then(data => {
            populateFilterSelect('programFilter', data.programs);
        })
        .catch(error => console.error('Failed to load programs:', error));
}

function populateFilterSelect(selectId, options) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // Clear existing options (except first one)
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Add new options
    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option;
        optionElement.textContent = option;
        select.appendChild(optionElement);
    });
}

function handleFilterChange() {
    if (!currentQuery) return;
    
    // Collect current filter values
    const filters = {};
    const filterInputs = filterForm.querySelectorAll('select, input');
    
    filterInputs.forEach(input => {
        if (input.value && input.value !== '') {
            filters[input.name] = input.value;
        }
    });
    
    // Perform filtered search
    performSearch(currentQuery, 1, filters);
}

// View toggle
function toggleView() {
    isGridView = !isGridView;
    
    // Update button state
    const gridBtn = viewToggle.querySelector('.btn:first-child');
    const listBtn = viewToggle.querySelector('.btn:last-child');
    
    if (isGridView) {
        gridBtn.classList.add('active');
        listBtn.classList.remove('active');
    } else {
        gridBtn.classList.remove('active');
        listBtn.classList.add('active');
    }
    
    // Update results display
    if (searchResults) {
        searchResults.className = `search-results ${isGridView ? 'grid-view' : 'list-view'}`;
    }
}

// Pagination
function updatePagination(data) {
    if (!paginationContainer) return;
    
    const totalPages = Math.ceil(data.total / data.per_page);
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    let paginationHTML = '<nav><ul class="pagination justify-content-center">';
    
    // Previous button
    if (currentPage > 1) {
        paginationHTML += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="goToPage(${currentPage - 1})">
                    <i class="fas fa-chevron-left"></i> Sebelumnya
                </a>
            </li>
        `;
    }
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === currentPage ? 'active' : '';
        paginationHTML += `
            <li class="page-item ${activeClass}">
                <a class="page-link" href="#" onclick="goToPage(${i})">${i}</a>
            </li>
        `;
    }
    
    // Next button
    if (currentPage < totalPages) {
        paginationHTML += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="goToPage(${currentPage + 1})">
                    Selanjutnya <i class="fas fa-chevron-right"></i>
                </a>
            </li>
        `;
    }
    
    paginationHTML += '</ul></nav>';
    paginationContainer.innerHTML = paginationHTML;
}

function goToPage(page) {
    if (currentQuery) {
        performSearch(currentQuery, page, currentFilters);
    }
}

// Search stats
function updateSearchStats(data) {
    if (!searchStats) return;
    
    const total = data.total || 0;
    const resultsText = total === 1 ? 'hasil' : 'hasil';
    const timeText = data.search_time ? ` dalam ${data.search_time}ms` : '';
    
    searchStats.innerHTML = `
        <div class="text-end">
            <h4 class="text-white mb-1">${total.toLocaleString()}</h4>
            <small class="text-white-50">${resultsText} ditemukan${timeText}</small>
        </div>
    `;
}

// Quick tags
function initializeQuickTags() {
    const quickTags = document.querySelectorAll('.quick-tag');
    quickTags.forEach(tag => {
        tag.addEventListener('click', function(e) {
            e.preventDefault();
            const query = this.textContent.trim();
            if (searchInput) {
                searchInput.value = query;
                performSearch(query);
            }
        });
    });
}

// Search history
function loadSearchHistory() {
    try {
        const history = localStorage.getItem('facultySearchHistory');
        if (history) {
            searchHistory = JSON.parse(history);
        }
    } catch (error) {
        console.error('Failed to load search history:', error);
        searchHistory = [];
    }
}

function addToSearchHistory(query) {
    if (!query || searchHistory.includes(query)) return;
    
    searchHistory.unshift(query);
    
    // Keep only last 10 searches
    if (searchHistory.length > 10) {
        searchHistory = searchHistory.slice(0, 10);
    }
    
    // Save to localStorage
    try {
        localStorage.setItem('facultySearchHistory', JSON.stringify(searchHistory));
    } catch (error) {
        console.error('Failed to save search history:', error);
    }
}

// Loading states
function showLoadingState() {
    if (loadingSpinner) {
        loadingSpinner.style.display = 'block';
    }
    
    if (searchResults) {
        searchResults.classList.add('loading');
    }
}

function hideLoadingState() {
    if (loadingSpinner) {
        loadingSpinner.style.display = 'none';
    }
    
    if (searchResults) {
        searchResults.classList.remove('loading');
    }
}

// Animations
function initializeAnimations() {
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            once: true
        });
    }
}

function animateResults() {
    const resultItems = document.querySelectorAll('.result-item');
    resultItems.forEach((item, index) => {
        setTimeout(() => {
            item.classList.add('fade-in-up');
        }, index * 100);
    });
}

function addHoverEffect(element) {
    element.style.transform = 'translateY(-5px)';
}

function removeHoverEffect(element) {
    element.style.transform = 'translateY(0)';
}

// Keyboard shortcuts
function handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to clear search
    if (e.key === 'Escape') {
        if (document.activeElement === searchInput) {
            searchInput.blur();
            hideSuggestions();
        }
    }
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateURL(query, page, filters) {
    const params = new URLSearchParams();
    params.set('q', query);
    
    if (page > 1) {
        params.set('page', page);
    }
    
    Object.keys(filters).forEach(key => {
        if (filters[key]) {
            params.set(key, filters[key]);
        }
    });
    
    const newURL = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newURL);
}

function showErrorMessage(message) {
    if (searchResults) {
        searchResults.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${escapeHtml(message)}
            </div>
        `;
    }
}

// Export functions for global access
window.goToPage = goToPage;
window.performSearch = performSearch;

// Initialize tooltips and popovers if Bootstrap is available
document.addEventListener('DOMContentLoaded', function() {
    if (typeof bootstrap !== 'undefined') {
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        // Initialize popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
});