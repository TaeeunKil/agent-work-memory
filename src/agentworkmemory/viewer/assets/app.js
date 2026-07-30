const state = {
  view: "overview",
  overview: null,
  sessions: [],
  pages: [],
  projects: [],
  receipts: { sync: [], distill: [] },
  activity: [],
  schedules: [],
  selectedActivityId: null,
};

const workspace = document.querySelector("#workspace");
const inspector = document.querySelector("#inspector-content");
const syncButton = document.querySelector("#sync-button");
const buildWikiButton = document.querySelector("#build-wiki-button");
const toast = document.querySelector("#toast");

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelector("#close-inspector").addEventListener("click", closeInspector);
document.querySelector("#search-form").addEventListener("submit", search);
syncButton.addEventListener("click", syncTranscripts);
buildWikiButton.addEventListener("click", openBuildWiki);
window.addEventListener("hashchange", openHashTarget);

boot();

async function boot() {
  window.setInterval(refreshActivity, 2000);
  window.setInterval(refreshSchedules, 30000);
  try {
    await refreshActivity();
    await refreshSchedules();
    await refreshData();
    render();
    openHashTarget();
  } catch (error) {
    state.view = "activity";
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === "activity");
    });
    renderActivity();
    showToast(`Vault data is busy. Activity remains live.`);
  }
}

async function refreshSchedules() {
  try {
    state.schedules = await api("/api/schedules");
    if (state.view === "activity") renderActivity();
  } catch {
    // Keep the last scheduler snapshot; OS status reads are intentionally slower.
  }
}

async function refreshData() {
  const [overview, sessions, pages, projects, receipts] = await Promise.all([
    api("/api/overview"),
    api("/api/sessions"),
    api("/api/pages"),
    api("/api/projects"),
    api("/api/receipts"),
  ]);
  state.overview = overview;
  state.sessions = sessions;
  state.pages = pages;
  state.projects = projects;
  state.receipts = receipts;
  updateRailStatus();
}

async function refreshActivity() {
  try {
    state.activity = await api("/api/activity");
    updateRailStatus();
    if (state.view === "activity") {
      renderActivity();
      if (state.selectedActivityId) {
        openScheduledActivity(state.selectedActivityId);
      }
    }
  } catch {
    // Keep the last known activity snapshot while the local viewer recovers.
  }
}

function updateRailStatus() {
  const running = state.activity.find((run) => run.status === "running");
  const label = running
    ? `${activityTaskLabel(running.task)} running`
    : state.overview?.last_sync_at
      ? `Synced ${relativeTime(state.overview.last_sync_at)}`
      : "Local vault";
  document.querySelector("#rail-status").textContent = label;
  document.querySelector(".status-dot").classList.toggle(
    "is-running",
    Boolean(running),
  );
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  if (state.view === "projects") renderProjects();
  else if (state.view === "sessions") renderSessions();
  else if (state.view === "knowledge") renderKnowledge();
  else if (state.view === "activity") renderActivity();
  else renderOverview();
}

function renderProjects() {
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Connected knowledge</p>
        <h1>Projects</h1>
      </div>
      <p class="quiet">Each project gathers its canonical topic pages and the sessions that support them.</p>
    </header>
    <section class="section-block">
      ${sectionHeading("Project hubs", `${state.projects.length} total`)}
      <div class="record-list">${state.projects.map(projectRow).join("") || emptyRow("Build the Wiki to create the first project hub.")}</div>
    </section>
  `;
  bindRows();
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
  const receipts = [
    ...state.receipts.sync.map((receipt) => ({ ...receipt, type: "sync" })),
    ...state.receipts.distill.map((receipt) => ({ ...receipt, type: "distill" })),
  ].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
  const active = state.activity.filter((run) => run.status === "running").length;
  const nextSchedule = state.schedules[0] || null;
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">Local operations</p>
        <h1>Activity</h1>
      </div>
      <p class="quiet">Scheduled work from start to finish. Select a row to inspect its timeline and recent log.</p>
    </header>
    <section class="activity-live">
      <div class="activity-live-count">
        <strong>${active}</strong>
        <span>running now</span>
      </div>
      <div class="activity-next">
        <p class="eyebrow">Next run</p>
        <p>${nextSchedule ? `${escapeHtml(activityTaskLabel(nextSchedule.task))} · <strong>${escapeHtml(formatScheduleMoment(nextSchedule.next_run_at))}</strong>` : "No installed schedule"}</p>
      </div>
    </section>
    <section class="section-block">
      ${sectionHeading("Scheduled operations", `${state.activity.length} retained`)}
      <div class="activity-list">${state.activity.map(scheduledActivityRow).join("") || emptyRow("The next scheduled run will appear here.")}</div>
    </section>
    <section class="section-block">
      ${sectionHeading("Run receipts", `${receipts.length} retained`)}
      <div class="activity-list">${receipts.map(activityLine).join("") || emptyRow("No completed receipts yet.")}</div>
    </section>
  `;
  bindActivityRows();
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
  document.querySelectorAll("[data-project]").forEach((row) => {
    row.addEventListener("click", () => openProject(row.dataset.project));
  });
  document.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => renderKnowledge(button.dataset.category));
  });
}

