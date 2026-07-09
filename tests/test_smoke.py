from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_schema import valid_payload

from vidiom.config import Settings
from vidiom.providers import ImageGenerationResult
from vidiom.smoke import run_real_model_storyboard_smoke


def test_real_model_smoke_runner_records_success(tmp_path: Path) -> None:
    result_path = tmp_path / "real-model-smoke-result.md"

    result = run_real_model_storyboard_smoke(
        result_path=result_path,
        database_path=tmp_path / "smoke.sqlite3",
        settings=make_settings(tmp_path),
        language_client=FakeSmokeLanguageClient(),
        image_client=FakeImageClient(),
    )

    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert result["overall_status"] == "completed"
    assert stages["agent_project"]["status"] == "completed"
    assert stages["agent_project"]["details"]["agent_nodes"]["completed"] == 5
    assert stages["storyboard_generation"]["details"]["shot_count"] == 2
    assert stages["project_image_generation"]["details"]["b64_json_present"] is True
    assert stages["export_package"]["details"]["project_image_asset_count"] == 1
    assert "`completed`" in result_path.read_text(encoding="utf-8")


def test_real_model_smoke_runner_records_missing_language_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("HM_BASE_URL", raising=False)
    monkeypatch.delenv("HM_LLM_APIKEY", raising=False)

    result = run_real_model_storyboard_smoke(
        result_path=tmp_path / "result.md",
        database_path=tmp_path / "smoke.sqlite3",
        settings=make_settings(tmp_path),
        image_client=FakeImageClient(),
    )

    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert result["overall_status"] == "failed"
    assert stages["agent_project"]["status"] == "failed"
    assert "HM_BASE_URL" in stages["agent_project"]["error_message"]
    assert stages["storyboard_generation"]["status"] == "incomplete"


def test_real_model_smoke_runner_records_missing_image_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HM_BASE_URL", "https://provider.test")
    monkeypatch.setenv("HM_LLM_APIKEY", "secret-language-key")
    monkeypatch.delenv("HM_IMG_APIKEY", raising=False)

    result = run_real_model_storyboard_smoke(
        result_path=tmp_path / "result.md",
        database_path=tmp_path / "smoke.sqlite3",
        settings=make_settings(tmp_path),
        language_client=FakeSmokeLanguageClient(),
    )

    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert result["overall_status"] == "failed"
    assert stages["project_image_generation"]["status"] == "failed"
    assert "HM_IMG_APIKEY" in stages["project_image_generation"]["error_message"]
    assert "secret-language-key" not in json.dumps(result, ensure_ascii=False)
    assert stages["export_package"]["status"] == "incomplete"


def test_real_model_smoke_runner_records_invalid_storyboard_payload(
    tmp_path: Path,
) -> None:
    result = run_real_model_storyboard_smoke(
        result_path=tmp_path / "result.md",
        database_path=tmp_path / "smoke.sqlite3",
        settings=make_settings(tmp_path),
        language_client=FakeSmokeLanguageClient(storyboard_payload={"shots": []}),
        image_client=FakeImageClient(),
    )

    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert result["overall_status"] == "failed"
    assert stages["agent_project"]["status"] == "completed"
    assert stages["storyboard_generation"]["status"] == "failed"
    assert "missing required fields" in stages["storyboard_generation"]["error_message"]
    assert stages["project_image_generation"]["status"] == "incomplete"


def test_real_model_smoke_runner_records_keyboard_interrupt(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "result.md"

    result = run_real_model_storyboard_smoke(
        result_path=result_path,
        database_path=tmp_path / "smoke.sqlite3",
        settings=make_settings(tmp_path),
        language_client=FakeSmokeLanguageClient(interrupt_storyboard=True),
        image_client=FakeImageClient(),
    )

    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert result["overall_status"] == "interrupted"
    assert stages["storyboard_generation"]["status"] == "interrupted"
    assert stages["project_image_generation"]["status"] == "incomplete"
    assert "`interrupted`" in result_path.read_text(encoding="utf-8")


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "unused.sqlite3",
        model_base_url=None,
        language_model="gpt-5.5",
        image_model="gpt-image-2",
        batch_size=1,
        schedule_minute=0,
        log_level="INFO",
    )


