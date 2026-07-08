from __future__ import annotations

from fastapi.testclient import TestClient
from test_schema import valid_payload

from vidiom.canvas import create_canvas_project
from vidiom.config import Settings
from vidiom.storage import Storage
from vidiom.web import STATIC_DIR, app, get_settings, get_storage


def test_studio_static_review_panel_exposes_workflow_tabs() -> None:
    index_html = (STATIC_DIR / "index.html").read_text()
    app_js = (STATIC_DIR / "app.js").read_text()

    assert 'id="exportProject"' in index_html
    assert 'id="duplicateProject"' in index_html
    assert 'id="projectSearch"' in index_html
    assert 'id="projectStatusFilter"' in index_html
    assert 'name="duration_minutes"' in index_html
    assert 'name="aspect_ratio"' in index_html
    assert 'data-review-tab="script"' in index_html
    assert 'data-review-tab="characters"' in index_html
    assert 'data-review-tab="production"' in index_html
    assert "function briefFromForm" in app_js
    assert "function renderBriefFields" in app_js
    assert "function projectListQuery" in app_js
    assert "function applyProjectFilters" in app_js
    assert "async function downloadProjectExport" in app_js
    assert "async function duplicateProject" in app_js
    assert "function renderCharacterReview" in app_js
    assert "function renderProductionReview" in app_js


def test_create_project_api(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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
    assert body["project"]["nodes"][0]["key"] == "seed"
    assert body["project"]["nodes"][0]["output"]["brief"]["aspect_ratio"] == "9:16 vertical"


def test_list_projects_api_filters_by_status_and_query(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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
    storage.update_project_status(completed_id, "completed")
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
    assert [project["id"] for project in completed_response.json()["projects"]] == [completed_id]
    assert search_response.status_code == 200
    assert [project["id"] for project in search_response.json()["projects"]] == [completed_id]
    assert failed_search_response.status_code == 200
    assert [project["id"] for project in failed_search_response.json()["projects"]] == [failed_id]
    assert draft_id not in [project["id"] for project in search_response.json()["projects"]]


def test_update_draft_project_api_updates_seed_node(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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


def test_get_project_api_returns_activity_timeline(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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


def test_export_project_api_returns_completed_deliverable_package(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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
    assert body["deliverables"]["script"]["title"] == "倒计时素材"
    assert body["deliverables"]["production_pack"]["shot_plan"][0]["shot"] == "屏幕特写"
    assert body["agent_outputs"]["seed"]["text"] == "一个剪辑师发现素材里藏着未来事故。"


def test_export_project_api_rejects_draft_project(tmp_path) -> None:
    db_path = tmp_path / "studio.sqlite3"

    def override_settings() -> Settings:
        return Settings(
            database_path=db_path,
            openai_model="test-model",
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
            openai_model="test-model",
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
