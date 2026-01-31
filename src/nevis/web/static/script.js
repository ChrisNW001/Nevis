// Nevis Meeting Analyzer - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh stats every 30 seconds on dashboard
    if (document.querySelector('.stats-grid')) {
        // Could add auto-refresh here if needed
    }

    // Form validation for compare
    const compareForm = document.querySelector('.meeting-select-list');
    if (compareForm) {
        const form = compareForm.closest('form');
        form.addEventListener('submit', function(e) {
            const checked = document.querySelectorAll('input[name="meeting_ids"]:checked');
            if (checked.length < 2) {
                e.preventDefault();
                alert('Please select at least 2 meetings to compare.');
            }
        });
    }

    // Highlight search terms in results
    const searchQuery = new URLSearchParams(window.location.search).get('q');
    if (searchQuery) {
        const excerpts = document.querySelectorAll('.excerpt');
        excerpts.forEach(excerpt => {
            const html = excerpt.innerHTML;
            const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
            excerpt.innerHTML = html.replace(regex, '<mark>$1</mark>');
        });
    }
});

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
