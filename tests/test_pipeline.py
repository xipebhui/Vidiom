from __future__ import annotations

from pathlib import Path

from test_schema import valid_payload

from vidiom.pipeline import run_once
from vidiom.storage import Storage


class FakeGenerator:
    def generate(self, inspiration_text: str) -> dict:
        payload = valid_payload()
        payload["logline"] = f"{payload['logline']} 来源：{inspiration_text[:8]}"
        return payload


def test_run_once_generates_and_stores_production(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    storage.add_inspiration("一个剪辑师发现素材里藏着未来事故。")

    result = run_once(storage, FakeGenerator(), limit=1)

    assert result.processed == 1
    assert result.succeeded == 1
    assert result.failed == 0
    productions = storage.list_productions(limit=10)
    assert len(productions) == 1
    assert productions[0].title == "倒计时素材"


def test_project_canvas_persists_nodes_and_edges(tmp_path: Path) -> None:
    from vidiom.canvas import create_canvas_project

    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()

    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    project = storage.get_project(project_id)

    assert project["status"] == "draft"
    assert [node["key"] for node in project["nodes"]] == [
        "seed",
        "premise",
        "characters",
        "beats",
        "script",
        "production",
    ]
    assert project["edges"][0] == {"source": "seed", "target": "premise"}
    assert project["nodes"][0]["output"]["text"].startswith("一个剪辑师")
