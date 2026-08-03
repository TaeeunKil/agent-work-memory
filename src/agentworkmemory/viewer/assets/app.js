import {
  localeName,
  pageLabel,
  persistLocale,
  preferredLocale,
  translate,
} from "/assets/i18n.js";

const state = {
  view: "overview",
  overview: null,
  sessions: [],
  pages: [],
  projects: [],
  graph: null,
  graphLoading: false,
  graphCategory: "all",
  graphQuery: "",
  graphSelectedId: null,
  receipts: { sync: [], distill: [] },
  activity: [],
  schedules: [],
  selectedActivityId: null,
  locale: preferredLocale(),
  pageLocaleOverrides: {},
};

const GRAPH_POSITION_KEY = "awm.knowledge-graph.positions.v1";
const RAIL_COLLAPSED_KEY = "awm.viewer.rail-collapsed.v1";
const DETAIL_PEEK_HISTORY_KEY = "awmDetailPeek";
const GRAPH_COLORS = {
  projects: "#e25832",
  decisions: "#d9a441",
  problems: "#bd7780",
  procedures: "#80a078",
  systems: "#69a0b4",
  unfinished: "#9b86ad",
  imports: "#879096",
};

let knowledgeGraph = null;
let graphResizeTimer = null;
let activeSelectMenu = null;
let detailPeekRestoreTarget = null;
let renderedDetailPeekRoute = null;
let detailPeekHeadings = [];

const workspace = document.querySelector("#workspace");
const detailPeek = document.querySelector("#detail-peek");
const detailPeekDialog = document.querySelector("#detail-peek-dialog");
const detailPeekBody = document.querySelector(".detail-peek-body");
const detailPeekContent = document.querySelector("#detail-peek-content");
const detailPeekContext = document.querySelector("#detail-peek-context");
const expandDetailPeekButton = document.querySelector("#expand-detail-peek");
const detailPeekToc = document.querySelector("#detail-peek-toc");
const detailPeekTocList = document.querySelector("#detail-peek-toc-list");
const detailPeekTocToggle = document.querySelector("#detail-peek-toc-toggle");
const syncButton = document.querySelector("#sync-button");
const buildWikiButton = document.querySelector("#build-wiki-button");
const railToggle = document.querySelector("#rail-toggle");
const toast = document.querySelector("#toast");

initializeLocale();
initializeRail();

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelector("#close-detail-peek").addEventListener("click", closeDetailPeek);
document.querySelector("#detail-peek-backdrop").addEventListener("click", closeDetailPeek);
expandDetailPeekButton.addEventListener("click", toggleDetailPeekSize);
detailPeekTocToggle.addEventListener("click", toggleDetailPeekToc);
detailPeekContent.addEventListener("scroll", updateActiveDetailPeekHeading, {
  passive: true,
});
document.querySelector("#search-form").addEventListener("submit", search);
syncButton.addEventListener("click", syncTranscripts);
buildWikiButton.addEventListener("click", openBuildWiki);
railToggle.addEventListener("click", () => {
  setRailCollapsed(!document.body.classList.contains("rail-collapsed"));
});
document.querySelectorAll("[data-locale]").forEach((button) => {
  button.addEventListener("click", () => setLocale(button.dataset.locale));
});
document.addEventListener("pointerdown", (event) => {
  if (activeSelectMenu && !activeSelectMenu.root.contains(event.target)) {
    activeSelectMenu.close(false);
  }
});
document.addEventListener("keydown", handleDetailPeekKeydown);
window.addEventListener("popstate", restoreDetailPeekHistory);
window.addEventListener("hashchange", () => {
  if (!window.history.state?.[DETAIL_PEEK_HISTORY_KEY]) {
    openHashTarget({ fromHistory: true });
  }
});
window.addEventListener("resize", () => {
  queueGraphResize();
  syncDetailPeekTocLayout();
});

boot();

function t(key, values = {}) {
  return translate(state.locale, key, values);
}

function initializeLocale() {
  applyLocaleToChrome();
}

function setLocale(locale) {
  if (locale === state.locale) return;
  const graphViewport = knowledgeGraph
    ? { zoom: knowledgeGraph.zoom(), pan: knowledgeGraph.pan() }
    : null;
  if (knowledgeGraph) saveGraphPositions();
  state.locale = locale;
  persistLocale(locale);
  applyLocaleToChrome();
  updateRailStatus();
  render();
  if (graphViewport && state.view === "graph") {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      if (!knowledgeGraph) return;
      knowledgeGraph.zoom(graphViewport.zoom);
      knowledgeGraph.pan(graphViewport.pan);
    }));
  }
  if (renderedDetailPeekRoute) {
    openDetailPeekRoute(renderedDetailPeekRoute, { fromHistory: true });
  }
}

function applyLocaleToChrome() {
  document.documentElement.lang = state.locale;
  const navKeys = {
    overview: "nav.today",
    projects: "nav.projects",
    sessions: "nav.sessions",
    knowledge: "nav.knowledge",
    graph: "nav.graph",
    activity: "nav.activity",
  };
  document.querySelector("#primary-navigation").setAttribute("aria-label", t("nav.primary"));
  document.querySelectorAll(".nav-item").forEach((button) => {
    const label = t(navKeys[button.dataset.view]);
    button.title = label;
    button.querySelector(".nav-label").textContent = label;
  });
  document.querySelector("#search-input").placeholder = t("search.placeholder");
  document.querySelector("#search-input").setAttribute("aria-label", t("action.search"));
  document.querySelector("#search-form").setAttribute("aria-label", t("action.search"));
  document.querySelector(".search-submit").setAttribute("aria-label", t("action.search"));
  syncButton.textContent = t("action.sync");
  buildWikiButton.textContent = t("action.buildWiki");
  document.querySelector(".language-switch").setAttribute("aria-label", t("language.label"));
  document.querySelectorAll("[data-locale]").forEach((button) => {
    const selected = button.dataset.locale === state.locale;
    button.setAttribute("aria-pressed", String(selected));
    button.title = localeName(button.dataset.locale, state.locale);
  });
  document.querySelector("#close-detail-peek").setAttribute("aria-label", t("action.close"));
  document.querySelector("#detail-peek-backdrop").setAttribute("aria-label", t("action.close"));
  detailPeekToc.setAttribute("aria-label", t("wiki.onThisPage"));
  detailPeekTocToggle.querySelector("span").textContent = t("wiki.onThisPage");
  updateDetailPeekSizeControl();
}

async function boot() {
  window.setInterval(refreshActivity, 2000);
  window.setInterval(refreshSchedules, 30000);
  try {
    await refreshActivity();
    await refreshSchedules();
    await refreshData();
    render();
    openHashTarget({ fromHistory: true });
  } catch (error) {
    state.view = "activity";
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === "activity");
    });
    renderActivity();
    showToast(t("status.vaultBusy"));
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
  state.graph = null;
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
    ? t("status.running", { task: activityTaskLabel(running.task) })
    : state.overview?.last_sync_at
      ? t("status.synced", { time: relativeTime(state.overview.last_sync_at) })
      : t("status.localVault");
  document.querySelector("#rail-status").textContent = label;
  document.querySelector(".status-dot").classList.toggle(
    "is-running",
    Boolean(running),
  );
}

