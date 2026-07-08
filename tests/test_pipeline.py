from __future__ import annotations

from pathlib import Path

from test_schema import valid_payload

from vidiom.canvas import CanvasAgentStep, create_canvas_project, run_canvas_project
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


class FakeCanvasAgent:
    def generate_step(self, step: CanvasAgentStep, seed_text: str, context: dict) -> dict:
        if step.key == "premise":
            return {
                "one_sentence_pitch": f"{seed_text} 触发一场倒计时救援。",
                "genre": "悬疑亲情",
                "target_audience": "18-35 岁短剧用户",
                "emotional_hook": "错过一次报警的人必须补上选择。",
                "story_promise": "每个素材细节都会变成救人的线索。",
                "risk_flags": [],
            }
        if step.key == "characters":
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
        if step.key == "beats":
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
        if step.key == "script":
            return valid_payload()
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


def test_run_canvas_project_persists_review_outputs(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")

    project = run_canvas_project(storage, project_id, FakeCanvasAgent())

    nodes = {node["key"]: node for node in project["nodes"]}
    assert project["status"] == "completed"
    assert project["title"] == "倒计时素材"
    assert nodes["script"]["output"]["scenes"][0]["dialogue"][0]["speaker"] == "林澈"
    assert nodes["production"]["output"]["shot_plan"][0]["shot"] == "屏幕特写"
