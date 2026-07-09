const state = {
  projects: [],
  project: null,
  activity: [],
  progress: null,
  selectedKey: "seed",
  reviewTab: "script",
  scriptEditing: false,
  productionEditing: false,
  running: false,
  pollingProjectId: null,
  pollTimer: null,
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
  duplicateProject: document.querySelector("#duplicateProject"),
  resetProject: document.querySelector("#resetProject"),
  pauseProject: document.querySelector("#pauseProject"),
  runProject: document.querySelector("#runProject"),
  projectSearch: document.querySelector("#projectSearch"),
  projectStatusFilter: document.querySelector("#projectStatusFilter"),
  projectList: document.querySelector("#projectList"),
  nodeLayer: document.querySelector("#nodeLayer"),
  edgeLayer: document.querySelector("#edgeLayer"),
  canvasTitle: document.querySelector("#canvasTitle"),
  canvasMeta: document.querySelector("#canvasMeta"),
  runProgress: document.querySelector("#runProgress"),
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
el.duplicateProject.addEventListener("click", duplicateProject);
el.resetProject.addEventListener("click", resetProject);
el.pauseProject.addEventListener("click", pauseProject);
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

function resetReviewEditors() {
  state.scriptEditing = false;
  state.productionEditing = false;
}

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
      state.progress = null;
      state.selectedKey = "seed";
      stopProjectPolling();
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
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = state.project.nodes.find((node) => node.key === state.selectedKey)
      ? state.selectedKey
      : "seed";
    resetReviewEditors();
    render();
    syncProjectPolling();
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
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = "seed";
    resetReviewEditors();
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
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = activeNodeKey(state.progress) || "premise";
    resetReviewEditors();
    await loadProjects();
    render();
    syncProjectPolling();
  } catch (error) {
    showError(error.message);
    await loadProject(state.project.id);
  } finally {
    setBusy(false);
  }
}