function setView(view) {
  if (state.view === "graph" && view !== "graph") destroyKnowledgeGraph();
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  const graphView = state.view === "graph";
  workspace.classList.toggle("graph-workspace", graphView);
  if (!graphView) destroyKnowledgeGraph();
  if (state.view === "projects") renderProjects();
  else if (state.view === "sessions") renderSessions();
  else if (state.view === "knowledge") renderKnowledge();
  else if (state.view === "graph") renderGraph();
  else if (state.view === "activity") renderActivity();
  else renderOverview();
}

function renderProjects() {
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">${t("projects.eyebrow")}</p>
        <h1>${t("nav.projects")}</h1>
      </div>
      <p class="quiet">${t("projects.description")}</p>
    </header>
    <section class="section-block">
      ${sectionHeading(t("section.projectHubs"), t("count.total", { count: state.projects.length }))}
      <div class="record-list">${state.projects.map(projectRow).join("") || emptyRow(t("empty.projects"))}</div>
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
        <p class="eyebrow">${t("overview.eyebrow")}</p>
        <h1>${t("nav.today")}</h1>
      </div>
      <p class="quiet">${t("overview.description")}</p>
    </header>
    <div class="measure-strip">
      ${measure(state.overview.session_count, t("measure.sessions"))}
      ${measure(state.overview.knowledge_count, t("measure.pages"))}
      ${measure(state.overview.pending_distill_count, t("measure.pending"))}
    </div>
    <section class="section-block">
      ${sectionHeading(t("section.recentSessions"), t("count.shown", { count: recent.length }))}
      <div class="record-list">${recent.map(sessionRow).join("") || emptyRow(t("empty.sessions"))}</div>
    </section>
    <section class="section-block">
      ${sectionHeading(t("section.waiting"), t("count.sessions", { count: pending.length }))}
      <div class="record-list">${pending.slice(0, 6).map(sessionRow).join("") || emptyRow(t("empty.waiting"))}</div>
    </section>
    <section class="section-block">
      ${sectionHeading(t("section.knowledgeAreas"), t("count.pages", { count: state.pages.length }))}
      ${categoryGrid()}
    </section>
  `;
  bindRows();
}

function renderSessions() {
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">${t("sessions.eyebrow")}</p>
        <h1>${t("nav.sessions")}</h1>
      </div>
      <p class="quiet">${t("sessions.description")}</p>
    </header>
    <section class="section-block">
      ${sectionHeading(t("section.allSessions"), t("count.total", { count: state.sessions.length }))}
      <div class="record-list">${state.sessions.map(sessionRow).join("") || emptyRow(t("empty.sessions"))}</div>
    </section>
  `;
  bindRows();
}

