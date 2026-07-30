const state = {
  view: "overview",
  overview: null,
  sessions: [],
  pages: [],
  receipts: { sync: [], distill: [] },
};

const workspace = document.querySelector("#workspace");
const inspector = document.querySelector("#inspector-content");
const syncButton = document.querySelector("#sync-button");
const toast = document.querySelector("#toast");

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelector("#close-inspector").addEventListener("click", closeInspector);
document.querySelector("#search-form").addEventListener("submit", search);
syncButton.addEventListener("click", syncTranscripts);
window.addEventListener("hashchange", openHashTarget);

boot();

async function boot() {
  try {
    await refreshData();
    render();
    openHashTarget();
  } catch (error) {
    workspace.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

async function refreshData() {
  const [overview, sessions, pages, receipts] = await Promise.all([
    api("/api/overview"),
    api("/api/sessions"),
    api("/api/pages"),
    api("/api/receipts"),
  ]);
  state.overview = overview;
  state.sessions = sessions;
  state.pages = pages;
  state.receipts = receipts;
  const lastSync = overview.last_sync_at
    ? `Synced ${relativeTime(overview.last_sync_at)}`
    : "Local vault";
  document.querySelector("#rail-status").textContent = lastSync;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  render();
}

function render() {
  if (state.view === "sessions") renderSessions();
  else if (state.view === "knowledge") renderKnowledge();
  else if (state.view === "activity") renderActivity();
  else renderOverview();
}

function renderOverview() {
  const recent = state.sessions.slice(0, 8);
  const pending = state.sessions.filter(
    (session) => session.content_captured && !session.distilled_at,
  );
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Private work memory</p>
        <h1>Today</h1>
      </div>
      <p class="quiet">What your agents did, what is worth keeping, and where the evidence lives.</p>
    </header>
    <div class="measure-strip">
      ${measure(state.overview.session_count, "Retained sessions")}
      ${measure(state.overview.knowledge_count, "Durable Wiki pages")}
      ${measure(state.overview.pending_distill_count, "Waiting to distill")}
    </div>
    <section class="section-block">
      ${sectionHeading("Recent sessions", `${recent.length} shown`)}
      <div class="record-list">${recent.map(sessionRow).join("") || emptyRow("No sessions retained yet.")}</div>
    </section>
    <section class="section-block">
      ${sectionHeading("Waiting to distill", `${pending.length} sessions`)}
      <div class="record-list">${pending.slice(0, 6).map(sessionRow).join("") || emptyRow("Nothing waiting.")}</div>
    </section>
    <section class="section-block">
      ${sectionHeading("Knowledge areas", `${state.pages.length} pages`)}
      ${categoryGrid()}
    </section>
  `;
  bindRows();
}

function renderSessions() {
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Evidence layer</p>
        <h1>Sessions</h1>
      </div>
      <p class="quiet">Codex, Claude, manual notes, and imported local-agent records in one chronology.</p>
    </header>
    <section class="section-block">
      ${sectionHeading("All retained sessions", `${state.sessions.length} total`)}
      <div class="record-list">${state.sessions.map(sessionRow).join("") || emptyRow("No sessions retained yet.")}</div>
    </section>
  `;
  bindRows();
}

function renderKnowledge(category = null) {
  const pages = category
    ? state.pages.filter((page) => page.category === category)
    : state.pages;
  const title = category ? categoryTitle(category) : "Knowledge";
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Durable layer</p>
        <h1>${escapeHtml(title)}</h1>
      </div>
      <p class="quiet">Decisions, systems, problems, and procedures promoted from selected evidence.</p>
    </header>
    ${category ? "" : `<section class="section-block">${categoryGrid()}</section>`}
    <section class="section-block">
      ${sectionHeading(category ? `${title} pages` : "All Wiki pages", `${pages.length} total`)}
      <div class="record-list">${pages.map(pageRow).join("") || emptyRow("No durable pages yet.")}</div>
    </section>
  `;
  bindRows();
}

function renderActivity() {
  const lines = [
    ...state.receipts.sync.map((receipt) => ({ ...receipt, type: "sync" })),
    ...state.receipts.distill.map((receipt) => ({ ...receipt, type: "distill" })),
  ].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Local operations</p>
        <h1>Activity</h1>
      </div>
      <p class="quiet">Body-free receipts for synchronization and Wiki distillation.</p>
    </header>
    <section class="section-block">
      ${sectionHeading("Recent runs", `${lines.length} retained`)}
      <div>${lines.map(activityLine).join("") || emptyRow("No activity yet.")}</div>
    </section>
  `;
}

function categoryGrid() {
  const categories = ["projects", "decisions", "problems", "procedures", "systems", "unfinished", "imports"];
  return `<div class="category-grid">${categories.map((category) => {
    const count = state.pages.filter((page) => page.category === category).length;
    return `
      <div class="category">
        <button type="button" data-category="${category}">
          <strong>${escapeHtml(categoryTitle(category))}</strong>
          <span>${count} page${count === 1 ? "" : "s"}</span>
        </button>
      </div>`;
  }).join("")}</div>`;
}

function bindRows() {
  document.querySelectorAll("[data-session]").forEach((row) => {
    row.addEventListener("click", () => openSession(row.dataset.session));
  });
  document.querySelectorAll("[data-page]").forEach((row) => {
    row.addEventListener("click", () => openPage(row.dataset.page));
  });
  document.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => renderKnowledge(button.dataset.category));
  });
}

