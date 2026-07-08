const state = {
  projects: [],
  project: null,
  activity: [],
  selectedKey: "seed",
  reviewTab: "script",
  running: false,
  projectFilters: {
    search: "",
    status: "",
  },
  projectListRequestId: 0,
};

const el = {
  seedText: document.querySelector("#seedText"),
  createProject: document.querySelector("#createProject"),
  refreshProjects: document.querySelector("#refreshProjects"),
  exportProject: document.querySelector("#exportProject"),
  runProject: document.querySelector("#runProject"),
  projectSearch: document.querySelector("#projectSearch"),
  projectStatusFilter: document.querySelector("#projectStatusFilter"),
  projectList: document.querySelector("#projectList"),
  nodeLayer: document.querySelector("#nodeLayer"),
  edgeLayer: document.querySelector("#edgeLayer"),
  canvasTitle: document.querySelector("#canvasTitle"),
  canvasMeta: document.querySelector("#canvasMeta"),
  projectStatus: document.querySelector("#projectStatus"),
  inspectorBody: document.querySelector("#inspectorBody"),
  scriptPreview: document.querySelector("#scriptPreview"),
  reviewTabs: document.querySelectorAll(".review-tab"),
  activityTimeline: document.querySelector("#activityTimeline"),
  seedPanel: document.querySelector(".seed-panel"),
};

el.createProject.addEventListener("click", createProject);
el.refreshProjects.addEventListener("click", loadProjects);
el.exportProject.addEventListener("click", downloadProjectExport);
el.runProject.addEventListener("click", runProject);
el.projectSearch.addEventListener("input", applyProjectFilters);
el.projectStatusFilter.addEventListener("change", applyProjectFilters);
el.reviewTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    state.reviewTab = tab.dataset.reviewTab;
    renderScript();
  });
});

loadProjects();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || "Request failed");
  }
  return body;
}

async function loadProjects() {
  try {
    const requestId = state.projectListRequestId + 1;
    state.projectListRequestId = requestId;
    const currentProjectId = state.project?.id;
    const body = await api(`/api/projects${projectListQuery()}`);
    if (requestId !== state.projectListRequestId) return;

    state.projects = body.projects;
    const selectedProjectIsVisible = state.projects.some(
      (project) => project.id === currentProjectId,
    );
    if (state.projects.length > 0 && (!state.project || !selectedProjectIsVisible)) {
      await loadProject(state.projects[0].id);
      return;
    }
    if (state.projects.length === 0 && !selectedProjectIsVisible) {
      state.project = null;
      state.activity = [];
      state.selectedKey = "seed";
      render();
      return;
    }
    renderProjects();
  } catch (error) {
    showError(error.message);
  }
}

async function loadProject(projectId) {
  try {
    const body = await api(`/api/projects/${projectId}`);
    state.project = body.project;
    state.activity = body.activity || [];
    state.selectedKey = state.project.nodes.find((node) => node.key === state.selectedKey)
      ? state.selectedKey
      : "seed";
    render();
  } catch (error) {
    showError(error.message);
  }
}

