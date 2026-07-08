from __future__ import annotations

from fastapi.testclient import TestClient

from vidiom.config import Settings
from vidiom.storage import Storage
from vidiom.web import app, get_settings, get_storage


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