async function openSession(sessionId) {
  const detail = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  document.body.classList.add("has-inspector");
  inspector.innerHTML = `
    <p class="eyebrow">${escapeHtml(detail.session.provider)} session</p>
    <h2>${escapeHtml(detail.session.title)}</h2>
    <div class="inspector-meta">
      <span>${detail.session.event_count} events</span>
      <span>${detail.session.content_captured ? "content retained" : "metadata only"}</span>
      <span>${detail.session.distilled_at ? "distilled" : "not distilled"}</span>
    </div>
    ${detail.workspace ? `<p class="quiet">${escapeHtml(detail.workspace)}</p>` : ""}
    ${detail.session.content_captured ? distillControls(detail.session.session_id) : ""}
    <div class="events">${detail.events.map(eventBlock).join("") || `<p class="quiet">No event bodies retained.</p>`}</div>
  `;
  const distillButton = document.querySelector("#distill-button");
  if (distillButton) distillButton.addEventListener("click", distillSelected);
}

async function openPage(path) {
  const detail = await api(`/api/page?path=${encodeURIComponent(path)}`);
  document.body.classList.add("has-inspector");
  inspector.innerHTML = `
    <p class="eyebrow">${escapeHtml(categoryTitle(detail.category))}</p>
    <h2>${escapeHtml(detail.title)}</h2>
    <div class="inspector-meta">
      <span>${escapeHtml(detail.path)}</span>
      <span>${detail.backlinks.length} backlinks</span>
    </div>
    <article class="markdown">${detail.html}</article>
    ${detail.backlinks.length ? `
      <div class="section-block">
        <p class="eyebrow">Linked from</p>
        ${detail.backlinks.map(pageRow).join("")}
      </div>` : ""}
  `;
  bindRows();
  inspector.querySelectorAll("a[href^='#/wiki/']").forEach((link) => {
    link.addEventListener("click", openHashTarget);
  });
}

function closeInspector() {
  document.body.classList.remove("has-inspector");
}

async function search(event) {
  event.preventDefault();
  const query = document.querySelector("#search-input").value.trim();
  if (!query) return;
  const results = await api(`/api/search?q=${encodeURIComponent(query)}`);
  state.view = "search";
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.remove("is-active"));
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Search</p>
        <h1>${escapeHtml(query)}</h1>
      </div>
      <p class="quiet">${results.length} result${results.length === 1 ? "" : "s"} across retained evidence and durable Wiki pages.</p>
    </header>
    <div class="record-list">${results.map(searchRow).join("") || emptyRow("No matching records.")}</div>
  `;
  bindRows();
}

async function syncTranscripts() {
  syncButton.classList.add("is-busy");
  syncButton.textContent = "Syncing…";
  try {
    const receipt = await api("/api/sync", {
      method: "POST",
      headers: actionHeaders(),
      body: JSON.stringify({ include_content: true }),
    });
    await refreshData();
    render();
    showToast(`${receipt.events_added} new events retained.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    syncButton.classList.remove("is-busy");
    syncButton.textContent = "Sync transcripts";
  }
}

async function distillSelected() {
  const button = document.querySelector("#distill-button");
  const runtime = document.querySelector("#distill-runtime").value;
  const model = document.querySelector("#distill-model").value.trim() || null;
  const contentAccess = document.querySelector("#distill-access").value;
  button.classList.add("is-busy");
  button.textContent = "Distilling…";
  try {
    const receipt = await api("/api/distill", {
      method: "POST",
      headers: actionHeaders(),
      body: JSON.stringify({
        session_ids: [button.dataset.session],
        runtime,
        model,
        content_access: contentAccess,
      }),
    });
    await refreshData();
    showToast(`${receipt.changed_files.length} durable pages changed.`);
    await openSession(button.dataset.session);
  } catch (error) {
    showToast(error.message);
    button.classList.remove("is-busy");
    button.textContent = "Distill selected session";
  }
}

