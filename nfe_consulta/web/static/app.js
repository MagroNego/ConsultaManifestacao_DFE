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

    const formatDateInput = (input, completeYear = false) => {
      const cursor = input.selectionStart;
      const beforeCursor = input.value.slice(0, cursor ?? input.value.length).replace(/\D/g, "").length;
      const digits = input.value.replace(/\D/g, "").slice(0, 8);
      if (digits.length <= 2) {
        input.value = digits;
      } else if (digits.length <= 4) {
        input.value = digits.slice(0, 2) + "/" + digits.slice(2);
      } else {
        input.value = digits.slice(0, 2) + "/" + digits.slice(2, 4) + "/" + digits.slice(4);
      }
      if (completeYear && digits.length === 4) {
        const year = new Intl.DateTimeFormat("en", { year: "numeric", timeZone: "America/Sao_Paulo" }).format(new Date());
        input.value += "/" + year;
      } else if (document.activeElement === input && cursor !== null) {
        let position = 0;
        let count = 0;
        while (position < input.value.length && count < beforeCursor) {
          if (/\d/.test(input.value[position])) count++;
          position++;
        }
        input.setSelectionRange(position, position);
      }
    };

    document.querySelectorAll("[data-date-input]").forEach((input) => {
      input.addEventListener("input", () => formatDateInput(input));
      input.addEventListener("blur", () => formatDateInput(input, true));
      input.form?.addEventListener("submit", () => formatDateInput(input, true));
    });

    document.querySelectorAll("[data-processing-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        const download = form.hasAttribute("data-download-form");
        if (download) event.preventDefault();
        if (form.classList.contains("busy")) {
          event.preventDefault();
          return;
        }
        if (form.hasAttribute("data-sync-confirm") && !window.confirm(
          "Sincronizar com a SEFAZ agora? A atualização automática ocorre às 08:00 e 15:00. Novas tentativas ficarão bloqueadas por 60 minutos."
        )) {
          event.preventDefault();
          return;
        }
        form.classList.add("busy");
        const button = form.querySelector('button[type="submit"]');
        if (button) {
          button.disabled = true;
          button.dataset.originalText = button.textContent;
          button.textContent = "Processando…";
        }
        if (!download) return;
        const previousError = form.querySelector("[data-download-error]");
        if (previousError) previousError.remove();
        try {
          const method = (form.method || "get").toUpperCase();
          const data = new FormData(form);
          const url = new URL(form.action, window.location.href);
          const options = { method, credentials: "same-origin" };
          if (method === "GET") {
            for (const [key, value] of data) url.searchParams.append(key, value);
          } else {
            options.body = data;
          }
          const response = await fetch(url, options);
          const contentType = response.headers.get("Content-Type") || "";
          if (!response.ok || contentType.includes("text/html")) {
            let message = "Não foi possível gerar o arquivo. Tente novamente.";
            if (contentType.includes("application/json")) {
              const error = await response.json();
              if (typeof error.detail === "string") message = error.detail;
            } else if (contentType.includes("text/html")) {
              const page = new DOMParser().parseFromString(await response.text(), "text/html");
              message = page.querySelector(".alert.error")?.textContent?.trim() || message;
            }
            throw new Error(message);
          }
          const blob = await response.blob();
          const disposition = response.headers.get("Content-Disposition") || "";
          const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
          const plainName = disposition.match(/filename="([^"]+)"/i);
          const filename = encodedName ? decodeURIComponent(encodedName[1]) : plainName?.[1] || "Relatorio.xlsx";
          const objectUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = objectUrl;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
        } catch (error) {
          const notice = document.createElement("div");
          notice.className = "alert error";
          notice.setAttribute("data-download-error", "");
          notice.setAttribute("role", "alert");
          notice.textContent = error instanceof TypeError ? "Não foi possível conectar ao servidor. Tente novamente." : error.message;
          form.appendChild(notice);
        } finally {
          form.classList.remove("busy");
          if (button) {
            button.disabled = false;
            button.textContent = button.dataset.originalText;
          }
        }
      });
    });
  });
})();