function renderKnowledge(category = null) {
  const pages = category
    ? state.pages.filter((page) => page.category === category)
    : state.pages;
  const title = category ? categoryTitle(category) : t("nav.knowledge");
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">${t("knowledge.eyebrow")}</p>
        <h1>${escapeHtml(title)}</h1>
      </div>
      <p class="quiet">${t("knowledge.description")}</p>
    </header>
    ${category ? "" : `<section class="section-block">${categoryGrid()}</section>`}
    <section class="section-block">
      ${sectionHeading(category ? `${title} · ${t("count.pages", { count: pages.length })}` : t("section.allWiki"), t("count.total", { count: pages.length }))}
      <div class="record-list">${pages.map(pageRow).join("") || emptyRow(t("empty.pages"))}</div>
    </section>
  `;
  bindRows();
}

function initializeRail() {
  let collapsed = false;
  try {
    collapsed = window.localStorage.getItem(RAIL_COLLAPSED_KEY) === "true";
  } catch {
    // A private browser context may decline storage; the rail still works in-session.
  }
  setRailCollapsed(collapsed, false);
}

function setRailCollapsed(collapsed, persist = true) {
  document.body.classList.toggle("rail-collapsed", collapsed);
  railToggle.setAttribute("aria-expanded", String(!collapsed));
  const label = collapsed ? t("action.expandSidebar") : t("action.collapseSidebar");
  railToggle.setAttribute("aria-label", label);
  railToggle.title = label;
  if (persist) {
    try {
      window.localStorage.setItem(RAIL_COLLAPSED_KEY, String(collapsed));
    } catch {
      // Keep the current layout even when persistence is unavailable.
    }
  }
  queueGraphResize(reducedMotion() ? 0 : 240);
}

function renderGraph() {
  destroyKnowledgeGraph();
  if (!state.graph) {
    workspace.innerHTML = `
      <section class="graph-shell graph-shell-loading">
        <div class="graph-loading-mark" aria-hidden="true"><span></span><span></span><span></span></div>
        <p>${t("graph.loading")}</p>
      </section>`;
    loadGraph();
    return;
  }

  const categories = [...new Set(state.graph.nodes.map((node) => node.category))]
    .sort((a, b) => categoryTitle(a).localeCompare(categoryTitle(b)));
  const categoryOptions = [
    { value: "all", label: t("graph.all"), tone: "neutral" },
    ...categories.map((category) => ({
      value: category,
      label: categoryTitle(category),
      tone: category,
    })),
  ];
  const isolated = state.graph.nodes.filter(
    (node) => node.incoming_count + node.outgoing_count === 0,
  ).length;
  workspace.innerHTML = `
    <section class="graph-shell">
      <header class="graph-toolbar">
        <div class="graph-title">
          <p class="eyebrow">${t("graph.eyebrow")}</p>
          <div>
            <h1>${t("nav.graph")}</h1>
            <p id="graph-summary">${t("graph.summary", { notes: state.graph.nodes.length, links: state.graph.edges.length, isolated })}</p>
          </div>
        </div>
        <div class="graph-controls">
          <label class="graph-search">
            <span class="sr-only">${t("graph.searchLabel")}</span>
            <input id="graph-search" type="search" value="${escapeHtml(state.graphQuery)}" placeholder="${t("graph.search")}" autocomplete="off">
          </label>
          ${selectMenuMarkup({
            id: "graph-category",
            label: t("graph.filter"),
            value: state.graphCategory,
            options: categoryOptions,
          })}
          <button id="graph-fit" class="graph-tool" type="button">${t("graph.fit")}</button>
          <button id="graph-relayout" class="graph-tool" type="button">${t("graph.relayout")}</button>
        </div>
      </header>
      <div class="graph-stage">
        <div
          id="knowledge-graph"
          role="application"
          tabindex="0"
          aria-label="${t("graph.canvasLabel")}"
          aria-describedby="graph-instructions"
        ></div>
        <p id="graph-instructions" class="sr-only">${t("graph.instructions")}</p>
        <div class="graph-legend" aria-label="${t("graph.legend")}">
          ${categories.map((category) => `
            <span><i class="${graphColorClass(category)}" aria-hidden="true"></i>${escapeHtml(categoryTitle(category))}</span>
          `).join("")}
        </div>
        <div id="graph-readout" class="graph-readout" aria-live="polite">
          <span>${t("graph.hint")}</span>
        </div>
      </div>
    </section>`;

  document.querySelector("#graph-search").addEventListener("input", (event) => {
    state.graphQuery = event.target.value.trim();
    applyGraphFilters();
  });
  document.querySelector("#graph-search").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    focusGraphMatches();
  });
  bindSelectMenu(document.querySelector("#graph-category"), (value) => {
    state.graphCategory = value;
    applyGraphFilters();
    fitVisibleGraph();
  });
  document.querySelector("#graph-fit").addEventListener("click", fitVisibleGraph);
  document.querySelector("#graph-relayout").addEventListener("click", () => {
    clearStoredGraphPositions();
    runGraphLayout();
  });

  window.requestAnimationFrame(mountKnowledgeGraph);
}

function selectMenuMarkup({ id, label, value, options }) {
  const selected = options.find((option) => option.value === value) || options[0];
  return `
    <div id="${escapeHtml(id)}" class="select-menu graph-category-control" data-value="${escapeHtml(selected.value)}">
      <span id="${escapeHtml(id)}-label" class="sr-only">${escapeHtml(label)}</span>
      <button
        class="select-menu-trigger"
        type="button"
        aria-haspopup="listbox"
        aria-expanded="false"
        aria-controls="${escapeHtml(id)}-options"
        aria-labelledby="${escapeHtml(id)}-label ${escapeHtml(id)}-value"
      >
        <span id="${escapeHtml(id)}-value" class="select-menu-value">
          <i class="select-menu-dot ${graphColorClass(selected.tone)}" aria-hidden="true"></i>
          <span class="select-menu-value-text">${escapeHtml(selected.label)}</span>
        </span>
        <svg class="select-menu-chevron" viewBox="0 0 12 8" aria-hidden="true"><path d="m1 1 5 5 5-5" /></svg>
      </button>
      <div id="${escapeHtml(id)}-options" class="select-menu-popover" role="listbox" aria-labelledby="${escapeHtml(id)}-label" hidden>
        ${options.map((option, index) => `
          <button
            id="${escapeHtml(id)}-option-${index}"
            class="select-menu-option"
            type="button"
            role="option"
            data-value="${escapeHtml(option.value)}"
            data-tone="${escapeHtml(option.tone)}"
            aria-selected="${String(option.value === selected.value)}"
          >
            <i class="select-menu-dot ${graphColorClass(option.tone)}" aria-hidden="true"></i>
            <span>${escapeHtml(option.label)}</span>
            <svg class="select-menu-check" viewBox="0 0 14 10" aria-hidden="true"><path d="m1 5 4 4 8-8" /></svg>
          </button>`).join("")}
      </div>
    </div>`;
}

function bindSelectMenu(root, onChange) {
  const trigger = root.querySelector(".select-menu-trigger");
  const popover = root.querySelector(".select-menu-popover");
  const options = [...root.querySelectorAll(".select-menu-option")];
  const valueText = root.querySelector(".select-menu-value-text");
  const valueDot = root.querySelector(".select-menu-value .select-menu-dot");

  const selectedIndex = () => Math.max(
    0,
    options.findIndex((option) => option.getAttribute("aria-selected") === "true"),
  );
  const focusOption = (index) => options[(index + options.length) % options.length].focus();

  const close = (restoreFocus = false) => {
    popover.hidden = true;
    root.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    if (activeSelectMenu?.root === root) activeSelectMenu = null;
    if (restoreFocus) trigger.focus();
  };
  const open = () => {
    if (activeSelectMenu && activeSelectMenu.root !== root) activeSelectMenu.close(false);
    popover.hidden = false;
    root.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    activeSelectMenu = { root, close };
    window.requestAnimationFrame(() => focusOption(selectedIndex()));
  };
  const choose = (option) => {
    options.forEach((candidate) => {
      candidate.setAttribute("aria-selected", String(candidate === option));
    });
    root.dataset.value = option.dataset.value;
    valueText.textContent = option.querySelector("span").textContent;
    valueDot.className = `select-menu-dot ${graphColorClass(option.dataset.tone)}`;
    close(true);
    onChange(option.dataset.value);
  };

  trigger.addEventListener("click", () => {
    if (popover.hidden) open();
    else close(false);
  });
  trigger.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    open();
  });
  options.forEach((option) => option.addEventListener("click", () => choose(option)));
  popover.addEventListener("keydown", (event) => {
    const focusedIndex = options.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusOption(focusedIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusOption(focusedIndex - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusOption(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusOption(options.length - 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      close(false);
    } else if ((event.key === "Enter" || event.key === " ") && focusedIndex >= 0) {
      event.preventDefault();
      choose(options[focusedIndex]);
    }
  });
}

function closeActiveSelectMenu(restoreFocus = false) {
  if (activeSelectMenu) activeSelectMenu.close(restoreFocus);
}

async function loadGraph() {
  if (state.graphLoading) return;
  state.graphLoading = true;
  try {
    state.graph = await api("/api/graph");
    if (state.view === "graph") renderGraph();
  } catch (error) {
    if (state.view === "graph") {
      workspace.innerHTML = `
        <section class="graph-shell graph-shell-loading">
          <p>${escapeHtml(error.message)}</p>
        </section>`;
    }
  } finally {
    state.graphLoading = false;
  }
}

function mountKnowledgeGraph() {
  const container = document.querySelector("#knowledge-graph");
  if (!container || !state.graph || typeof window.cytoscape !== "function") {
    if (container) container.innerHTML = `<p class="graph-fallback">${t("graph.unavailable")}</p>`;
    return;
  }
  if (state.graph.nodes.length === 0) {
    container.innerHTML = `<p class="graph-fallback">${t("graph.empty")}</p>`;
    return;
  }

  const positions = storedGraphPositions();
  const hasCompleteLayout = state.graph.nodes.every((node) => positions[node.id]);
  const maxDegree = Math.max(
    1,
    ...state.graph.nodes.map((node) => node.incoming_count + node.outgoing_count),
  );
  const elements = [
    ...state.graph.nodes.map((node) => ({
      data: {
        ...node,
        label: pageLabel(node, state.locale),
        degree: node.incoming_count + node.outgoing_count,
        color: categoryColor(node.category),
      },
      position: positions[node.id],
    })),
    ...state.graph.edges.map((edge) => ({ data: edge })),
  ];

  knowledgeGraph = window.cytoscape({
    container,
    elements,
    layout: { name: "preset", fit: false },
    minZoom: 0.12,
    maxZoom: 3.2,
    selectionType: "single",
    boxSelectionEnabled: false,
    style: [
      {
        selector: "node",
        style: {
          width: `mapData(degree, 0, ${maxDegree}, 9, 29)`,
          height: `mapData(degree, 0, ${maxDegree}, 9, 29)`,
          "background-color": "data(color)",
          "background-opacity": 0.94,
          "border-width": 1,
          "border-color": "#fff9ef",
          "border-opacity": 0.34,
          label: "data(label)",
          color: "#f6f0e6",
          "font-family": "Segoe UI Variable, Aptos, sans-serif",
          "font-size": 9,
          "font-weight": 500,
          "min-zoomed-font-size": 10,
          "text-margin-y": -10,
          "text-outline-color": "#121a22",
          "text-outline-width": 3,
          "text-outline-opacity": 0.86,
          "text-wrap": "ellipsis",
          "text-max-width": 150,
          "transition-property": "opacity, border-width, border-opacity",
          "transition-duration": "140ms",
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "curve-style": "haystack",
          "line-color": "#8b98a1",
          opacity: 0.24,
          "transition-property": "opacity, line-color, width",
          "transition-duration": "140ms",
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#fffdf8",
          "border-opacity": 1,
          "border-width": 3,
          "overlay-color": "#e25832",
          "overlay-opacity": 0.12,
          "overlay-padding": 8,
          "z-index": 20,
        },
      },
      {
        selector: ".graph-filtered",
        style: { display: "none" },
      },
      {
        selector: ".graph-search-muted, .graph-context-muted",
        style: { opacity: 0.075 },
      },
      {
        selector: "node.graph-match, node.graph-neighbor",
        style: {
          opacity: 1,
          "border-opacity": 0.9,
          "border-width": 2,
          "min-zoomed-font-size": 0,
          "z-index": 12,
        },
      },
      {
        selector: "edge.graph-active-edge",
        style: {
          opacity: 0.82,
          "line-color": "#e9c9b4",
          width: 1.7,
          "z-index": 10,
        },
      },
    ],
  });

  bindGraphInteractions();
  applyGraphFilters();
  if (hasCompleteLayout) {
    fitVisibleGraph(false);
  } else {
    runGraphLayout();
  }
}

function bindGraphInteractions() {
  knowledgeGraph.on("mouseover", "node", (event) => {
    focusGraphNeighborhood(event.target);
    updateGraphReadout(event.target);
  });
  knowledgeGraph.on("mouseout", "node", () => {
    clearGraphNeighborhood();
    const selected = knowledgeGraph.getElementById(state.graphSelectedId || "");
    if (selected.length) focusGraphNeighborhood(selected);
    else updateGraphReadout(null);
  });
  knowledgeGraph.on("tap", "node", (event) => {
    const node = event.target;
    state.graphSelectedId = node.id();
    knowledgeGraph.nodes().unselect();
    node.select();
    focusGraphNeighborhood(node);
    knowledgeGraph.animate(
      {
        center: { eles: node },
        zoom: Math.max(knowledgeGraph.zoom(), 1.05),
      },
      { duration: reducedMotion() ? 0 : 280 },
    );
    openPage(node.id()).then(queueGraphResize).catch((error) => showToast(error.message));
  });
  knowledgeGraph.on("tap", (event) => {
    if (event.target !== knowledgeGraph) return;
    state.graphSelectedId = null;
    knowledgeGraph.nodes().unselect();
    clearGraphNeighborhood();
    updateGraphReadout(null);
  });
  knowledgeGraph.on("dragfree", "node", saveGraphPositions);
}

function applyGraphFilters() {
  if (!knowledgeGraph) return;
  const category = state.graphCategory;
  const query = state.graphQuery.toLocaleLowerCase();
  knowledgeGraph.batch(() => {
    knowledgeGraph.elements().removeClass(
      "graph-filtered graph-search-muted graph-match graph-active-edge",
    );
    const hiddenNodes = knowledgeGraph.nodes().filter(
      (node) => category !== "all" && node.data("category") !== category,
    );
    hiddenNodes.addClass("graph-filtered");
    knowledgeGraph.edges().filter((edge) => (
      edge.source().hasClass("graph-filtered") || edge.target().hasClass("graph-filtered")
    )).addClass("graph-filtered");

    const visibleNodes = knowledgeGraph.nodes().not(".graph-filtered");
    if (query) {
      const matches = visibleNodes.filter((node) => graphNodeMatches(node, query));
      visibleNodes.not(matches).addClass("graph-search-muted");
      matches.addClass("graph-match");
      knowledgeGraph.edges().not(".graph-filtered").addClass("graph-search-muted");
      matches.connectedEdges().not(".graph-filtered").removeClass("graph-search-muted");
    }
  });
  updateGraphSummary();
}

function graphNodeMatches(node, query) {
  const searchable = [
    node.data("title"),
    node.data("short_title_ko"),
    node.data("short_title_en"),
    node.id(),
    ...node.data("tags"),
  ]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase();
  return searchable.includes(query);
}

function focusGraphMatches() {
  if (!knowledgeGraph || !state.graphQuery) return;
  const matches = knowledgeGraph.nodes(".graph-match").not(".graph-filtered");
  if (!matches.length) return;
  knowledgeGraph.animate(
    { fit: { eles: matches, padding: 110 } },
    { duration: reducedMotion() ? 0 : 280 },
  );
}

function focusGraphNeighborhood(node) {
  if (!knowledgeGraph || node.hasClass("graph-filtered")) return;
  clearGraphNeighborhood();
  const visible = knowledgeGraph.elements().not(".graph-filtered");
  const neighborhood = node.closedNeighborhood().not(".graph-filtered");
  visible.not(neighborhood).addClass("graph-context-muted");
  neighborhood.nodes().addClass("graph-neighbor");
  neighborhood.edges().addClass("graph-active-edge");
}

function clearGraphNeighborhood() {
  if (!knowledgeGraph) return;
  knowledgeGraph.elements().removeClass(
    "graph-context-muted graph-neighbor graph-active-edge",
  );
}

function updateGraphReadout(node) {
  const readout = document.querySelector("#graph-readout");
  if (!readout) return;
  if (!node) {
    readout.innerHTML = `<span>${t("graph.hint")}</span>`;
    return;
  }
  const degree = node.data("incoming_count") + node.data("outgoing_count");
  readout.innerHTML = `
    <strong>${escapeHtml(node.data("label"))}</strong>
    <span>${escapeHtml(categoryTitle(node.data("category")))} &middot; ${degree} connection${degree === 1 ? "" : "s"}</span>`;
}

function updateGraphSummary() {
  if (!knowledgeGraph) return;
  const summary = document.querySelector("#graph-summary");
  if (!summary) return;
  const visibleNodes = knowledgeGraph.nodes().not(".graph-filtered");
  const visibleEdges = knowledgeGraph.edges().not(".graph-filtered");
  const matches = knowledgeGraph.nodes(".graph-match").not(".graph-filtered");
  const suffix = state.graphQuery
    ? ` &middot; ${t("graph.matches", { count: matches.length })}`
    : "";
  summary.innerHTML = `${t("graph.filteredSummary", {
    notes: visibleNodes.length,
    links: visibleEdges.length,
  })}${suffix}`;
}

function fitVisibleGraph(animate = true) {
  if (!knowledgeGraph) return;
  const visible = knowledgeGraph.elements().not(".graph-filtered");
  if (!visible.length) return;
  const container = knowledgeGraph.container();
  const components = visible.components();
  const target = container.clientWidth < 520 && components.length > 1
    ? components.reduce((largest, component) => (
        component.nodes().length > largest.nodes().length ? component : largest
      ))
    : visible;
  if (!animate || reducedMotion()) {
    knowledgeGraph.fit(target, 64);
    return;
  }
  knowledgeGraph.animate({ fit: { eles: target, padding: 64 } }, { duration: 260 });
}

function runGraphLayout() {
  if (!knowledgeGraph) return;
  const layout = knowledgeGraph.layout({
    name: "cose",
    animate: reducedMotion() || knowledgeGraph.nodes().length > 450 ? false : "end",
    animationDuration: 620,
    randomize: true,
    componentSpacing: 96,
    nodeRepulsion: 8600,
    idealEdgeLength: 94,
    edgeElasticity: 110,
    nestingFactor: 1.1,
    gravity: 0.28,
    numIter: 1000,
    initialTemp: 180,
    coolingFactor: 0.96,
    minTemp: 1,
    fit: false,
  });
  knowledgeGraph.one("layoutstop", () => {
    saveGraphPositions();
    fitVisibleGraph();
  });
  layout.run();
}

function storedGraphPositions() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(GRAPH_POSITION_KEY) || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([, position]) => (
        position && Number.isFinite(position.x) && Number.isFinite(position.y)
      )),
    );
  } catch {
    return {};
  }
}

function saveGraphPositions() {
  if (!knowledgeGraph) return;
  const positions = {};
  knowledgeGraph.nodes().forEach((node) => {
    const position = node.position();
    positions[node.id()] = { x: position.x, y: position.y };
  });
  try {
    window.localStorage.setItem(GRAPH_POSITION_KEY, JSON.stringify(positions));
  } catch {
    // The graph remains usable when browser storage is unavailable.
  }
}

function clearStoredGraphPositions() {
  try {
    window.localStorage.removeItem(GRAPH_POSITION_KEY);
  } catch {
    // The current layout can still be recalculated in memory.
  }
}

function destroyKnowledgeGraph() {
  closeActiveSelectMenu(false);
  if (!knowledgeGraph) return;
  knowledgeGraph.destroy();
  knowledgeGraph = null;
}

function queueGraphResize(delay = 290) {
  window.clearTimeout(graphResizeTimer);
  graphResizeTimer = window.setTimeout(() => {
    if (!knowledgeGraph) return;
    knowledgeGraph.resize();
    fitVisibleGraph(false);
  }, delay);
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function categoryColor(category) {
  return GRAPH_COLORS[category] || "#879096";
}

function graphColorClass(category) {
  return `graph-color-${GRAPH_COLORS[category] ? category : "neutral"}`;
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
          <span>${t("count.pages", { count })}</span>
        </button>
      </div>`;
  }).join("")}</div>`;
}

function bindRows(root = document) {
  root.querySelectorAll("[data-session]").forEach((row) => {
    row.addEventListener("click", () => openSession(row.dataset.session));
  });
  root.querySelectorAll("[data-page]").forEach((row) => {
    row.addEventListener("click", () => openPage(row.dataset.page));
  });
  root.querySelectorAll("[data-project]").forEach((row) => {
    row.addEventListener("click", () => openProject(row.dataset.project));
  });
  root.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => renderKnowledge(button.dataset.category));
  });
}

function showDetailPeek(context, route, { fromHistory = false } = {}) {
  const wasOpen = document.body.classList.contains("has-detail-peek");
  const isSameRenderedRoute = detailPeekRoutesMatch(
    renderedDetailPeekRoute,
    route,
  );
  if (!wasOpen) {
    detailPeekRestoreTarget = document.activeElement;
    document.body.classList.remove("detail-peek-expanded");
    updateDetailPeekSizeControl();
  }
  if (!fromHistory && !detailPeekRouteMatches(route)) {
    window.history.pushState(
      { ...window.history.state, [DETAIL_PEEK_HISTORY_KEY]: route },
      "",
      detailPeekUrl(route),
    );
  }
  detailPeekContext.textContent = context;
  if (!isSameRenderedRoute) detailPeekContent.scrollTop = 0;
  renderedDetailPeekRoute = route;
  detailPeek.setAttribute("aria-hidden", "false");
  detailPeek.inert = false;
  document.body.classList.add("has-detail-peek");
  configureDetailPeekToc();
  if (!wasOpen) {
    window.requestAnimationFrame(() => {
      document.querySelector("#close-detail-peek").focus();
    });
  }
}

function detailPeekRouteMatches(route) {
  const activeRoute = window.history.state?.[DETAIL_PEEK_HISTORY_KEY];
  return detailPeekRoutesMatch(activeRoute, route);
}

function detailPeekRoutesMatch(left, right) {
  return Boolean(
    left
    && right
    && left.kind === right.kind
    && left.id === right.id
    && left.type === right.type,
  );
}

function detailPeekUrl(route) {
  if (route.kind === "page") {
    return `#/wiki/${encodeURIComponent(route.id)}`;
  }
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function hideDetailPeek({ restoreFocus = true } = {}) {
  document.body.classList.remove("has-detail-peek", "detail-peek-expanded");
  detailPeek.setAttribute("aria-hidden", "true");
  detailPeek.inert = true;
  state.selectedActivityId = null;
  renderedDetailPeekRoute = null;
  detailPeekHeadings = [];
  updateDetailPeekSizeControl();
  if (restoreFocus && detailPeekRestoreTarget?.isConnected) {
    detailPeekRestoreTarget.focus();
  }
  detailPeekRestoreTarget = null;
}

