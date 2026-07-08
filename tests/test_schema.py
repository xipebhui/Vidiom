from __future__ import annotations

import pytest

from vidiom.schema import validate_short_drama


def valid_payload() -> dict:
    return {
        "title": "倒计时素材",
        "logline": "剪辑师发现客户素材预告事故，必须在截稿前救下陌生人。",
        "genre": "悬疑亲情",
        "target_audience": "18-35 岁短剧用户",
        "runtime_minutes": 6,
        "content_rating": "PG",
        "tags": ["悬疑", "反转", "都市"],
        "characters": [
            {
                "name": "林澈",
                "age": 28,
                "role": "剪辑师",
                "desire": "准时交片",
                "secret": "曾经逃避过一次报警",
                "voice": "克制、快节奏",
            },
            {
                "name": "周岚",
                "age": 42,
                "role": "委托人",
                "desire": "阻止事故",
                "secret": "素材来自她失踪的女儿",
                "voice": "温柔但紧绷",
            },
        ],
        "story_engine": {
            "hook": "素材中出现明天的街口事故。",
            "conflict": "客户要求删掉关键画面。",
            "turning_point": "事故对象是客户女儿。",
            "climax": "林澈直播公开素材。",
            "ending": "母女重逢，林澈补上迟到的报警。",
        },
        "episode_outline": [
            {"beat": "异常素材", "purpose": "抓住观众"},
            {"beat": "删除要求", "purpose": "制造道德压力"},
            {"beat": "追查地点", "purpose": "推进行动"},
            {"beat": "身份反转", "purpose": "加深情感"},
            {"beat": "公开选择", "purpose": "完成主角弧光"},
        ],
        "scenes": [
            {
                "scene_number": 1,
                "setting": "剪辑室",
                "time": "夜",
                "summary": "林澈发现素材异常。",
                "dialogue": [
                    {"speaker": "林澈", "line": "这不是素材，是预告。", "direction": "低声"},
                    {"speaker": "林澈", "line": "明早七点，雨都还没下。", "direction": "盯住屏幕"},
                ],
            },
            {
                "scene_number": 2,
                "setting": "电话",
                "time": "夜",
                "summary": "周岚要求删除画面。",
                "dialogue": [
                    {"speaker": "周岚", "line": "删掉它。", "direction": "停顿"},
                    {"speaker": "林澈", "line": "为什么你比我还怕它？", "direction": "追问"},
                ],
            },
            {
                "scene_number": 3,
                "setting": "街口",
                "time": "晨",
                "summary": "林澈确认地点。",
                "dialogue": [
                    {"speaker": "林澈", "line": "我到现场了。", "direction": "喘息"},
                    {"speaker": "周岚", "line": "别靠近那辆白车。", "direction": "压低声音"},
                ],
            },
            {
                "scene_number": 4,
                "setting": "直播间",
                "time": "晨",
                "summary": "他公开素材阻止事故。",
                "dialogue": [
                    {"speaker": "林澈", "line": "这次我不会沉默。", "direction": "坚定"},
                    {"speaker": "周岚", "line": "谢谢你替我按下报警键。", "direction": "哽咽"},
                ],
            },
        ],
        "production_notes": {
            "locations": ["剪辑室", "街口"],
            "props": ["电脑", "手机"],
            "shooting_style": "手持近景与屏幕录制交替",
            "risk_flags": [],
        },
    }


def test_validate_short_drama_accepts_complete_payload() -> None:
    validate_short_drama(valid_payload())


def test_validate_short_drama_rejects_missing_field() -> None:
    payload = valid_payload()
    del payload["title"]

    with pytest.raises(ValueError, match="missing required fields"):
        validate_short_drama(payload)
