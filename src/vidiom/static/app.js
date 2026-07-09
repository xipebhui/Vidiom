const WORKSPACE_STORAGE_KEY = "vidiom.studio.workspace.v1";
const REVIEW_TABS = new Set([
  "script",
  "characters",
  "production",
  "images",
  "storyboard",
  "quality",
  "delivery",
]);
const NODE_KEYS = new Set(["seed", "premise", "characters", "beats", "script", "production"]);
const PROJECT_STATUSES = new Set(["", "draft", "running", "paused", "completed", "failed"]);
const AGENT_SEQUENCE = [
  { key: "premise", title: "Premise Agent" },
  { key: "characters", title: "Character Agent" },
  { key: "beats", title: "Beat Agent" },
  { key: "script", title: "Script Agent" },
  { key: "production", title: "Production Agent" },
];

const state = {
  projects: [],
  project: null,
  activity: [],
  progress: null,
  runtime: null,
  selectedKey: "seed",
  reviewTab: "script",
  scriptEditing: false,
  productionEditing: false,
  reviewNotesEditing: false,
  imageGenerating: false,
  storyboard: null,
  storyboardLoading: false,
  storyboardGenerating: false,
  selectedStoryboardShotId: null,
  storyboardPollTimer: null,
  running: false,
  pollingProjectId: null,
  pollTimer: null,
  projectFilters: {
    search: "",
    status: "",
  },
  restoredProjectId: null,
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
  runReadiness: document.querySelector("#runReadiness"),
  scriptPreview: document.querySelector("#scriptPreview"),
  reviewTabs: document.querySelectorAll(".review-tab"),
  activityTimeline: document.querySelector("#activityTimeline"),
  runtimeSummary: document.querySelector("#runtimeSummary"),
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
    saveWorkspaceState();
    renderScript();
    if (state.reviewTab === "storyboard") {
      loadStoryboard();
    }
  });
});

restoreWorkspaceState();
loadProjects();

function resetReviewEditors() {
  state.scriptEditing = false;
  state.productionEditing = false;
  state.reviewNotesEditing = false;
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
      const preferredProjectId = currentProjectId || state.restoredProjectId;
      const preferredProject = state.projects.find((project) => project.id === preferredProjectId);
      await loadProject((preferredProject || state.projects[0]).id);
      return;
    }
    if (state.projects.length === 0 && !selectedProjectIsVisible) {
      state.project = null;
      state.activity = [];
      state.progress = null;
      state.runtime = null;
      state.selectedKey = "seed";
      state.restoredProjectId = null;
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
    state.runtime = body.runtime || null;
    state.storyboard = null;
    state.selectedStoryboardShotId = null;
    state.selectedKey = state.project.nodes.find((node) => node.key === state.selectedKey)
      ? state.selectedKey
      : "seed";
    state.restoredProjectId = null;
    resetReviewEditors();
    render();
    syncProjectPolling();
    if (state.reviewTab === "storyboard") {
      await loadStoryboard();
    }
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
    state.runtime = body.runtime || null;
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
  saveWorkspaceState();
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
    resetReviewEditors();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function saveReviewNotes(event) {
  event.preventDefault();
  if (!state.project || state.project.status !== "completed") return;

  const reviewNotes = reviewNotesFromEditor(event.currentTarget);
  if (!reviewNotes.release_status) {
    showError("请选择发布状态。");
    return;
  }
  if (!reviewNotes.summary) {
    showError("Review Summary 不能为空。");
    return;
  }

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/review-notes`, {
      method: "PATCH",
      body: JSON.stringify(reviewNotes),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.runtime = body.runtime || null;
    resetReviewEditors();
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function generateProjectImage(event) {
  event.preventDefault();
  if (!state.project) return;

  const form = event.currentTarget;
  const prompt = form.querySelector("[name='prompt']").value.trim();
  if (!prompt) {
    showError("图像提示词不能为空。");
    return;
  }

  state.imageGenerating = true;
  setBusy(true);
  renderScript();
  try {
    const body = await api(`/api/projects/${state.project.id}/images`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.runtime = body.runtime || null;
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
    await loadProject(state.project.id);
  } finally {
    state.imageGenerating = false;
    setBusy(false);
    renderScript();
  }
}

async function loadStoryboard() {
  if (!state.project) return;
  state.storyboardLoading = true;
  renderScript();
  try {
    const body = await api(`/api/projects/${state.project.id}/storyboard`);
    state.storyboard = body;
    if (!state.selectedStoryboardShotId && body.shots?.length) {
      state.selectedStoryboardShotId = body.shots[0].id;
    }
    renderScript();
    if (body.storyboard?.generation_status === "generating") {
      startStoryboardPolling();
    } else {
      stopStoryboardPolling();
    }
  } catch (error) {
    showError(error.message);
  } finally {
    state.storyboardLoading = false;
    renderScript();
  }
}

async function generateStoryboard() {
  if (!state.project || state.project.status !== "completed") return;
  state.storyboardGenerating = true;
  renderScript();
  try {
    const body = await api(`/api/projects/${state.project.id}/storyboard/generate`, {
      method: "POST",
    });
    state.storyboard = body.storyboard;
    startStoryboardPolling();
    renderScript();
  } catch (error) {
    showError(error.message);
  } finally {
    state.storyboardGenerating = false;
    renderScript();
  }
}

async function saveStoryboardReview(event) {
  const button = event.currentTarget;
  const shotId = Number(button.dataset.storyboardReview);
  const reviewStatus = button.dataset.reviewStatus;
  const shot = state.storyboard?.shots?.find((item) => item.id === shotId);
  if (!state.project || !shot) return;
  try {
    const body = await api(`/api/projects/${state.project.id}/storyboard/shots/review`, {
      method: "PATCH",
      body: JSON.stringify({
        reviews: [
          {
            shot_id: shotId,
            review_status: reviewStatus,
            prompt_ready: Boolean(shot.prompt_ready),
          },
        ],
      }),
    });
    state.storyboard = body.storyboard;
    renderScript();
  } catch (error) {
    showError(error.message);
  }
}

async function toggleStoryboardImageLink(event) {
  const button = event.currentTarget;
  const shotId = Number(button.dataset.storyboardImageShot);
  const assetId = Number(button.dataset.storyboardImageAsset);
  const linked = button.dataset.linked === "true";
  if (!state.project || !shotId || !assetId) return;
  try {
    const method = linked ? "DELETE" : "POST";
    const body = await api(
      `/api/projects/${state.project.id}/storyboard/shots/${shotId}/image-assets/${assetId}?link_type=reference`,
      { method },
    );
    state.storyboard = body.storyboard;
    renderScript();
  } catch (error) {
    showError(error.message);
  }
}

function startStoryboardPolling() {
  if (state.storyboardPollTimer) return;
  state.storyboardPollTimer = window.setInterval(async () => {
    if (!state.project) {
      stopStoryboardPolling();
      return;
    }
    try {
      const body = await api(`/api/projects/${state.project.id}/storyboard`);
      state.storyboard = body;
      renderScript();
      if (body.storyboard?.generation_status !== "generating") {
        stopStoryboardPolling();
      }
    } catch (error) {
      showError(error.message);
      stopStoryboardPolling();
    }
  }, 2000);
}

function stopStoryboardPolling() {
  if (!state.storyboardPollTimer) return;
  window.clearInterval(state.storyboardPollTimer);
  state.storyboardPollTimer = null;
}

async function saveNodeInstructions(event) {
  event.preventDefault();
  if (!state.project) return;

  const form = event.currentTarget;
  const nodeKey = form.dataset.nodeInstructions;
  const guidance = form.querySelector("[name='guidance']").value.trim();

  setBusy(true);
  try {
    const body = await api(`/api/projects/${state.project.id}/nodes/${nodeKey}/instructions`, {
      method: "PATCH",
      body: JSON.stringify({ guidance }),
    });
    state.project = body.project;
    state.activity = body.activity || [];
    state.progress = body.progress || progressFromProject(state.project);
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
    state.runtime = body.runtime || null;
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
  renderRunReadiness();
  renderScript();
  renderActivity();
  saveWorkspaceState();
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
      const progress = renderProjectRowProgress(project);
      return `
        <button class="project-row${active}" data-project-id="${project.id}">
          <div class="project-row-head">
            <strong>${title}</strong>
            <span class="status-pill status-${escapeHtml(project.status)}">${escapeHtml(project.status)}</span>
          </div>
          <div class="project-row-seed">${escapeHtml(project.seed_text)}</div>
          <div class="project-row-progress">
            ${progress}
          </div>
          <div class="project-row-next">
            ${escapeHtml(projectNextActionLabel(project))}
          </div>
          <div class="project-row-meta">
            <span>#${project.id}</span>
            <span>${escapeHtml(formatTime(project.updated_at))}</span>
          </div>
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
      saveWorkspaceState();
      render();
    });
  });
}