function closeDetailPeek() {
  if (window.history.state?.[DETAIL_PEEK_HISTORY_KEY]) {
    window.history.back();
    return;
  }
  if (window.location.hash.startsWith("#/wiki/")) {
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}`,
    );
  }
  hideDetailPeek();
}

function toggleDetailPeekSize() {
  document.body.classList.toggle("detail-peek-expanded");
  updateDetailPeekSizeControl();
}

function updateDetailPeekSizeControl() {
  const isExpanded = document.body.classList.contains("detail-peek-expanded");
  const label = isExpanded
    ? t("action.restoreDetail")
    : t("action.expandDetail");
  expandDetailPeekButton.setAttribute("aria-label", label);
  expandDetailPeekButton.title = label;
  expandDetailPeekButton.setAttribute("aria-pressed", String(isExpanded));
}

function configureDetailPeekToc() {
  detailPeekHeadings = [
    ...detailPeekContent.querySelectorAll(".markdown h2, .markdown h3"),
  ];
  detailPeekTocList.innerHTML = "";
  if (detailPeekHeadings.length < 2) {
    detailPeekToc.hidden = true;
    detailPeekBody.classList.remove("has-toc");
    detailPeekToc.classList.remove("is-open");
    return;
  }
  detailPeekHeadings.forEach((heading, index) => {
    if (!heading.id) heading.id = `awm-detail-heading-${index + 1}`;
    const headingText = heading.textContent.trim();
    const button = document.createElement("button");
    button.type = "button";
    button.className = `detail-peek-toc-link is-${heading.tagName.toLowerCase()}`;
    button.dataset.tocTarget = heading.id;
    button.textContent = headingText;
    button.title = headingText;
    button.addEventListener("click", () => scrollToDetailPeekHeading(heading));
    detailPeekTocList.append(button);
  });
  detailPeekToc.hidden = false;
  detailPeekBody.classList.add("has-toc");
  syncDetailPeekTocLayout();
  window.requestAnimationFrame(updateActiveDetailPeekHeading);
}

function toggleDetailPeekToc() {
  setDetailPeekTocExpanded(!detailPeekToc.classList.contains("is-open"));
}

function syncDetailPeekTocLayout() {
  if (detailPeekToc.hidden) return;
  setDetailPeekTocExpanded(!window.matchMedia("(max-width: 980px)").matches);
}

function setDetailPeekTocExpanded(isExpanded) {
  detailPeekToc.classList.toggle("is-open", isExpanded);
  detailPeekTocToggle.setAttribute("aria-expanded", String(isExpanded));
}

function scrollToDetailPeekHeading(heading) {
  heading.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth",
    block: "start",
  });
  setActiveDetailPeekHeading(heading.id);
  if (window.matchMedia("(max-width: 980px)").matches) {
    setDetailPeekTocExpanded(false);
  }
}

function updateActiveDetailPeekHeading() {
  if (detailPeekToc.hidden || detailPeekHeadings.length === 0) return;
  const readingLine = detailPeekContent.getBoundingClientRect().top + 120;
  let activeHeading = detailPeekHeadings[0];
  detailPeekHeadings.forEach((heading) => {
    if (heading.getBoundingClientRect().top <= readingLine) {
      activeHeading = heading;
    }
  });
  setActiveDetailPeekHeading(activeHeading.id);
}

function setActiveDetailPeekHeading(headingId) {
  detailPeekTocList.querySelectorAll("[data-toc-target]").forEach((button) => {
    const isActive = button.dataset.tocTarget === headingId;
    button.classList.toggle("is-active", isActive);
    if (isActive) {
      button.setAttribute("aria-current", "location");
    } else {
      button.removeAttribute("aria-current");
    }
  });
}

function handleDetailPeekKeydown(event) {
  if (!document.body.classList.contains("has-detail-peek")) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeDetailPeek();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...detailPeekDialog.querySelectorAll(
    "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
  )].filter((element) => element.getClientRects().length > 0);
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function restoreDetailPeekHistory() {
  const route = window.history.state?.[DETAIL_PEEK_HISTORY_KEY];
  if (route) {
    openDetailPeekRoute(route, { fromHistory: true });
    return;
  }
  if (window.location.hash.startsWith("#/wiki/")) {
    openHashTarget({ fromHistory: true });
    return;
  }
  hideDetailPeek();
}

function openDetailPeekRoute(route, options) {
  const openings = {
    activity: () => openScheduledActivity(route.id, options),
    build: () => openBuildWiki(options),
    page: () => openPage(route.id, options),
    project: () => openProject(route.id, options),
    receipt: () => openReceipt(route.id, route.type, options),
    session: () => openSession(route.id, options),
  };
  const openRoute = openings[route.kind];
  if (!openRoute) {
    hideDetailPeek();
    return;
  }
  Promise.resolve(openRoute()).catch((error) => showToast(error.message));
}

function bindWikiLinks() {
  detailPeekContent.querySelectorAll("a[href^='#/wiki/']").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const prefix = "#/wiki/";
      const path = decodeURIComponent(link.getAttribute("href").slice(prefix.length));
      openPage(path).catch((error) => showToast(error.message));
    });
  });
}

async function openProject(path, options = {}) {
  const locale = requestedPageLocale(path);
  const detail = await api(`/api/project?path=${encodeURIComponent(path)}&locale=${locale}`);
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${t("detail.projectHub")}</p>
    <h2 id="detail-peek-title">${escapeHtml(detail.page.title)}</h2>
    <div class="detail-meta">
      <span>${t("count.topicPages", { count: detail.topics.length })}</span>
      <span>${t("count.sourceSessions", { count: detail.sessions.length })}</span>
    </div>
    ${translationControls(detail.page, path)}
    <article class="markdown">${detail.page.html}</article>
    <section class="detail-section">
      <p class="eyebrow">${t("section.topics")}</p>
      <div class="record-list">${detail.topics.map(pageRow).join("") || emptyRow(t("empty.topicPages"))}</div>
    </section>
    <section class="detail-section">
      <p class="eyebrow">${t("section.evidence")}</p>
      <div class="record-list">${detail.sessions.map(sessionRow).join("") || emptyRow(t("empty.sourceSessions"))}</div>
    </section>
  `;
  showDetailPeek(t("detail.projectHub"), { kind: "project", id: path }, options);
  bindRows(detailPeekContent);
  bindWikiLinks();
  bindPageLanguageControl(path);
}

