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
    def __init__(self) -> None:
        self.contexts: list[tuple[str, dict]] = []

    def generate_step(self, step: CanvasAgentStep, seed_text: str, context: dict) -> dict:
        self.contexts.append((step.key, dict(context)))
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


class PausingCanvasAgent(FakeCanvasAgent):
    def __init__(self, storage: Storage, project_id: int) -> None:
        super().__init__()
        self.storage = storage
        self.project_id = project_id

    def generate_step(self, step: CanvasAgentStep, seed_text: str, context: dict) -> dict:
        output = super().generate_step(step, seed_text, context)
        if step.key == "premise":
            self.storage.pause_running_project(self.project_id)
        return output


def test_run_canvas_project_persists_review_outputs(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    brief = {
        "duration_minutes": 5,
        "aspect_ratio": "9:16 vertical",
        "tone": "强钩子、快反转",
        "target_audience": "18-35 岁短剧用户",
        "must_include": "前三秒出现异常素材",
    }
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。", brief)
    storage.update_canvas_node_instructions(
        project_id,
        "script",
        {"guidance": "对白更短，每场保留一个强反转。"},
    )
    agent = FakeCanvasAgent()

    project = run_canvas_project(storage, project_id, agent)

    nodes = {node["key"]: node for node in project["nodes"]}
    assert project["status"] == "completed"
    assert project["title"] == "倒计时素材"
    assert project["brief"]["aspect_ratio"] == "9:16 vertical"
    assert nodes["seed"]["output"]["brief"]["must_include"] == "前三秒出现异常素材"
    assert agent.contexts[0][1]["creative_brief"]["duration_minutes"] == 5
    script_context = next(context for key, context in agent.contexts if key == "script")
    production_context = next(context for key, context in agent.contexts if key == "production")
    assert script_context["current_node_instructions"]["guidance"] == (
        "对白更短，每场保留一个强反转。"
    )
    assert "current_node_instructions" not in production_context
    assert nodes["script"]["instructions"]["guidance"] == "对白更短，每场保留一个强反转。"
    assert nodes["script"]["output"]["scenes"][0]["dialogue"][0]["speaker"] == "林澈"
    assert nodes["production"]["output"]["shot_plan"][0]["shot"] == "屏幕特写"


def test_run_canvas_project_pauses_after_current_node_and_resumes(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    pausing_agent = PausingCanvasAgent(storage, project_id)

    paused_project = run_canvas_project(storage, project_id, pausing_agent)

    paused_nodes = {node["key"]: node for node in paused_project["nodes"]}
    assert paused_project["status"] == "paused"
    assert [key for key, _ in pausing_agent.contexts] == ["premise"]
    assert paused_nodes["premise"]["status"] == "completed"
    assert paused_nodes["characters"]["status"] == "pending"

    resume_agent = FakeCanvasAgent()
    completed_project = run_canvas_project(storage, project_id, resume_agent)

    completed_nodes = {node["key"]: node for node in completed_project["nodes"]}
    assert completed_project["status"] == "completed"
    assert [key for key, _ in resume_agent.contexts] == [
        "characters",
        "beats",
        "script",
        "production",
    ]
    assert resume_agent.contexts[0][1]["premise"]["genre"] == "悬疑亲情"
    assert completed_nodes["production"]["output"]["shot_plan"][0]["shot"] == "屏幕特写"