async function pauseProject() {
  if (!state.project || state.project.status !== "running") return;

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/pause`, { method: "POST" });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    resetReviewEditors();
    await loadProjects();
    render();
    syncProjectPolling();
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
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = "seed";
    resetReviewEditors();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function saveScriptEdits(event) {
  event.preventDefault();
  if (!state.project || state.project.status !== "completed") return;

  const script = scriptFromEditor(event.currentTarget);
  if (!script.title.trim()) {
    showError("标题不能为空。");
    return;
  }
  if (script.logline.trim().length < 10) {
    showError("Logline 至少需要 10 个字符。");
    return;
  }

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/script`, {
      method: "PATCH",
      body: JSON.stringify({ script }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    resetReviewEditors();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function saveProductionEdits(event) {
  event.preventDefault();
  if (!state.project || state.project.status !== "completed") return;

  const production = productionFromEditor(event.currentTarget);
  if (!production.visual_style) {
    showError("Visual Style 不能为空。");
    return;
  }
  if (production.shot_plan.some((shot) => !shot.shot || !shot.purpose)) {
    showError("每个镜头都需要镜头描述和目的。");
    return;
  }
  if (
    production.shot_plan.some(
      (shot) =>
        !Number.isInteger(shot.duration_seconds) ||
        shot.duration_seconds < 1 ||
        shot.duration_seconds > 60,
    )
  ) {
    showError("每个镜头时长需要是 1-60 秒。");
    return;
  }

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/production`, {
      method: "PATCH",
      body: JSON.stringify(production),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    resetReviewEditors();
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

async function duplicateProject() {
  if (!state.project) return;

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/duplicate`, { method: "POST" });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = "seed";
    resetReviewEditors();
    resetProjectFilters();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function reviseProjectFromNode(startNode) {
  if (!state.project || state.project.status !== "completed") return;

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/revise`, {
      method: "POST",
      body: JSON.stringify({ start_node: startNode }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = startNode;
    resetReviewEditors();
    resetProjectFilters();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function resetProject() {
  if (!state.project || state.project.status !== "failed") return;

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/reset`, { method: "POST" });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = activeNodeKey(state.progress) || "seed";
    resetReviewEditors();
    await loadProjects();
    render();
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
  const pausePending = project?.status === "paused" && Boolean(state.progress?.active_key);
  el.runProject.disabled = !project || state.running || project.status === "running" || pausePending;
  el.runProject.textContent = project?.status === "paused" ? "继续 Agent" : "运行 Agent";
  el.exportProject.disabled = !project || state.running || !projectCanExport(project);
  el.duplicateProject.disabled = !project || state.running;
  el.resetProject.disabled = !project || state.running || project.status !== "failed";
  el.pauseProject.disabled = !project || state.running || project.status !== "running";
  el.canvasTitle.textContent = project?.title || "Untitled";
  el.canvasMeta.textContent = project ? `#${project.id} · ${project.status}` : "";
  el.projectStatus.textContent = project ? project.status : "Ready";
  el.runProgress.innerHTML = renderRunProgress(project, state.progress);
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

  const revisionAction = renderRevisionAction(node);
  const output = node.output ? JSON.stringify(node.output, null, 2) : "";
  el.inspectorBody.innerHTML = `
    ${revisionAction}
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
  const reviseButton = el.inspectorBody.querySelector("[data-revise-node]");
  if (reviseButton) {
    reviseButton.addEventListener("click", () => reviseProjectFromNode(reviseButton.dataset.reviseNode));
  }
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
  if (state.reviewTab === "quality") {
    renderQualityReview(script, production);
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
    tab.disabled =
      !hasScript || (tab.dataset.reviewTab === "production" && !hasProduction);
  });
}

function renderScriptReview(script) {
  if (state.scriptEditing && state.project?.status === "completed") {
    renderScriptEditor(script);
    return;
  }

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
    ${renderScriptEditAction()}
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
  const editButton = el.scriptPreview.querySelector("[data-edit-script]");
  if (editButton) {
    editButton.addEventListener("click", () => {
      state.scriptEditing = true;
      renderScript();
    });
  }
}

function renderScriptEditAction() {
  if (state.project?.status !== "completed") return "";
  return `
    <div class="review-actions">
      <button class="secondary-button full-width" type="button" data-edit-script>
        编辑成片脚本
      </button>
    </div>
  `;
}

function renderScriptEditor(script) {
  const outlineFields = script.episode_outline
    .map(
      (beat, index) => `
        <fieldset class="edit-group" data-outline-index="${index}">
          <legend>Beat ${index + 1}</legend>
          <label for="outlineBeat${index}">Beat</label>
          <input id="outlineBeat${index}" name="beat" value="${escapeHtml(beat.beat)}" />
          <label for="outlinePurpose${index}">Purpose</label>
          <textarea id="outlinePurpose${index}" name="purpose" rows="2">${escapeHtml(beat.purpose)}</textarea>
        </fieldset>
      `,
    )
    .join("");
  const sceneFields = script.scenes
    .map(
      (scene, sceneIndex) => `
        <fieldset class="edit-group" data-scene-index="${sceneIndex}">
          <legend>Scene ${scene.scene_number}</legend>
          <label for="sceneSummary${sceneIndex}">Summary</label>
          <textarea id="sceneSummary${sceneIndex}" name="summary" rows="3">${escapeHtml(scene.summary)}</textarea>
          <div class="dialogue-edit-list">
            ${scene.dialogue.map((line, lineIndex) => renderDialogueEditor(line, sceneIndex, lineIndex)).join("")}
          </div>
        </fieldset>
      `,
    )
    .join("");

  el.scriptPreview.innerHTML = `
    <form id="scriptEditor" class="script-editor">
      <label for="scriptTitle">Title</label>
      <input id="scriptTitle" name="title" maxlength="120" value="${escapeHtml(script.title)}" />
      <label for="scriptLogline">Logline</label>
      <textarea id="scriptLogline" name="logline" rows="3">${escapeHtml(script.logline)}</textarea>
      <div class="review-section">
        <h3>Episode Beats</h3>
        ${outlineFields}
      </div>
      <div class="review-section">
        <h3>Scenes & Dialogue</h3>
        ${sceneFields}
      </div>
      <div class="form-actions">
        <button class="secondary-button" type="button" data-cancel-script-edit>取消</button>
        <button class="primary-button" type="submit">保存脚本</button>
      </div>
    </form>
  `;
  el.scriptPreview.querySelector("#scriptEditor").addEventListener("submit", saveScriptEdits);
  el.scriptPreview.querySelector("[data-cancel-script-edit]").addEventListener("click", () => {
    state.scriptEditing = false;
    renderScript();
  });
}

function renderDialogueEditor(line, sceneIndex, lineIndex) {
  return `
    <fieldset class="dialogue-edit" data-dialogue-index="${lineIndex}">
      <legend>${escapeHtml(line.speaker)}</legend>
      <label for="dialogueLine${sceneIndex}-${lineIndex}">Line</label>
      <textarea id="dialogueLine${sceneIndex}-${lineIndex}" name="line" rows="2">${escapeHtml(
        line.line,
      )}</textarea>
      <label for="dialogueDirection${sceneIndex}-${lineIndex}">Direction</label>
      <input
        id="dialogueDirection${sceneIndex}-${lineIndex}"
        name="direction"
        value="${escapeHtml(line.direction)}"
      />
    </fieldset>
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
  if (state.productionEditing && state.project?.status === "completed") {
    renderProductionEditor(production);
    return;
  }

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
    ${renderProductionEditAction()}
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
  const editButton = el.scriptPreview.querySelector("[data-edit-production]");
  if (editButton) {
    editButton.addEventListener("click", () => {
      state.productionEditing = true;
      renderScript();
    });
  }
}

function renderProductionEditAction() {
  if (state.project?.status !== "completed") return "";
  return `
    <div class="review-actions">
      <button class="secondary-button full-width" type="button" data-edit-production>
        编辑拍摄包
      </button>
    </div>
  `;
}

function renderProductionEditor(production) {
  const shotFields = production.shot_plan
    .map(
      (shot, index) => `
        <fieldset class="edit-group" data-shot-index="${index}">
          <legend>Shot ${index + 1}</legend>
          <label for="shotName${index}">Shot</label>
          <input id="shotName${index}" name="shot" value="${escapeHtml(shot.shot)}" />
          <label for="shotPurpose${index}">Purpose</label>
          <textarea id="shotPurpose${index}" name="purpose" rows="2">${escapeHtml(
            shot.purpose,
          )}</textarea>
          <label for="shotDuration${index}">Duration seconds</label>
          <input
            id="shotDuration${index}"
            name="duration_seconds"
            type="number"
            min="1"
            max="60"
            value="${escapeHtml(shot.duration_seconds)}"
          />
        </fieldset>
      `,
    )
    .join("");

  el.scriptPreview.innerHTML = `
    <form id="productionEditor" class="production-editor">
      <label for="productionVisualStyle">Visual Style</label>
      <textarea id="productionVisualStyle" name="visual_style" rows="3">${escapeHtml(
        production.visual_style,
      )}</textarea>
      <label for="productionLocations">Locations</label>
      <textarea id="productionLocations" name="locations" rows="4">${escapeHtml(
        production.locations.join("\n"),
      )}</textarea>
      <label for="productionProps">Props</label>
      <textarea id="productionProps" name="props" rows="4">${escapeHtml(
        production.props.join("\n"),
      )}</textarea>
      <label for="productionEditNotes">Edit Notes</label>
      <textarea id="productionEditNotes" name="edit_notes" rows="4">${escapeHtml(
        production.edit_notes.join("\n"),
      )}</textarea>
      <div class="review-section">
        <h3>Shot Plan</h3>
        ${shotFields}
      </div>
      <div class="form-actions">
        <button class="secondary-button" type="button" data-cancel-production-edit>取消</button>
        <button class="primary-button" type="submit">保存拍摄包</button>
      </div>
    </form>
  `;
  el.scriptPreview.querySelector("#productionEditor").addEventListener("submit", saveProductionEdits);
  el.scriptPreview.querySelector("[data-cancel-production-edit]").addEventListener("click", () => {
    state.productionEditing = false;
    renderScript();
  });
}

function renderQualityReview(script, production) {
  const report = qualityReport(script, production, state.project?.brief || {});
  const issues = report.issues.length
    ? report.issues.map(renderQualityIssue).join("")
    : `<div class="empty">No blocking issues found</div>`;

  el.scriptPreview.innerHTML = `
    <div class="quality-summary status-${escapeHtml(report.status)}">
      <strong>${escapeHtml(report.label)}</strong>
      <span>${escapeHtml(report.summary)}</span>
    </div>
    <div class="quality-metrics">
      ${report.metrics.map(renderQualityMetric).join("")}
    </div>
    <div class="review-section">
      <h3>Release Checks</h3>
      <div class="quality-issue-list">${issues}</div>
    </div>
  `;
}

function renderQualityMetric(metric) {
  return `
    <div class="quality-metric">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
    </div>
  `;
}

function renderQualityIssue(issue) {
  return `
    <article class="quality-issue ${escapeHtml(issue.severity)}">
      <strong>${escapeHtml(issue.title)}</strong>
      <p>${escapeHtml(issue.detail)}</p>
    </article>
  `;
}

function qualityReport(script, production, brief) {
  const scenes = Array.isArray(script.scenes) ? script.scenes : [];
  const outline = Array.isArray(script.episode_outline) ? script.episode_outline : [];
  const dialogueCount = scenes.reduce(
    (count, scene) => count + (Array.isArray(scene.dialogue) ? scene.dialogue.length : 0),
    0,
  );
  const shotPlan = Array.isArray(production?.shot_plan) ? production.shot_plan : [];
  const shotSeconds = shotPlan.reduce(
    (total, shot) => total + Number(shot.duration_seconds || 0),
    0,
  );
  const plannedMinutes = shotSeconds ? `${Math.round((shotSeconds / 60) * 10) / 10} min` : "—";
  const targetMinutes = Number(brief?.duration_minutes || script.runtime_minutes || 0);
  const issues = [];

  if (String(script.logline || "").trim().length < 18) {
    issues.push({
      severity: "blocker",
      title: "Logline too thin",
      detail: "Rewrite the logline so the hook, pressure, and choice are clear.",
    });
  }
  if (outline.length < 5) {
    issues.push({
      severity: "warning",
      title: "Beat count is light",
      detail: "Add enough episode beats to carry setup, turn, pressure, climax, and ending.",
    });
  }
  if (scenes.length < 3) {
    issues.push({
      severity: "blocker",
      title: "Too few scenes",
      detail: "Add at least three playable scenes before export review.",
    });
  }
  if (dialogueCount < scenes.length * 2) {
    issues.push({
      severity: "warning",
      title: "Dialogue coverage is low",
      detail: "Give each scene enough spoken action for actors and edit timing.",
    });
  }
  if (!production) {
    issues.push({
      severity: "blocker",
      title: "Production pack missing",
      detail: "Run or revise the Production Agent before delivery review.",
    });
  } else {
    const missingLocations = missingItems(
      script.production_notes?.locations || [],
      production.locations || [],
    );
    const missingProps = missingItems(script.production_notes?.props || [], production.props || []);
    if (missingLocations.length) {
      issues.push({
        severity: "blocker",
        title: "Location mismatch",
        detail: `Production pack is missing: ${missingLocations.join(", ")}`,
      });
    }
    if (missingProps.length) {
      issues.push({
        severity: "warning",
        title: "Prop mismatch",
        detail: `Production pack should include: ${missingProps.join(", ")}`,
      });
    }
    if (shotPlan.length < Math.max(5, scenes.length)) {
      issues.push({
        severity: "warning",
        title: "Shot plan coverage is low",
        detail: "Add more shots so every scene has a clear capture plan.",
      });
    }
    if (targetMinutes && shotSeconds > targetMinutes * 60 + 30) {
      issues.push({
        severity: "blocker",
        title: "Shot timing exceeds target",
        detail: `Shot plan totals ${plannedMinutes} against a ${targetMinutes} min target.`,
      });
    }
    (script.production_notes?.risk_flags || []).forEach((risk) => {
      issues.push({
        severity: "warning",
        title: "Script risk flag",
        detail: risk,
      });
    });
  }

  const blockers = issues.filter((issue) => issue.severity === "blocker").length;
  const warnings = issues.filter((issue) => issue.severity === "warning").length;
  return {
    status: blockers ? "failed" : warnings ? "pending" : "completed",
    label: blockers ? "Needs edits" : warnings ? "Ready with warnings" : "Ready for export",
    summary: `${blockers} blockers · ${warnings} warnings`,
    issues,
    metrics: [
      { label: "Runtime", value: `${script.runtime_minutes || "—"} min` },
      { label: "Scenes", value: String(scenes.length) },
      { label: "Dialogue", value: String(dialogueCount) },
      { label: "Shot Coverage", value: plannedMinutes },
    ],
  };
}

function missingItems(requiredItems, availableItems) {
  const available = availableItems.map((item) => String(item).trim()).filter(Boolean);
  return requiredItems
    .map((item) => String(item).trim())
    .filter(Boolean)
    .filter((item) => !available.some((availableItem) => availableItem.includes(item)));
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

function renderRevisionAction(node) {
  if (state.project?.status !== "completed" || node.kind !== "agent") return "";
  return `
    <div class="node-actions">
      <button class="secondary-button full-width" type="button" data-revise-node="${escapeHtml(node.key)}">
        从此节点修订
      </button>
    </div>
  `;
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

function scriptFromEditor(form) {
  const currentScript = state.project.nodes.find((node) => node.key === "script").output;
  const script = JSON.parse(JSON.stringify(currentScript));
  script.title = form.querySelector("[name='title']").value.trim();
  script.logline = form.querySelector("[name='logline']").value.trim();

  form.querySelectorAll("[data-outline-index]").forEach((group) => {
    const index = Number(group.dataset.outlineIndex);
    script.episode_outline[index].beat = group.querySelector("[name='beat']").value.trim();
    script.episode_outline[index].purpose = group.querySelector("[name='purpose']").value.trim();
  });

  form.querySelectorAll("[data-scene-index]").forEach((group) => {
    const sceneIndex = Number(group.dataset.sceneIndex);
    script.scenes[sceneIndex].summary = group.querySelector("[name='summary']").value.trim();
    group.querySelectorAll("[data-dialogue-index]").forEach((dialogueGroup) => {
      const lineIndex = Number(dialogueGroup.dataset.dialogueIndex);
      script.scenes[sceneIndex].dialogue[lineIndex].line = dialogueGroup
        .querySelector("[name='line']")
        .value.trim();
      script.scenes[sceneIndex].dialogue[lineIndex].direction = dialogueGroup
        .querySelector("[name='direction']")
        .value.trim();
    });
  });

  return script;
}

function productionFromEditor(form) {
  const shotPlan = Array.from(form.querySelectorAll("[data-shot-index]")).map((group) => ({
    shot: group.querySelector("[name='shot']").value.trim(),
    purpose: group.querySelector("[name='purpose']").value.trim(),
    duration_seconds: Number(group.querySelector("[name='duration_seconds']").value),
  }));

  return {
    visual_style: form.querySelector("[name='visual_style']").value.trim(),
    locations: linesFromTextarea(form.querySelector("[name='locations']")),
    props: linesFromTextarea(form.querySelector("[name='props']")),
    shot_plan: shotPlan,
    edit_notes: linesFromTextarea(form.querySelector("[name='edit_notes']")),
  };
}

function linesFromTextarea(textarea) {
  return textarea.value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
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

function renderRunProgress(project, progress) {
  if (!project || !progress || progress.total === 0) return "";
  const label = progressLabel(project, progress);
  const percent = Math.round((progress.completed / progress.total) * 100);
  return `
    <div class="progress-label">${escapeHtml(label)}</div>
    <div class="progress-track" aria-label="Agent progress">
      <span style="width:${percent}%"></span>
    </div>
  `;
}

function progressLabel(project, progress) {
  if (project.status === "failed") {
    return progress.failed_title
      ? `${progress.completed}/${progress.total} · ${progress.failed_title} failed`
      : `${progress.completed}/${progress.total} · failed`;
  }
  if (project.status === "completed") {
    return `${progress.total}/${progress.total} · completed`;
  }
  if (project.status === "running") {
    return progress.active_title
      ? `${progress.completed}/${progress.total} · ${progress.active_title}`
      : `${progress.completed}/${progress.total} · starting`;
  }
  if (project.status === "paused") {
    return progress.active_title
      ? `${progress.completed}/${progress.total} · pausing after ${progress.active_title}`
      : `${progress.completed}/${progress.total} · paused`;
  }
  return `${progress.completed}/${progress.total} · draft`;
}

function syncProjectPolling() {
  if (
    state.project?.status === "running" ||
    (state.project?.status === "paused" && state.progress?.active_key)
  ) {
    startProjectPolling(state.project.id);
    return;
  }
  stopProjectPolling();
}

function startProjectPolling(projectId) {
  if (state.pollingProjectId === projectId && state.pollTimer) return;
  stopProjectPolling();
  state.pollingProjectId = projectId;
  state.pollTimer = window.setInterval(() => pollRunningProject(projectId), 1800);
}

function stopProjectPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
  }
  state.pollTimer = null;
  state.pollingProjectId = null;
}

async function pollRunningProject(projectId) {
  if (!state.project || state.project.id !== projectId) {
    stopProjectPolling();
    return;
  }

  try {
    const body = await api(`/api/projects/${projectId}`);
    if (!state.project || state.project.id !== projectId) return;
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.selectedKey = activeNodeKey(state.progress) || state.selectedKey;
    render();
    if (state.project.status !== "running") {
      stopProjectPolling();
      await loadProjects();
    }
  } catch (error) {
    showError(error.message);
    stopProjectPolling();
  }
}

function progressFromProject(project) {
  if (!project) return null;
  const agentNodes = project.nodes.filter((node) => node.kind === "agent");
  const active = agentNodes.find((node) => node.status === "running");
  const failed = agentNodes.find((node) => node.status === "failed");
  return {
    completed: agentNodes.filter((node) => node.status === "completed").length,
    total: agentNodes.length,
    active_key: active?.key || null,
    active_title: active?.title || null,
    failed_key: failed?.key || null,
    failed_title: failed?.title || null,
  };
}

function activeNodeKey(progress) {
  return progress?.active_key || progress?.failed_key || null;
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
  el.duplicateProject.disabled = isBusy || !state.project;
  el.resetProject.disabled = isBusy || !state.project || state.project.status !== "failed";
  el.pauseProject.disabled = isBusy || !state.project || state.project.status !== "running";
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
