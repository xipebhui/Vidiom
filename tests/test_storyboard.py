from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from test_schema import valid_payload

from vidiom.canvas import create_canvas_project
from vidiom.storage import Storage
from vidiom.storyboard import StoryboardContextBuilder, generate_project_storyboard
from vidiom.storyboard_schema import derive_storyboard_readiness, validate_storyboard_payload


def test_storyboard_migration_creates_tables_and_indexes(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")

    storage.migrate()

    with sqlite3.connect(storage.db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    assert {
        "storyboards",
        "storyboard_shots",
        "project_story_assets",
        "storyboard_shot_assets",
        "storyboard_shot_image_assets",
    } <= tables
    assert {
        "idx_storyboards_project_id",
        "idx_storyboard_shots_storyboard_sequence",
        "idx_project_story_assets_project_type",
        "idx_storyboard_shot_assets_asset_id",
        "idx_storyboard_shot_image_assets_image_asset_id",
    } <= indexes
    with sqlite3.connect(storage.db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(storyboards)").fetchall()
        }
    assert {
        "generation_status",
        "generation_started_at",
        "generation_finished_at",
        "generation_error_message",
        "last_completed_at",
        "last_completed_model",
    } <= columns


def test_storyboard_migration_preserves_existing_project_and_image_assets(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    image_id = storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，剪辑室屏幕出现未来事故。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/image.png",
    )

    storage.migrate()
    project = storage.get_project(project_id)

    assert project["id"] == project_id
    assert project["nodes"][0]["output"]["text"] == "一个剪辑师发现素材里藏着未来事故。"
    assert project["image_assets"][0]["id"] == image_id
    assert project["image_assets"][0]["artifact_url"] == "https://provider.test/image.png"


def test_validate_storyboard_payload_rejects_invalid_generated_shapes() -> None:
    validate_storyboard_payload(valid_storyboard_payload())

    missing_shot_field = valid_storyboard_payload()
    del missing_shot_field["shots"][0]["image_prompt"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_storyboard_payload(missing_shot_field)

    invalid_asset_type = valid_storyboard_payload()
    invalid_asset_type["assets"][0]["asset_type"] = "vehicle"
    with pytest.raises(ValueError, match="invalid asset type"):
        validate_storyboard_payload(invalid_asset_type)

    empty_prompt = valid_storyboard_payload()
    empty_prompt["shots"][0]["image_prompt"] = "   "
    with pytest.raises(ValueError, match="image prompt"):
        validate_storyboard_payload(empty_prompt)


def test_completed_project_saves_and_reads_storyboard_relationships(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)

    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )

    assert storyboard["storyboard"]["status"] == "completed"
    assert storyboard["storyboard"]["generation_status"] == "completed"
    assert storyboard["storyboard"]["last_completed_model"] == "gpt-5.5"
    assert storyboard["has_completed_result"] is True
    assert storyboard["storyboard"]["model"] == "gpt-5.5"
    assert [shot["sequence_index"] for shot in storyboard["shots"]] == [1, 2]
    assert storyboard["shots"][0]["characters"] == ["林澈"]
    assert storyboard["shots"][1]["props"] == ["手机"]
    assert {asset["name"] for asset in storyboard["assets"]} == {"林澈", "剪辑室", "手机"}
    assert {
        (relationship["shot_sequence_index"], relationship["asset_name"], relationship["role"])
        for relationship in storyboard["relationships"]
    } == {
        (1, "林澈", "featured_character"),
        (1, "剪辑室", "location"),
        (2, "手机", "key_prop"),
    }
    activity = storage.get_project_activity(project_id)
    assert activity[-1]["type"] == "storyboard_generation"
    assert activity[-1]["details"]["shot_count"] == 2


def test_storyboard_failed_attempt_retains_completed_result(tmp_path: Path) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    first_shot_id = storyboard["shots"][0]["id"]

    storage.update_project_storyboard_status(
        project_id,
        status="failed",
        model="gpt-5.5",
        error_message="Provider returned invalid storyboard JSON.",
    )
    refreshed = storage.get_project_storyboard(project_id)
    package = storage.export_project_package(project_id)

    assert refreshed is not None
    assert refreshed["storyboard"]["generation_status"] == "failed"
    assert refreshed["storyboard"]["generation_error_message"] == (
        "Provider returned invalid storyboard JSON."
    )
    assert refreshed["has_completed_result"] is True
    assert refreshed["latest_attempt_failed"] is True
    assert refreshed["shots"][0]["id"] == first_shot_id
    exported = package["deliverables"]["storyboard"]
    assert exported["storyboard"]["generation_status"] == "failed"
    assert exported["has_completed_result"] is True


def test_storyboard_interrupted_attempt_retains_completed_result(tmp_path: Path) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    first_shot_id = storyboard["shots"][0]["id"]

    storage.update_project_storyboard_status(
        project_id,
        status="interrupted",
        model="gpt-5.5",
        error_message="Interrupted by user or external process.",
    )
    refreshed = storage.get_project_storyboard(project_id)
    package = storage.export_project_package(project_id)

    assert refreshed is not None
    assert refreshed["storyboard"]["generation_status"] == "interrupted"
    assert refreshed["storyboard"]["generation_finished_at"] is not None
    assert refreshed["storyboard"]["generation_error_message"] == (
        "Interrupted by user or external process."
    )
    assert refreshed["has_completed_result"] is True
    assert refreshed["latest_attempt_failed"] is False
    assert refreshed["latest_attempt_interrupted"] is True
    assert refreshed["shots"][0]["id"] == first_shot_id
    exported = package["deliverables"]["storyboard"]
    assert exported["storyboard"]["generation_status"] == "interrupted"
    assert exported["has_completed_result"] is True


def test_storyboard_interrupted_attempt_without_completed_result_creates_no_shots(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)

    storage.update_project_storyboard_status(
        project_id,
        status="interrupted",
        model="gpt-5.5",
        error_message="Interrupted by user or external process.",
    )
    refreshed = storage.get_project_storyboard(project_id)
    package = storage.export_project_package(project_id)

    assert refreshed is not None
    assert refreshed["storyboard"]["generation_status"] == "interrupted"
    assert refreshed["has_completed_result"] is False
    assert refreshed["latest_attempt_interrupted"] is True
    assert refreshed["shots"] == []
    assert "storyboard" not in package["deliverables"]


def test_storyboard_context_builder_includes_project_outputs_and_image_assets(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，剪辑室屏幕出现未来事故。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/image.png",
    )

    context = StoryboardContextBuilder(storage).build(project_id)

    assert context["project"]["seed_text"] == "一个剪辑师发现素材里藏着未来事故。"
    assert context["agent_outputs"]["script"]["title"] == "倒计时素材"
    assert context["agent_outputs"]["production"]["visual_style"].startswith("冷色剪辑室")
    assert context["reviewed_script"]["logline"]
    assert context["reviewed_production_pack"]["shot_plan"]
    assert context["image_assets"][0]["model"] == "gpt-image-2"
    assert context["image_assets"][0]["artifact_url"] == "https://provider.test/image.png"


def test_generate_project_storyboard_uses_gpt55_and_persists_payload(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    client = FakeLanguageClient(valid_storyboard_payload())

    storyboard = generate_project_storyboard(
        storage=storage,
        project_id=project_id,
        model="gpt-5.5",
        client=client,
    )

    assert client.calls[0]["model"] == "gpt-5.5"
    assert client.calls[0]["schema_name"] == "storyboard"
    assert "一个剪辑师发现素材里藏着未来事故" in client.calls[0]["input_payload"]
    assert storyboard is not None
    assert storyboard["storyboard"]["generation_status"] == "completed"
    assert len(storyboard["shots"]) == 2


def test_generate_project_storyboard_failed_provider_does_not_create_shots(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)

    storyboard = generate_project_storyboard(
        storage=storage,
        project_id=project_id,
        model="gpt-5.5",
        client=FakeLanguageClient({"shots": [], "assets": [], "relationships": []}),
    )

    assert storyboard is not None
    assert storyboard["storyboard"]["generation_status"] == "failed"
    assert storyboard["has_completed_result"] is False
    assert storyboard["shots"] == []
    assert "at least one shot" in storyboard["storyboard"]["generation_error_message"]


def test_storyboard_export_includes_shots_assets_relations_and_image_links(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    image_id = storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，林澈盯着异常素材。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/storyboard-frame.png",
    )
    shot_id = storyboard["shots"][0]["id"]
    storage.link_storyboard_shot_image_asset(
        project_id,
        shot_id,
        image_id,
        link_type="storyboard_frame",
    )

    package = storage.export_project_package(project_id)

    exported_storyboard = package["deliverables"]["storyboard"]
    assert exported_storyboard["storyboard"]["status"] == "completed"
    assert exported_storyboard["shots"][0]["image_prompt"].startswith("竖屏电影感")
    assert exported_storyboard["assets"][0]["asset_type"] == "character"
    assert exported_storyboard["relationships"][0]["asset_name"] == "林澈"
    assert exported_storyboard["image_links"][0]["image_asset"]["id"] == image_id
    assert exported_storyboard["readiness_summary"] == storyboard["readiness_summary"]
    assert exported_storyboard["shot_blockers"] == storyboard["shot_blockers"]
    assert package["deliverables"]["image_assets"][0]["id"] == image_id


def test_storyboard_readiness_helper_counts_blockers_and_review_states() -> None:
    shots = [
        {
            "id": 10,
            "sequence_index": 1,
            "review_status": "approved",
            "characters": ["林澈"],
            "scene": "剪辑室",
            "props": ["手机"],
            "visual_description": "林澈盯着屏幕。",
            "image_prompt": "竖屏电影感，剪辑室。",
            "duration_seconds": 8,
            "prompt_ready": True,
        },
        {
            "id": 11,
            "sequence_index": 2,
            "review_status": "pending",
            "characters": ["林澈"],
            "scene": "",
            "props": ["手机"],
            "visual_description": " ",
            "image_prompt": "",
            "duration_seconds": 0,
            "prompt_ready": False,
        },
        {
            "id": 12,
            "sequence_index": 3,
            "review_status": "needs_changes",
            "characters": ["林澈"],
            "scene": "剪辑室",
            "props": ["手机"],
            "visual_description": "手机来电盖住事故画面。",
            "image_prompt": "竖屏电影感，手机来电。",
            "duration_seconds": 6,
            "prompt_ready": True,
        },
    ]
    assets = [
        {"id": 1, "asset_type": "character", "name": "林澈"},
        {"id": 2, "asset_type": "scene", "name": "剪辑室"},
        {"id": 3, "asset_type": "prop", "name": "手机"},
    ]
    relationships = [
        {
            "shot_id": 10,
            "shot_sequence_index": 1,
            "asset_id": 1,
            "asset_type": "character",
            "asset_name": "林澈",
            "role": "featured_character",
        },
        {
            "shot_id": 10,
            "shot_sequence_index": 1,
            "asset_id": 2,
            "asset_type": "scene",
            "asset_name": "剪辑室",
            "role": "location",
        },
        {
            "shot_id": 10,
            "shot_sequence_index": 1,
            "asset_id": 3,
            "asset_type": "prop",
            "asset_name": "手机",
            "role": "key_prop",
        },
        {
            "shot_id": 12,
            "shot_sequence_index": 3,
            "asset_id": 2,
            "asset_type": "scene",
            "asset_name": "剪辑室",
            "role": "location",
        },
    ]

    readiness = derive_storyboard_readiness(
        shots=shots,
        assets=assets,
        relationships=relationships,
        image_links=[],
    )

    assert readiness["readiness_summary"] == {
        "shot_count": 3,
        "approved_count": 1,
        "needs_changes_count": 1,
        "pending_count": 1,
        "prompt_not_ready_count": 1,
        "shots_with_blockers_count": 2,
        "ready_for_media_generation": False,
    }
    blockers_by_sequence = {
        item["sequence_index"]: {blocker["code"] for blocker in item["blockers"]}
        for item in readiness["shot_blockers"]
    }
    assert blockers_by_sequence[1] == set()
    assert {
        "review_pending",
        "prompt_not_ready",
        "missing_visual_description",
        "missing_image_prompt",
        "invalid_duration_seconds",
        "missing_scene",
        "character_relationship_review_needed",
        "prop_relationship_review_needed",
    } <= blockers_by_sequence[2]
    assert {
        "review_needs_changes",
        "character_relationship_review_needed",
        "prop_relationship_review_needed",
    } <= blockers_by_sequence[3]


def test_storyboard_response_includes_readiness_summary_and_shot_blockers(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)

    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )

    assert storyboard["readiness_summary"] == {
        "shot_count": 2,
        "approved_count": 0,
        "needs_changes_count": 1,
        "pending_count": 1,
        "prompt_not_ready_count": 0,
        "shots_with_blockers_count": 2,
        "ready_for_media_generation": False,
    }
    assert "blockers" in storyboard["shots"][0]
    assert storyboard["shot_blockers"][0]["blockers"] == storyboard["shots"][0]["blockers"]
    first_codes = {blocker["code"] for blocker in storyboard["shots"][0]["blockers"]}
    second_codes = {blocker["code"] for blocker in storyboard["shots"][1]["blockers"]}
    assert "review_pending" in first_codes
    assert "review_needs_changes" in second_codes
    assert "missing_scene_asset_relationship" in second_codes
    assert "character_relationship_review_needed" in second_codes


def test_storyboard_image_link_delete_preserves_project_image_asset(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    image_id = storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，剪辑室屏幕。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/reference.png",
    )
    shot_id = storyboard["shots"][0]["id"]
    storage.link_storyboard_shot_image_asset(project_id, shot_id, image_id)

    storage.delete_storyboard_shot_image_asset(project_id, shot_id, image_id)
    refreshed = storage.get_project_storyboard(project_id)
    project = storage.get_project(project_id)

    assert refreshed is not None
    assert refreshed["image_links"] == []
    assert project["image_assets"][0]["id"] == image_id


def test_storyboard_shot_update_persists_and_resets_prompt_ready(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    shot_id = storyboard["shots"][0]["id"]

    refreshed = storage.update_storyboard_shot(
        project_id,
        shot_id,
        {
            "beat_ref": "异常素材放大",
            "scene_ref": "剪辑室 深夜",
            "characters": ["林澈", "周岚"],
            "scene": "剪辑室工位",
            "props": ["电脑", "硬盘"],
            "visual_description": "林澈把异常素材放大到街口车牌。",
            "action_focus": "他截取关键帧并确认时间码。",
            "dialogue_or_sound": "林澈低声说：这是明天早上。",
            "duration_seconds": 10,
            "aspect_ratio": "9:16 vertical",
            "visual_style": "冷色屏幕光，快速推近",
            "image_prompt": "竖屏电影感，剪辑室，异常素材放大到车牌。",
            "review_status": "approved",
            "prompt_ready": True,
        },
    )
    package = storage.export_project_package(project_id)

    assert refreshed is not None
    edited = refreshed["shots"][0]
    assert edited["beat_ref"] == "异常素材放大"
    assert edited["characters"] == ["林澈", "周岚"]
    assert edited["duration_seconds"] == 10
    assert edited["review_status"] == "approved"
    assert edited["prompt_ready"] is False
    exported = package["deliverables"]["storyboard"]["shots"][0]
    assert exported["visual_description"] == "林澈把异常素材放大到街口车牌。"
    assert exported["prompt_ready"] is False
    activity = storage.get_project_activity(project_id)
    assert activity[-1]["type"] == "storyboard_edit"
    assert activity[-1]["title"] == "Storyboard shot updated"
    assert activity[-1]["details"]["prompt_ready_reset"] is True


def test_storyboard_shot_create_delete_and_reorder_keep_sequences_and_cleanup(
    tmp_path: Path,
) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    first_shot_id = storyboard["shots"][0]["id"]
    second_shot_id = storyboard["shots"][1]["id"]
    image_id = storage.create_generated_image_asset(
        project_id=project_id,
        prompt="竖屏电影感，手机来电。",
        model="gpt-image-2",
        status="completed",
        artifact_url="https://provider.test/phone.png",
    )
    storage.link_storyboard_shot_image_asset(project_id, first_shot_id, image_id)

    created = storage.create_storyboard_shot(
        project_id,
        new_storyboard_shot_fields(),
        sequence_index=2,
    )
    assert created is not None
    assert [shot["sequence_index"] for shot in created["shots"]] == [1, 2, 3]
    new_shot = created["shots"][1]
    assert new_shot["beat_ref"] == "追查地点"
    assert new_shot["prompt_ready"] is False

    reordered = storage.reorder_storyboard_shots(
        project_id,
        [second_shot_id, new_shot["id"], first_shot_id],
    )
    assert reordered is not None
    assert [shot["id"] for shot in reordered["shots"]] == [
        second_shot_id,
        new_shot["id"],
        first_shot_id,
    ]
    assert [shot["sequence_index"] for shot in reordered["shots"]] == [1, 2, 3]
    assert all(not shot["prompt_ready"] for shot in reordered["shots"])

    deleted = storage.delete_storyboard_shot(project_id, first_shot_id)
    package = storage.export_project_package(project_id)

    assert deleted is not None
    assert [shot["sequence_index"] for shot in deleted["shots"]] == [1, 2]
    assert first_shot_id not in [shot["id"] for shot in deleted["shots"]]
    assert first_shot_id not in [item["shot_id"] for item in deleted["relationships"]]
    assert deleted["image_links"] == []
    assert storage.get_project(project_id)["image_assets"][0]["id"] == image_id
    exported = package["deliverables"]["storyboard"]
    assert [shot["sequence_index"] for shot in exported["shots"]] == [1, 2]
    assert exported["image_links"] == []


def test_storyboard_shot_reorder_rejects_partial_or_duplicate_ids(tmp_path: Path) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )
    first_shot_id = storyboard["shots"][0]["id"]

    with pytest.raises(ValueError, match="every current shot"):
        storage.reorder_storyboard_shots(project_id, [first_shot_id])
    with pytest.raises(ValueError, match="duplicate"):
        storage.reorder_storyboard_shots(project_id, [first_shot_id, first_shot_id])


def test_storyboard_shot_delete_rejects_final_remaining_shot(tmp_path: Path) -> None:
    storage, project_id = completed_project_storage(tmp_path)
    storyboard = storage.replace_project_storyboard(
        project_id,
        valid_storyboard_payload(),
        model="gpt-5.5",
    )

    storage.delete_storyboard_shot(project_id, storyboard["shots"][0]["id"])
    remaining = storage.get_project_storyboard(project_id)
    assert remaining is not None
    with pytest.raises(ValueError, match="final storyboard shot"):
        storage.delete_storyboard_shot(project_id, remaining["shots"][0]["id"])


def test_storyboard_shot_editing_requires_completed_storyboard(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")

    with pytest.raises(RuntimeError, match="completed project"):
        storage.create_storyboard_shot(project_id, new_storyboard_shot_fields())

    storage.update_project_status(project_id, "completed")
    with pytest.raises(RuntimeError, match="completed storyboard"):
        storage.create_storyboard_shot(project_id, new_storyboard_shot_fields())


def completed_project_storage(tmp_path: Path) -> tuple[Storage, int]:
    storage = Storage(tmp_path / "vidiom.sqlite3")
    storage.migrate()
    project_id = create_canvas_project(storage, "一个剪辑师发现素材里藏着未来事故。")
    script = valid_payload()
    storage.complete_canvas_node(project_id, "script", script)
    storage.complete_canvas_node(project_id, "production", production_output())
    project = storage.get_project(project_id)
    storage.complete(project["inspiration_id"], script)
    storage.update_project_title(project_id, "倒计时素材")
    storage.update_project_status(project_id, "completed")
    return storage, project_id


def new_storyboard_shot_fields() -> dict:
    return {
        "beat_ref": "追查地点",
        "scene_ref": "街口 清晨",
        "characters": ["林澈"],
        "scene": "街口",
        "props": ["手机"],
        "visual_description": "林澈举着手机跑向素材里的街口。",
        "action_focus": "他一边看倒计时一边确认路牌。",
        "dialogue_or_sound": "远处车流声逐渐压过喘息。",
        "duration_seconds": 9,
        "aspect_ratio": "9:16 vertical",
        "visual_style": "清晨逆光，手持奔跑镜头",
        "image_prompt": "竖屏电影感，清晨街口，林澈举着手机奔跑。",
        "review_status": "pending",
        "prompt_ready": True,
    }


def valid_storyboard_payload() -> dict:
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
                "review_status": "needs_changes",
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
            {
                "asset_type": "prop",
                "name": "手机",
                "description": "客户来电和直播救援都依赖的手机。",
                "reference_prompt": "黑色智能手机，来电界面，屏幕反光。",
                "consistency_notes": "同一部手机贯穿剪辑室和直播间。",
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
            {
                "shot_sequence_index": 2,
                "asset_type": "prop",
                "asset_name": "手机",
                "role": "key_prop",
            },
        ],
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


class FakeLanguageClient:
    def __init__(self, payload: dict | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict] = []

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: str,
        schema_name: str,
        schema: dict,
    ) -> dict:
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input_payload": input_payload,
                "schema_name": schema_name,
                "schema": schema,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload
