// WodSniper - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu functionality
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const navLinks = document.getElementById('navLinks');
    const mobileOverlay = document.getElementById('mobileOverlay');

    function toggleMobileMenu() {
        mobileMenuToggle.classList.toggle('active');
        navLinks.classList.toggle('active');
        mobileOverlay.classList.toggle('active');
        document.body.style.overflow = navLinks.classList.contains('active') ? 'hidden' : '';
    }

    function closeMobileMenu() {
        mobileMenuToggle.classList.remove('active');
        navLinks.classList.remove('active');
        mobileOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', toggleMobileMenu);
    }

    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', closeMobileMenu);
    }

    // Close mobile menu when clicking a link
    if (navLinks) {
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', closeMobileMenu);
        });
    }

    // Close mobile menu on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && navLinks && navLinks.classList.contains('active')) {
            closeMobileMenu();
        }
    });

    // Close mobile menu on window resize (if switching to desktop)
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768 && navLinks && navLinks.classList.contains('active')) {
            closeMobileMenu();
        }
    });

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
