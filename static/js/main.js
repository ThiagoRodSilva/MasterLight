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