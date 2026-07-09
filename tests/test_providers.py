from __future__ import annotations

import json

from vidiom.providers import (
    _openai_api_base_url,
    _parse_json_object,
    _response_output_text,
    _response_to_dict,
)


class FakeImageResponse:
    def model_dump_json(self) -> str:
        return json.dumps(
            {
                "data": [
                    {
                        "url": "https://provider.test/image.png",
                        "revised_prompt": "cinematic frame",
                    }
                ]
            }
        )


class FakeImageItem:
    url = "https://provider.test/image.png"
    b64_json = None
    revised_prompt = "cinematic frame"


class FakeDataImageResponse:
    data = [FakeImageItem()]


def test_openai_api_base_url_appends_v1_when_missing() -> None:
    assert _openai_api_base_url("https://provider.test") == "https://provider.test/v1"


def test_openai_api_base_url_keeps_existing_v1_path() -> None:
    assert _openai_api_base_url("https://provider.test/v1") == "https://provider.test/v1"


def test_response_to_dict_accepts_model_dump_json_response() -> None:
    payload = _response_to_dict(FakeImageResponse())

    assert payload["data"][0]["url"] == "https://provider.test/image.png"
    assert payload["data"][0]["revised_prompt"] == "cinematic frame"


def test_response_to_dict_accepts_data_response() -> None:
    payload = _response_to_dict(FakeDataImageResponse())

    assert payload["data"][0]["url"] == "https://provider.test/image.png"
    assert payload["data"][0]["revised_prompt"] == "cinematic frame"


def test_response_to_dict_accepts_string_reference_response() -> None:
    payload = _response_to_dict("https://provider.test/image.png")

    assert payload["data"][0]["url"] == "https://provider.test/image.png"


def test_response_output_text_accepts_string_json() -> None:
    assert _response_output_text('{"title":"ok"}') == '{"title":"ok"}'


def test_response_output_text_accepts_responses_output_shape() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"title":"ok"}',
                    }
                ]
            }
        ]
    }

    assert _response_output_text(payload) == '{"title":"ok"}'


def test_response_output_text_accepts_chat_completion_shape() -> None:
    payload = {"choices": [{"message": {"content": '{"title":"ok"}'}}]}

    assert _response_output_text(payload) == '{"title":"ok"}'


def test_parse_json_object_accepts_markdown_json_block() -> None:
    payload = _parse_json_object('```json\n{"title":"ok"}\n```')

    assert payload == {"title": "ok"}


def test_parse_json_object_accepts_surrounding_text() -> None:
    payload = _parse_json_object('Here is the JSON:\n{"title":"ok"}')

    assert payload == {"title": "ok"}
