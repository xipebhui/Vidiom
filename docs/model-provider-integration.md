# Model Provider Integration Notes

## Purpose

Vidiom must connect its agent runtime to real model providers before the next product iteration. The current product experience depends on actual language generation for agent nodes and image generation for visual/storyboard features.

This document records the model configuration that is already available in `.env` and the expected integration contract for the next development task.

## Environment Variables

The local `.env` file already contains the required provider configuration. Do not print or commit secret values.

Required variables:

- `HM_BASE_URL`: OpenAI-compatible API base URL.
- `HM_LLM_APIKEY`: API key for language model calls.
- `HM_IMG_APIKEY`: API key for image model calls.

Model names:

- Language model: `gpt-5.5`
- Image model: `gpt-image-2`

The provider interfaces are OpenAI-compatible. The implementation should use the OpenAI SDK or equivalent HTTP calls with `base_url=HM_BASE_URL` and the correct API key for each model family.

## Required Language Model Integration

The agent canvas must call the real language model when users run a project. The current agent nodes are:

- Premise Agent
- Character Agent
- Beat Agent
- Script Agent
- Production Agent

Each node should call `gpt-5.5` with the node instruction, seed text, creative brief, previous node outputs, and node-level user guidance. The response must remain structured JSON and must be validated against the existing schema for that node.

Expected implementation details:

- Read `HM_BASE_URL` and `HM_LLM_APIKEY` from environment.
- Use `gpt-5.5` for all language agent nodes.
- Preserve the existing per-node JSON schema validation.
- Persist model outputs to the existing project canvas nodes.
- Persist model errors to the existing project/node failure state.
- Do not add a fallback generator or silent fake-output path.
- Tests may use explicit fake clients or monkeypatched provider clients, but production runtime must call the configured model provider.

## Required Image Model Integration

Vidiom should introduce the first real image-generation capability using `gpt-image-2`.

The first implementation should be intentionally narrow and useful:

- Provide a backend image generation service/client using `HM_BASE_URL`, `HM_IMG_APIKEY`, and model `gpt-image-2`.
- Expose a minimal API endpoint for generating an image from a prompt and optional project/node context.
- Persist the generated image metadata and provider response in the project context or a dedicated generated asset record.
- Surface the generated image in Studio so the user can verify the visual output from a project.

The first image feature does not need to replicate all LibTV image tools. It should create the foundation for later storyboard image nodes, character references, visual style references, and shot thumbnails.

Do not add a fallback image generator or placeholder image path as production behavior.

## Verification Requirements

The next development task should verify both model families.

Language model verification:

- Run an agent project from Studio or CLI using the configured `.env`.
- Confirm that each agent node stores real model output.
- Confirm that invalid or missing model configuration produces a visible failed state rather than fake success.

Image model verification:

- Call the new image-generation API with a short prompt.
- Confirm that the response contains a generated image artifact or provider image payload.
- Confirm the artifact is visible or downloadable from Studio.

Automated tests:

- Unit tests should use fake provider clients to avoid spending model credits.
- Add tests for settings parsing, provider client construction, schema validation, error handling, and asset persistence.

Manual smoke test:

```bash
source .venv/bin/activate
vidiom serve
```

Then create a draft in Studio, run the agent, and generate one image asset from the resulting project context.

## Security Notes

- Never commit `.env`.
- Never print `HM_LLM_APIKEY` or `HM_IMG_APIKEY`.
- README and docs may mention variable names, but not values.
- Error messages should identify missing variable names without exposing secret values.
