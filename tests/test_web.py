from __future__ import annotations

from fastapi.testclient import TestClient
from test_schema import valid_payload
from test_storyboard import completed_project_storage, valid_storyboard_payload

import vidiom.web as web_module
from vidiom.canvas import create_canvas_project
from vidiom.config import Settings
from vidiom.providers import ImageGenerationResult
from vidiom.storage import Storage
from vidiom.web import STATIC_DIR, app, get_image_client, get_settings, get_storage


class FakeImageClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def generate_image(self, *, model: str, prompt: str) -> ImageGenerationResult:
        self.calls.append({"model": model, "prompt": prompt})
        if self.error is not None:
            raise self.error
        return ImageGenerationResult(
            artifact_url="https://provider.test/generated/image-1.png",
            b64_json=None,
            revised_prompt="cinematic vertical frame",
            provider_response={
                "id": "img_1",
                "data": [
                    {
                        "url": "https://provider.test/generated/image-1.png",
                        "revised_prompt": "cinematic vertical frame",
                    }
                ],
            },
        )


def test_studio_static_review_panel_exposes_workflow_tabs() -> None:
    index_html = (STATIC_DIR / "index.html").read_text()
    app_js = (STATIC_DIR / "app.js").read_text()

    assert 'id="exportProject"' in index_html
    assert 'id="duplicateProject"' in index_html
    assert 'id="resetProject"' in index_html
    assert 'id="pauseProject"' in index_html
    assert 'id="runProgress"' in index_html
    assert 'id="runtimeSummary"' in index_html
    assert 'id="runReadiness"' in index_html
    assert 'id="projectSearch"' in index_html
    assert 'id="projectStatusFilter"' in index_html
    assert '<option value="paused">Paused</option>' in index_html
    assert 'name="duration_minutes"' in index_html
    assert 'name="aspect_ratio"' in index_html
    assert 'data-review-tab="script"' in index_html
    assert 'data-review-tab="characters"' in index_html
    assert 'data-review-tab="production"' in index_html
    assert 'data-review-tab="images"' in index_html
    assert 'data-review-tab="storyboard"' in index_html
    assert 'data-review-tab="quality"' in index_html
    assert 'data-review-tab="delivery"' in index_html
    assert "function briefFromForm" in app_js
    assert "function renderBriefFields" in app_js
    assert "function projectListQuery" in app_js
    assert "function applyProjectFilters" in app_js
    assert "vidiom.studio.workspace.v1" in app_js
    assert "function restoreWorkspaceState" in app_js
    assert "function saveWorkspaceState" in app_js
    assert "function projectNextActionLabel" in app_js
    assert "function nextPendingAgent" in app_js
    assert "project-row-next" in app_js
    assert "function renderProjectRowProgress" in app_js
    assert "function startProjectPolling" in app_js
    assert "function pollRunningProject" in app_js
    assert "function renderRunProgress" in app_js
    assert "function renderRuntimeSummary" in app_js
    assert "function renderRunReadiness" in app_js
    assert "function runReadinessReport" in app_js
    assert "function readinessCheck" in app_js
    assert "function renderReadinessMetric" in app_js
    assert "function renderReadinessCheck" in app_js
    assert "Run Scope" in app_js
    assert "Ready with notes" in app_js
    assert "data-readiness-select" in app_js
    assert "function formatDuration" in app_js
    assert "async function downloadProjectExport" in app_js
    assert "async function duplicateProject" in app_js
    assert "async function pauseProject" in app_js
    assert "async function reviseProjectFromNode" in app_js
    assert "async function resetProject" in app_js
    assert "function renderRevisionAction" in app_js
    assert "data-revise-node" in app_js
    assert "function renderCharacterReview" in app_js
    assert "function renderProductionReview" in app_js
    assert "async function saveProductionEdits" in app_js
    assert "function renderProductionEditor" in app_js
    assert "function productionFromEditor" in app_js
    assert "data-edit-production" in app_js
    assert "async function generateProjectImage" in app_js
    assert "function renderImageReview" in app_js
    assert "function renderImageAsset" in app_js
    assert "/images" in app_js
    assert "async function loadStoryboard" in app_js
    assert "async function generateStoryboard" in app_js
    assert "function renderStoryboardReview" in app_js
    assert "function renderStoryboardShot" in app_js
    assert "function renderStoryboardAssets" in app_js
    assert "/storyboard/generate" in app_js
    assert "function renderQualityReview" in app_js
    assert "function qualityReport" in app_js
    assert "function missingItems" in app_js
    assert "Release Checks" in app_js
    assert "function renderDeliveryReview" in app_js
    assert "function deliveryManifest" in app_js
    assert "function briefSummary" in app_js
    assert "Package Manifest" in app_js
    assert "data-download-delivery" in app_js
    assert "async function saveReviewNotes" in app_js
    assert "function renderReviewNotesEditor" in app_js
    assert "function reviewNotesFromEditor" in app_js
    assert "function renderReviewActionItems" in app_js
    assert "function reviewActionSummary" in app_js
    assert "data-review-action" in app_js
    assert "Review Tasks" in app_js
    assert "async function saveNodeInstructions" in app_js
    assert "function renderNodeInstructionsEditor" in app_js
    assert "data-node-instructions" in app_js
    assert "Node Guidance" in app_js
    assert "/instructions" in app_js
    assert "/review-notes" in app_js
    assert "async function saveScriptEdits" in app_js
    assert "function renderScriptEditor" in app_js
    assert "function scriptFromEditor" in app_js
    assert "/script" in app_js
    assert "/production" in app_js


