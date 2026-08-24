/**
 * MasterLight - Main JavaScript
 * Consolidated vanilla JS modules (no external dependencies except Bootstrap Icons CSS)
 */

// ============================================================
// Utilities
// ============================================================

const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];

function showToast(message, type = 'info') {
  const container = document.querySelector('.toast-container');
  if (!container) return;

  const bgColors = {
    success: 'bg-green-500',
    danger: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500',
  };

  const icons = {
    success: 'bi-check2-circle',
    danger: 'bi-x-circle',
    warning: 'bi-exclamation-triangle',
    info: 'bi-info-circle',
  };

  const toast = document.createElement('div');
  toast.className = `flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg ${bgColors[type] || bgColors.info} text-white min-w-[300px] max-w-md animate-slide-in`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <i class="bi ${icons[type] || icons.info} text-xl flex-shrink-0"></i>
    <div class="flex-1 text-sm">${message}</div>
    <button type="button" class="text-white/70 hover:text-white toast-close" aria-label="Fechar">
      <i class="bi bi-x-lg"></i>
    </button>
  `;

  container.appendChild(toast);

  toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());
  setTimeout(() => toast.remove(), 5000);
}

// ============================================================
// Loading State (forms com data-loading)
// ============================================================

function initLoadingState() {
  document.addEventListener('submit', function(e) {
    const form = e.target;
    if (!form || !form.hasAttribute('data-loading')) return;
    const btn = form.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.classList.add('opacity-75', 'cursor-not-allowed');
    btn.setAttribute('aria-busy', 'true');
  });
}

// ============================================================
// Scroll Reveal (.reveal)
// ============================================================

function initRevealObserver() {
  document.documentElement.classList.add('js');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('opacity-100', 'translate-y-0');
        entry.target.classList.remove('opacity-0', 'translate-y-8');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  $$('.reveal').forEach((el) => {
    el.classList.add('opacity-0', 'translate-y-8', 'transition-all', 'duration-600', 'ease-out');
    observer.observe(el);
  });
}

// ============================================================
// Navbar Scroll Effect
// ============================================================

function initNavbarScrollEffect() {
  const navbar = $('.navbar-custom');
  if (!navbar) return;

  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 100) navbar.classList.add('scrolled');
    else navbar.classList.remove('scrolled');
  }, { passive: true });
}

// ============================================================
// Gallery Thumbs (product detail)
// ============================================================

function initGallery() {
  const coverImg = $('#cover-img');
  if (!coverImg) return;

  $$('.gallery-thumb__item').forEach((thumb) => {
    thumb.addEventListener('click', () => {
      coverImg.src = thumb.dataset.galleryImg;
      coverImg.alt = thumb.dataset.galleryAlt || coverImg.alt;
      $$('.gallery-thumb__item').forEach((t) => t.classList.remove('ring-2', 'ring-brand-500'));
      thumb.classList.add('ring-2', 'ring-brand-500');
    });
  });
}

// ============================================================
// Copy to Clipboard
// ============================================================

function initCopyToClipboard() {
  $$('[data-copy-target]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = $(btn.dataset.copyTarget);
      if (!target) return;
      target.select();
      navigator.clipboard?.writeText(target.value).then(() => {
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check-lg"></i>';
        btn.classList.add('bg-green-500', 'text-white', 'border-green-500');
        btn.classList.remove('border-dark-500', 'text-dark-500');
        setTimeout(() => {
          btn.innerHTML = original;
          btn.classList.remove('bg-green-500', 'text-white', 'border-green-500');
          btn.classList.add('border-dark-500', 'text-dark-500');
        }, 2000);
      });
    });
  });

  // Legacy affiliate copy button
  const copyBtn = $('#copy-btn');
  const refLink = $('#ref-link');
  if (copyBtn && refLink) {
    copyBtn.addEventListener('click', () => {
      refLink.select();
      navigator.clipboard?.writeText(refLink.value).then(() => {
        const original = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
        copyBtn.classList.add('bg-green-500', 'text-white', 'border-green-500');
        copyBtn.classList.remove('border-dark-500', 'text-dark-500');
        setTimeout(() => {
          copyBtn.innerHTML = original;
          copyBtn.classList.remove('bg-green-500', 'text-white', 'border-green-500');
          copyBtn.classList.add('border-dark-500', 'text-dark-500');
        }, 2000);
      });
    });
  }
}

// ============================================================
// Paylink Form AJAX
// ============================================================

function initPaylinkForm() {
  const form = $('#paylink-form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const btn = form.querySelector('button');
    if (!btn) return;
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Gerando...';

    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]')?.value;
    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: new FormData(form),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.url) window.open(data.url, '_blank', 'noopener');
        else showToast(data.error || 'Falha ao gerar o link de pagamento.', 'danger');
      })
      .catch(() => showToast('Falha ao gerar o link de pagamento.', 'danger'))
      .finally(() => {
        btn.disabled = false;
        btn.innerHTML = original;
      });
  });
}

// ============================================================
// Confirmation Modal (<dialog>)
// ============================================================

function initConfirmationModal() {
  const modal = $('#confirm-modal');
  if (!modal) return;

  // Open modal
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-confirm-modal]');
    if (!trigger) return;
    e.preventDefault();

    modal.dataset.confirmAction = trigger.dataset.confirmAction || trigger.href;
    modal.dataset.confirmMethod = trigger.dataset.confirmMethod || 'POST';
    const csrf = $('[name=csrfmiddlewaretoken]')?.value;
    modal.dataset.csrfToken = csrf;

    modal.showModal();
  });

  // Close modal
  $$('.modal-close', modal).forEach((btn) => {
    btn.addEventListener('click', () => modal.close());
  });

  // Backdrop click to close
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.close();
  });

  // Escape key to close
  modal.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') modal.close();
  });

  // Submit confirmation
  modal.addEventListener('click', (e) => {
    const confirmBtn = e.target.closest('[data-confirm-submit]');
    if (!confirmBtn) return;

    const actionUrl = modal.dataset.confirmAction;
    const method = modal.dataset.confirmMethod;
    const csrf = modal.dataset.csrfToken;
    if (!actionUrl) return;

    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Confirmando...';

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', csrf);

    fetch(actionUrl, {
      method: method,
      headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      body: formData,
    })
      .then((r) => {
        if (r.ok || r.redirected) window.location.reload();
        else return r.json().then((d) => { throw new Error(d.error || 'Falha ao confirmar ação'); });
      })
      .catch((err) => {
        showToast(err.message, 'danger');
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Confirmar';
      });
  });

  // Update message from data-confirm-message
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-confirm-message]');
    if (trigger) {
      const msg = trigger.dataset.confirmMessage;
      const el = $('#confirm-modal-message');
      if (el && msg) el.innerHTML = msg;
    }
  });
}

// ============================================================
// Dropdown (details/summary) - Keyboard Navigation
// ============================================================

function initDropdowns() {
  $$('details.dropdown').forEach((dropdown) => {
    const summary = dropdown.querySelector('summary');
    const menu = dropdown.querySelector('[role="menu"]');

    if (!summary || !menu) return;

    // Keyboard navigation
    summary.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        dropdown.toggleAttribute('open');
      }
    });

    menu.addEventListener('keydown', (e) => {
      const items = [...menu.querySelectorAll('[role="menuitem"]')];
      const index = items.indexOf(document.activeElement);

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = items[(index + 1) % items.length];
        next?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = items[(index - 1 + items.length) % items.length];
        prev?.focus();
      } else if (e.key === 'Escape') {
        dropdown.removeAttribute('open');
        summary.focus();
      }
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!dropdown.contains(e.target)) dropdown.removeAttribute('open');
    });
  });
}

// ============================================================
// Mobile Navbar (details/summary)
// ============================================================

function initMobileNavbar() {
  const mobileMenu = $('#mobile-nav');
  if (!mobileMenu) return;

  const summary = mobileMenu.querySelector('summary');
  if (!summary) return;

  summary.addEventListener('click', (e) => {
    e.stopPropagation();
  });

  document.addEventListener('click', (e) => {
    if (!mobileMenu.contains(e.target)) mobileMenu.removeAttribute('open');
  });

  mobileMenu.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      mobileMenu.removeAttribute('open');
      summary.focus();
    }
  });
}

// ============================================================
// Initialize All
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  initLoadingState();
  initRevealObserver();
  initNavbarScrollEffect();
  initGallery();
  initCopyToClipboard();
  initPaylinkForm();
  initConfirmationModal();
  initDropdowns();
  initMobileNavbar();
});

// Export for testing
window.MasterLight = {
  showToast,
};