function renderNode(node) {
  const selected = state.selectedKey === node.key ? " selected" : "";
  const statusClass = `status-${node.status}`;
  const instructionMarker = node.instructions?.guidance
    ? `<span class="node-instruction-marker" title="Custom guidance">Guide</span>`
    : "";
  return `
    <button class="canvas-node${selected}" data-node-key="${node.key}" style="left:${node.x}px;top:${node.y}px">
      <div class="node-kind">
        <span>${escapeHtml(node.kind)}${instructionMarker}</span>
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
  const instructionEditor = renderNodeInstructionsEditor(node);
  const output = node.output ? JSON.stringify(node.output, null, 2) : "";
  el.inspectorBody.innerHTML = `
    ${revisionAction}
    ${instructionEditor}
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
  const instructionForm = el.inspectorBody.querySelector("[data-node-instructions]");
  if (instructionForm) {
    instructionForm.addEventListener("submit", saveNodeInstructions);
  }
}

function renderRunReadiness() {
  const project = state.project;
  if (!project) {
    el.runReadiness.innerHTML = `<div class="empty">No project selected</div>`;
    return;
  }

  const report = runReadinessReport(project);
  el.runReadiness.innerHTML = `
    <div class="readiness-summary status-${escapeHtml(report.status)}">
      <strong>${escapeHtml(report.label)}</strong>
      <span>${escapeHtml(report.summary)}</span>
    </div>
    <div class="readiness-metrics">
      ${report.metrics.map(renderReadinessMetric).join("")}
    </div>
    <div class="readiness-checks">
      ${report.checks.map(renderReadinessCheck).join("")}
    </div>
    <div class="readiness-actions">
      <button class="secondary-button" type="button" data-readiness-select="seed">
        Seed
      </button>
      ${
        report.nextNode
          ? `<button class="secondary-button" type="button" data-readiness-select="${escapeHtml(
              report.nextNode.key,
            )}">
              ${escapeHtml(report.nextNode.title)}
            </button>`
          : ""
      }
    </div>
  `;
  el.runReadiness.querySelectorAll("[data-readiness-select]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedKey = button.dataset.readinessSelect;
      render();
    });
  });
}

