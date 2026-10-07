(() => {
  const storageKey = "nfe-download-notifications-v1";
  const retention = 24 * 60 * 60 * 1000;
  let notifications = [];
  let bell, panel, count, list, toast, toastTimer;

  const validNotifications = (value) => Array.isArray(value) ? value.filter(item =>
    item && ["success", "error"].includes(item.type) && Number.isFinite(item.time) &&
    item.time <= Date.now() && item.time > Date.now() - retention
  ).slice(0, 20).map(item => ({ type: item.type, time: item.time, read: item.read === true })) : [];
  const load = () => {
    try { return validNotifications(JSON.parse(localStorage.getItem(storageKey) || "[]")); }
    catch { return []; }
  };
  const save = () => {
    try { localStorage.setItem(storageKey, JSON.stringify(notifications)); }
    catch { /* O aviso continua funcionando mesmo sem armazenamento local. */ }
  };
  const title = item => item.type === "success" ? "Processamento concluído" : "Erro na geração";

  function renderNotifications() {
    if (!list) return;
    list.replaceChildren();
    const unread = notifications.filter(item => !item.read).length;
    count.hidden = !unread;
    count.textContent = String(unread);
    bell.setAttribute("aria-label", unread ? `Notificações: ${unread} não lidas` : "Notificações");
    if (!notifications.length) {
      const empty = document.createElement("li");
      empty.className = "notification-empty";
      empty.textContent = "Nenhuma notificação recente.";
      list.appendChild(empty);
    }
    for (const item of notifications) {
      const row = document.createElement("li");
      row.className = `notification-item notification-${item.type}`;
      const message = document.createElement(item.type === "success" ? "a" : "strong");
      message.textContent = title(item);
      if (item.type === "success") message.href = panel.dataset.downloadsUrl;
      const time = document.createElement("time");
      time.dateTime = new Date(item.time).toISOString();
      time.textContent = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(item.time);
      row.append(message, time);
      list.appendChild(row);
    }
  }

  function notify(type) {
    notifications = [{ type, time: Date.now(), read: panel ? !panel.hidden : false }, ...validNotifications(notifications)].slice(0, 20);
    save();
    renderNotifications();
    if (toast) {
      clearTimeout(toastTimer);
      toast.textContent = title({ type });
      toast.dataset.type = type;
      toast.hidden = false;
      toastTimer = setTimeout(() => { toast.hidden = true; }, 6000);
    }
  }

  function setProgress(container, received, total, complete = false) {
    if (!container) return;
    container.hidden = false;
    container.dataset.state = complete ? "complete" : "receiving";
    const bar = container.querySelector("progress");
    const label = container.querySelector("[data-progress-label]");
    if (complete || total > 0) {
      const percent = complete ? 100 : Math.min(99, Math.floor(received / total * 100));
      bar.value = percent;
      label.textContent = `${percent}%`;
    } else {
      bar.removeAttribute("value");
      label.textContent = "Recebendo…";
    }
  }

  async function download(url, options = {}, { progress, expectedBytes = 0, notification = true } = {}) {
    if (progress) {
      progress.hidden = false;
      progress.dataset.state = "waiting";
      progress.querySelector("progress").value = 0;
      progress.querySelector("[data-progress-label]").textContent = "0%";
    }
    try {
      const response = await fetch(url, { credentials: "same-origin", ...options });
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
      const declared = Number(response.headers.get("Content-Length"));
      const compressed = response.headers.get("Content-Encoding");
      const total = compressed ? expectedBytes : declared > 0 ? declared : expectedBytes;
      let blob;
      if (response.body?.getReader) {
        const reader = response.body.getReader();
        const chunks = [];
        let received = 0;
        setProgress(progress, 0, total);
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            received += value.byteLength;
            setProgress(progress, received, total);
          }
        } finally { reader.releaseLock(); }
        if (!compressed && declared > 0 && received !== declared) throw new Error("O download foi interrompido. Tente novamente.");
        blob = new Blob(chunks, { type: contentType || "application/octet-stream" });
      } else {
        blob = await response.blob();
      }
      const disposition = response.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const plainName = disposition.match(/filename=(?:"([^"]+)"|([^;]+))/i);
      let filename = plainName?.[1] || plainName?.[2]?.trim() || "Relatorio.xlsx";
      if (encodedName) {
        try { filename = decodeURIComponent(encodedName[1]); } catch { /* Preserve o nome alternativo. */ }
      }
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      try {
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
      } finally {
        link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      }
      setProgress(progress, 0, 0, true);
      if (notification) notify("success");
    } catch (error) {
      if (progress) {
        progress.dataset.state = "error";
        progress.querySelector("[data-progress-label]").textContent = "Erro no download";
      }
      if (notification) notify("error");
      throw error;
    }
  }

  window.nfeDownloads = { download };
  document.addEventListener("DOMContentLoaded", () => {
    bell = document.querySelector("[data-notification-bell]");
    panel = document.querySelector("[data-notification-panel]");
    count = document.querySelector("[data-notification-count]");
    list = document.querySelector("[data-notification-list]");
    toast = document.querySelector("[data-notification-toast]");
    notifications = load();
    renderNotifications();
    function closePanel() {
      if (!panel) return;
      panel.hidden = true;
      bell.setAttribute("aria-expanded", "false");
    }
    bell?.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      bell.setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden) {
        notifications = notifications.map(item => ({ ...item, read: true }));
        save();
        renderNotifications();
      }
    });
    document.querySelector("[data-notification-clear]")?.addEventListener("click", () => {
      notifications = [];
      save();
      renderNotifications();
    });
    document.addEventListener("click", event => {
      if (panel && !panel.hidden && !panel.contains(event.target) && !bell.contains(event.target)) closePanel();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && panel && !panel.hidden) { closePanel(); bell.focus(); }
    });
    window.addEventListener("storage", event => {
      if (event.key === storageKey) { notifications = load(); renderNotifications(); }
    });
    document.querySelectorAll("[data-download-link]").forEach(link => {
      link.addEventListener("click", async event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || (event.button !== undefined && event.button !== 0)) return;
        event.preventDefault();
        if (link.dataset.busy === "true") return;
        link.dataset.busy = "true";
        link.setAttribute("aria-disabled", "true");
        const progress = link.closest("tr")?.querySelector("[data-download-progress]");
        const previousError = link.parentElement.querySelector("[data-download-error]");
        previousError?.remove();
        try {
          await download(link.href, {}, { progress, expectedBytes: Number(link.dataset.downloadSize) || 0,
            notification: !link.hasAttribute("data-archived-download") });
        } catch (error) {
          const notice = document.createElement("span");
          notice.className = "download-error";
          notice.setAttribute("data-download-error", "");
          notice.setAttribute("role", "alert");
          notice.textContent = error instanceof TypeError ? "Conexão interrompida. Tente novamente." : error.message;
          link.parentElement.appendChild(notice);
        } finally {
          delete link.dataset.busy;
          link.removeAttribute("aria-disabled");
        }
      });
    });
  });
})();