async function openSession(sessionId, options = {}) {
  const detail = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(t("session.provider", { provider: detail.session.provider }))}</p>
    <h2 id="detail-peek-title">${escapeHtml(detail.session.title)}</h2>
    <div class="detail-meta">
      <span>${t("count.events", { count: detail.session.event_count })}</span>
      <span>${detail.session.content_captured ? t("session.contentRetained") : t("session.metadataOnly")}</span>
      <span>${detail.session.distilled_at ? t("session.distilled") : t("session.notDistilled")}</span>
    </div>
    ${detail.workspace ? `<p class="quiet">${escapeHtml(detail.workspace)}</p>` : ""}
    ${detail.session.content_captured ? distillControls(detail.session.session_id) : ""}
    <div class="events">${detail.events.map(eventBlock).join("") || `<p class="quiet">${t("session.noEvents")}</p>`}</div>
  `;
  showDetailPeek(t("detail.sourceSession"), { kind: "session", id: sessionId }, options);
  const distillButton = document.querySelector("#distill-button");
  if (distillButton) distillButton.addEventListener("click", distillSelected);
}

async function openPage(path, options = {}) {
  const locale = requestedPageLocale(path);
  const detail = await api(`/api/page?path=${encodeURIComponent(path)}&locale=${locale}`);
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(categoryTitle(detail.category))}</p>
    <h2 id="detail-peek-title">${escapeHtml(detail.title)}</h2>
    <div class="detail-meta">
      <span>${escapeHtml(detail.path)}</span>
      <span>${t("wiki.backlinks", { count: detail.backlinks.length })}</span>
    </div>
    ${translationControls(detail, path)}
    <article class="markdown">${detail.html}</article>
    ${detail.backlinks.length ? `
      <div class="section-block">
        <p class="eyebrow">${t("wiki.linkedFrom")}</p>
        ${detail.backlinks.map(pageRow).join("")}
      </div>` : ""}
  `;
  showDetailPeek(t("wiki.page"), { kind: "page", id: path }, options);
  bindRows(detailPeekContent);
  bindWikiLinks();
  bindPageLanguageControl(path);
}

