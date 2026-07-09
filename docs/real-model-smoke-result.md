# Real Model Smoke Result

- Run started at: `2026-07-09T20:48:42.312673+00:00`
- Run finished at: `2026-07-09T20:56:31.647877+00:00`
- Overall status: `interrupted`
- Product requirement: `docs/next-product-requirement.md` Real Model End-to-End Acceptance Gate, updated 2026-07-10 CST
- Architecture task: `docs/development-task-breakdown.md` Task 1 强化真实 smoke 发布门禁
- Acceptance scope: `smoke-real-model-storyboard` covers agent, Storyboard, project image and export package stages in one real end-to-end gate.
- Database path: `/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-g_tkeved/vidiom.sqlite3`
- Project ID: `1`
- Language model: `gpt-5.5`
- Image model: `gpt-image-2`
- Secret handling: `HM_BASE_URL`, `HM_LLM_APIKEY` and `HM_IMG_APIKEY` values are not written to this file.

## Stage Results

| Stage | Status | Model | Duration | Summary | Error |
| --- | --- | --- | ---: | --- | --- |
| `agent_project` | `completed` | `gpt-5.5` | 178.121 | Agent project completed 5/5 nodes. |  |
| `storyboard_generation` | `interrupted` | `gpt-5.5` | 291.208 | Smoke run was interrupted before this stage completed. | Interrupted by user or external process. |
| `project_image_generation` | `incomplete` | `` |  | Not completed because the smoke run was interrupted. |  |
| `export_package` | `incomplete` | `` |  | Not completed because the smoke run was interrupted. |  |

## Structured Result

```json
{
  "run_started_at": "2026-07-09T20:48:42.312673+00:00",
  "run_finished_at": "2026-07-09T20:56:31.647877+00:00",
  "duration_seconds": 469.335,
  "overall_status": "interrupted",
  "project_id": 1,
  "database_path": "/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-g_tkeved/vidiom.sqlite3",
  "result_path": "docs/real-model-smoke-result.md",
  "models": {
    "language": "gpt-5.5",
    "image": "gpt-image-2"
  },
  "stages": [
    {
      "stage": "agent_project",
      "status": "completed",
      "started_at": "2026-07-09T20:48:42.316201+00:00",
      "finished_at": "2026-07-09T20:51:40.437443+00:00",
      "duration_seconds": 178.121,
      "model": "gpt-5.5",
      "summary": "Agent project completed 5/5 nodes.",
      "error_message": null,
      "details": {
        "project_id": 1,
        "title": "8:17异常帧",
        "agent_nodes": {
          "total": 5,
          "completed": 5,
          "failed": 0,
          "running": 0,
          "pending": 0
        }
      }
    },
    {
      "stage": "storyboard_generation",
      "status": "interrupted",
      "started_at": "2026-07-09T20:51:40.437507+00:00",
      "finished_at": "2026-07-09T20:56:31.645448+00:00",
      "duration_seconds": 291.208,
      "model": "gpt-5.5",
      "summary": "Smoke run was interrupted before this stage completed.",
      "error_message": "Interrupted by user or external process.",
      "details": {}
    },
    {
      "stage": "project_image_generation",
      "status": "incomplete",
      "started_at": null,
      "finished_at": null,
      "duration_seconds": null,
      "model": null,
      "summary": "Not completed because the smoke run was interrupted.",
      "error_message": null,
      "details": {}
    },
    {
      "stage": "export_package",
      "status": "incomplete",
      "started_at": null,
      "finished_at": null,
      "duration_seconds": null,
      "model": null,
      "summary": "Not completed because the smoke run was interrupted.",
      "error_message": null,
      "details": {}
    }
  ]
}
```
