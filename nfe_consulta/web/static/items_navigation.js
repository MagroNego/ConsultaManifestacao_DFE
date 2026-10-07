(() => {
  const key = 'nfe-items-return';
  const current = () => window.location.pathname + window.location.search;
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-items-open]').forEach((link) => {
      link.addEventListener('click', () => {
        try {
          sessionStorage.setItem(key, JSON.stringify({ url: current(), y: window.scrollY }));
        } catch (_) { /* A navegação funciona mesmo sem armazenamento. */ }
      });
    });
    try {
      const state = JSON.parse(sessionStorage.getItem(key) || 'null');
      if (state && state.url === current() && Number.isFinite(state.y)) {
        sessionStorage.removeItem(key);
        requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, Math.max(0, state.y))));
      }
    } catch (_) { /* Estado ausente ou inválido não impede a página. */ }
  });
})();