function requestedPageLocale(path) {
  return state.pageLocaleOverrides[path] || state.locale;
}

function translationControls(detail, path) {
  const requestedName = localeName(detail.requested_locale, state.locale);
  const notices = {
    missing: t("wiki.translationMissing", { language: requestedName }),
    invalid: t("wiki.translationInvalid", { language: requestedName }),
    stale: t("wiki.translationStale"),
  };
  const notice = notices[detail.translation_status];
  let target = null;
  let label = null;
  if (detail.resolved_locale !== detail.original_locale) {
    target = detail.original_locale;
    label = t("action.original");
  } else if (
    state.locale !== detail.original_locale
    && requestedPageLocale(path) === detail.original_locale
  ) {
    target = state.locale;
    label = t("action.translation", {
      language: localeName(state.locale, state.locale),
    });
  }
  if (!notice && !target) return "";
  return `
    <div class="translation-state ${detail.translation_status === "stale" ? "is-stale" : ""}">
      ${notice ? `<span>${escapeHtml(notice)}</span>` : "<span></span>"}
      ${target ? `<button type="button" data-page-locale="${target}">${escapeHtml(label)}</button>` : ""}
    </div>`;
}

function bindPageLanguageControl(path) {
  const button = detailPeekContent.querySelector("[data-page-locale]");
  if (!button) return;
  button.addEventListener("click", () => {
    const locale = button.dataset.pageLocale;
    if (locale === state.locale) delete state.pageLocaleOverrides[path];
    else state.pageLocaleOverrides[path] = locale;
    const route = renderedDetailPeekRoute;
    if (route?.kind === "project") openProject(path, { fromHistory: true });
    else openPage(path, { fromHistory: true });
  });
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

function openScheduledActivity(activityId, options = {}) {
  const run = state.activity.find((item) => item.activity_id === activityId);
  if (!run) return;
  const isRefreshingSelection = state.selectedActivityId === activityId;
  const detailPeekScroll = isRefreshingSelection
    ? captureEndAwareScroll(detailPeekContent)
    : null;
  const logScroll = isRefreshingSelection
    ? captureEndAwareScroll(detailPeekContent.querySelector("[data-live-log]"))
    : null;
  state.selectedActivityId = activityId;
  const finished = run.finished_at || new Date().toISOString();
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(activityTaskLabel(run.task))}</p>
    <h2 id="detail-peek-title">${escapeHtml(activityStatusLabel(run.status))}</h2>
    <div class="detail-meta">
      <span>${t("activity.started")} ${escapeHtml(formatMoment(run.started_at))}</span>
      <span>${run.finished_at ? t("activity.ended", { time: escapeHtml(formatMoment(run.finished_at)) }) : t("activity.inProgress")}</span>
      <span>${escapeHtml(durationBetween(run.started_at, finished))}</span>
    </div>
    <div class="activity-timeline">
      ${timelineStep(t("activity.started"), run.started_at, true)}
      ${timelineStep(run.summary, run.finished_at || "Now", run.status !== "failed", run.status === "running")}
      ${run.finished_at ? timelineStep(activityStatusLabel(run.status), run.finished_at, run.status === "succeeded") : ""}
    </div>
    <section class="activity-log">
      <div class="activity-log-heading">
        <p class="eyebrow">${t("section.recentLog")}</p>
        <span>${t("count.lines", { count: run.log_lines.length })}</span>
      </div>
      <pre data-live-log tabindex="0" aria-label="${t("section.recentLog")}">${escapeHtml(run.log_lines.join("\n") || t("activity.waitingLog"))}</pre>
    </section>
  `;
  showDetailPeek(
    t("detail.scheduledActivity"),
    { kind: "activity", id: activityId },
    options,
  );
  restoreEndAwareScroll(
    detailPeekContent.querySelector("[data-live-log]"),
    logScroll,
  );
  restoreEndAwareScroll(detailPeekContent, detailPeekScroll);
}

function captureEndAwareScroll(element) {
  if (!element) return null;
  const distanceFromEnd =
    element.scrollHeight - element.clientHeight - element.scrollTop;
  return {
    followsEnd: distanceFromEnd <= 24,
    scrollTop: element.scrollTop,
  };
}

function restoreEndAwareScroll(element, snapshot) {
  if (!element) return;
  element.scrollTop = snapshot && !snapshot.followsEnd
    ? snapshot.scrollTop
    : element.scrollHeight;
}

function openReceipt(runId, type, options = {}) {
  const collection = type === "sync"
    ? state.receipts.sync
    : state.receipts.distill;
  const receipt = collection.find((item) => item.run_id === runId);
  if (!receipt) return;
  state.selectedActivityId = null;
  const changed = receipt.changed_files
    ? `${receipt.changed_files.length} Wiki files`
    : `${receipt.events_added} new events`;
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${escapeHtml(activityTaskLabel(type))} receipt</p>
    <h2 id="detail-peek-title">${escapeHtml(activityStatusLabel(receipt.status))}</h2>
    <div class="detail-meta">
      <span>${escapeHtml(receipt.run_id)}</span>
      <span>${escapeHtml(changed)}</span>
      <span>${escapeHtml(durationBetween(receipt.started_at, receipt.finished_at))}</span>
    </div>
    <div class="activity-timeline">
      ${timelineStep(t("activity.started"), receipt.started_at, true)}
      ${timelineStep(activityStatusLabel(receipt.status), receipt.finished_at, receipt.status === "succeeded")}
    </div>
    ${distillOutcomeDetails(receipt)}
  `;
  showDetailPeek(
    t("detail.runReceipt"),
    { kind: "receipt", id: runId, type },
    options,
  );
}