function openHashTarget() {
  const prefix = "#/wiki/";
  if (!window.location.hash.startsWith(prefix)) return;
  const path = decodeURIComponent(window.location.hash.slice(prefix.length));
  openPage(path);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) message = body.detail;
    } catch {
      // Keep the bounded status message.
    }
    throw new Error(message);
  }
  return response.json();
}

function actionHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Work-Almanac-Action": "viewer",
  };
}

function measure(value, label) {
  return `<div class="measure"><strong>${value}</strong><span>${label}</span></div>`;
}

function sectionHeading(title, detail) {
  return `<div class="section-heading"><h2>${escapeHtml(title)}</h2><span>${escapeHtml(detail)}</span></div>`;
}

function sessionRow(session) {
  return `
    <button class="record-row" type="button" data-session="${escapeHtml(session.session_id)}">
      <span>
        <span class="record-title">${escapeHtml(session.title)}</span>
        <span class="record-meta">${escapeHtml(session.provider)} · ${session.event_count} events</span>
      </span>
      <span class="record-side">${relativeTime(session.modified_at)}</span>
    </button>`;
}

function pageRow(page) {
  return `
    <button class="record-row" type="button" data-page="${escapeHtml(page.path)}">
      <span>
        <span class="record-title">${escapeHtml(page.title)}</span>
        <span class="record-meta">${escapeHtml(categoryTitle(page.category))}${page.tags.length ? ` · ${escapeHtml(page.tags.join(", "))}` : ""}</span>
      </span>
      <span class="record-side">${page.backlink_count} backlinks</span>
    </button>`;
}

function searchRow(result) {
  const attribute = result.kind === "session"
    ? `data-session="${escapeHtml(result.identity)}"`
    : `data-page="${escapeHtml(result.identity)}"`;
  return `
    <button class="record-row" type="button" ${attribute}>
      <span>
        <span class="record-title">${escapeHtml(result.title)}</span>
        <span class="record-meta">${escapeHtml(result.excerpt || result.kind)}</span>
      </span>
      <span class="record-side">${escapeHtml(result.kind)}</span>
    </button>`;
}

function eventBlock(event) {
  return `
    <div class="event">
      <div class="event-label">${event.sequence} · ${escapeHtml(event.role || event.kind)} · ${escapeHtml(event.label)}</div>
      <pre>${escapeHtml(event.content)}</pre>
    </div>`;
}

function distillControls(sessionId) {
  return `
    <div class="distill-controls">
      <select id="distill-runtime" aria-label="Curator runtime">
        <option value="ollama">Ollama · local</option>
        <option value="codex">Codex · remote</option>
        <option value="claude">Claude · remote</option>
      </select>
      <input id="distill-model" placeholder="Model (required for Ollama)" aria-label="Model">
      <select id="distill-access" aria-label="Content access">
        <option value="metadata-only">Metadata only</option>
        <option value="selected-local">Selected content · local only</option>
        <option value="selected-remote">Selected content · remote</option>
      </select>
      <button id="distill-button" class="primary-action" type="button" data-session="${escapeHtml(sessionId)}">
        Distill selected session
      </button>
    </div>`;
}

function activityLine(receipt) {
  const changed = receipt.changed_files ? `${receipt.changed_files.length} files` : `${receipt.events_added} events`;
  return `
    <div class="activity-line">
      <strong>${escapeHtml(receipt.type)}</strong>
      <code>${escapeHtml(receipt.run_id)}</code>
      <span>${escapeHtml(receipt.status)} · ${changed} · ${relativeTime(receipt.started_at)}</span>
    </div>`;
}

function emptyRow(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function categoryTitle(value) {
  const labels = {
    projects: "Projects",
    decisions: "Decisions",
    problems: "Problems",
    procedures: "Procedures",
    systems: "Systems",
    unfinished: "Unfinished work",
    imports: "Imported Almanacs",
    "agent-sessions": "Agent sessions",
    home: "Work Almanac",
  };
  return labels[value] || value;
}

function relativeTime(value) {
  if (!value) return "never";
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return formatter.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
