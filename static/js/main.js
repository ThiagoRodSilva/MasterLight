(function () {
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || !form.hasAttribute('data-loading')) return;
    var btn = form.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.classList.add('btn-loading');
    btn.setAttribute('aria-busy', 'true');
  });
})();

/* ============================================================
   Scroll Reveal Observer
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  document.documentElement.classList.add('js');

  var revealObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  document.querySelectorAll('.reveal').forEach(function (el) {
    revealObserver.observe(el);
  });

  /* ============================================================
     Navbar scroll effect
     ============================================================ */
  var navbar = document.querySelector('.navbar-brand-custom');
  if (navbar) {
    window.addEventListener('scroll', function () {
      if (window.pageYOffset > 100) {
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    }, { passive: true });
  }
});