function distillOutcomeDetails(receipt) {
  if (!receipt.session_outcomes || receipt.session_outcomes.length === 0) return "";
  return `
    <div class="detail-section">
      <div class="section-heading">
        <p class="eyebrow">${t("section.sessionOutcomes")}</p>
        <span>${t("count.reviewed", { count: receipt.session_outcomes.length })}</span>
      </div>
      <div class="record-list">
        ${receipt.session_outcomes.map((outcome) => `
          <div class="record-row">
            <div>
              <strong>${escapeHtml(distillDispositionLabel(outcome.disposition))}</strong>
              <span>${escapeHtml(outcome.reason)}</span>
              ${outcome.pages.length
                ? `<span>${escapeHtml(outcome.pages.join(", "))}</span>`
                : ""}
            </div>
            <span>${escapeHtml(outcome.session_id)}</span>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function distillDispositionLabel(value) {
  return {
    created: "Created",
    merged: "Merged",
    "already-covered": "Already covered",
    "no-durable-knowledge": "No durable knowledge",
  }[value] || value;
}

async function search(event) {
  event.preventDefault();
  const query = document.querySelector("#search-input").value.trim();
  if (!query) return;
  const results = await api(`/api/search?q=${encodeURIComponent(query)}`);
  destroyKnowledgeGraph();
  state.view = "search";
  workspace.classList.remove("graph-workspace");
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.remove("is-active"));
  workspace.innerHTML = `
    <header class="view-header">
      <div>
        <p class="eyebrow">${t("search.resultsEyebrow")}</p>
        <h1>${escapeHtml(query)}</h1>
      </div>
      <p class="quiet">${t("count.results", { count: results.length })}</p>
    </header>
    <div class="record-list">${results.map(searchRow).join("") || emptyRow(t("empty.search"))}</div>
  `;
  bindRows();
}

async function syncTranscripts() {
  syncButton.classList.add("is-busy");
  syncButton.textContent = t("sync.running");
  try {
    const receipt = await api("/api/sync", {
      method: "POST",
      headers: actionHeaders(),
      body: JSON.stringify({ include_content: true }),
    });
    await refreshData();
    render();
    showToast(t("sync.retained", { count: receipt.events_added }));
  } catch (error) {
    showToast(error.message);
  } finally {
    syncButton.classList.remove("is-busy");
    syncButton.textContent = t("action.sync");
  }
}

