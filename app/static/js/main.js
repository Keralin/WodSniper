// WodSniper - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.3s';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Confirm dangerous actions
    const dangerButtons = document.querySelectorAll('.btn-danger');
    dangerButtons.forEach(btn => {
        if (!btn.closest('form[onsubmit]')) {
            btn.addEventListener('click', function(e) {
                if (!confirm('Are you sure?')) {
                    e.preventDefault();
                }
            });
        }
    });

    // Format time inputs
    const timeInputs = document.querySelectorAll('input[name="time"]');
    timeInputs.forEach(input => {
        input.addEventListener('blur', function() {
            let value = this.value.replace(/[^\d:]/g, '');

            // If just numbers, add colon
            if (/^\d{3,4}$/.test(value)) {
                if (value.length === 3) {
                    value = '0' + value;
                }
                value = value.slice(0, 2) + ':' + value.slice(2);
            }

            this.value = value;
        });
    });
});

/**
 * Fetch available classes from WodBuster
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<Array>} - Array of class objects
 */
async function fetchClasses(date) {
    try {
        const response = await fetch(`/classes?date=${date}`);
        const data = await response.json();

        if (data.error) {
            console.error('Error fetching classes:', data.error);
            return [];
        }

        return data.classes;
    } catch (error) {
        console.error('Error:', error);
        return [];
    }
}
