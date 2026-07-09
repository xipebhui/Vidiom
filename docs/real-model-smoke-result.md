# Real Model Smoke Result

- Run started at: `2026-07-09T19:52:39.275872+00:00`
- Run finished at: `2026-07-09T19:53:52.722855+00:00`
- Overall status: `failed`
- Product requirement: `docs/next-product-requirement.md` Real Model Storyboard Acceptance, updated 2026-07-10 CST
- Architecture task: `docs/development-task-breakdown.md` Task 1 real `.env` end-to-end smoke runner
- Database path: `/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-ez0brxkk/vidiom.sqlite3`
- Project ID: `1`
- Language model: `gpt-5.5`
- Image model: `gpt-image-2`
- Secret handling: `HM_BASE_URL`, `HM_LLM_APIKEY` and `HM_IMG_APIKEY` values are not written to this file.

## Stage Results

| Stage | Status | Model | Duration | Summary | Error |
| --- | --- | --- | ---: | --- | --- |
| `agent_project` | `failed` | `gpt-5.5` | 73.444 | agent_project failed before completion. | Error code: 503 - {'error': {'message': 'system cpu overloaded (current: 99.8%, threshold: 90%)', 'type': 'new_api_error', 'param': '', 'code': 'system_cpu_overloaded'}} |
| `storyboard_generation` | `incomplete` | `` |  | Not run because agent_project did not complete. |  |
| `project_image_generation` | `incomplete` | `` |  | Not run because agent_project did not complete. |  |
| `export_package` | `incomplete` | `` |  | Not run because agent_project did not complete. |  |

## Structured Result

```json
{
  "run_started_at": "2026-07-09T19:52:39.275872+00:00",
  "run_finished_at": "2026-07-09T19:53:52.722855+00:00",
  "duration_seconds": 73.447,
  "overall_status": "failed",
  "project_id": 1,
  "database_path": "/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-ez0brxkk/vidiom.sqlite3",
  "result_path": "docs/real-model-smoke-result.md",
  "models": {
    "language": "gpt-5.5",
    "image": "gpt-image-2"
  },
  "stages": [
    {
      "stage": "agent_project",
      "status": "failed",
      "started_at": "2026-07-09T19:52:39.278764+00:00",
      "finished_at": "2026-07-09T19:53:52.722766+00:00",
      "duration_seconds": 73.444,
      "model": "gpt-5.5",
      "summary": "agent_project failed before completion.",
      "error_message": "Error code: 503 - {'error': {'message': 'system cpu overloaded (current: 99.8%, threshold: 90%)', 'type': 'new_api_error', 'param': '', 'code': 'system_cpu_overloaded'}}",
      "details": {}
    },
    {
      "stage": "storyboard_generation",
      "status": "incomplete",
      "started_at": null,
      "finished_at": null,
      "duration_seconds": null,
      "model": null,
      "summary": "Not run because agent_project did not complete.",
      "error_message": null,
      "details": {}
    },
    {
      "stage": "project_image_generation",
      "status": "incomplete",
      "started_at": null,
      "finished_at": null,
      "duration_seconds": null,
      "model": null,
      "summary": "Not run because agent_project did not complete.",
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
      "summary": "Not run because agent_project did not complete.",
      "error_message": null,
      "details": {}
    }
  ]
}
```