function runReadinessReport(project) {
  const agentNodes = project.nodes.filter((node) => node.kind === "agent");
  const completedNodes = agentNodes.filter((node) => node.status === "completed");
  const pendingNodes = agentNodes.filter((node) => node.status === "pending");
  const runningNode = agentNodes.find((node) => node.status === "running");
  const failedNode = agentNodes.find((node) => node.status === "failed");
  const nextNode = runningNode || failedNode || pendingNodes[0] || null;
  const briefFields = [
    ["duration_minutes", "Duration"],
    ["aspect_ratio", "Aspect ratio"],
    ["tone", "Tone"],
    ["target_audience", "Audience"],
    ["must_include", "Must include"],
  ];
  const filledBriefFields = briefFields.filter(([key]) => {
    const value = project.brief?.[key];
    return value !== null && value !== undefined && String(value).trim() !== "";
  });
  const guidanceNodes = agentNodes.filter((node) => node.instructions?.guidance);
  const checks = [
    readinessCheck(
      "Seed",
      String(project.seed_text || "").trim().length >= 12,
      "Strong enough",
      "一句话太短，Premise Agent 缺少可执行钩子。",
    ),
    readinessCheck(
      "Creative Brief",
      filledBriefFields.length >= 4,
      `${filledBriefFields.length}/${briefFields.length} fields set`,
      "补齐时长、画幅、语气、观众和必含要素，生成约束会更稳定。",
    ),
    readinessCheck(
      "Agent Guidance",
      guidanceNodes.length > 0,
      `${guidanceNodes.length} custom nodes`,
      "没有节点级指令，agent 将只使用项目 Brief 和上游输出。",
      "pending",
    ),
    readinessCheck(
      "Run Scope",
      project.status !== "failed",
      `${completedNodes.length}/${agentNodes.length} completed`,
      "当前有失败节点，请先重置或从失败状态恢复。",
    ),
  ];
  const blockers = checks.filter((check) => check.status === "failed").length;
  const warnings = checks.filter((check) => check.status === "pending").length;
  const label = blockers ? "Needs attention" : warnings ? "Ready with notes" : "Ready to run";
  const status = blockers ? "failed" : warnings ? "pending" : "completed";

  return {
    label,
    status,
    summary: `${blockers} blockers · ${warnings} notes`,
    nextNode,
    checks,
    metrics: [
      { label: "Brief", value: `${filledBriefFields.length}/${briefFields.length}` },
      { label: "Guidance", value: String(guidanceNodes.length) },
      { label: "Next", value: nextNode ? nextNode.title : "Complete" },
    ],
  };
}

function readinessCheck(title, passed, passDetail, failDetail, failStatus = "failed") {
  return {
    title,
    status: passed ? "completed" : failStatus,
    detail: passed ? passDetail : failDetail,
  };
}

function renderReadinessMetric(metric) {
  return `
    <div class="readiness-metric">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
    </div>
  `;
}

function renderReadinessCheck(check) {
  return `
    <article class="readiness-check status-${escapeHtml(check.status)}">
      <span class="activity-dot status-${escapeHtml(check.status)}"></span>
      <div>
        <strong>${escapeHtml(check.title)}</strong>
        <p>${escapeHtml(check.detail)}</p>
      </div>
    </article>
  `;
}