class FakeSmokeLanguageClient:
    def __init__(
        self,
        *,
        storyboard_payload: dict[str, Any] | None = None,
        interrupt_storyboard: bool = False,
    ) -> None:
        self.storyboard_payload = storyboard_payload or valid_storyboard_payload()
        self.interrupt_storyboard = interrupt_storyboard

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if schema_name == "premise":
            return {
                "one_sentence_pitch": "剪辑师被未来素材拖进救援。",
                "genre": "悬疑亲情",
                "target_audience": "18-35 岁短剧用户",
                "emotional_hook": "错过一次报警的人必须补上选择。",
                "story_promise": "每个素材细节都会变成救人的线索。",
                "risk_flags": [],
            }
        if schema_name == "characters":
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
                "relationship_map": ["林澈欠周岚真相", "周岚隐瞒女儿身份"],
                "character_arcs": ["逃避到承担", "控制到求助", "交易到信任"],
            }
        if schema_name == "beats":
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
        if schema_name == "script":
            return valid_payload()
        if schema_name == "production":
            return production_payload()
        if schema_name == "storyboard":
            if self.interrupt_storyboard:
                raise KeyboardInterrupt
            return self.storyboard_payload
        raise AssertionError(f"Unexpected schema name: {schema_name}")


class FakeImageClient:
    def generate_image(self, *, model: str, prompt: str) -> ImageGenerationResult:
        return ImageGenerationResult(
            artifact_url=None,
            b64_json="image-payload",
            revised_prompt="cinematic vertical frame",
            provider_response={"id": "image-test"},
        )


def production_payload() -> dict[str, Any]:
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


def valid_storyboard_payload() -> dict[str, Any]:
    return {
        "shots": [
            {
                "sequence_index": 1,
                "review_status": "pending",
                "beat_ref": "异常素材",
                "scene_ref": "剪辑室 夜",
                "characters": ["林澈"],
                "scene": "剪辑室",
                "props": ["电脑"],
                "visual_description": "林澈盯着屏幕里提前出现的街口事故画面。",
                "action_focus": "他暂停画面并放大时间码。",
                "dialogue_or_sound": "键盘声和林澈低声说这不是素材。",
                "duration_seconds": 8,
                "aspect_ratio": "9:16 vertical",
                "visual_style": "冷色屏幕光，手持近景",
                "image_prompt": "竖屏电影感，剪辑室，林澈盯着异常素材屏幕，冷色光。",
                "prompt_ready": True,
            },
            {
                "sequence_index": 2,
                "review_status": "pending",
                "beat_ref": "删除要求",
                "scene_ref": "电话 夜",
                "characters": ["林澈"],
                "scene": "剪辑室",
                "props": ["手机"],
                "visual_description": "手机来电盖住事故画面，客户要求立刻删除。",
                "action_focus": "林澈在接听和保存素材之间犹豫。",
                "dialogue_or_sound": "电话里传来周岚压低的删除要求。",
                "duration_seconds": 6,
                "aspect_ratio": "9:16 vertical",
                "visual_style": "手机近景和屏幕反光",
                "image_prompt": "竖屏电影感，剪辑室手机来电，屏幕反射未来事故画面。",
                "prompt_ready": True,
            },
        ],
        "assets": [
            {
                "asset_type": "character",
                "name": "林澈",
                "description": "28 岁剪辑师，克制但行动很快。",
                "reference_prompt": "年轻剪辑师，黑色连帽衫，疲惫但专注。",
                "consistency_notes": "始终保持眼下疲惫和短发造型。",
            },
            {
                "asset_type": "scene",
                "name": "剪辑室",
                "description": "夜间小型剪辑工位，主光来自电脑屏幕。",
                "reference_prompt": "狭窄剪辑室，冷色屏幕光，桌面有硬盘和手机。",
                "consistency_notes": "桌面布局在前两镜保持一致。",
            },
        ],
        "relationships": [
            {
                "shot_sequence_index": 1,
                "asset_type": "character",
                "asset_name": "林澈",
                "role": "featured_character",
            },
            {
                "shot_sequence_index": 1,
                "asset_type": "scene",
                "asset_name": "剪辑室",
                "role": "location",
            },
        ],
    }
