# Manus API Reference

**Base URL:** `https://api.manus.ai/v1`
**Auth header:** `API_KEY: <MANUS_API_KEY>`

---

## Tasks

| Method | Path | Description |
|--------|------|-------------|
| POST | `/tasks` | Create task |
| GET | `/tasks?limit=20` | List tasks with pagination |
| GET | `/tasks/{task_id}` | Get task by ID |
| PUT | `/tasks/{task_id}` | Update task metadata |
| DELETE | `/tasks/{task_id}` | Delete task |

### POST /tasks

```json
{
  "prompt": "<string>",
  "agent_profile": "manus-1.6",
  "task_mode": "agent",
  "project_id": "<optional project_id>",
  "task_id": "<optional, to continue thread>",
  "attachments": [
    {"file_id": "<id>"},
    {"url": "<https://...>"}
  ]
}
```

`task_mode`: `agent` (full reasoning) | `chat` (fast) | `adaptive` (auto-select)

Response:
```json
{"task_id": "...", "task_url": "..."}
```

### GET /tasks/{task_id}

```json
{
  "status": "running|completed|failed|cancelled",
  "model": "manus-1.6",
  "metadata": {"task_url": "...", "task_title": "..."},
  "output": [{"role": "assistant", "content": [{"text": "..."}]}],
  "created_at": "<unix timestamp>"
}
```

### PUT /tasks/{task_id}

```json
{"metadata": {"task_title": "New title"}}
```

### DELETE /tasks/{task_id}

Response: `{"deleted": true}`

---

## Files

| Method | Path | Description |
|--------|------|-------------|
| POST | `/files` | Create file record + get presigned S3 URL |
| GET | `/files` | List 10 most recent files |
| GET | `/files/{file_id}` | Get file details |
| DELETE | `/files/{file_id}` | Delete file |

### POST /files (upload step 1)

```json
{"filename": "...", "content": "<base64>", "encoding": "base64"}
```

Response:
```json
{"id": "...", "upload_url": "<s3-presigned-url or null>"}
```

### PUT {upload_url} (upload step 2)

Headers: `Content-Type: <mime>`
Body: raw bytes
Success: 200 or 204

### GET /files/{file_id}

Returns file metadata (id, filename, size, created_at, etc.)

### DELETE /files/{file_id}

Deletes the file and returns confirmation.

---

## Projects

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects` | Create a new project |
| GET | `/projects` | List all projects |

### POST /projects

```json
{
  "name": "<project name>",
  "instructions": "<optional default instructions>"
}
```

Response: `{"id": "...", "name": "..."}`

### GET /projects

Response:
```json
{"data": [{"id": "...", "name": "...", "instructions": "..."}]}
```

---

## Webhooks

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks` | Register a new webhook |
| DELETE | `/webhooks/{webhook_id}` | Delete a webhook |

### POST /webhooks

```json
{
  "url": "<https://your-endpoint.com/webhook>",
  "events": ["task.completed", "task.failed"]
}
```

Response:
```json
{"id": "...", "secret": "<signing secret — save this!>"}
```

**Events:**
- `task.completed` — Task finished successfully
- `task.failed` — Task failed
- `task.cancelled` — Task was cancelled

**Security:** Webhook payloads are signed with the secret. Verify the signature header to authenticate requests.

### DELETE /webhooks/{webhook_id}

Removes the webhook subscription.

---

## Local Agent Protocol

The local agent executes commands on the user's machine. No network API involved.

### Safety Levels

| Level | Behavior |
|-------|----------|
| `prompt` | Ask approval for every command |
| `allowlist` | Auto-approve safe commands, prompt for others |
| `unrestricted` | Auto-approve all (with audit logging) |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MANUS_API_KEY` | (required for cloud) | Cloud API authentication |
| `MANUS_BASE_URL` | `https://api.manus.ai/v1` | API base URL |
| `MANUS_SAFETY_LEVEL` | `prompt` | Safety level for local commands |
| `MANUS_AUDIT_LOG` | `~/.manus/audit.log` | Audit log path |

### Risk Classification

| Risk | Examples | Behavior |
|------|----------|----------|
| Safe | `ls`, `cat`, `git status`, `nvidia-smi`, `whoami` | Auto-approve in allowlist mode |
| Moderate | `pip install`, `npm install`, `mkdir`, `cp`, `mv` | Prompt in allowlist mode |
| Dangerous | `rm -rf /`, `sudo rm`, `format`, `shutdown` | Always prompt, even in unrestricted |

### Desktop Commands (platform-dependent)

| Command | Windows | Unix/Mac |
|---------|---------|----------|
| List apps | `tasklist` | `ps aux` |
| Launch app | `start <app>` | `open` / `xdg-open` |
| Kill process | `taskkill /PID` | `kill -9` |
| GPU info | `nvidia-smi` / `wmic` | `nvidia-smi` / `lspci` |
| System info | `systeminfo` | `uname -a && lscpu && free -h` |
| Screenshot | PowerShell capture | `screencapture` / `scrot` |