function renderScript() {
  const script = state.project?.nodes.find((node) => node.key === "script")?.output;
  const production = state.project?.nodes.find((node) => node.key === "production")?.output;
  const canExport = state.project ? projectCanExport(state.project) : false;
  renderReviewTabs(Boolean(script), Boolean(production), canExport, Boolean(state.project));
  if (!script) {
    if (state.reviewTab === "images" && state.project) {
      renderImageReview(null, null);
      return;
    }
    if (state.reviewTab === "storyboard" && state.project) {
      renderStoryboardReview(null, null);
      return;
    }
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
  if (state.reviewTab === "images") {
    renderImageReview(script, production);
    return;
  }
  if (state.reviewTab === "storyboard") {
    renderStoryboardReview(script, production);
    return;
  }
  if (state.reviewTab === "quality") {
    renderQualityReview(script, production);
    return;
  }
  if (state.reviewTab === "delivery") {
    renderDeliveryReview(script, production);
    return;
  }

  renderScriptReview(script);
}

function renderReviewTabs(hasScript, hasProduction, canExport, hasProject) {
  if (state.reviewTab === "production" && !hasProduction) {
    state.reviewTab = "script";
  }
  if (state.reviewTab === "delivery" && !canExport) {
    state.reviewTab = "script";
  }
  el.reviewTabs.forEach((tab) => {
    const isActive = tab.dataset.reviewTab === state.reviewTab;
    const needsProduction = tab.dataset.reviewTab === "production";
    const needsExport = tab.dataset.reviewTab === "delivery";
    const needsProject = tab.dataset.reviewTab === "images" || tab.dataset.reviewTab === "storyboard";
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
    tab.disabled =
      (!hasScript && !needsProject) ||
      (needsProject && !hasProject) ||
      (needsProduction && !hasProduction) ||
      (needsExport && !canExport);
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

function renderImageReview(script, production) {
  if (!state.project) {
    el.scriptPreview.innerHTML = `<div class="empty">No project selected</div>`;
    return;
  }

  const assets = state.project.image_assets || [];
  const prompt = imagePromptFromProject(script, production, state.project);
  const assetList = assets.length
    ? assets.map(renderImageAsset).join("")
    : `<div class="empty">No generated images</div>`;
  el.scriptPreview.innerHTML = `
    <form id="imageGenerator" class="image-generator">
      <label for="imagePrompt">Image Prompt</label>
      <textarea id="imagePrompt" name="prompt" rows="6" maxlength="2000">${escapeHtml(prompt)}</textarea>
      <button class="primary-button full-width" type="submit" ${state.imageGenerating ? "disabled" : ""}>
        ${state.imageGenerating ? "生成中..." : "生成项目图像"}
      </button>
    </form>
    <div class="review-section">
      <h3>Generated Image Assets</h3>
      <div class="image-asset-list">${assetList}</div>
    </div>
  `;
  el.scriptPreview.querySelector("#imageGenerator").addEventListener("submit", generateProjectImage);
}

function imagePromptFromProject(script, production, project) {
  const style = production?.visual_style || script?.production_notes?.shooting_style || "";
  const firstScene =
    Array.isArray(script?.scenes) && script.scenes.length ? script.scenes[0] : null;
  const parts = [
    script?.title || project.title || project.seed_text,
    script?.logline || project.seed_text,
    style,
    firstScene ? `${firstScene.setting} ${firstScene.time}: ${firstScene.summary}` : "",
    project.brief?.aspect_ratio ? `Frame: ${project.brief.aspect_ratio}` : "",
  ].filter(Boolean);
  return parts.join("\n");
}

function renderImageAsset(asset) {
  const imageSource = asset.artifact_url
    ? asset.artifact_url
    : asset.b64_json
      ? `data:image/png;base64,${asset.b64_json}`
      : "";
  const media = imageSource
    ? `<img src="${escapeHtml(imageSource)}" alt="${escapeHtml(asset.prompt)}" />`
    : `<div class="image-reference">${escapeHtml(asset.revised_prompt || asset.error_message || "No retrievable image reference")}</div>`;
  return `
    <article class="image-asset status-${escapeHtml(asset.status)}">
      <div class="image-asset-media">${media}</div>
      <div class="image-asset-body">
        <div class="image-asset-head">
          <strong>${escapeHtml(asset.model)}</strong>
          <span class="status-pill status-${escapeHtml(asset.status)}">${escapeHtml(asset.status)}</span>
        </div>
        <p>${escapeHtml(asset.prompt)}</p>
        ${
          asset.revised_prompt
            ? `<small>Revised: ${escapeHtml(asset.revised_prompt)}</small>`
            : ""
        }
        ${
          asset.error_message
            ? `<small class="error-text">${escapeHtml(asset.error_message)}</small>`
            : ""
        }
        <small>${escapeHtml(formatTime(asset.created_at))}</small>
      </div>
    </article>
  `;
}

function renderStoryboardReview(script, production) {
  if (!state.project) {
    el.scriptPreview.innerHTML = `<div class="empty">No project selected</div>`;
    return;
  }
  const storyboard = state.storyboard;
  if (state.storyboardLoading && !storyboard) {
    el.scriptPreview.innerHTML = `<div class="empty">Loading storyboard</div>`;
    return;
  }
  const status = storyboard?.storyboard?.generation_status || "not_started";
  const canGenerate = state.project.status === "completed";
  const shots = storyboard?.shots || [];
  const selectedShot =
    shots.find((shot) => shot.id === state.selectedStoryboardShotId) || shots[0] || null;
  const shotList = shots.length
    ? shots.map(renderStoryboardShot).join("")
    : `<div class="empty">No storyboard shots yet</div>`;
  el.scriptPreview.innerHTML = `
    <div class="review-actions">
      <button class="primary-button full-width" type="button" data-generate-storyboard ${
        !canGenerate || state.storyboardGenerating || status === "generating" ? "disabled" : ""
      }>
        ${status === "generating" || state.storyboardGenerating ? "故事板生成中..." : "生成故事板"}
      </button>
    </div>
    ${renderStoryboardStatus(storyboard, status, canGenerate)}
    <div class="review-section">
      <h3>Storyboard Shots</h3>
      <div class="storyboard-shot-list">${shotList}</div>
    </div>
    <div class="review-section">
      <h3>Story Assets</h3>
      ${renderStoryboardAssets(storyboard?.assets || [], storyboard?.relationships || [])}
    </div>
    <div class="review-section">
      <h3>Image Links</h3>
      ${renderStoryboardImageLinks(selectedShot, storyboard)}
    </div>
  `;
  const generateButton = el.scriptPreview.querySelector("[data-generate-storyboard]");
  if (generateButton) {
    generateButton.addEventListener("click", generateStoryboard);
  }
  el.scriptPreview.querySelectorAll("[data-storyboard-shot]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStoryboardShotId = Number(button.dataset.storyboardShot);
      renderScript();
    });
  });
  el.scriptPreview.querySelectorAll("[data-storyboard-review]").forEach((button) => {
    button.addEventListener("click", saveStoryboardReview);
  });
  el.scriptPreview.querySelectorAll("[data-storyboard-image-asset]").forEach((button) => {
    button.addEventListener("click", toggleStoryboardImageLink);
  });
}

function renderStoryboardStatus(storyboard, status, canGenerate) {
  if (!canGenerate) {
    return `<div class="quality-summary status-pending"><strong>Agent 未完成</strong><span>需先完成 Script 和 Production。</span></div>`;
  }
  if (!storyboard || status === "not_started") {
    return `<div class="quality-summary status-pending"><strong>未生成</strong><span>完成项目可触发真实 gpt-5.5 故事板生成。</span></div>`;
  }
  if (status === "generating") {
    return `<div class="quality-summary status-running"><strong>生成中</strong><span>正在调用 gpt-5.5 拆解结构化 shots。</span></div>`;
  }
  if (status === "failed" && storyboard.has_completed_result) {
    return `
      <div class="quality-summary status-failed">
        <strong>本次生成失败</strong>
        <span>${escapeHtml(storyboard.storyboard.generation_error_message || "Storyboard generation failed.")}；下面是上次成功结果。</span>
      </div>
    `;
  }
  if (status === "failed") {
    return `
      <div class="quality-summary status-failed">
        <strong>生成失败</strong>
        <span>${escapeHtml(storyboard.storyboard.generation_error_message || "Storyboard generation failed.")}</span>
      </div>
    `;
  }
  return `
    <div class="quality-summary status-completed">
      <strong>故事板已生成</strong>
      <span>${escapeHtml(storyboard.shots.length)} shots · ${escapeHtml(storyboard.assets.length)} assets · ${escapeHtml(storyboard.image_links.length)} image links</span>
    </div>
  `;
}

function renderStoryboardShot(shot) {
  const selected = shot.id === state.selectedStoryboardShotId ? " selected" : "";
  return `
    <article class="storyboard-shot${selected}">
      <button class="storyboard-shot-select" type="button" data-storyboard-shot="${escapeHtml(shot.id)}">
        <strong>${escapeHtml(shot.sequence_index)}. ${escapeHtml(shot.beat_ref)}</strong>
        <span class="status-pill status-${escapeHtml(shot.review_status)}">${escapeHtml(shot.review_status)}</span>
      </button>
      <p>${escapeHtml(shot.visual_description)}</p>
      <dl>
        <dt>Scene</dt><dd>${escapeHtml(shot.scene_ref)} · ${escapeHtml(shot.scene)}</dd>
        <dt>Characters</dt><dd>${escapeHtml(shot.characters.join(", ") || "None")}</dd>
        <dt>Props</dt><dd>${escapeHtml(shot.props.join(", ") || "None")}</dd>
        <dt>Action</dt><dd>${escapeHtml(shot.action_focus)}</dd>
        <dt>Sound</dt><dd>${escapeHtml(shot.dialogue_or_sound)}</dd>
        <dt>Duration</dt><dd>${escapeHtml(shot.duration_seconds)}s · ${escapeHtml(shot.aspect_ratio)}</dd>
        <dt>Style</dt><dd>${escapeHtml(shot.visual_style)}</dd>
        <dt>Image Prompt</dt><dd>${escapeHtml(shot.image_prompt)}</dd>
      </dl>
      <div class="storyboard-shot-actions">
        <span class="status-pill status-${shot.prompt_ready ? "completed" : "pending"}">
          ${shot.prompt_ready ? "Prompt ready" : "Prompt not ready"}
        </span>
        <button class="secondary-button" type="button" data-storyboard-review="${escapeHtml(shot.id)}" data-review-status="approved">批准</button>
        <button class="secondary-button" type="button" data-storyboard-review="${escapeHtml(shot.id)}" data-review-status="needs_changes">需修改</button>
      </div>
    </article>
  `;
}

function renderStoryboardAssets(assets, relationships) {
  if (!assets.length) return `<div class="empty">No story assets</div>`;
  return assets
    .map((asset) => {
      const appearances = relationships
        .filter((relationship) => relationship.asset_id === asset.id)
        .map((relationship) => `#${relationship.shot_sequence_index} ${relationship.role}`);
      return `
        <article class="story-asset">
          <strong>${escapeHtml(asset.asset_type)} · ${escapeHtml(asset.name)}</strong>
          <p>${escapeHtml(asset.description)}</p>
          <small>${escapeHtml(asset.consistency_notes || "No consistency notes")}</small>
          <small>Shots: ${escapeHtml(appearances.join(", ") || "None")}</small>
        </article>
      `;
    })
    .join("");
}

function renderStoryboardImageLinks(selectedShot, storyboard) {
  if (!selectedShot) return `<div class="empty">Select a shot after generation</div>`;
  const imageAssets = storyboard?.image_assets || [];
  if (!imageAssets.length) return `<div class="empty">No project image assets</div>`;
  const links = storyboard?.image_links || [];
  return imageAssets
    .map((asset) => {
      const linked = links.some(
        (link) =>
          link.shot_id === selectedShot.id &&
          link.image_asset.id === asset.id &&
          link.link_type === "reference",
      );
      return `
        <article class="storyboard-image-link">
          <div>
            <strong>${escapeHtml(asset.model)}</strong>
            <p>${escapeHtml(asset.prompt)}</p>
          </div>
          <button
            class="secondary-button"
            type="button"
            data-storyboard-image-shot="${escapeHtml(selectedShot.id)}"
            data-storyboard-image-asset="${escapeHtml(asset.id)}"
            data-linked="${linked ? "true" : "false"}"
          >
            ${linked ? "解除关联" : "关联到选中镜头"}
          </button>
        </article>
      `;
    })
    .join("");
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
  if (state.reviewNotesEditing && state.project?.status === "completed") {
    renderReviewNotesEditor(state.project.review_notes, report);
    return;
  }

  const issues = report.issues.length
    ? report.issues.map(renderQualityIssue).join("")
    : `<div class="empty">No blocking issues found</div>`;

  el.scriptPreview.innerHTML = `
    ${renderReviewNotesAction()}
    <div class="quality-summary status-${escapeHtml(report.status)}">
      <strong>${escapeHtml(report.label)}</strong>
      <span>${escapeHtml(report.summary)}</span>
    </div>
    <div class="quality-metrics">
      ${report.metrics.map(renderQualityMetric).join("")}
    </div>
    ${renderReviewNotes(state.project?.review_notes)}
    <div class="review-section">
      <h3>Release Checks</h3>
      <div class="quality-issue-list">${issues}</div>
    </div>
  `;
  const editButton = el.scriptPreview.querySelector("[data-edit-review-notes]");
  if (editButton) {
    editButton.addEventListener("click", () => {
      state.reviewNotesEditing = true;
      renderScript();
    });
  }
}

function renderReviewNotesAction() {
  if (state.project?.status !== "completed") return "";
  const label = state.project.review_notes ? "编辑发布备注" : "添加发布备注";
  return `
    <div class="review-actions">
      <button class="secondary-button full-width" type="button" data-edit-review-notes>
        ${label}
      </button>
    </div>
  `;
}

function renderReviewNotes(notes) {
  if (!notes) return "";
  return `
    <div class="review-section">
      <h3>Human Review</h3>
      <div class="review-notes-card status-${escapeHtml(notes.release_status)}">
        <strong>${escapeHtml(releaseStatusLabel(notes.release_status))}</strong>
        <p>${escapeHtml(notes.summary)}</p>
      </div>
      ${renderReviewActionItems(notes.action_items || [])}
      ${renderChecklist("Next Actions", notes.next_actions || [])}
      ${renderChecklist("Approval Notes", notes.approval_notes || [])}
    </div>
  `;
}

function renderReviewNotesEditor(notes, report) {
  const values = notes || {
    release_status: "",
    summary: "",
    next_actions: report.issues.map((issue) => `${issue.title}: ${issue.detail}`),
    approval_notes: [],
    action_items: report.issues.map((issue) => ({
      text: `${issue.title}: ${issue.detail}`,
      status: issue.severity === "blocker" ? "blocked" : "open",
    })),
  };
  const actionItems = [...(values.action_items || []), { text: "", status: "open" }];
  el.scriptPreview.innerHTML = `
    <form id="reviewNotesEditor" class="review-notes-editor">
      <label for="reviewReleaseStatus">Release Status</label>
      <select id="reviewReleaseStatus" name="release_status">
        <option value="">选择发布状态</option>
        ${renderOption("ready", "Ready", values.release_status)}
        ${renderOption("needs_edits", "Needs Edits", values.release_status)}
        ${renderOption("blocked", "Blocked", values.release_status)}
      </select>
      <label for="reviewSummary">Review Summary</label>
      <textarea id="reviewSummary" name="summary" rows="4" maxlength="500">${escapeHtml(
        values.summary || "",
      )}</textarea>
      <label for="reviewNextActions">Next Actions</label>
      <textarea id="reviewNextActions" name="next_actions" rows="5">${escapeHtml(
        (values.next_actions || []).join("\n"),
      )}</textarea>
      <div class="review-section">
        <h3>Review Tasks</h3>
        <div id="reviewActionItems" class="review-action-editor-list">
          ${actionItems.map(renderReviewActionEditor).join("")}
        </div>
        <button class="secondary-button full-width" type="button" data-add-review-action>
          添加发布任务
        </button>
      </div>
      <label for="reviewApprovalNotes">Approval Notes</label>
      <textarea id="reviewApprovalNotes" name="approval_notes" rows="4">${escapeHtml(
        (values.approval_notes || []).join("\n"),
      )}</textarea>
      <div class="form-actions">
        <button class="secondary-button" type="button" data-cancel-review-notes>取消</button>
        <button class="primary-button" type="submit">保存发布备注</button>
      </div>
    </form>
  `;
  el.scriptPreview
    .querySelector("#reviewNotesEditor")
    .addEventListener("submit", saveReviewNotes);
  el.scriptPreview.querySelector("[data-cancel-review-notes]").addEventListener("click", () => {
    state.reviewNotesEditing = false;
    renderScript();
  });
  el.scriptPreview.querySelector("[data-add-review-action]").addEventListener("click", () => {
    addReviewActionEditorRow();
  });
}

function renderReviewActionItems(actionItems) {
  if (!actionItems.length) return "";
  return `
    <div class="review-action-list">
      ${actionItems
        .map(
          (item) => `
            <article class="review-action-item status-${escapeHtml(item.status)}">
              <span>${escapeHtml(reviewActionStatusLabel(item.status))}</span>
              <p>${escapeHtml(item.text)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderReviewActionEditor(item) {
  return `
    <fieldset class="review-action-editor" data-review-action>
      <label>Task</label>
      <input name="action_text" maxlength="300" value="${escapeHtml(item.text || "")}" />
      <label>Status</label>
      <select name="action_status">
        ${renderActionStatusOptions(item.status || "open")}
      </select>
    </fieldset>
  `;
}

function addReviewActionEditorRow() {
  const list = el.scriptPreview.querySelector("#reviewActionItems");
  list.insertAdjacentHTML("beforeend", renderReviewActionEditor({ text: "", status: "open" }));
}

function renderActionStatusOptions(selectedValue) {
  return [
    renderOption("open", "Open", selectedValue),
    renderOption("done", "Done", selectedValue),
    renderOption("blocked", "Blocked", selectedValue),
  ].join("");
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

function renderDeliveryReview(script, production) {
  if (!state.project || !projectCanExport(state.project)) {
    el.scriptPreview.innerHTML = `<div class="empty">Project is not ready to export</div>`;
    return;
  }

  const report = qualityReport(script, production, state.project.brief || {});
  const manifest = deliveryManifest(state.project, script, production, report);
  el.scriptPreview.innerHTML = `
    <div class="review-actions">
      <button class="secondary-button full-width" type="button" data-download-delivery>
        下载 JSON 成片包
      </button>
    </div>
    <div class="delivery-summary status-${escapeHtml(report.status)}">
      <strong>${escapeHtml(manifest.filename)}</strong>
      <span>${escapeHtml(manifest.status)} · ${escapeHtml(manifest.updated_at)}</span>
    </div>
    <div class="delivery-grid">
      ${manifest.metrics.map(renderDeliveryMetric).join("")}
    </div>
    <div class="review-section">
      <h3>Package Manifest</h3>
      <div class="kv">
        ${renderDeliveryRow("Title", manifest.title)}
        ${renderDeliveryRow("Seed", manifest.seed)}
        ${renderDeliveryRow("Brief", manifest.brief)}
        ${renderDeliveryRow("Review", manifest.review)}
        ${renderDeliveryRow("Review Tasks", manifest.review_tasks)}
        ${renderDeliveryRow("Storyboard", manifest.storyboard)}
        ${renderDeliveryRow("Activity", manifest.activity)}
      </div>
    </div>
    <div class="review-section">
      <h3>Included Sections</h3>
      ${renderChecklist("JSON Export", manifest.sections)}
    </div>
  `;
  el.scriptPreview
    .querySelector("[data-download-delivery]")
    .addEventListener("click", downloadProjectExport);
}

function renderDeliveryMetric(metric) {
  return `
    <div class="delivery-metric">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
    </div>
  `;
}

function renderDeliveryRow(label, value) {
  return `
    <div class="kv-row">
      <div class="kv-key">${escapeHtml(label)}</div>
      <div class="kv-value">${escapeHtml(value)}</div>
    </div>
  `;
}

function deliveryManifest(project, script, production, report) {
  const scenes = Array.isArray(script.scenes) ? script.scenes : [];
  const beats = Array.isArray(script.episode_outline) ? script.episode_outline : [];
  const shots = Array.isArray(production.shot_plan) ? production.shot_plan : [];
  const totalShotSeconds = shots.reduce(
    (total, shot) => total + Number(shot.duration_seconds || 0),
    0,
  );
  const review = project.review_notes
    ? releaseStatusLabel(project.review_notes.release_status)
    : "Not reviewed";
  const reviewTasks = reviewActionSummary(project.review_notes?.action_items || []);
  const agentOutputs = project.nodes.filter((node) => node.output).length;
  const storyboard = state.storyboard;
  const storyboardShots = storyboard?.has_completed_result ? storyboard.shots || [] : [];
  const approvedStoryboardShots = storyboardShots.filter(
    (shot) => shot.review_status === "approved",
  ).length;
  const promptReadyShots = storyboardShots.filter((shot) => shot.prompt_ready).length;
  const storyboardSummary = storyboard?.has_completed_result
    ? `${storyboardShots.length} shots · ${approvedStoryboardShots} approved · ${promptReadyShots} prompt ready`
    : "Not generated";
  return {
    filename: exportFileName(project),
    title: project.title || "Untitled",
    seed: project.seed_text,
    status: report.label,
    updated_at: formatTime(project.updated_at),
    brief: briefSummary(project.brief),
    review,
    review_tasks: reviewTasks,
    storyboard: storyboardSummary,
    activity: `${state.activity.length} timeline events`,
    metrics: [
      { label: "Scenes", value: String(scenes.length) },
      { label: "Beats", value: String(beats.length) },
      { label: "Shots", value: String(shots.length) },
      { label: "Storyboard", value: String(storyboardShots.length) },
      { label: "Shot Time", value: formatDuration(totalShotSeconds) },
    ],
    sections: [
      "project metadata",
      `script: ${beats.length} beats, ${scenes.length} scenes`,
      `production_pack: ${shots.length} shots`,
      `image_assets: ${(project.image_assets || []).length}`,
      `storyboard: ${storyboardSummary}`,
      `storyboard_image_links: ${storyboard?.image_links?.length || 0}`,
      `review_notes: ${review}`,
      `review_tasks: ${reviewTasks}`,
      `agent_outputs: ${agentOutputs} nodes`,
      `activity: ${state.activity.length} events`,
    ],
  };
}

function reviewActionSummary(actionItems) {
  if (!actionItems.length) return "No tracked tasks";
  const counts = actionItemCounts(actionItems);
  return `${counts.open} open · ${counts.blocked} blocked · ${counts.done} done`;
}

function actionItemCounts(actionItems) {
  return actionItems.reduce(
    (counts, item) => {
      if (item.status === "open") counts.open += 1;
      if (item.status === "blocked") counts.blocked += 1;
      if (item.status === "done") counts.done += 1;
      return counts;
    },
    { open: 0, blocked: 0, done: 0 },
  );
}

function briefSummary(brief) {
  if (!brief) return "—";
  const parts = [];
  if (brief.duration_minutes) parts.push(`${brief.duration_minutes} min`);
  if (brief.aspect_ratio) parts.push(brief.aspect_ratio);
  if (brief.tone) parts.push(brief.tone);
  if (brief.target_audience) parts.push(brief.target_audience);
  if (brief.must_include) parts.push(`Must include: ${brief.must_include}`);
  return parts.join(" · ") || "—";
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

function renderNodeInstructionsEditor(node) {
  if (node.kind !== "agent") return "";
  const guidance = node.instructions?.guidance || "";
  const disabled = state.project?.status === "running" && node.status !== "pending";
  return `
    <form class="node-instruction-editor" data-node-instructions="${escapeHtml(node.key)}">
      <label for="nodeGuidance-${escapeHtml(node.key)}">Node Guidance</label>
      <textarea
        id="nodeGuidance-${escapeHtml(node.key)}"
        name="guidance"
        rows="4"
        maxlength="1000"
        ${disabled ? "disabled" : ""}
      >${escapeHtml(guidance)}</textarea>
      <button class="secondary-button full-width" type="submit" ${disabled ? "disabled" : ""}>
        保存节点指令
      </button>
    </form>
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

function reviewNotesFromEditor(form) {
  return {
    release_status: form.querySelector("[name='release_status']").value,
    summary: form.querySelector("[name='summary']").value.trim(),
    next_actions: linesFromTextarea(form.querySelector("[name='next_actions']")),
    approval_notes: linesFromTextarea(form.querySelector("[name='approval_notes']")),
    action_items: Array.from(form.querySelectorAll("[data-review-action]"))
      .map((group) => ({
        text: group.querySelector("[name='action_text']").value.trim(),
        status: group.querySelector("[name='action_status']").value,
      }))
      .filter((item) => item.text),
  };
}

function linesFromTextarea(textarea) {
  return textarea.value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function releaseStatusLabel(status) {
  const labels = {
    ready: "Ready",
    needs_edits: "Needs Edits",
    blocked: "Blocked",
  };
  return labels[status];
}

function reviewActionStatusLabel(status) {
  const labels = {
    open: "Open",
    done: "Done",
    blocked: "Blocked",
  };
  return labels[status] || status;
}

function renderActivity() {
  renderRuntimeSummary();
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

function renderRuntimeSummary() {
  if (!state.project) {
    el.runtimeSummary.innerHTML = "";
    return;
  }

  const runtime = state.runtime || {};
  const started = runtime.started_at ? formatTime(runtime.started_at) : "Not started";
  const elapsed =
    runtime.elapsed_seconds === null || runtime.elapsed_seconds === undefined
      ? "—"
      : formatDuration(runtime.elapsed_seconds);
  const active = runtime.active_node
    ? `${runtime.active_node.title} · ${formatDuration(runtime.active_node.elapsed_seconds)}`
    : "—";
  const lastActivity = runtime.last_activity
    ? `${runtime.last_activity.title} · ${formatTime(runtime.last_activity.occurred_at)}`
    : "—";

  el.runtimeSummary.innerHTML = `
    <div class="runtime-card">
      <span>Started</span>
      <strong>${escapeHtml(started)}</strong>
    </div>
    <div class="runtime-card">
      <span>Elapsed</span>
      <strong>${escapeHtml(elapsed)}</strong>
    </div>
    <div class="runtime-card">
      <span>Active Node</span>
      <strong>${escapeHtml(active)}</strong>
    </div>
    <div class="runtime-card">
      <span>Last Activity</span>
      <strong>${escapeHtml(lastActivity)}</strong>
    </div>
  `;
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
  const runtimeSuffix =
    state.runtime?.elapsed_seconds === null || state.runtime?.elapsed_seconds === undefined
      ? ""
      : ` · ${formatDuration(state.runtime.elapsed_seconds)}`;
  const label = `${progressLabel(project, progress)}${runtimeSuffix}`;
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

function projectNextActionLabel(project) {
  const progress = project.progress;
  if (project.status === "failed") {
    return progress.failed_title
      ? `Next: reset or revise ${progress.failed_title}`
      : "Next: reset failed run";
  }
  if (project.status === "running") {
    return progress.active_title
      ? `Now running: ${progress.active_title}`
      : "Now running: starting agents";
  }
  if (project.status === "paused") {
    return progress.active_title
      ? `Next: wait for ${progress.active_title} to pause`
      : "Next: continue agent run";
  }
  if (project.status === "completed") {
    if (!project.review_notes) return "Next: review release checks";
    return "Next: export deliverable package";
  }
  const nextNode = nextPendingAgent(project, progress);
  if (nextNode && progress.completed > 0) {
    return `Next: continue from ${nextNode.title}`;
  }
  return "Next: edit brief or run agents";
}

function nextPendingAgent(project, progress) {
  const node = project.nodes?.find((item) => item.kind === "agent" && item.status !== "completed");
  if (node) return node;
  return AGENT_SEQUENCE[Math.min(progress.completed, AGENT_SEQUENCE.length - 1)];
}

function renderProjectRowProgress(project) {
  const progress = project.progress;
  const percent = progress.total ? Math.round((progress.completed / progress.total) * 100) : 0;
  return `
    <div class="project-progress-label">${escapeHtml(progressLabel(project, progress))}</div>
    <div class="progress-track" aria-label="Project agent progress">
      <span style="width:${percent}%"></span>
    </div>
  `;
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
    state.runtime = body.runtime || null;
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

function restoreWorkspaceState() {
  const rawValue = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
  if (!rawValue) return;

  const saved = JSON.parse(rawValue);
  if (Number.isInteger(saved.projectId)) {
    state.restoredProjectId = saved.projectId;
  }
  if (typeof saved.selectedKey === "string" && NODE_KEYS.has(saved.selectedKey)) {
    state.selectedKey = saved.selectedKey;
  }
  if (typeof saved.reviewTab === "string" && REVIEW_TABS.has(saved.reviewTab)) {
    state.reviewTab = saved.reviewTab;
  }
  if (saved.filters) {
    if (typeof saved.filters.search === "string") {
      state.projectFilters.search = saved.filters.search;
      el.projectSearch.value = saved.filters.search;
    }
    if (typeof saved.filters.status === "string" && PROJECT_STATUSES.has(saved.filters.status)) {
      state.projectFilters.status = saved.filters.status;
      el.projectStatusFilter.value = saved.filters.status;
    }
  }
}

function saveWorkspaceState() {
  const payload = {
    projectId: state.project?.id || state.restoredProjectId,
    selectedKey: state.selectedKey,
    reviewTab: state.reviewTab,
    filters: state.projectFilters,
    savedAt: new Date().toISOString(),
  };
  window.localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(payload));
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

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(total / 60);
  const remainingSeconds = total % 60;
  if (minutes < 1) return `${remainingSeconds}s`;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
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
