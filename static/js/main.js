(function () {
  var root = document.documentElement;
  var toggle = document.getElementById('themeToggle');
  var meta = document.getElementById('theme-color-meta');

  function applyIcons(theme) {
    if (!toggle) return;
    var sun = toggle.querySelector('.icon-sun');
    var moon = toggle.querySelector('.icon-moon');
    if (!sun || !moon) return;
    sun.classList.toggle('d-none', theme !== 'dark');
    moon.classList.toggle('d-none', theme === 'dark');
  }

  function setTheme(theme) {
    root.setAttribute('data-bs-theme', theme);
    applyIcons(theme);
    try { localStorage.setItem('ml-theme', theme); } catch (e) {}
    if (meta) { meta.setAttribute('content', theme === 'dark' ? '#121212' : '#111111'); }
  }

  applyIcons(root.getAttribute('data-bs-theme') || 'light');

  if (toggle) {
    toggle.addEventListener('click', function () {
      var current = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      setTheme(current);
    });
  }

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