async function openProject(path) {
  const detail = await api(`/api/project?path=${encodeURIComponent(path)}`);
  document.body.classList.add("has-inspector");
  inspector.innerHTML = `
    <p class="eyebrow">Project hub</p>
    <h2>${escapeHtml(detail.page.title)}</h2>
    <div class="inspector-meta">
      <span>${detail.topics.length} topic pages</span>
      <span>${detail.sessions.length} source sessions</span>
    </div>
    <article class="markdown">${detail.page.html}</article>
    <section class="inspector-section">
      <p class="eyebrow">Topics</p>
      <div class="record-list">${detail.topics.map(pageRow).join("") || emptyRow("No linked topic pages yet.")}</div>
    </section>
    <section class="inspector-section">
      <p class="eyebrow">Evidence</p>
      <div class="record-list">${detail.sessions.map(sessionRow).join("") || emptyRow("No source sessions cited yet.")}</div>
    </section>
  `;
  bindRows();
  inspector.querySelectorAll("a[href^='#/wiki/']").forEach((link) => {
    link.addEventListener("click", openHashTarget);
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
  state.selectedActivityId = null;
}

function bindActivityRows() {
  document.querySelectorAll("[data-activity]").forEach((row) => {
    row.addEventListener("click", () => openScheduledActivity(row.dataset.activity));
  });
  document.querySelectorAll("[data-receipt]").forEach((row) => {
    row.addEventListener("click", () => {
      openReceipt(row.dataset.receipt, row.dataset.type);
    });
  });
}

function openScheduledActivity(activityId) {
  const run = state.activity.find((item) => item.activity_id === activityId);
  if (!run) return;
  state.selectedActivityId = activityId;
  document.body.classList.add("has-inspector");
  const finished = run.finished_at || new Date().toISOString();
  inspector.innerHTML = `
    <p class="eyebrow">${escapeHtml(activityTaskLabel(run.task))}</p>
    <h2>${escapeHtml(activityStatusLabel(run.status))}</h2>
    <div class="inspector-meta">
      <span>Started ${escapeHtml(formatMoment(run.started_at))}</span>
      <span>${run.finished_at ? `Ended ${escapeHtml(formatMoment(run.finished_at))}` : "In progress"}</span>
      <span>${escapeHtml(durationBetween(run.started_at, finished))}</span>
    </div>
    <div class="activity-timeline">
      ${timelineStep("Started", run.started_at, true)}
      ${timelineStep(run.summary, run.finished_at || "Now", run.status !== "failed", run.status === "running")}
      ${run.finished_at ? timelineStep(activityStatusLabel(run.status), run.finished_at, run.status === "succeeded") : ""}
    </div>
    <section class="activity-log">
      <div class="activity-log-heading">
        <p class="eyebrow">Recent log</p>
        <span>${run.log_lines.length} lines</span>
      </div>
      <pre>${escapeHtml(run.log_lines.join("\n") || "Waiting for the first log line...")}</pre>
    </section>
  `;
}

function openReceipt(runId, type) {
  const collection = type === "sync"
    ? state.receipts.sync
    : state.receipts.distill;
  const receipt = collection.find((item) => item.run_id === runId);
  if (!receipt) return;
  state.selectedActivityId = null;
  document.body.classList.add("has-inspector");
  const changed = receipt.changed_files
    ? `${receipt.changed_files.length} Wiki files`
    : `${receipt.events_added} new events`;
  inspector.innerHTML = `
    <p class="eyebrow">${escapeHtml(activityTaskLabel(type))} receipt</p>
    <h2>${escapeHtml(activityStatusLabel(receipt.status))}</h2>
    <div class="inspector-meta">
      <span>${escapeHtml(receipt.run_id)}</span>
      <span>${escapeHtml(changed)}</span>
      <span>${escapeHtml(durationBetween(receipt.started_at, receipt.finished_at))}</span>
    </div>
    <div class="activity-timeline">
      ${timelineStep("Started", receipt.started_at, true)}
      ${timelineStep(activityStatusLabel(receipt.status), receipt.finished_at, receipt.status === "succeeded")}
    </div>
  `;
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

function openBuildWiki() {
  document.body.classList.add("has-inspector");
  inspector.innerHTML = `
    <p class="eyebrow">Durable knowledge</p>
    <h2>Build the Wiki</h2>
    <div class="inspector-meta">
      <span>${state.overview.pending_distill_count} sessions waiting</span>
      <span>${state.projects.length} project hubs</span>
    </div>
    <p class="quiet">The next bounded batch will be merged into canonical topic pages. Existing topics are updated instead of duplicated.</p>
    ${buildWikiControls()}
  `;
  const button = document.querySelector("#build-pending-button");
  button.addEventListener("click", distillPending);
}

async function distillPending() {
  const button = document.querySelector("#build-pending-button");
  const runtime = document.querySelector("#build-runtime").value;
  const model = document.querySelector("#build-model").value.trim() || null;
  const contentAccess = document.querySelector("#build-access").value;
  const limit = Number(document.querySelector("#build-limit").value);
  if (!contentAccess) {
    showToast("Choose what session content the curator may read.");
    return;
  }
  button.classList.add("is-busy");
  button.textContent = "Building topic pages…";
  try {
    const receipt = await api("/api/distill/pending", {
      method: "POST",
      headers: actionHeaders(),
      body: JSON.stringify({
        limit,
        runtime,
        model,
        content_access: contentAccess,
      }),
    });
    await refreshData();
    state.view = "projects";
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("is-active", item.dataset.view === "projects");
    });
    renderProjects();
    openBuildWiki();
    showToast(`${receipt.changed_files.length} topic pages changed.`);
  } catch (error) {
    showToast(error.message);
    button.classList.remove("is-busy");
    button.textContent = "Build next batch";
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
    "X-AWM-Action": "viewer",
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

function projectRow(project) {
  return `
    <button class="record-row project-row" type="button" data-project="${escapeHtml(project.path)}">
      <span>
        <span class="record-title">${escapeHtml(project.title)}</span>
        <span class="record-meta">${project.topic_count} topics · ${project.source_session_ids.length} source sessions</span>
      </span>
      <span class="record-side">Open project →</span>
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

function buildWikiControls() {
  const disabled = state.overview.pending_distill_count === 0 ? "disabled" : "";
  return `
    <div class="distill-controls build-wiki-controls">
      <label>
        <span>Runtime</span>
        <select id="build-runtime" aria-label="Curator runtime">
          <option value="codex">Codex · remote</option>
          <option value="ollama">Ollama · local</option>
          <option value="claude">Claude · remote</option>
        </select>
      </label>
      <label>
        <span>Batch size</span>
        <select id="build-limit" aria-label="Pending session batch size">
          <option value="5">5 sessions</option>
          <option value="10" selected>10 sessions</option>
          <option value="20">20 sessions</option>
        </select>
      </label>
      <label class="control-wide">
        <span>Model</span>
        <input id="build-model" placeholder="Required for Ollama" aria-label="Model">
      </label>
      <label class="control-wide">
        <span>Content permission</span>
        <select id="build-access" aria-label="Content access">
          <option value="" selected disabled>Choose permission…</option>
          <option value="metadata-only">Metadata only</option>
          <option value="selected-local">Selected content · local only</option>
          <option value="selected-remote">Selected content · remote</option>
        </select>
      </label>
      <button id="build-pending-button" class="primary-action" type="button" ${disabled}>
        ${disabled ? "Nothing waiting" : "Build next batch"}
      </button>
    </div>`;
}

function activityLine(receipt) {
  const changed = receipt.changed_files
    ? `${receipt.changed_files.length} files`
    : `${receipt.events_added} events`;
  return `
    <button class="activity-row" type="button" data-receipt="${escapeHtml(receipt.run_id)}" data-type="${escapeHtml(receipt.type)}">
      <span class="activity-state is-${escapeHtml(receipt.status)}" aria-hidden="true"></span>
      <span>
        <strong>${escapeHtml(activityTaskLabel(receipt.type))}</strong>
        <span class="activity-summary">${escapeHtml(receipt.run_id)}</span>
      </span>
      <span class="activity-when">${escapeHtml(activityStatusLabel(receipt.status))} · ${changed}<br>${relativeTime(receipt.started_at)}</span>
    </button>`;
}

function scheduledActivityRow(run) {
  return `
    <button class="activity-row ${run.status === "running" ? "is-running" : ""}" type="button" data-activity="${escapeHtml(run.activity_id)}">
      <span class="activity-state is-${escapeHtml(run.status)}" aria-hidden="true"></span>
      <span>
        <strong>${escapeHtml(activityTaskLabel(run.task))}</strong>
        <span class="activity-summary">${escapeHtml(run.summary)}</span>
      </span>
      <span class="activity-when">${escapeHtml(activityStatusLabel(run.status))}<br>${relativeTime(run.started_at)}</span>
    </button>`;
}

function timelineStep(label, moment, completed, current = false) {
  return `
    <div class="timeline-step ${completed ? "is-complete" : "is-failed"} ${current ? "is-current" : ""}">
      <span class="timeline-marker" aria-hidden="true"></span>
      <span>
        <strong>${escapeHtml(label)}</strong>
        <small>${moment === "Now" ? "Now" : escapeHtml(formatMoment(moment))}</small>
      </span>
    </div>`;
}

function activityTaskLabel(value) {
  const labels = {
    sync: "Transcript sync",
    "auto-distill": "Wiki distillation",
    distill: "Wiki distillation",
  };
  return labels[value] || value;
}

function activityStatusLabel(value) {
  const labels = {
    running: "Running",
    succeeded: "Completed",
    skipped: "Skipped",
    failed: "Failed",
    skipped_locked: "Skipped",
  };
  return labels[value] || value;
}

function formatMoment(value) {
  if (!value) return "Not finished";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatScheduleMoment(value) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function durationBetween(start, finish) {
  if (!start || !finish) return "Duration unavailable";
  const seconds = Math.max(
    0,
    Math.round((new Date(finish) - new Date(start)) / 1000),
  );
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
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
    home: "Agent Work Memory",
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
