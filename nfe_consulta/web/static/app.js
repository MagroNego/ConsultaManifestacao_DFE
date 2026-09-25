(() => {
  const root = document.documentElement;
  const stored = localStorage.getItem("nfe-theme");

  if (stored === "light" || stored === "dark") {
    root.dataset.theme = stored;
  }

  const currentTheme = () => {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const updateThemeIcon = () => {
    const icon = document.querySelector("[data-theme-icon]");
    if (!icon) return;
    icon.textContent = currentTheme() === "dark" ? "☀" : "◐";
  };

  document.addEventListener("DOMContentLoaded", () => {
    updateThemeIcon();

    document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      localStorage.setItem("nfe-theme", next);
      updateThemeIcon();
    });

    const inputs = [...document.querySelectorAll("[data-file-input]")];
    const selection = document.querySelector("[data-selection]");

    const updateSelection = () => {
      if (!selection) return;
      const files = inputs.flatMap((input) => [...input.files]);
      if (!files.length) {
        selection.textContent = "Nenhum arquivo selecionado";
        return;
      }
      const txts = files.filter((file) => file.name.toLowerCase().endsWith(".txt"));
      selection.textContent = txts.length === 1
        ? "1 arquivo TXT selecionado"
        : txts.length + " arquivos TXT selecionados";
    };

    inputs.forEach((input) => input.addEventListener("change", updateSelection));

    document.querySelectorAll("[data-processing-form]").forEach((form) => {
      form.addEventListener("submit", () => {
        form.classList.add("busy");
        const button = form.querySelector('button[type="submit"]');
        if (button) {
          button.disabled = true;
          button.dataset.originalText = button.textContent;
          button.textContent = "Processando…";
        }
      });
    });
  });
})();
