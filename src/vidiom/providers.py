from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from .config import require_image_api_key, require_language_api_key, require_model_base_url


class LanguageJSONClient(Protocol):
    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ImageGenerationResult:
    artifact_url: str | None
    b64_json: str | None
    revised_prompt: str | None
    provider_response: dict[str, Any]


class ImageGenerationClient(Protocol):
    def generate_image(self, *, model: str, prompt: str) -> ImageGenerationResult:
        ...


class OpenAICompatibleLanguageClient:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=_openai_api_base_url(base_url), api_key=api_key)

    @classmethod
    def from_env(cls) -> OpenAICompatibleLanguageClient:
        return cls(base_url=require_model_base_url(), api_key=require_language_api_key())

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_payload},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        return _parse_json_object(_response_output_text(response))


class OpenAICompatibleImageClient:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=_openai_api_base_url(base_url), api_key=api_key)

    @classmethod
    def from_env(cls) -> OpenAICompatibleImageClient:
        return cls(base_url=require_model_base_url(), api_key=require_image_api_key())

    def generate_image(self, *, model: str, prompt: str) -> ImageGenerationResult:
        response = self._client.images.generate(model=model, prompt=prompt, n=1)
        provider_response = _response_to_dict(response)
        first = _first_image_payload(provider_response)
        return ImageGenerationResult(
            artifact_url=_string_or_none(first.get("url")),
            b64_json=_string_or_none(first.get("b64_json")),
            revised_prompt=_string_or_none(first.get("revised_prompt"))
            or _provider_reference(provider_response),
            provider_response=provider_response,
        )


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump_json"):
        payload = json.loads(response.model_dump_json())
    elif hasattr(response, "model_dump"):
        payload = response.model_dump(mode="json")
    elif hasattr(response, "to_dict"):
        payload = response.to_dict()
    elif isinstance(response, dict):
        payload = response
    elif isinstance(response, str):
        payload = {"data": [_image_string_to_dict(response)]}
    elif isinstance(response, bytes):
        payload = {"data": [{"b64_json": response.decode("utf-8")}]}
    elif hasattr(response, "data"):
        payload = {"data": [_image_item_to_dict(item) for item in response.data]}
    elif hasattr(response, "__dict__"):
        payload = {
            key: value
            for key, value in vars(response).items()
            if not key.startswith("_") and _is_json_scalar_or_container(value)
        }
    else:
        payload = {"raw": str(response)}
    if not isinstance(payload, dict):
        return {"raw": str(payload)}
    return _json_safe(payload)


def _openai_api_base_url(base_url: str) -> str:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        raise RuntimeError("HM_BASE_URL is required before calling the model provider.")
    path = urlparse(clean_url).path.rstrip("/")
    if path.endswith("/v1"):
        return clean_url
    return f"{clean_url}/v1"


def _response_output_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    payload = _response_to_dict(response)
    for key in ("output_text", "text", "content"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    output = payload.get("output")
    if isinstance(output, list):
        text_parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for content_item in content:
                    if isinstance(content_item, dict):
                        text = content_item.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
            text = item.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return "".join(text_parts)
    raise TypeError("Provider language response does not contain output text.")


def _parse_json_object(text: str) -> dict[str, Any]:
    clean_text = text.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()

    try:
        payload = json.loads(clean_text)
    except json.JSONDecodeError:
        start = clean_text.find("{")
        end = clean_text.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(clean_text[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("Provider language response must be a JSON object.")
    return payload


def _first_image_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
        if isinstance(first, str):
            return _image_string_to_dict(first)

    for key in ("image", "output", "result", "url", "b64_json"):
        value = payload.get(key)
        if isinstance(value, str):
            if key in {"url", "b64_json"}:
                return {key: value}
            return _image_string_to_dict(value)
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return first
            if isinstance(first, str):
                return _image_string_to_dict(first)
    return {}


def _image_item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        payload = item.model_dump(mode="json")
        if isinstance(payload, dict):
            return payload
    return {
        key: value
        for key in ("url", "b64_json", "revised_prompt")
        if (value := getattr(item, key, None)) is not None
    }


def _image_string_to_dict(value: str) -> dict[str, Any]:
    clean_value = value.strip()
    if clean_value.startswith("http://") or clean_value.startswith("https://"):
        return {"url": clean_value}
    return {"b64_json": clean_value}


def _provider_reference(payload: dict[str, Any]) -> str | None:
    for key in ("id", "created", "raw"):
        value = payload.get(key)
        if value is not None:
            return f"{key}: {value}"
    return None


def _is_json_scalar_or_container(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool | list | dict)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean_value = str(value).strip()
    return clean_value or None
