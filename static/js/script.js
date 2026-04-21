/**
 * SecureLifeAI - Main JavaScript Module
 * Handles interactive features across the platform
 */

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FLASH MESSAGE AUTO-DISMISS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

document.addEventListener('DOMContentLoaded', function() {
    const flashMessage = document.getElementById('flash');
    if (flashMessage) {
        setTimeout(() => {
            flashMessage.style.animation = 'slideDown 0.3s ease-out reverse';
            setTimeout(() => flashMessage.remove(), 300);
        }, 3000);
    }
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MOBILE SIDEBAR TOGGLE
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const hamburger = document.getElementById('hamburger');
if (hamburger) {
    hamburger.addEventListener('click', () => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('open');
        }
    });

    // Close sidebar when clicking outside
    document.addEventListener('click', (e) => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && hamburger && !sidebar.contains(e.target) && !hamburger.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// BMI CALCULATOR
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function calculateBMI() {
    const heightInput = document.getElementById('height');
    const weightInput = document.getElementById('weight');
    const bmiDisplay = document.getElementById('bmi_display');

    if (!heightInput || !weightInput || !bmiDisplay) return;

    function update() {
        const height = parseFloat(heightInput.value);
        const weight = parseFloat(weightInput.value);

        if (height > 0 && weight > 0) {
            const bmi = weight / ((height / 100) ** 2);
            const bmiValue = bmi.toFixed(2);
            bmiDisplay.value = bmiValue;

            // Color coding
            let borderColor = '#3b82f6'; // blue
            if (bmi >= 18.5 && bmi < 25) {
                borderColor = '#10b981'; // green
            } else if (bmi >= 25 && bmi < 30) {
                borderColor = '#f59e0b'; // amber
            } else if (bmi >= 30) {
                borderColor = '#ef4444'; // red
            }

            bmiDisplay.style.borderColor = borderColor;
        }
    }

    heightInput.addEventListener('input', update);
    weightInput.addEventListener('input', update);
    update(); // Initial calculation
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MULTI-STEP FORM NAVIGATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function showSection(n) {
    // Hide all sections
    for (let i = 1; i <= 5; i++) {
        const section = document.getElementById(`section-${i}`);
        if (section) {
            section.style.display = i === n ? 'block' : 'none';
        }
    }

    // Update progress circles
    const circles = document.querySelectorAll('.step-circle');
    circles.forEach((circle, idx) => {
        const step = idx + 1;
        circle.classList.remove('active', 'completed');
        if (step === n) {
            circle.classList.add('active');
        } else if (step < n) {
            circle.classList.add('completed');
        }
    });

    window.scrollTo(0, 0);
}

function nextSection(n) {
    if (validateSection(n - 1)) {
        showSection(n);
    }
}

function prevSection(n) {
    showSection(n);
}

function validateSection(n) {
    // `nextSection(2)` calls `validateSection(1)`; validate the *current* section.
    const section = document.getElementById(`section-${n}`);
    if (!section) return true;

    const inputs = section.querySelectorAll('[required]');
    let valid = true;

    inputs.forEach(input => {
        if (!input.value || input.value.trim() === '') {
            valid = false;
            input.classList.add('invalid');
            const errorText = input.parentElement.querySelector('.error-text');
            if (errorText) {
                errorText.style.display = 'block';
            }
        } else {
            input.classList.remove('invalid');
            const errorText = input.parentElement.querySelector('.error-text');
            if (errorText) {
                errorText.style.display = 'none';
            }
        }
    });

    return valid;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// COVERAGE SLIDER SYNC
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initCoverageSlider() {
    const slider = document.getElementById('coverage_amount');
    const numberInput = document.getElementById('coverage_number');

    if (!slider || !numberInput) return;

    slider.addEventListener('input', function() {
        numberInput.value = this.value;
        updateSliderBackground(this);
    });

    numberInput.addEventListener('input', function() {
        if (parseInt(this.value) >= parseInt(slider.min) && parseInt(this.value) <= parseInt(slider.max)) {
            slider.value = this.value;
        }
    });

    function updateSliderBackground(sliderElement) {
        const val = (sliderElement.value - sliderElement.min) / (sliderElement.max - sliderElement.min) * 100;
        sliderElement.style.background = `linear-gradient(to right, #2563eb 0%, #2563eb ${val}%, #e5e7eb ${val}%, #e5e7eb 100%)`;
    }

    updateSliderBackground(slider);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// LIVE COVERAGE LIMITS API
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function updateLimits() {
    const typeRadios = document.querySelectorAll('input[name="insurance_type"]');
    const coverageSlider = document.getElementById('coverage_amount');
    const limitsBox = document.getElementById('limitsBox');

    if (!typeRadios.length || !coverageSlider || !limitsBox) return;

    const type = document.querySelector('input[name="insurance_type"]:checked')?.value || 'life';
    const amount = parseInt(coverageSlider.value);

    try {
        const response = await fetch(`/api/limits?type=${type}`);
        if (!response.ok) throw new Error('Failed to fetch limits');

        const data = await response.json();

        limitsBox.style.display = 'block';
        document.getElementById('minLimit').textContent = `₹${data.min_coverage.toLocaleString('en-IN')}`;
        document.getElementById('maxLimit').textContent = `₹${data.max_coverage.toLocaleString('en-IN')}`;

        const statusEl = document.getElementById('limitsStatus');
        if (amount >= data.min_coverage && amount <= data.max_coverage) {
            statusEl.textContent = '✓ Amount is within your eligible range';
            statusEl.style.color = '#10b981';
            coverageSlider.style.borderColor = '#10b981';
        } else if (amount < data.min_coverage) {
            statusEl.textContent = `⚠ Amount is below minimum (₹${data.min_coverage.toLocaleString('en-IN')})`;
            statusEl.style.color = '#f59e0b';
            coverageSlider.style.borderColor = '#ef4444';
        } else {
            statusEl.textContent = `⚠ Amount exceeds maximum (₹${data.max_coverage.toLocaleString('en-IN')})`;
            statusEl.style.color = '#f59e0b';
            coverageSlider.style.borderColor = '#ef4444';
        }
    } catch (error) {
        console.error('Error updating limits:', error);
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// INSURANCE TYPE CHANGE
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initInsuranceTypeListeners() {
    const radioButtons = document.querySelectorAll('input[name="insurance_type"]');
    radioButtons.forEach(radio => {
        radio.addEventListener('change', () => {
            updateLimits();
        });
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TABLE SORTING (HISTORY PAGE)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initTableSorting() {
    const table = document.getElementById('historyTable');
    if (!table) return;

    let sortState = {};

    const headers = table.querySelectorAll('th');
    headers.forEach((header, columnIndex) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            const isAscending = !sortState[columnIndex] || !sortState[columnIndex].ascending;

            rows.sort((a, b) => {
                let aValue = a.querySelectorAll('td')[columnIndex].textContent.trim();
                let bValue = b.querySelectorAll('td')[columnIndex].textContent.trim();

                // Parse numbers
                if (!isNaN(aValue.replace(/[₹,]/g, ''))) {
                    aValue = parseFloat(aValue.replace(/[₹,]/g, ''));
                    bValue = parseFloat(bValue.replace(/[₹,]/g, ''));
                } else if (aValue.match(/\d{4}-\d{2}-\d{2}/)) {
                    aValue = new Date(aValue);
                    bValue = new Date(bValue);
                }

                return isAscending ? 
                    (aValue > bValue ? 1 : -1) :
                    (aValue < bValue ? 1 : -1);
            });

            // Re-append sorted rows
            rows.forEach(row => tbody.appendChild(row));

            // Update sort indicators
            headers.forEach((th, idx) => {
                const arrow = th.querySelector('.sort-arrow');
                if (arrow) {
                    arrow.style.color = idx === columnIndex ? '#2563eb' : '#ddd';
                }
            });

            sortState[columnIndex] = { ascending: isAscending };
        });
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// RISK SCORE CIRCLE ANIMATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function animateRiskScoreCircle() {
    const circle = document.querySelector('.progress-ring');
    if (!circle) return;

    const riskScoreElement = document.querySelector('.risk-score-circle');
    if (!riskScoreElement) return;

    const riskScore = parseFloat(riskScoreElement.dataset.risk || 50);
    const circumference = 565;
    const offset = circumference - (riskScore / 100) * circumference;

    setTimeout(() => {
        circle.style.strokeDashoffset = offset;
        circle.style.transition = 'stroke-dashoffset 1.2s ease-in-out';
    }, 100);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CHARTS.JS INITIALIZATION (DASHBOARD)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initCharts() {
    // Risk Factor Breakdown Chart
    const riskChartCanvas = document.getElementById('riskChart');
    if (riskChartCanvas && typeof Chart !== 'undefined') {
        try {
            const ctx = riskChartCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Health', 'Financial', 'Lifestyle', 'Family', 'Vehicles'],
                    datasets: [{
                        data: [25, 20, 20, 15, 20],
                        backgroundColor: [
                            '#ef4444',
                            '#f59e0b',
                            '#eab308',
                            '#8b5cf6',
                            '#3b82f6'
                        ],
                        borderColor: '#fff',
                        borderWidth: 2,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        } catch (e) {
            console.warn('Risk chart initialization failed:', e);
        }
    }

    // Factor Contributions Chart
    const factorsChartCanvas = document.getElementById('factorsChart');
    if (factorsChartCanvas && typeof Chart !== 'undefined') {
        try {
            const ctx = factorsChartCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Age', 'BMI', 'Smoking', 'Property', 'Exercise'],
                    datasets: [{
                        label: 'Impact on Risk',
                        data: [5, -10, 20, -15, -8],
                        backgroundColor: [
                            '#3b82f6',
                            '#ef4444',
                            '#ef4444',
                            '#10b981',
                            '#10b981'
                        ],
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        } catch (e) {
            console.warn('Factors chart initialization failed:', e);
        }
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// INITIALIZATION ON DOM READY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

document.addEventListener('DOMContentLoaded', function() {
    // BMI Calculator
    calculateBMI();

    // Coverage Slider
    initCoverageSlider();

    // Insurance Type Listeners
    initInsuranceTypeListeners();

    // Update Limits on Load
    updateLimits();

    // Table Sorting
    initTableSorting();

    // Animate Risk Score
    animateRiskScoreCircle();

    // Initialize Charts
    initCharts();
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// UTILITY: FORMAT CURRENCY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function formatCurrency(num) {
    return '₹' + num.toLocaleString('en-IN');
}
