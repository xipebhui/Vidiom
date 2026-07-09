# Product Gap Analysis

## Current Priority

The most important immediate gap is real model integration. Vidiom already presents an agent canvas workflow, but the next iteration must ensure the runtime uses the configured production model provider for both language and image generation.

## LibTV Reference Capability

LibTV combines an infinite canvas, agent-like nodes, story/script decomposition, image generation, video generation, image tools, video tools, audio tools, asset management, and a director stage. A key part of that experience is that nodes create real media or structured creative artifacts through connected models.

## Vidiom Current State

Observed from the repository:

- Vidiom has a Studio UI with project creation, agent canvas, node inspector, review panels, project export, pause/resume, revision drafts, and run timeline.
- Vidiom has language-agent code paths for Premise, Character, Beat, Script, and Production nodes.
- Vidiom has an older `OpenAIShortDramaGenerator` path for batch generation.
- Vidiom has no documented image model integration and no visible Studio image-generation workflow.
- `.env` contains OpenAI-compatible provider configuration via `HM_BASE_URL`, `HM_LLM_APIKEY`, and `HM_IMG_APIKEY`.

## Gap: Real Model Runtime

Vidiom must use the configured provider instead of any fake or incomplete generation path when running the product.

Required target:

- Language agent runtime calls `gpt-5.5`.
- Image generation runtime calls `gpt-image-2`.
- Both use `HM_BASE_URL`.
- Language calls use `HM_LLM_APIKEY`.
- Image calls use `HM_IMG_APIKEY`.
- Runtime outputs are persisted and visible to the user.
- Runtime failures are visible in project/node state.

## Gap: Image Foundation

LibTV provides extensive image capabilities, including image nodes, image generation, style references, image editing, storyboard generation, multi-angle, lighting, panorama, annotation, and image grouping.

Vidiom should not attempt all of these at once. The next practical step is to add a narrow image-generation foundation:

- A provider client for `gpt-image-2`.
- A backend endpoint to request image generation.
- Persistence for generated image metadata.
- A Studio surface to trigger generation and inspect the result.

This foundation enables future image nodes, storyboard images, character cards, shot thumbnails, and style references.

## Next Development Priority

Implement model provider integration first. Do not start broader LibTV parity work until the agent can call `gpt-5.5` and the app can generate at least one real image asset with `gpt-image-2`.

See `docs/model-provider-integration.md` and `docs/next-product-function-spec.md`.
