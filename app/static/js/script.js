document.addEventListener('DOMContentLoaded', () => {

    // --- Navbar Scroll Effect ---
    const header = document.querySelector('.site-header');
    if (header) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });
    }

    // --- Mobile Navigation Toggle ---
    const navToggle = document.getElementById('nav-toggle');
    const mainNav = document.getElementById('main-nav');

    if (navToggle && mainNav) {
        navToggle.addEventListener('click', () => {
            document.body.classList.toggle('nav-open');
            mainNav.classList.toggle('is-active');
            const isExpanded = mainNav.classList.contains('is-active');
            navToggle.setAttribute('aria-expanded', isExpanded);
        });

        mainNav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (document.body.classList.contains('nav-open')) {
                    document.body.classList.remove('nav-open');
                    mainNav.classList.remove('is-active');
                    navToggle.setAttribute('aria-expanded', 'false');
                }
            });
        });
    }

    // --- Scroll Animation ---
    const animateElements = document.querySelectorAll('.animate-on-scroll');
    if (animateElements.length > 0 && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.15 });

        animateElements.forEach(el => observer.observe(el));
    } else {
        // Fallback for browsers without IntersectionObserver
        console.log('IntersectionObserver not supported, using fallback');
        animateElements.forEach(el => el.classList.add('visible'));
    }

    // --- Smooth Scroll for internal Anchor Links ---
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        if (anchor.getAttribute('href') !== '#') {
            anchor.addEventListener('click', function (e) {
                const hrefAttribute = this.getAttribute('href');
                if (hrefAttribute.length > 1 && hrefAttribute.startsWith('#')) {
                    const targetElement = document.querySelector(hrefAttribute);
                    if (targetElement) {
                        e.preventDefault();
                        targetElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        }
    });

    // --- Dynamic Footer Year ---
    const yearSpan = document.getElementById('current-year');
    if (yearSpan) {
        yearSpan.textContent = new Date().getFullYear();
    }

    // --- Lazy Load Images (already in home.html, keep it there or consolidate) ---
    // const lazyImages = document.querySelectorAll('img.lazy');
    // lazyImages.forEach(img => {
    //     img.setAttribute('loading', 'lazy');
    // });

    // --- FUTURE INTERACTIVITY EXAMPLE (using Fetch API) ---
    /*
    const dateInput = document.getElementById('appointment-date-input');
    if (dateInput) {
        dateInput.addEventListener('change', async (event) => {
            const selectedDate = event.target.value;
            const availabilityStatus = document.getElementById('availability-status');

            if (!selectedDate || !availabilityStatus) return;

            availabilityStatus.textContent = 'Checking...';
            availabilityStatus.style.color = 'grey';

            try {
                const response = await fetch(`/check-availability?date=${selectedDate}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();

                if (data.available) {
                    availabilityStatus.textContent = 'Date is available!';
                    availabilityStatus.style.color = 'green';
                } else {
                    availabilityStatus.textContent = 'Date is already booked.';
                    availabilityStatus.style.color = 'red';
                }
            } catch (error) {
                console.error('Error checking availability:', error);
                availabilityStatus.textContent = 'Could not check availability.';
                availabilityStatus.style.color = 'orange';
            }
        });
    }
    */

}); // End DOMContentLoaded
