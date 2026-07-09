# Next Product Function Spec: Real Model Provider Integration

## 1. Goal

Connect Vidiom to the real OpenAI-compatible model provider configured in `.env`, so the next product iteration can be tested with actual language-agent output and first-pass image generation.

This is the required next development task.

## 2. User Value

Users should be able to create a Vidiom project, run the agent canvas, and see real generated creative output instead of an incomplete or fake product loop. Users should also be able to generate the first visual artifact from a project, making later LibTV-style image/storyboard work possible.

## 3. Configuration Contract

Read these environment variables:

- `HM_BASE_URL`: OpenAI-compatible API base URL.
- `HM_LLM_APIKEY`: language model API key.
- `HM_IMG_APIKEY`: image model API key.

Use these models:

- Language model: `gpt-5.5`
- Image model: `gpt-image-2`

Both interfaces are OpenAI-compatible. Use the configured base URL and the correct key for each model family.

Do not print or commit secret values.

## 4. Functional Scope

### 4.1 Language Agent Runtime

The existing project run flow must call `gpt-5.5` for these agent nodes:

- Premise Agent
- Character Agent
- Beat Agent
- Script Agent
- Production Agent

Each call must include:

- seed text
- creative brief
- previous node outputs
- current node instruction
- node-level user guidance when present

Each response must be parsed as structured JSON and validated against the existing schema for the node.

### 4.2 Image Generation Foundation

Add the first real image generation path using `gpt-image-2`.

Minimum user-facing capability:

- From Studio, the user can request one generated image from a prompt tied to the current project.
- The generated result is persisted as a project artifact or generated asset.
- Studio displays enough result information for the user to verify the image was generated.

Minimum backend capability:

- A provider/client module that calls the OpenAI-compatible image API with `HM_BASE_URL`, `HM_IMG_APIKEY`, and model `gpt-image-2`.
- An API endpoint for image generation.
- Persistence for generated image metadata and provider result payload required to display or retrieve the image.

## 5. Non-Goals

Do not implement the full LibTV image tool suite in this iteration.

Out of scope for this round:

- full storyboard image batch generation
- image editing
- multi-angle generation
- lighting controls
- panorama generation
- director stage
- video generation
- video composition
- audio tools

## 6. UX Requirements

Studio should make the model-backed behavior obvious to the user:

- Running an agent project should update node statuses and outputs as it does today, but backed by `gpt-5.5`.
- Image generation should have a visible trigger, prompt input, loading/running state, success state, and failure state.
- If model configuration is missing or invalid, the UI should show a clear error attached to the project or image request.

## 7. Data and API Requirements

Add or update data structures so generated image assets can be associated with a project.

At minimum, store:

- project id
- prompt
- model name
- provider response metadata needed to retrieve or display the image
- created timestamp
- generation status
- error message when failed

API requirements:

- Endpoint to create an image generation request for a project.
- Endpoint or project response field to list generated image assets for a project.
- Existing project export should include generated image asset metadata if practical in this iteration.

## 8. Acceptance Criteria

Language model:

- Running a project uses `HM_BASE_URL`, `HM_LLM_APIKEY`, and `gpt-5.5`.
- Completed agent nodes contain schema-valid model output.
- Missing `HM_LLM_APIKEY` or `HM_BASE_URL` causes the run to fail visibly; it must not produce fake success.
- Existing tests for project run, pause/resume, revisions, and export still pass.

Image model:

- A user can trigger image generation for a project from Studio.
- The backend calls `gpt-image-2` using `HM_BASE_URL` and `HM_IMG_APIKEY`.
- Generated image metadata is persisted and returned in project/API output.
- Studio displays the generated result or a retrievable artifact reference.
- Missing `HM_IMG_APIKEY` or `HM_BASE_URL` causes a visible failure; it must not produce fake success.

Documentation:

- `README.md` documents the model environment variables and the image generation smoke test.
- `README.md` iteration record is updated with this implementation.
- `.env.example` documents variable names without secret values.

Verification:

- Run lint and tests.
- Add unit tests with fake provider clients for language and image clients.
- Run one manual smoke test with the real `.env` when credentials are available locally.

## 9. Implementation Notes

- Prefer a small provider abstraction so tests can inject fake clients.
- Preserve existing schema validation for language node outputs.
- Do not add fake production behavior, placeholder success output, or fallback generators.
- Keep the first image feature narrow and verifiable.
- Do not expose API keys in logs, API responses, README, or exported project files.
