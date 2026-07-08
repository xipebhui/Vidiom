from __future__ import annotations

from fastapi.testclient import TestClient

from vidiom.config import Settings
from vidiom.storage import Storage
from vidiom.web import STATIC_DIR, app, get_settings, get_storage


def test_studio_static_review_panel_exposes_workflow_tabs() -> None:
    index_html = (STATIC_DIR / "index.html").read_text()
    app_js = (STATIC_DIR / "app.js").read_text()

    assert 'data-review-tab="script"' in index_html
    assert 'data-review-tab="characters"' in index_html
    assert 'data-review-tab="production"' in index_html
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
            json={"seed_text": "一个剪辑师发现素材里藏着未来事故。"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["status"] == "draft"
    assert body["project"]["nodes"][0]["key"] == "seed"


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
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["title"] == "未来素材案"
    assert project["seed_text"] == "一个剪辑师在客户素材里看见明天的事故现场。"
    assert project["nodes"][0]["output"]["text"] == project["seed_text"]


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
