const state = {
  projects: [],
  project: null,
  selectedKey: "seed",
  running: false,
};

const el = {
  seedText: document.querySelector("#seedText"),
  createProject: document.querySelector("#createProject"),
  refreshProjects: document.querySelector("#refreshProjects"),
  runProject: document.querySelector("#runProject"),
  projectList: document.querySelector("#projectList"),
  nodeLayer: document.querySelector("#nodeLayer"),
  edgeLayer: document.querySelector("#edgeLayer"),
  canvasTitle: document.querySelector("#canvasTitle"),
  canvasMeta: document.querySelector("#canvasMeta"),
  projectStatus: document.querySelector("#projectStatus"),
  inspectorBody: document.querySelector("#inspectorBody"),
  scriptPreview: document.querySelector("#scriptPreview"),
};

el.createProject.addEventListener("click", createProject);
el.refreshProjects.addEventListener("click", loadProjects);
el.runProject.addEventListener("click", runProject);

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
    const body = await api("/api/projects");
    state.projects = body.projects;
    if (!state.project && state.projects.length > 0) {
      await loadProject(state.projects[0].id);
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
      body: JSON.stringify({ seed_text: seedText }),
    });
    state.project = body.project;
    state.selectedKey = "seed";
    el.seedText.value = "";
    await loadProjects();
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function runProject() {
  if (!state.project) return;
  setBusy(true);
  state.project.status = "running";
  render();

  try {
    const body = await api(`/api/projects/${state.project.id}/run`, { method: "POST" });
    state.project = body.project;
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
      body: JSON.stringify({ title, seed_text: seedText }),
    });
    state.project = body.project;
    state.selectedKey = "seed";
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
}

function renderHeader() {
  const project = state.project;
  el.runProject.disabled = !project || state.running || project.status === "running";
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
  if (!script) {
    el.scriptPreview.innerHTML = `<div class="empty">No script</div>`;
    return;
  }
  const scenes = script.scenes
    .map(
      (scene) => `
        <div class="scene">
          <strong>${scene.scene_number}. ${escapeHtml(scene.setting)} · ${escapeHtml(scene.time)}</strong>
          <p>${escapeHtml(scene.summary)}</p>
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
    </div>
    ${scenes}
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