function openBuildWiki(options = {}) {
  detailPeekContent.innerHTML = `
    <p class="eyebrow">${t("build.eyebrow")}</p>
    <h2 id="detail-peek-title">${t("build.title")}</h2>
    <div class="detail-meta">
      <span>${t("build.waiting", { count: state.overview.pending_distill_count })}</span>
      <span>${t("build.projectHubs", { count: state.projects.length })}</span>
    </div>
    <p class="quiet">${t("build.description")}</p>
    ${buildWikiControls()}
  `;
  showDetailPeek(t("detail.wikiWorkflow"), { kind: "build", id: "pending" }, options);
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
    showToast(t("build.choosePermission"));
    return;
  }
  button.classList.add("is-busy");
  button.textContent = t("build.running");
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
    showToast(t("build.changed", { count: receipt.changed_files.length }));
  } catch (error) {
    showToast(error.message);
    button.classList.remove("is-busy");
    button.textContent = t("control.buildNext");
  }
}

async function distillSelected() {
  const button = document.querySelector("#distill-button");
  const runtime = document.querySelector("#distill-runtime").value;
  const model = document.querySelector("#distill-model").value.trim() || null;
  const contentAccess = document.querySelector("#distill-access").value;
  button.classList.add("is-busy");
  button.textContent = t("distill.running");
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
    showToast(t("distill.changed", { count: receipt.changed_files.length }));
    await openSession(button.dataset.session);
  } catch (error) {
    showToast(error.message);
    button.classList.remove("is-busy");
    button.textContent = t("distill.selected");
  }
}

function openHashTarget(options = {}) {
  const prefix = "#/wiki/";
  if (!window.location.hash.startsWith(prefix)) return;
  const path = decodeURIComponent(window.location.hash.slice(prefix.length));
  openPage(path, options).catch((error) => showToast(error.message));
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
        <span class="record-meta">${escapeHtml(session.provider)} · ${t("count.events", { count: session.event_count })}</span>
      </span>
      <span class="record-side">${relativeTime(session.modified_at)}</span>
    </button>`;
}

function pageRow(page) {
  return `
    <button class="record-row" type="button" data-page="${escapeHtml(page.path)}">
      <span>
        <span class="record-title">${escapeHtml(pageLabel(page, state.locale))}</span>
        <span class="record-meta">${escapeHtml(categoryTitle(page.category))}${page.tags.length ? ` · ${escapeHtml(page.tags.join(", "))}` : ""}</span>
      </span>
      <span class="record-side">${t("wiki.backlinks", { count: page.backlink_count })}</span>
    </button>`;
}

function projectRow(project) {
  const page = state.pages.find((item) => item.path === project.path);
  const title = page ? pageLabel(page, state.locale) : project.title;
  return `
    <button class="record-row project-row" type="button" data-project="${escapeHtml(project.path)}">
      <span>
        <span class="record-title">${escapeHtml(title)}</span>
        <span class="record-meta">${t("count.topics", { count: project.topic_count })} · ${t("count.sources", { count: project.source_session_ids.length })}</span>
      </span>
      <span class="record-side">${t("action.openProject")}</span>
    </button>`;
}

function searchRow(result) {
  const page = result.kind === "wiki"
    ? state.pages.find((item) => item.path === result.identity)
    : null;
  const title = page ? pageLabel(page, state.locale) : result.title;
  const attribute = result.kind === "session"
    ? `data-session="${escapeHtml(result.identity)}"`
    : `data-page="${escapeHtml(result.identity)}"`;
  return `
    <button class="record-row" type="button" ${attribute}>
      <span>
        <span class="record-title">${escapeHtml(title)}</span>
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
      <select id="distill-runtime" aria-label="${t("control.runtime")}">
        <option value="ollama">Ollama · local</option>
        <option value="codex">Codex · remote</option>
        <option value="claude">Claude · remote</option>
      </select>
      <input id="distill-model" placeholder="${t("control.modelOllama")}" aria-label="${t("control.model")}">
      <select id="distill-access" aria-label="${t("control.contentPermission")}">
        <option value="metadata-only">${t("control.metadataOnly")}</option>
        <option value="selected-local">${t("control.selectedLocal")}</option>
        <option value="selected-remote">${t("control.selectedRemote")}</option>
      </select>
      <button id="distill-button" class="primary-action" type="button" data-session="${escapeHtml(sessionId)}">
        ${t("distill.selected")}
      </button>
    </div>`;
}

function buildWikiControls() {
  const disabled = state.overview.pending_distill_count === 0 ? "disabled" : "";
  return `
    <div class="distill-controls build-wiki-controls">
      <label>
        <span>${t("control.runtime")}</span>
        <select id="build-runtime" aria-label="${t("control.runtime")}">
          <option value="codex">Codex · remote</option>
          <option value="ollama">Ollama · local</option>
          <option value="claude">Claude · remote</option>
        </select>
      </label>
      <label>
        <span>${t("control.batchSize")}</span>
        <select id="build-limit" aria-label="${t("control.batchSize")}">
          <option value="5">${t("control.sessions", { count: 5 })}</option>
          <option value="10" selected>${t("control.sessions", { count: 10 })}</option>
          <option value="20">${t("control.sessions", { count: 20 })}</option>
        </select>
      </label>
      <label class="control-wide">
        <span>${t("control.model")}</span>
        <input id="build-model" placeholder="${t("control.modelOllama")}" aria-label="${t("control.model")}">
      </label>
      <label class="control-wide">
        <span>${t("control.contentPermission")}</span>
        <select id="build-access" aria-label="${t("control.contentPermission")}">
          <option value="" selected disabled>${t("control.choosePermission")}</option>
          <option value="metadata-only">${t("control.metadataOnly")}</option>
          <option value="selected-local">${t("control.selectedLocal")}</option>
          <option value="selected-remote">${t("control.selectedRemote")}</option>
        </select>
      </label>
      <button id="build-pending-button" class="primary-action" type="button" ${disabled}>
        ${disabled ? t("control.nothingWaiting") : t("control.buildNext")}
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
        <small>${moment === "Now" ? t("activity.now") : escapeHtml(formatMoment(moment))}</small>
      </span>
    </div>`;
}

function activityTaskLabel(value) {
  const labels = {
    sync: t("activity.sync"),
    "auto-distill": t("activity.distill"),
    distill: t("activity.distill"),
  };
  return labels[value] || value;
}

function activityStatusLabel(value) {
  const labels = {
    running: t("activity.running"),
    succeeded: t("activity.succeeded"),
    skipped: t("activity.skipped"),
    failed: t("activity.failed"),
    skipped_locked: t("activity.skipped"),
  };
  return labels[value] || value;
}

function formatMoment(value) {
  if (!value) return t("time.notFinished");
  return new Intl.DateTimeFormat(state.locale === "ko" ? "ko-KR" : "en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatScheduleMoment(value) {
  if (!value) return t("time.notScheduled");
  return new Intl.DateTimeFormat(state.locale === "ko" ? "ko-KR" : "en", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function durationBetween(start, finish) {
  if (!start || !finish) return t("time.durationUnavailable");
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
  const key = `category.${value}`;
  const label = t(key);
  return label === key ? value : label;
}

function relativeTime(value) {
  if (!value) return t("time.never");
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(
    state.locale === "ko" ? "ko-KR" : "en",
    { numeric: "auto" },
  );
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return formatter.format(Math.round(seconds / size), unit);
  }
  return t("time.justNow");
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
