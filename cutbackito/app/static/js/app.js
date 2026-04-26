async function postJSON(url, body) {
  const opts = { method: "POST" };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  const text = await r.text();
  try {
    return { ok: r.ok, data: JSON.parse(text) };
  } catch {
    return { ok: r.ok, data: text };
  }
}

function show(target, payload) {
  const el = document.getElementById(target);
  if (!el) return;
  el.textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  const project = btn.dataset.project;
  const map = {
    sync: { url: `/projects/${project}/sync`, target: "sync-output" },
    transcribe: { url: `/projects/${project}/transcribe`, target: "transcribe-output" },
    highlights: { url: `/projects/${project}/highlights`, target: "highlights-output" },
  };
  const cfg = map[action];
  if (!cfg) return;

  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Procesando…";
  show(cfg.target, "(corriendo, puede tardar varios minutos para transcribir)");
  const fd = new FormData();
  if (action === "highlights") {
    fd.append("top_k", "5");
    fd.append("seconds", "30");
  }
  const { ok, data } = await postJSON(cfg.url, action === "highlights" ? fd : null);
  show(cfg.target, ok ? data : `Error: ${JSON.stringify(data)}`);
  btn.disabled = false;
  btn.textContent = original;
});

document.addEventListener("submit", async (ev) => {
  const form = ev.target;
  if (form.id !== "chat-form") return;
  ev.preventDefault();
  const project = form.dataset.project;
  const fd = new FormData(form);
  show("chat-output", "Pensando con Claude…");
  const { ok, data } = await postJSON(`/projects/${project}/chat`, fd);
  show("chat-output", ok ? data : `Error: ${JSON.stringify(data)}`);
  if (ok) setTimeout(() => location.reload(), 800);
});
