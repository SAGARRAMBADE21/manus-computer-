---
name: manus-unified
description: Operate Manus AI — send tasks, manage files/projects, chat interactively, run a local machine agent, or launch the web UI. Use /manus-unified <prompt> to send a task, or: tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task> | ui
argument-hint: "<prompt> | tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task> | ui"
---

# Manus AI Skill

**API:** `https://api.manus.ai/v1` | **Auth:** `MANUS_API_KEY` in `.env`

## Arguments
$ARGUMENTS

---

## Command Routing

| Arguments | Command |
|-----------|---------|
| `<prompt>` | `echo "<prompt>" \| python manus_cli.py` |
| `tasks` | `python manus_cli.py --tasks` |
| `task <id>` | `python manus_cli.py --task <id>` |
| `delete <id>` | `python manus_cli.py --delete <id>` |
| `files` | `python manus_cli.py --files` |
| `upload <path>` | `python manus_cli.py --upload "<path>"` |
| `projects` | `python manus_cli.py --projects` |
| `chat` | `python manus_cli.py` |
| `chat --mode chat` | `python manus_cli.py --mode chat` |
| `nowait <prompt>` | `python manus_cli.py --no-wait` then send prompt |
| `local <task>` | `python manus_local.py "<task>"` |
| `local --yes <task>` | `python manus_local.py --yes "<task>"` |
| `local` | `python manus_local.py` |
| `ui` | `python ui/app.py` → open `http://localhost:5000` |

---

## manus_cli.py — CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `manus-1.6` | Model profile |
| `--mode` | `agent` | `agent` \| `chat` \| `adaptive` |
| `--no-wait` | off | Fire and forget |
| `--tasks` | — | List tasks (last 20) |
| `--task <ID>` | — | View task output |
| `--delete <ID>` | — | Delete task |
| `--upload <FILE>` | — | Upload file |
| `--projects` | — | List projects |
| `--files` | — | List files |
| `--help` / `-h` | — | Help |

### In-Chat Commands

| Command | Action |
|---------|--------|
| `/exit`, `/quit`, `exit`, `quit` | Quit |
| `/tasks` | List tasks |
| `/task <id>` | View task |
| `/delete <id>` | Delete task |
| `/upload <path>` | Upload file → queued for next prompt |
| `/url <https://...>` | Queue URL for next prompt |
| `/files` | List files |
| `/projects` | List projects |
| `/help` | Show help |
| *(any text)* | Send as task (with any queued attachments) |

### File & URL Attachments
Queue files/URLs before sending a prompt — all are bundled with the next task:
- `/upload <path>` → uploads file, queues `{"file_id": "<id>"}`
- `/url <url>` → queues `{"url": "<url>"}` directly
- Queue clears after each send

---

## manus_local.py — Local Agent

Manus AI plans steps and generates shell/Python commands. Each command requires approval before running on your machine.

### CLI Flags

| Flag | Description |
|------|-------------|
| `<task>` | Run agent loop immediately |
| *(no args)* | Interactive shell (`Task>` prompt) |
| `--yes` / `-y` | Auto-approve all commands |
| `--cwd <dir>` | Set working directory |

### Approval Keys

| Key | Action |
|-----|--------|
| `y` / Enter | Run this command |
| `a` | Run this + auto-approve all future |
| `n` | Skip |
| `q` | Quit |

**Auto-approved (no prompt):** `dir`, `ls`, `echo`, `type`, `cat`, `pwd`, `cd`, `python --version`, `pip list`, `git status`, `git log`, `whoami`, `hostname`

**Max steps:** 10 — if reached: `Reached max steps (10). Use /local again to continue.`

### Interactive Shell Built-ins

| Command | Action |
|---------|--------|
| `ls [path]` / `dir [path]` | List directory |
| `read <file>` | Read file content |
| `cd <dir>` | Change directory |
| `run <cmd>` | Run shell command (with approval) |
| `exit` / `quit` | Exit |
| *(anything else)* | Send to agent loop |

---

## ui/app.py — Web UI

Browser-based local agent. Run: `python ui/app.py` → `http://localhost:5000`

### Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Web UI |
| GET | `/api/cwd` | Current directory |
| POST | `/api/task` | Submit task |
| POST | `/api/approve` | Approve / skip command |
| GET | `/api/files` | List directory |
| POST | `/api/read` | Read file or cd into folder |
| POST | `/api/cd` | Change directory |
| GET | `/api/history` | Last 20 tasks |

### POST /api/task
```json
// Request
{"task": "<string>"}

// Response — commands to approve
{"type": "plan", "text": "...", "commands": [...], "step_id": "<id>"}

// Response — task complete
{"type": "done", "text": "..."}
```

### POST /api/approve
```json
// Request
{"step_id": "<id>", "cmd_index": 0, "action": "approve|skip|always"}

// Response
{"output": "...", "error": false, "next": {"type": "plan|done", ...}}
```

### UI Features
- **Left sidebar:** Chat, Files, History, Quick Tasks (list files / disk usage / processes / system info)
- **Main area:** Chat with Manus, command approval buttons (Run / Run All / Skip)
- **Right panel:** Local file browser — click file to read, click folder to navigate

---

## Errors

| Error | Message |
|-------|---------|
| Missing API key | `MANUS_API_KEY not set` → exits |
| API failure | `API Error <status>: <detail>` |
| No internet | `Connection error. Check your internet.` |
| File not found | `File not found: <path>` |
| S3 upload fail | `S3 upload failed: <status>` |
| No Manus response | `No response from Manus.` |
| Shell timeout | `Error: timed out` |
| Python timeout | `Error: script timed out` |
