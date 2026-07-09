from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from .canvas_schema import BEAT_SCHEMA, CHARACTER_SCHEMA, PREMISE_SCHEMA, PRODUCTION_SCHEMA
from .config import require_openai_api_key
from .prompts import SYSTEM_PROMPT
from .schema import SHORT_DRAMA_SCHEMA, validate_short_drama
from .storage import Storage


@dataclass(frozen=True)
class CanvasAgentStep:
    key: str
    title: str
    kind: str
    x: int
    y: int
    schema: dict
    instruction: str


AGENT_STEPS: tuple[CanvasAgentStep, ...] = (
    CanvasAgentStep(
        key="premise",
        title="Premise Agent",
        kind="agent",
        x=320,
        y=96,
        schema=PREMISE_SCHEMA,
        instruction=(
            "Extract the strongest short-drama premise from the seed. "
            "Keep it mobile-first, emotionally direct, and shootable."
        ),
    ),
    CanvasAgentStep(
        key="characters",
        title="Character Agent",
        kind="agent",
        x=610,
        y=96,
        schema=CHARACTER_SCHEMA,
        instruction=(
            "Design the central characters and pressure system. "
            "Make desires, wounds, and choices playable on screen."
        ),
    ),
    CanvasAgentStep(
        key="beats",
        title="Beat Agent",
        kind="agent",
        x=900,
        y=96,
        schema=BEAT_SCHEMA,
        instruction=(
            "Build a 3-8 minute episode outline with hook, escalation, reversal, "
            "climax, and cliffhanger."
        ),
    ),
    CanvasAgentStep(
        key="script",
        title="Script Agent",
        kind="agent",
        x=1190,
        y=96,
        schema=SHORT_DRAMA_SCHEMA,
        instruction=(
            "Write the complete short-drama episode in Simplified Chinese using the "
            "approved premise, characters, and beats."
        ),
    ),
    CanvasAgentStep(
        key="production",
        title="Production Agent",
        kind="agent",
        x=1190,
        y=360,
        schema=PRODUCTION_SCHEMA,
        instruction=(
            "Create a practical production pack for a small crew filming vertical video."
        ),
    ),
)

CANVAS_EDGES: tuple[tuple[str, str], ...] = (
    ("seed", "premise"),
    ("premise", "characters"),
    ("characters", "beats"),
    ("beats", "script"),
    ("script", "production"),
)


class CanvasAgent(Protocol):
    def generate_step(self, step: CanvasAgentStep, seed_text: str, context: dict[str, Any]) -> dict:
        ...


class OpenAICanvasAgent:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate_step(self, step: CanvasAgentStep, seed_text: str, context: dict[str, Any]) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=require_openai_api_key())
        guidance = str((context.get("current_node_instructions") or {}).get("guidance", "")).strip()
        step_instruction = step.instruction
        if guidance:
            step_instruction = (
                f"{step_instruction}\n\nUser guidance for this node:\n{guidance}"
            )
        response = client.responses.create(
            model=self.model,
            instructions=f"{SYSTEM_PROMPT}\n\n{step_instruction}",
            input=json.dumps(
                {"seed_text": seed_text, "previous_outputs": context},
                ensure_ascii=False,
                indent=2,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": step.key,
                    "strict": True,
                    "schema": step.schema,
                }
            },
        )
        payload = json.loads(response.output_text)
        if step.key == "script":
            validate_short_drama(payload)
        return payload


def create_canvas_project(
    storage: Storage, seed_text: str, brief: dict[str, Any] | None = None
) -> int:
    project_id = storage.create_project(seed_text, brief)
    seed_output: dict[str, Any] = {"text": seed_text}
    if brief is not None:
        seed_output["brief"] = brief
    storage.create_canvas_node(
        project_id=project_id,
        node_key="seed",
        title="Seed",
        kind="input",
        x=40,
        y=96,
        status="completed",
        output=seed_output,
    )
    for step in AGENT_STEPS:
        storage.create_canvas_node(
            project_id=project_id,
            node_key=step.key,
            title=step.title,
            kind=step.kind,
            x=step.x,
            y=step.y,
            status="pending",
            output=None,
        )
    storage.create_canvas_edges(project_id, CANVAS_EDGES)
    return project_id


def create_revision_project(
    storage: Storage, source_project_id: int, start_node_key: str
) -> int:
    source = storage.get_project(source_project_id)
    if source["status"] != "completed":
        raise RuntimeError("Only completed projects can be revised.")

    step_keys = [step.key for step in AGENT_STEPS]
    if start_node_key not in step_keys:
        raise ValueError("Revision start node must be an agent node.")

    revision_id = create_canvas_project(
        storage=storage,
        seed_text=str(source["seed_text"]),
        brief=source["brief"],
    )
    source_nodes = {node["key"]: node for node in source["nodes"]}
    for step in AGENT_STEPS:
        instructions = source_nodes[step.key].get("instructions")
        if instructions is not None:
            storage.update_canvas_node_instructions(revision_id, step.key, instructions)
    start_index = step_keys.index(start_node_key)
    for step in AGENT_STEPS[:start_index]:
        source_node = source_nodes[step.key]
        if source_node["status"] != "completed" or source_node["output"] is None:
            raise RuntimeError(f"Source node {step.title} is not ready for revision.")
        storage.complete_canvas_node(revision_id, step.key, source_node["output"])

    return revision_id


def run_canvas_project(storage: Storage, project_id: int, agent: CanvasAgent) -> dict[str, Any]:
    project = storage.get_project(project_id)
    seed_text = str(project["seed_text"])
    context: dict[str, Any] = {"creative_brief": project["brief"]}
    storage.update_project_status(project_id, "running")

    try:
        for node in project["nodes"]:
            if node["output"] is not None:
                context[node["key"]] = node["output"]

        for step in AGENT_STEPS:
            if _project_is_paused(storage, project_id):
                return storage.get_project(project_id)

            current = storage.get_canvas_node(project_id, step.key)
            if current["status"] == "completed" and current["output"] is not None:
                context[step.key] = current["output"]
                continue

            storage.update_canvas_node_status(project_id, step.key, "running", None)
            step_context = dict(context)
            if current["instructions"] is not None:
                step_context["current_node_instructions"] = current["instructions"]
            output = agent.generate_step(step, seed_text, step_context)
            storage.complete_canvas_node(project_id, step.key, output)
            context[step.key] = output

            if step.key == "script":
                storage.complete(project["inspiration_id"], output)
                storage.update_project_title(project_id, str(output["title"]))

            if _project_is_paused(storage, project_id):
                return storage.get_project(project_id)

        storage.update_project_status(project_id, "completed")
    except Exception as exc:
        storage.update_project_status(project_id, "failed", str(exc))
        active_key = _active_step_key(storage.get_project(project_id)["nodes"])
        if active_key is not None:
            storage.update_canvas_node_status(project_id, active_key, "failed", str(exc))
        raise

    return storage.get_project(project_id)


def step_titles() -> Iterable[str]:
    return (step.title for step in AGENT_STEPS)


def _active_step_key(nodes: list[dict[str, Any]]) -> str | None:
    for node in nodes:
        if node["status"] == "running":
            return str(node["key"])
    return None


def _project_is_paused(storage: Storage, project_id: int) -> bool:
    return storage.get_project(project_id)["status"] == "paused"