def test_create_project_api(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(
            "/api/projects",
            json={
                "seed_text": "一个剪辑师发现素材里藏着未来事故。",
                "brief": {
                    "duration_minutes": 5,
                    "aspect_ratio": "9:16 vertical",
                    "tone": "强钩子、快反转",
                    "target_audience": "18-35 岁短剧用户",
                    "must_include": "前三秒出现异常素材",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["status"] == "draft"
    assert body["project"]["brief"]["duration_minutes"] == 5
    assert body["project"]["brief"]["must_include"] == "前三秒出现异常素材"
    assert body["progress"]["completed"] == 0
    assert body["progress"]["total"] == 5
    assert body["project"]["nodes"][0]["key"] == "seed"
    assert body["project"]["nodes"][0]["output"]["brief"]["aspect_ratio"] == "9:16 vertical"


def test_list_projects_api_filters_by_status_and_query(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    draft_id = create_canvas_project(storage, "一个旧剧本顾问被迫重写失败短剧。")
    completed_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    failed_id = create_canvas_project(storage, "一个制片人在直播间遇到消失的主演。")
    storage.update_project_title(completed_id, "未来素材案")
    storage.complete_canvas_node(
        completed_id,
        "premise",
        {
            "one_sentence_pitch": "剪辑师被未来素材拖进救援。",
            "genre": "悬疑",
            "target_audience": "18-35 岁短剧用户",
            "emotional_hook": "错过报警的人必须补上选择。",
            "story_promise": "每个素材细节都会变成救人的线索。",
            "risk_flags": [],
        },
    )
    storage.update_project_status(completed_id, "completed")
    storage.update_canvas_node_status(failed_id, "characters", "failed", "模型返回结构无效")
    storage.update_project_status(failed_id, "failed", "模型返回结构无效")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        completed_response = client.get("/api/projects?status=completed")
        search_response = client.get("/api/projects?q=未来素材")
        failed_search_response = client.get("/api/projects?status=failed&q=直播间")
    finally:
        app.dependency_overrides.clear()

    assert completed_response.status_code == 200
    completed_projects = completed_response.json()["projects"]
    assert [project["id"] for project in completed_projects] == [completed_id]
    assert completed_projects[0]["progress"] == {
        "completed": 1,
        "total": 5,
        "active_key": None,
        "active_title": None,
        "failed_key": None,
        "failed_title": None,
    }
    assert search_response.status_code == 200
    assert [project["id"] for project in search_response.json()["projects"]] == [completed_id]
    assert failed_search_response.status_code == 200
    failed_projects = failed_search_response.json()["projects"]
    assert [project["id"] for project in failed_projects] == [failed_id]
    assert failed_projects[0]["progress"]["failed_key"] == "characters"
    assert failed_projects[0]["progress"]["failed_title"] == "Character Agent"
    assert draft_id not in [project["id"] for project in search_response.json()["projects"]]


def test_update_draft_project_api_updates_seed_node(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/projects",
            json={"seed_text": "一个剪辑师发现素材里藏着未来事故。"},
        )
        project_id = create_response.json()["project"]["id"]

        response = client.patch(
            f"/api/projects/{project_id}",
            json={
                "title": "未来素材案",
                "seed_text": "一个剪辑师在客户素材里看见明天的事故现场。",
                "brief": {
                    "duration_minutes": 8,
                    "aspect_ratio": "16:9 landscape",
                    "tone": "现实悬疑",
                    "target_audience": "都市悬疑用户",
                    "must_include": "结尾保留新倒计时",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["title"] == "未来素材案"
    assert project["seed_text"] == "一个剪辑师在客户素材里看见明天的事故现场。"
    assert project["brief"]["duration_minutes"] == 8
    assert project["brief"]["tone"] == "现实悬疑"
    assert project["nodes"][0]["output"]["text"] == project["seed_text"]
    assert project["nodes"][0]["output"]["brief"]["must_include"] == "结尾保留新倒计时"


def test_update_draft_project_api_clears_stale_agent_outputs(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(
        project_id,
        "premise",
        {
            "one_sentence_pitch": "旧 seed 的故事承诺",
            "genre": "悬疑",
            "target_audience": "18-35 岁短剧用户",
            "emotional_hook": "旧情绪钩子",
            "story_promise": "旧线索会回收",
            "risk_flags": [],
        },
    )

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}",
            json={
                "seed_text": "一个制片人在直播间看见消失主演的求救弹幕。",
                "brief": {"duration_minutes": 3, "aspect_ratio": "9:16 vertical"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    nodes = {node["key"]: node for node in response.json()["project"]["nodes"]}
    assert nodes["seed"]["output"]["text"] == "一个制片人在直播间看见消失主演的求救弹幕。"
    assert nodes["premise"]["status"] == "pending"
    assert nodes["premise"]["output"] is None


def test_update_node_instructions_api_persists_agent_guidance(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/nodes/script/instructions",
            json={"guidance": "对白更短，每场保留一个强反转。"},
        )
        seed_response = client.patch(
            f"/api/projects/{project_id}/nodes/seed/instructions",
            json={"guidance": "无效"},
        )
        clear_response = client.patch(
            f"/api/projects/{project_id}/nodes/script/instructions",
            json={"guidance": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    nodes = {node["key"]: node for node in response.json()["project"]["nodes"]}
    assert nodes["script"]["instructions"] == {
        "guidance": "对白更短，每场保留一个强反转。"
    }
    activity = response.json()["activity"]
    assert activity[-1]["type"] == "node_instruction"
    assert activity[-1]["details"]["node_key"] == "script"
    assert seed_response.status_code == 422
    assert clear_response.status_code == 200
    cleared_nodes = {node["key"]: node for node in clear_response.json()["project"]["nodes"]}
    assert cleared_nodes["script"]["instructions"] is None


def test_get_project_api_returns_activity_timeline(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/projects",
            json={"seed_text": "一个剪辑师发现素材里藏着未来事故。"},
        )
        project_id = create_response.json()["project"]["id"]

        response = client.get(f"/api/projects/{project_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    activity = response.json()["activity"]
    assert activity[0]["title"] == "Project created"
    assert activity[0]["status"] == "completed"
    assert activity[1]["title"] == "Seed"
    assert activity[1]["description"] == "一个剪辑师发现素材里藏着未来事故。"
    assert activity[-1]["title"] == "Production Agent"
    assert activity[-1]["status"] == "pending"
    assert response.json()["progress"] == {
        "completed": 0,
        "total": 5,
        "active_key": None,
        "active_title": None,
        "failed_key": None,
        "failed_title": None,
    }
    runtime = response.json()["runtime"]
    assert runtime["started_at"] is None
    assert runtime["elapsed_seconds"] is None
    assert runtime["active_node"] is None
    assert runtime["last_activity"]["title"] == "Seed"


def test_run_project_api_starts_observable_background_run(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    def no_background_run(database_path, project_id, model) -> None:
        assert database_path == db_path
        assert project_id == 1
        assert model == "gpt-5.5"

    monkeypatch.setattr(web_module, "_run_project_job", no_background_run)
    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/run")
        duplicate_response = client.post(f"/api/projects/{project_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["status"] == "running"
    assert body["activity"][0]["title"] == "Project created"
    status_event = body["activity"][-1]
    assert status_event["type"] == "status_change"
    assert status_event["title"] == "Project run started"
    assert status_event["details"]["previous_status"] == "draft"
    assert status_event["details"]["status"] == "running"
    assert body["progress"]["completed"] == 0
    assert body["progress"]["total"] == 5
    assert body["runtime"]["started_at"] == status_event["occurred_at"]
    assert body["runtime"]["elapsed_seconds"] >= 0
    assert body["runtime"]["last_activity"]["title"] == "Project run started"
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Project is already running."


def test_background_project_job_keeps_persisted_failure_inside_worker(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "studio.sqlite3"
    storage = Storage(db_path)
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")

    def failing_run(storage, project_id, agent) -> None:
        storage.update_project_status(project_id, "failed", "模型连接失败")
        raise RuntimeError("模型连接失败")

    monkeypatch.setattr(web_module, "run_canvas_project", failing_run)

    web_module._run_project_job(db_path, project_id, "test-model")

    project = Storage(db_path).get_project(project_id)
    activity = Storage(db_path).get_project_activity(project_id)
    assert project["status"] == "failed"
    assert activity[-1]["title"] == "Project failed"
    assert activity[-1]["description"] == "模型连接失败"


def test_pause_project_api_marks_running_project_and_blocks_early_resume(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.update_project_status(project_id, "running")
    storage.update_canvas_node_status(project_id, "premise", "running", None)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/pause")
        resume_response = client.post(f"/api/projects/{project_id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["status"] == "paused"
    assert body["progress"]["active_key"] == "premise"
    assert body["progress"]["active_title"] == "Premise Agent"
    assert body["activity"][-1]["title"] == "Project paused"
    assert body["activity"][-1]["details"]["previous_status"] == "running"
    assert body["runtime"]["started_at"] is not None
    assert body["runtime"]["finished_at"] == body["project"]["updated_at"]
    assert body["runtime"]["active_node"]["key"] == "premise"
    assert body["runtime"]["active_node"]["elapsed_seconds"] >= 0
    assert resume_response.status_code == 400
    assert resume_response.json()["detail"] == "Project is still pausing after the active node."


def test_reset_project_api_turns_failed_project_back_into_editable_draft(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(
        project_id,
        "premise",
        {
            "one_sentence_pitch": "剪辑师被未来素材拖进救援。",
            "genre": "悬疑",
            "target_audience": "18-35 岁短剧用户",
            "emotional_hook": "错过报警的人必须补上选择。",
            "story_promise": "每个素材细节都会变成救人的线索。",
            "risk_flags": [],
        },
    )
    storage.update_canvas_node_status(project_id, "characters", "failed", "模型超时")
    storage.update_project_status(project_id, "failed", "模型超时")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/reset")
        second_response = client.post(f"/api/projects/{project_id}/reset")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    nodes = {node["key"]: node for node in project["nodes"]}
    assert project["status"] == "draft"
    assert project["last_error"] is None
    assert nodes["premise"]["status"] == "completed"
    assert nodes["premise"]["output"]["one_sentence_pitch"] == "剪辑师被未来素材拖进救援。"
    assert nodes["characters"]["status"] == "pending"
    assert nodes["characters"]["error"] is None
    assert response.json()["progress"] == {
        "completed": 1,
        "total": 5,
        "active_key": None,
        "active_title": None,
        "failed_key": None,
        "failed_title": None,
    }
    assert response.json()["activity"][-1]["title"] == "Project reset to draft"
    assert response.json()["activity"][-1]["details"]["previous_status"] == "failed"
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Only failed projects can be reset."


def test_export_project_api_returns_completed_deliverable_package(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.complete_canvas_node(project_id, "production", production_output())
    storage.update_canvas_node_instructions(
        project_id,
        "script",
        {"guidance": "对白更短，每场保留一个强反转。"},
    )
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert (
        "filename*=UTF-8''vidiom-%E5%80%92%E8%AE%A1%E6%97%B6%E7%B4%A0%E6%9D%90.json"
        in response.headers["content-disposition"]
    )
    body = response.json()
    assert body["project"]["title"] == "倒计时素材"
    assert body["project"]["brief"] is None
    assert body["project"]["agent_instructions"]["script"]["guidance"] == (
        "对白更短，每场保留一个强反转。"
    )
    assert body["deliverables"]["script"]["title"] == "倒计时素材"
    assert body["deliverables"]["production_pack"]["shot_plan"][0]["shot"] == "屏幕特写"
    assert "storyboard" not in body["deliverables"]
    assert body["agent_outputs"]["seed"]["text"] == "一个剪辑师发现素材里藏着未来事故。"


def test_export_project_api_includes_completed_storyboard_deliverable(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.complete_canvas_node(project_id, "production", production_output())
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")
    storage.replace_project_storyboard(project_id, valid_storyboard_payload(), model="gpt-5.5")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    storyboard = response.json()["deliverables"]["storyboard"]
    assert storyboard["storyboard"]["status"] == "completed"
    assert storyboard["shots"][0]["sequence_index"] == 1
    assert storyboard["assets"][0]["asset_type"] == "character"


def test_storyboard_api_gets_not_started_and_generates_completed_payload(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    def complete_storyboard_job(database_path, project_id, model) -> None:
        assert database_path == db_path
        assert model == "gpt-5.5"
        storage = Storage(database_path)
        storage.migrate()
        storage.replace_project_storyboard(project_id, valid_storyboard_payload(), model=model)

    storage, project_id = completed_project_storage(tmp_path)
    db_path = storage.db_path
    monkeypatch.setattr(web_module, "_generate_storyboard_job", complete_storyboard_job)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        initial_response = client.get(f"/api/projects/{project_id}/storyboard")
        generate_response = client.post(f"/api/projects/{project_id}/storyboard/generate")
        refreshed_response = client.get(f"/api/projects/{project_id}/storyboard")
    finally:
        app.dependency_overrides.clear()

    assert initial_response.status_code == 200
    assert initial_response.json()["storyboard"]["generation_status"] == "not_started"
    assert generate_response.status_code == 200
    assert refreshed_response.status_code == 200
    storyboard = refreshed_response.json()
    assert storyboard["storyboard"]["generation_status"] == "completed"
    assert storyboard["storyboard"]["last_completed_model"] == "gpt-5.5"
    assert storyboard["has_completed_result"] is True
    assert len(storyboard["shots"]) == 2


def test_storyboard_generate_rejects_draft_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/storyboard/generate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Storyboard generation requires a completed project."


def test_storyboard_api_failed_attempt_keeps_previous_completed_result(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    def fail_storyboard_job(database_path, project_id, model) -> None:
        storage = Storage(database_path)
        storage.migrate()
        storage.update_project_storyboard_status(
            project_id,
            status="failed",
            model=model,
            error_message="Provider returned non-JSON storyboard output.",
        )

    storage, project_id = completed_project_storage(tmp_path)
    db_path = storage.db_path
    storage.replace_project_storyboard(project_id, valid_storyboard_payload(), model="gpt-5.5")
    monkeypatch.setattr(web_module, "_generate_storyboard_job", fail_storyboard_job)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        generate_response = client.post(f"/api/projects/{project_id}/storyboard/generate")
        refreshed_response = client.get(f"/api/projects/{project_id}/storyboard")
    finally:
        app.dependency_overrides.clear()

    assert generate_response.status_code == 200
    storyboard = refreshed_response.json()
    assert storyboard["storyboard"]["generation_status"] == "failed"
    assert storyboard["latest_attempt_failed"] is True
    assert storyboard["has_completed_result"] is True
    assert len(storyboard["shots"]) == 2
    assert "non-JSON" in storyboard["storyboard"]["generation_error_message"]


def test_storyboard_review_and_image_link_api(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage, project_id = completed_project_storage(tmp_path)
    db_path = storage.db_path
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    shot_id = storyboard["shots"][0]["id"]
    image_id = storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，林澈盯着异常素材。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/storyboard-frame.png",
    )

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        review_response = client.patch(
            f"/api/projects/{project_id}/storyboard/shots/review",
            json={
                "reviews": [
                    {
                        "shot_id": shot_id,
                        "review_status": "approved",
                        "prompt_ready": True,
                    }
                ]
            },
        )
        link_response = client.post(
            f"/api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{image_id}"
            "?link_type=storyboard_frame",
        )
        unlink_response = client.delete(
            f"/api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{image_id}"
            "?link_type=storyboard_frame",
        )
    finally:
        app.dependency_overrides.clear()

    assert review_response.status_code == 200
    assert review_response.json()["storyboard"]["shots"][0]["review_status"] == "approved"
    assert link_response.status_code == 200
    assert link_response.json()["storyboard"]["image_links"][0]["image_asset"]["id"] == image_id
    assert unlink_response.status_code == 200
    assert unlink_response.json()["storyboard"]["image_links"] == []


def test_update_project_script_api_saves_completed_deliverable_edits(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    original_script = valid_payload()
    storage.complete_canvas_node(project_id, "script", original_script)
    storage.complete_canvas_node(project_id, "production", production_output())
    project = storage.get_project(project_id)
    storage.complete(project["inspiration_id"], original_script)
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    edited_script = valid_payload()
    edited_script["title"] = "倒计时素材：直播版"
    edited_script["logline"] = "剪辑师发现未来事故素材后，选择直播公开证据救下陌生人。"
    edited_script["episode_outline"][0]["beat"] = "直播前的异常素材"
    edited_script["scenes"][0]["dialogue"][0]["line"] = "这不是素材，是明天的求救。"

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/script",
            json={"script": edited_script},
        )
        export_response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    nodes = {node["key"]: node for node in project["nodes"]}
    assert project["title"] == "倒计时素材：直播版"
    assert nodes["script"]["output"]["logline"] == edited_script["logline"]
    assert nodes["script"]["output"]["episode_outline"][0]["beat"] == "直播前的异常素材"
    assert (
        nodes["script"]["output"]["scenes"][0]["dialogue"][0]["line"]
        == "这不是素材，是明天的求救。"
    )
    activity = response.json()["activity"]
    script_edit = activity[-1]
    assert script_edit["type"] == "script_edit"
    assert script_edit["title"] == "Script edits saved"
    assert script_edit["status"] == "completed"
    assert script_edit["description"] == (
        "Updated title, logline; 1 beat; 1 dialogue line"
    )
    assert script_edit["details"]["changed_fields"] == ["title", "logline"]
    assert script_edit["details"]["changed_beats"] == 1
    assert script_edit["details"]["changed_dialogue"] == 1
    assert export_response.json()["deliverables"]["script"]["title"] == "倒计时素材：直播版"
    assert export_response.json()["activity"][-1]["type"] == "script_edit"
    productions = override_storage().list_productions(limit=10)
    assert productions[0].title == "倒计时素材：直播版"
    assert productions[0].payload["logline"] == edited_script["logline"]


def test_update_project_script_api_rejects_non_completed_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "script", valid_payload())

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/script",
            json={"script": valid_payload()},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Only completed projects can have script edits saved."


def test_update_project_production_api_saves_completed_deliverable_edits(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.complete_canvas_node(project_id, "production", production_output())
    project = storage.get_project(project_id)
    storage.complete(project["inspiration_id"], valid_payload())
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    edited_production = production_output()
    edited_production["visual_style"] = "冷色剪辑室与暖色直播画面交替推进"
    edited_production["locations"][0] = "剪辑室工位"
    edited_production["props"][1] = "直播手机"
    edited_production["shot_plan"][0]["purpose"] = "前三秒直接展示未来事故素材"
    edited_production["shot_plan"][0]["duration_seconds"] = 10
    edited_production["edit_notes"][0] = "开场 3 秒叠加素材时间码"

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/production",
            json=edited_production,
        )
        export_response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    nodes = {node["key"]: node for node in project["nodes"]}
    assert nodes["production"]["output"]["visual_style"] == "冷色剪辑室与暖色直播画面交替推进"
    assert nodes["production"]["output"]["locations"][0] == "剪辑室工位"
    assert nodes["production"]["output"]["props"][1] == "直播手机"
    assert nodes["production"]["output"]["shot_plan"][0]["duration_seconds"] == 10
    activity = response.json()["activity"]
    production_edit = activity[-1]
    assert production_edit["type"] == "production_edit"
    assert production_edit["title"] == "Production edits saved"
    assert production_edit["status"] == "completed"
    assert production_edit["description"] == (
        "Updated visual_style; 1 location; 1 prop; 1 shot; 1 edit note"
    )
    assert production_edit["details"]["changed_shots"] == 1
    export_body = export_response.json()
    assert export_body["deliverables"]["production_pack"]["shot_plan"][0]["purpose"] == (
        "前三秒直接展示未来事故素材"
    )
    assert export_body["activity"][-1]["type"] == "production_edit"


def test_update_project_production_api_rejects_non_completed_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "production", production_output())

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/production",
            json=production_output(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Only completed projects can have production edits saved."


def test_update_project_review_notes_api_saves_completed_release_notes(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.complete_canvas_node(project_id, "production", production_output())
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    review_notes = {
        "release_status": "needs_edits",
        "summary": "对白节奏可用，但街口镜头需要补拍。",
        "next_actions": ["补拍街口广角", "确认白车道具"],
        "approval_notes": ["剧本结构通过"],
        "action_items": [
            {"text": "补拍街口广角", "status": "open"},
            {"text": "确认白车道具", "status": "done"},
            {"text": "等待场地许可", "status": "blocked"},
        ],
    }

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/review-notes",
            json=review_notes,
        )
        export_response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["review_notes"] == review_notes
    review_event = response.json()["activity"][-1]
    assert review_event["type"] == "review_notes"
    assert review_event["title"] == "Review notes saved"
    assert review_event["description"] == (
        "Marked needs_edits; 2 next actions; 1 approval note; "
        "1 open, 1 blocked, 1 done review tasks"
    )
    assert review_event["details"]["changed_fields"] == [
        "release_status",
        "summary",
        "next_actions",
        "approval_notes",
        "action_items",
    ]
    assert review_event["details"]["action_item_counts"] == {
        "open": 1,
        "blocked": 1,
        "done": 1,
    }
    export_body = export_response.json()
    assert export_body["project"]["review_notes"] == review_notes
    assert export_body["deliverables"]["review_notes"] == review_notes
    assert export_body["activity"][-1]["type"] == "review_notes"


def test_update_project_review_notes_api_rejects_non_completed_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/projects/{project_id}/review-notes",
            json={
                "release_status": "ready",
                "summary": "可发布。",
                "next_actions": [],
                "approval_notes": ["人工通过"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Only completed projects can have review notes saved."


def test_export_project_api_rejects_draft_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.get(f"/api/projects/{project_id}/export")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Project is not ready to export."


def test_duplicate_project_api_creates_editable_draft_copy(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(
        storage,
        "一个剪辑师发现素材里藏着未来事故。",
        {
            "duration_minutes": 5,
            "aspect_ratio": "9:16 vertical",
            "tone": "强钩子",
        },
    )
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/duplicate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["id"] != project_id
    assert project["status"] == "draft"
    assert project["title"] == "倒计时素材 Copy"
    assert project["seed_text"] == "一个剪辑师发现素材里藏着未来事故。"
    assert project["brief"]["aspect_ratio"] == "9:16 vertical"
    assert project["nodes"][0]["key"] == "seed"
    assert project["nodes"][0]["output"]["brief"]["tone"] == "强钩子"
    assert [node["status"] for node in project["nodes"][1:]] == ["pending"] * 5


def test_revise_project_api_creates_partial_rerun_draft(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    storage = override_storage()
    project_id = create_canvas_project(
        storage,
        "一个剪辑师发现素材里藏着未来事故。",
        {"duration_minutes": 5, "aspect_ratio": "9:16 vertical"},
    )
    storage.complete_canvas_node(project_id, "premise", premise_output())
    storage.complete_canvas_node(project_id, "characters", characters_output())
    storage.complete_canvas_node(project_id, "beats", beats_output())
    storage.complete_canvas_node(project_id, "script", valid_payload())
    storage.complete_canvas_node(project_id, "production", production_output())
    storage.update_canvas_node_instructions(
        project_id,
        "script",
        {"guidance": "对白更短，每场保留一个强反转。"},
    )
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/revise", json={"start_node": "script"})
        source_response = client.post(
            f"/api/projects/{project_id}/revise", json={"start_node": "seed"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    nodes = {node["key"]: node for node in project["nodes"]}
    assert project["id"] != project_id
    assert project["status"] == "draft"
    assert project["title"] == "倒计时素材 Script Revision"
    assert project["brief"]["aspect_ratio"] == "9:16 vertical"
    assert nodes["premise"]["status"] == "completed"
    assert nodes["characters"]["status"] == "completed"
    assert nodes["beats"]["status"] == "completed"
    assert nodes["beats"]["output"]["episode_title"] == "倒计时素材"
    assert nodes["script"]["status"] == "pending"
    assert nodes["script"]["output"] is None
    assert nodes["script"]["instructions"]["guidance"] == "对白更短，每场保留一个强反转。"
    assert nodes["production"]["status"] == "pending"
    assert nodes["production"]["output"] is None
    assert response.json()["progress"] == {
        "completed": 3,
        "total": 5,
        "active_key": None,
        "active_title": None,
        "failed_key": None,
        "failed_title": None,
    }
    assert source_response.status_code == 422


def test_revise_project_api_rejects_non_completed_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    try:
        client = TestClient(app)
        response = client.post(f"/api/projects/{project_id}/revise", json={"start_node": "script"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Only completed projects can be revised."


def test_generate_project_image_api_persists_asset(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"
    fake_image_client = FakeImageClient()

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    app.dependency_overrides[get_image_client] = lambda: fake_image_client
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/projects/{project_id}/images",
            json={"prompt": "竖屏电影感，剪辑室屏幕里出现未来事故画面。"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assets = body["project"]["image_assets"]
    assert fake_image_client.calls == [
        {
            "model": "gpt-image-2",
            "prompt": "竖屏电影感，剪辑室屏幕里出现未来事故画面。",
        }
    ]
    assert len(assets) == 1
    assert assets[0]["status"] == "completed"
    assert assets[0]["model"] == "gpt-image-2"
    assert assets[0]["artifact_url"] == "https://provider.test/generated/image-1.png"
    assert assets[0]["provider_response"]["id"] == "img_1"
    assert body["activity"][-1]["type"] == "image_generation"
    assert body["activity"][-1]["status"] == "completed"


def test_generate_project_image_api_records_visible_failure(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            model_base_url="https://provider.test/v1",
            language_model="gpt-5.5",
            image_model="gpt-image-2",
            batch_size=3,
            schedule_minute=0,
            log_level="INFO",
        )

    def override_storage() -> Storage:
        storage = Storage(db_path)
        storage.migrate()
        return storage

    project_id = create_canvas_project(override_storage(), "一个剪辑师发现素材里藏着未来事故。")

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_storage] = override_storage
    app.dependency_overrides[get_image_client] = lambda: FakeImageClient(
        error=RuntimeError("HM_IMG_APIKEY is required before generating project images.")
    )
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/projects/{project_id}/images",
            json={"prompt": "未来事故画面"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assets = body["project"]["image_assets"]
    assert len(assets) == 1
    assert assets[0]["status"] == "failed"
    assert assets[0]["error_message"] == (
        "HM_IMG_APIKEY is required before generating project images."
    )
    assert body["activity"][-1]["type"] == "image_generation"
    assert body["activity"][-1]["status"] == "failed"


def premise_output() -> dict:
    return {
        "one_sentence_pitch": "剪辑师被未来素材拖进救援。",
        "genre": "悬疑亲情",
        "target_audience": "18-35 岁短剧用户",
        "emotional_hook": "错过报警的人必须补上选择。",
        "story_promise": "每个素材细节都会变成救人的线索。",
        "risk_flags": [],
    }


def characters_output() -> dict:
    return {
        "protagonist": {
            "name": "林澈",
            "age": 28,
            "desire": "准时交片",
            "wound": "曾逃避报警",
            "choice": "公开客户素材救人",
        },
        "pressure": {
            "name": "周岚",
            "form": "客户",
            "threat": "要求删除关键素材",
            "human_reason": "她害怕再次失去女儿",
        },
        "relationship_map": ["林澈欠周岚真相", "周岚隐瞒女儿身份", "素材连接事故现场"],
        "character_arcs": ["逃避到承担", "控制到求助", "交易到信任"],
    }


def beats_output() -> dict:
    return {
        "episode_title": "倒计时素材",
        "logline": "剪辑师发现素材预告事故，必须在截稿前救人。",
        "beats": [
            {"index": 1, "beat": "异常素材", "screen_purpose": "抓住观众"},
            {"index": 2, "beat": "删除要求", "screen_purpose": "制造压力"},
            {"index": 3, "beat": "追查地点", "screen_purpose": "推进行动"},
            {"index": 4, "beat": "身份反转", "screen_purpose": "加深情感"},
            {"index": 5, "beat": "公开视频", "screen_purpose": "完成选择"},
            {"index": 6, "beat": "报警回声", "screen_purpose": "留下余味"},
        ],
        "reversal": "事故对象是客户女儿。",
        "cliffhanger": "素材末尾出现下一次倒计时。",
    }


def production_output() -> dict:
    return {
        "visual_style": "冷色剪辑室和清晨街口形成对照",
        "locations": ["剪辑室", "街口"],
        "props": ["电脑", "手机", "白车线索"],
        "shot_plan": [
            {"shot": "屏幕特写", "purpose": "展示异常素材", "duration_seconds": 8},
            {"shot": "手机近景", "purpose": "呈现客户施压", "duration_seconds": 6},
            {"shot": "手持跟拍", "purpose": "制造奔跑紧迫感", "duration_seconds": 12},
            {"shot": "街口广角", "purpose": "确认事故空间", "duration_seconds": 9},
            {"shot": "直播推近", "purpose": "完成主角选择", "duration_seconds": 10},
        ],
        "edit_notes": ["前 3 秒必须出现异常画面", "电话声做压迫节奏", "结尾保留警笛声"],
    }