async function createProject() {
  const seedText = el.seedText.value.trim();
  if (!seedText) {
    showError("请输入一句话。");
    return;
  }

  setBusy(true);
  try {
    const body = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({ seed_text: seedText, brief: briefFromForm(el.seedPanel) }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.selectedKey = "seed";
    el.seedText.value = "";
    resetProjectFilters();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

function applyProjectFilters() {
  state.projectFilters.search = el.projectSearch.value.trim();
  state.projectFilters.status = el.projectStatusFilter.value;
  loadProjects();
}

function resetProjectFilters() {
  state.projectFilters.search = "";
  state.projectFilters.status = "";
  el.projectSearch.value = "";
  el.projectStatusFilter.value = "";
}

function projectListQuery() {
  const params = new URLSearchParams();
  if (state.projectFilters.search) {
    params.set("q", state.projectFilters.search);
  }
  if (state.projectFilters.status) {
    params.set("status", state.projectFilters.status);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function runProject() {
  if (!state.project) return;
  setBusy(true);
  state.project.status = "running";
  render();

  try {
    const body = await api(`/api/projects/${state.project.id}/run`, { method: "POST" });
    state.project = body.project;
    state.activity = body.activity || [];
    state.selectedKey = "script";
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
    await loadProject(state.project.id);
  } finally {
    setBusy(false);
  }
}

async function saveDraftEdits(event) {
  event.preventDefault();
  if (!state.project || state.project.status !== "draft") return;

  const form = event.currentTarget;
  const title = form.querySelector("[name='title']").value;
  const seedText = form.querySelector("[name='seed_text']").value.trim();
  if (!seedText) {
    showError("一句话不能为空。");
    return;
  }

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title, seed_text: seedText, brief: briefFromForm(form) }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.selectedKey = "seed";
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function downloadProjectExport() {
  if (!state.project || !projectCanExport(state.project)) return;

  setBusy(true);
  try {
    const response = await fetch(`/api/projects/${state.project.id}/export`);
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = exportFileName(state.project);
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

function render() {
  renderHeader();
  renderProjects();
  renderCanvas();
  renderInspector();
  renderScript();
  renderActivity();
}

function renderHeader() {
  const project = state.project;
  el.runProject.disabled = !project || state.running || project.status === "running";
  el.exportProject.disabled = !project || state.running || !projectCanExport(project);
  el.canvasTitle.textContent = project?.title || "Untitled";
  el.canvasMeta.textContent = project ? `#${project.id} · ${project.status}` : "";
  el.projectStatus.textContent = project ? project.status : "Ready";
}

function renderProjects() {
  if (!state.projects.length) {
    el.projectList.innerHTML = `<div class="empty">No projects</div>`;
    return;
  }
  el.projectList.innerHTML = state.projects
    .map((project) => {
      const active = state.project?.id === project.id ? " active" : "";
      const title = escapeHtml(project.title || project.seed_text);
      return `
        <button class="project-row${active}" data-project-id="${project.id}">
          <strong>${title}</strong>
          <span>#${project.id} · ${escapeHtml(project.status)}</span>
        </button>
      `;
    })
    .join("");

  el.projectList.querySelectorAll(".project-row").forEach((button) => {
    button.addEventListener("click", () => loadProject(button.dataset.projectId));
  });
}

function renderCanvas() {
  const project = state.project;
  if (!project) {
    el.nodeLayer.innerHTML = "";
    el.edgeLayer.innerHTML = "";
    return;
  }

  const nodeMap = new Map(project.nodes.map((node) => [node.key, node]));
  el.edgeLayer.innerHTML = project.edges
    .map((edge) => {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) return "";
      const sx = source.x + 220;
      const sy = source.y + 65;
      const tx = target.x;
      const ty = target.y + 65;
      const mx = sx + Math.max(60, (tx - sx) / 2);
      return `<path class="edge-path" d="M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}" />`;
    })
    .join("");

  el.nodeLayer.innerHTML = project.nodes.map(renderNode).join("");
  el.nodeLayer.querySelectorAll(".canvas-node").forEach((node) => {
    node.addEventListener("click", () => {
      state.selectedKey = node.dataset.nodeKey;
      render();
    });
  });
}

function renderNode(node) {
  const selected = state.selectedKey === node.key ? " selected" : "";
  const statusClass = `status-${node.status}`;
  return `
    <button class="canvas-node${selected}" data-node-key="${node.key}" style="left:${node.x}px;top:${node.y}px">
      <div class="node-kind">
        <span>${escapeHtml(node.kind)}</span>
        <span class="status-pill ${statusClass}">${escapeHtml(node.status)}</span>
      </div>
      <div class="node-title">${escapeHtml(node.title)}</div>
      <div class="node-summary">${escapeHtml(summaryForNode(node))}</div>
    </button>
  `;
}

function renderInspector() {
  const node = selectedNode();
  if (!node) {
    el.inspectorBody.innerHTML = `<div class="empty">No node selected</div>`;
    return;
  }

  if (node.key === "seed" && state.project?.status === "draft") {
    const seedText = node.output?.text || state.project.seed_text;
    el.inspectorBody.innerHTML = `
      <form id="draftEditor" class="draft-editor">
        <label for="draftTitle">Title</label>
        <input
          id="draftTitle"
          name="title"
          maxlength="120"
          value="${escapeHtml(state.project.title || "")}"
          placeholder="未命名短剧"
        />
        <label for="draftSeed">一句话</label>
        <textarea id="draftSeed" name="seed_text" rows="8">${escapeHtml(seedText)}</textarea>
        ${renderBriefFields(state.project.brief)}
        <button class="primary-button full-width" type="submit">保存草稿</button>
      </form>
    `;
    el.inspectorBody.querySelector("#draftEditor").addEventListener("submit", saveDraftEdits);
    return;
  }

  const output = node.output ? JSON.stringify(node.output, null, 2) : "";
  el.inspectorBody.innerHTML = `
    <div class="kv">
      <div class="kv-row">
        <div class="kv-key">Node</div>
        <div class="kv-value">${escapeHtml(node.title)}</div>
      </div>
      <div class="kv-row">
        <div class="kv-key">Status</div>
        <div class="kv-value">${escapeHtml(node.status)}</div>
      </div>
      ${
        node.error
          ? `<div class="kv-row"><div class="kv-key">Error</div><div class="kv-value">${escapeHtml(node.error)}</div></div>`
          : ""
      }
      <div class="kv-row">
        <div class="kv-key">Output</div>
        <div class="kv-value">${output ? `<pre>${escapeHtml(output)}</pre>` : "—"}</div>
      </div>
    </div>
  `;
}

function renderScript() {
  const script = state.project?.nodes.find((node) => node.key === "script")?.output;
  const production = state.project?.nodes.find((node) => node.key === "production")?.output;
  renderReviewTabs(Boolean(script), Boolean(production));
  if (!script) {
    el.scriptPreview.innerHTML = `<div class="empty">No generated script</div>`;
    return;
  }

  if (state.reviewTab === "characters") {
    renderCharacterReview(script);
    return;
  }
  if (state.reviewTab === "production") {
    renderProductionReview(script, production);
    return;
  }

  renderScriptReview(script);
}

function renderReviewTabs(hasScript, hasProduction) {
  if (state.reviewTab === "production" && !hasProduction) {
    state.reviewTab = "script";
  }
  el.reviewTabs.forEach((tab) => {
    const isActive = tab.dataset.reviewTab === state.reviewTab;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
    tab.disabled = !hasScript || (tab.dataset.reviewTab === "production" && !hasProduction);
  });
}

function renderScriptReview(script) {
  const scenes = script.scenes
    .map(
      (scene) => `
        <article class="scene">
          <div class="scene-head">
            <strong>${scene.scene_number}. ${escapeHtml(scene.setting)}</strong>
            <span>${escapeHtml(scene.time)}</span>
          </div>
          <p>${escapeHtml(scene.summary)}</p>
          <div class="dialogue-list">
            ${scene.dialogue.map(renderDialogueLine).join("")}
          </div>
        </article>
      `,
    )
    .join("");
  const outline = script.episode_outline
    .map(
      (beat, index) => `
        <div class="outline-item">
          <span>${index + 1}</span>
          <div>
            <strong>${escapeHtml(beat.beat)}</strong>
            <p>${escapeHtml(beat.purpose)}</p>
          </div>
        </div>
      `,
    )
    .join("");
  el.scriptPreview.innerHTML = `
    <div class="kv">
      <div class="kv-row">
        <div class="kv-key">Title</div>
        <div class="kv-value">${escapeHtml(script.title)}</div>
      </div>
      <div class="kv-row">
        <div class="kv-key">Logline</div>
        <div class="kv-value">${escapeHtml(script.logline)}</div>
      </div>
      <div class="kv-row">
        <div class="kv-key">Format</div>
        <div class="kv-value">
          ${escapeHtml(script.genre)} · ${escapeHtml(script.runtime_minutes)} min · ${escapeHtml(script.content_rating)}
        </div>
      </div>
    </div>
    <div class="tag-list">${script.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
    <div class="review-section">
      <h3>Episode Beats</h3>
      <div class="outline-list">${outline}</div>
    </div>
    <div class="review-section">
      <h3>Scenes & Dialogue</h3>
      ${scenes}
    </div>
  `;
}

function renderCharacterReview(script) {
  const characters = script.characters
    .map(
      (character) => `
        <article class="character-card">
          <div class="character-head">
            <strong>${escapeHtml(character.name)}</strong>
            <span>${escapeHtml(character.age)} · ${escapeHtml(character.role)}</span>
          </div>
          <dl>
            <dt>Desire</dt>
            <dd>${escapeHtml(character.desire)}</dd>
            <dt>Secret</dt>
            <dd>${escapeHtml(character.secret)}</dd>
            <dt>Voice</dt>
            <dd>${escapeHtml(character.voice)}</dd>
          </dl>
        </article>
      `,
    )
    .join("");
  const engine = script.story_engine;
  el.scriptPreview.innerHTML = `
    <div class="review-section">
      <h3>Characters</h3>
      <div class="character-grid">${characters}</div>
    </div>
    <div class="review-section">
      <h3>Story Engine</h3>
      <div class="engine-grid">
        ${renderEngineItem("Hook", engine.hook)}
        ${renderEngineItem("Conflict", engine.conflict)}
        ${renderEngineItem("Turn", engine.turning_point)}
        ${renderEngineItem("Climax", engine.climax)}
        ${renderEngineItem("Ending", engine.ending)}
      </div>
    </div>
  `;
}

function renderProductionReview(script, production) {
  const notes = script.production_notes;
  const shotPlan = production.shot_plan
    .map(
      (shot) => `
        <article class="shot-card">
          <strong>${escapeHtml(shot.shot)}</strong>
          <span>${escapeHtml(shot.duration_seconds)}s</span>
          <p>${escapeHtml(shot.purpose)}</p>
        </article>
      `,
    )
    .join("");
  el.scriptPreview.innerHTML = `
    <div class="review-section">
      <h3>Production Pack</h3>
      <div class="kv">
        <div class="kv-row">
          <div class="kv-key">Visual Style</div>
          <div class="kv-value">${escapeHtml(production.visual_style)}</div>
        </div>
        <div class="kv-row">
          <div class="kv-key">Shooting Style</div>
          <div class="kv-value">${escapeHtml(notes.shooting_style)}</div>
        </div>
      </div>
    </div>
    <div class="review-section">
      <h3>Checklist</h3>
      ${renderChecklist("Locations", production.locations)}
      ${renderChecklist("Props", production.props)}
      ${renderChecklist("Edit Notes", production.edit_notes)}
      ${renderChecklist("Risk Flags", notes.risk_flags)}
    </div>
    <div class="review-section">
      <h3>Shot Plan</h3>
      <div class="shot-list">${shotPlan}</div>
    </div>
  `;
}

function renderDialogueLine(line) {
  return `
    <div class="dialogue-line">
      <strong>${escapeHtml(line.speaker)}</strong>
      <p>${escapeHtml(line.line)}</p>
      <span>${escapeHtml(line.direction)}</span>
    </div>
  `;
}

function renderEngineItem(label, value) {
  return `
    <div class="engine-item">
      <span>${escapeHtml(label)}</span>
      <p>${escapeHtml(value)}</p>
    </div>
  `;
}

function renderChecklist(label, items) {
  return `
    <div class="checklist">
      <strong>${escapeHtml(label)}</strong>
      <ul>
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function renderBriefFields(brief = {}) {
  const values = brief || {};
  return `
    <div class="brief-grid">
      <label for="draftDuration">时长</label>
      <select id="draftDuration" name="duration_minutes">
        ${renderOption("3", "3 分钟", values.duration_minutes)}
        ${renderOption("5", "5 分钟", values.duration_minutes)}
        ${renderOption("8", "8 分钟", values.duration_minutes)}
      </select>
      <label for="draftAspect">画幅</label>
      <select id="draftAspect" name="aspect_ratio">
        ${renderOption("9:16 vertical", "9:16 竖屏", values.aspect_ratio)}
        ${renderOption("1:1 square", "1:1 方屏", values.aspect_ratio)}
        ${renderOption("16:9 landscape", "16:9 横屏", values.aspect_ratio)}
      </select>
      <label for="draftTone">语气</label>
      <input id="draftTone" name="tone" maxlength="80" value="${escapeHtml(values.tone || "")}" />
      <label for="draftAudience">观众</label>
      <input
        id="draftAudience"
        name="target_audience"
        maxlength="120"
        value="${escapeHtml(values.target_audience || "")}"
      />
      <label for="draftMustInclude">必含要素</label>
      <textarea id="draftMustInclude" name="must_include" rows="3" maxlength="500">${escapeHtml(
        values.must_include || "",
      )}</textarea>
    </div>
  `;
}

function renderOption(value, label, selectedValue) {
  const selected = String(selectedValue || "") === value ? " selected" : "";
  return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(label)}</option>`;
}

function briefFromForm(container) {
  const duration = container.querySelector("[name='duration_minutes']")?.value;
  const brief = {
    duration_minutes: duration ? Number(duration) : null,
    aspect_ratio: container.querySelector("[name='aspect_ratio']")?.value.trim(),
    tone: container.querySelector("[name='tone']")?.value.trim(),
    target_audience: container.querySelector("[name='target_audience']")?.value.trim(),
    must_include: container.querySelector("[name='must_include']")?.value.trim(),
  };

  return Object.fromEntries(
    Object.entries(brief).filter(([, value]) => value !== null && value !== ""),
  );
}

function renderActivity() {
  if (!state.project) {
    el.activityTimeline.innerHTML = `<div class="empty">No activity</div>`;
    return;
  }
  if (!state.activity.length) {
    el.activityTimeline.innerHTML = `<div class="empty">No activity</div>`;
    return;
  }

  el.activityTimeline.innerHTML = state.activity.map(renderActivityItem).join("");
}

function renderActivityItem(item) {
  return `
    <div class="activity-item">
      <span class="activity-dot status-${escapeHtml(item.status)}"></span>
      <div class="activity-content">
        <div class="activity-head">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(formatTime(item.occurred_at))}</span>
        </div>
        <div class="activity-description">${escapeHtml(item.description)}</div>
      </div>
    </div>
  `;
}

function selectedNode() {
  return state.project?.nodes.find((node) => node.key === state.selectedKey);
}

function summaryForNode(node) {
  if (node.error) return node.error;
  if (!node.output) return "Waiting";
  if (node.key === "seed") return node.output.text;
  if (node.output.one_sentence_pitch) return node.output.one_sentence_pitch;
  if (node.output.protagonist) return `${node.output.protagonist.name} · ${node.output.protagonist.desire}`;
  if (node.output.logline) return node.output.logline;
  if (node.output.title) return node.output.title;
  if (node.output.visual_style) return node.output.visual_style;
  return "Completed";
}

function setBusy(isBusy) {
  state.running = isBusy;
  el.createProject.disabled = isBusy;
  el.refreshProjects.disabled = isBusy;
  el.exportProject.disabled = isBusy || !state.project || !projectCanExport(state.project);
  renderHeader();
}

function showError(message) {
  el.projectStatus.textContent = message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function projectCanExport(project) {
  const script = project.nodes.find((node) => node.key === "script");
  const production = project.nodes.find((node) => node.key === "production");
  return (
    project.status === "completed" &&
    Boolean(project.title) &&
    Boolean(script?.output) &&
    Boolean(production?.output)
  );
}

function exportFileName(project) {
  const safeTitle = project.title
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `vidiom-${safeTitle}.json`;
}
