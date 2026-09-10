/**
 * JanSolve — Main JavaScript Utility Script
 * Government of Jharkhand | SIH 2026
 */

document.addEventListener('DOMContentLoaded', () => {
    // ════════════════════════════════════════════
    // 1. AUTO-DISMISS FLASH ALERTS
    // ════════════════════════════════════════════
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // Close button handler
        const closeBtn = alert.querySelector('.close-alert');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateX(40px)';
                setTimeout(() => alert.remove(), 300);
            });
        }

        // Auto dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateX(40px)';
                setTimeout(() => alert.remove(), 400);
            }
        }, 5000);
    });

    // ════════════════════════════════════════════
    // 2. MOBILE SIDEBAR / NAVBAR TOGGLE
    // ════════════════════════════════════════════
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const overlay = document.querySelector('.sidebar-overlay');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            if (overlay) overlay.classList.toggle('active');
        });
    }

    if (overlay && sidebar) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // Public Navbar mobile toggle
    const mobileToggle = document.querySelector('.mobile-toggle');
    const navLinks = document.querySelector('.navbar-links');
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');
        });
    }

    // ════════════════════════════════════════════
    // 3. NAVBAR SCROLL EFFECT
    // ════════════════════════════════════════════
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 20) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }

    // ════════════════════════════════════════════
    // 4. SIMPLE CANVAS CHART HELPER
    // ════════════════════════════════════════════
    window.renderBarChart = function(canvasId, labels, data, colors) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.parentElement.clientWidth || 500;
        const height = canvas.height = 240;

        ctx.clearRect(0, 0, width, height);

        if (!data || data.length === 0) {
            ctx.fillStyle = '#94a3b8';
            ctx.font = '14px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No data available', width / 2, height / 2);
            return;
        }

        const maxVal = Math.max(...data, 1);
        const paddingLeft = 40;
        const paddingBottom = 40;
        const paddingTop = 20;
        const chartHeight = height - paddingBottom - paddingTop;
        const barWidth = Math.min(45, (width - paddingLeft - 20) / data.length - 15);
        const step = (width - paddingLeft - 20) / data.length;

        // Draw horizontal grid lines
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = paddingTop + (chartHeight * (4 - i)) / 4;
            ctx.beginPath();
            ctx.moveTo(paddingLeft, y);
            ctx.lineTo(width - 10, y);
            ctx.stroke();

            // Y-axis label
            ctx.fillStyle = '#64748b';
            ctx.font = '11px Inter, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(Math.round((maxVal * i) / 4), paddingLeft - 8, y + 4);
        }

        // Draw bars
        data.forEach((val, idx) => {
            const barH = (val / maxVal) * chartHeight;
            const x = paddingLeft + idx * step + (step - barWidth) / 2;
            const y = height - paddingBottom - barH;

            // Bar background gradient
            const color = colors && colors[idx] ? colors[idx] : '#1a237e';
            ctx.fillStyle = color;

            // Rounded top bar
            ctx.beginPath();
            const r = 4;
            ctx.moveTo(x, height - paddingBottom);
            ctx.lineTo(x, y + r);
            ctx.quadraticCurveTo(x, y, x + r, y);
            ctx.lineTo(x + barWidth - r, y);
            ctx.quadraticCurveTo(x + barWidth, y, x + barWidth, y + r);
            ctx.lineTo(x + barWidth, height - paddingBottom);
            ctx.closePath();
            ctx.fill();

            // Value text on bar
            if (barH > 18) {
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(val, x + barWidth / 2, y + 14);
            } else {
                ctx.fillStyle = '#1e293b';
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(val, x + barWidth / 2, y - 4);
            }

            // X-axis label
            ctx.fillStyle = '#475569';
            ctx.font = '10px Inter, sans-serif';
            ctx.textAlign = 'center';
            const label = labels[idx] ? (labels[idx].length > 9 ? labels[idx].substring(0, 8) + '…' : labels[idx]) : '';
            ctx.fillText(label, x + barWidth / 2, height - paddingBottom + 16);
        });
    };
});
