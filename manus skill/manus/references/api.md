# Manus API Reference

**Base URL:** `https://api.manus.ai/v1`
**Auth header:** `API_KEY: <MANUS_API_KEY>`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/tasks` | Create task |
| GET | `/tasks/{id}` | Get task |
| GET | `/tasks?limit=20` | List tasks |
| DELETE | `/tasks/{id}` | Delete task |
| GET | `/projects` | List projects |
| GET | `/files` | List files |
| POST | `/files` | Register file upload |
| PUT | `{upload_url}` | S3 upload (step 2) |

## POST /tasks

```json
{
  "prompt": "<string>",
  "agent_profile": "manus-1.6",
  "task_mode": "agent",
  "attachments": [
    {"file_id": "<id>"},
    {"url": "<https://...>"}
  ]
}
```
`task_mode`: `agent` (full) | `chat` (fast) | `adaptive`
Response: `{"task_id": "...", "task_url": "..."}`

## GET /tasks/{id}

```json
{
  "status": "running|completed|failed|cancelled",
  "model": "manus-1.6",
  "metadata": {"task_url": "...", "task_title": "..."},
  "output": [{"role": "assistant", "content": [{"text": "..."}]}],
  "created_at": "<unix timestamp>"
}
```

## DELETE /tasks/{id}

Response: `{"deleted": true}`

## GET /files — Response

```json
{"data": [{"id": "...", "filename": "..."}]}
```

## POST /files (upload step 1)

```json
{"filename": "...", "content": "<base64>", "encoding": "base64"}
```
Response: `{"id": "...", "upload_url": "<s3-presigned-url or null>"}`

## PUT {upload_url} (upload step 2)

Headers: `Content-Type: <mime>`  Body: raw bytes  Success: 200 or 204
