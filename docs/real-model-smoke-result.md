# Real Model Smoke Result

- Run started at: `2026-07-09T21:48:43.277348+00:00`
- Run finished at: `2026-07-09T21:56:17.773074+00:00`
- Overall status: `completed`
- Product requirement: `docs/next-product-requirement.md` Complete Real Model End-to-End Acceptance, updated 2026-07-10 CST
- Architecture task: `docs/development-task-breakdown.md` Task 1 收口 Storyboard 真实生成生命周期与中断状态
- Acceptance scope: `smoke-real-model-storyboard` covers agent, Storyboard, project image and export package stages in one real end-to-end gate.
- Database path: `/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-ecf6q1vs/vidiom.sqlite3`
- Project ID: `1`
- Language model: `gpt-5.5`
- Image model: `gpt-image-2`
- Secret handling: `HM_BASE_URL`, `HM_LLM_APIKEY` and `HM_IMG_APIKEY` values are not written to this file.

## Stage Results

| Stage | Status | Model | Duration | Summary | Error |
| --- | --- | --- | ---: | --- | --- |
| `agent_project` | `completed` | `gpt-5.5` | 183.899 | Agent project completed 5/5 nodes. |  |
| `storyboard_generation` | `completed` | `gpt-5.5` | 218.401 | Storyboard completed with 18 shots and 18 assets. |  |
| `project_image_generation` | `completed` | `gpt-image-2` | 52.18 | Project image asset completed with gpt-image-2. |  |
| `export_package` | `completed` | `` | 0.012 | Export package contains completed storyboard and project image assets. |  |

## Structured Result

```json
{
  "run_started_at": "2026-07-09T21:48:43.277348+00:00",
  "run_finished_at": "2026-07-09T21:56:17.773074+00:00",
  "duration_seconds": 454.496,
  "overall_status": "completed",
  "project_id": 1,
  "database_path": "/var/folders/v_/s3sfnkdj6c729_y_g57bc46r0000gn/T/vidiom-real-smoke-ecf6q1vs/vidiom.sqlite3",
  "result_path": "docs/real-model-smoke-result.md",
  "models": {
    "language": "gpt-5.5",
    "image": "gpt-image-2"
  },
  "stages": [
    {
      "stage": "agent_project",
      "status": "completed",
      "started_at": "2026-07-09T21:48:43.280542+00:00",
      "finished_at": "2026-07-09T21:51:47.179916+00:00",
      "duration_seconds": 183.899,
      "model": "gpt-5.5",
      "summary": "Agent project completed 5/5 nodes.",
      "error_message": null,
      "details": {
        "project_id": 1,
        "title": "08:17前交片",
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
      "status": "completed",
      "started_at": "2026-07-09T21:51:47.179998+00:00",
      "finished_at": "2026-07-09T21:55:25.581062+00:00",
      "duration_seconds": 218.401,
      "model": "gpt-5.5",
      "summary": "Storyboard completed with 18 shots and 18 assets.",
      "error_message": null,
      "details": {
        "shot_count": 18,
        "asset_count": 18,
        "relationship_count": 119,
        "image_link_count": 0,
        "has_completed_result": true,
        "latest_attempt_failed": false,
        "result_source": "last_completed_result"
      }
    },
    {
      "stage": "project_image_generation",
      "status": "completed",
      "started_at": "2026-07-09T21:55:25.581171+00:00",
      "finished_at": "2026-07-09T21:56:17.760980+00:00",
      "duration_seconds": 52.18,
      "model": "gpt-image-2",
      "summary": "Project image asset completed with gpt-image-2.",
      "error_message": null,
      "details": {
        "image_asset_id": 1,
        "artifact_url_present": false,
        "b64_json_present": true,
        "revised_prompt_present": true
      }
    },
    {
      "stage": "export_package",
      "status": "completed",
      "started_at": "2026-07-09T21:56:17.761000+00:00",
      "finished_at": "2026-07-09T21:56:17.773053+00:00",
      "duration_seconds": 0.012,
      "model": null,
      "summary": "Export package contains completed storyboard and project image assets.",
      "error_message": null,
      "details": {
        "storyboard_generation_status": "completed",
        "storyboard_shot_count": 18,
        "storyboard_asset_count": 18,
        "storyboard_relationship_count": 119,
        "storyboard_image_link_count": 0,
        "project_image_asset_count": 1,
        "completed_project_image_asset_count": 1
      }
    }
  ]
}
```
