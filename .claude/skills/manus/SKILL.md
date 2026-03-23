---
name: manus
description: Send tasks to Manus AI, chat interactively, and manage tasks/files/projects.
argument-hint: "<prompt> | chat | tasks | task <id> | delete <id> | files | upload <path> | projects | local <task> | help"
---

# Manus AI

**Base URL:** `https://api.manus.ai/v1`
**Auth:** Set `MANUS_API_KEY` in `.env`

## Routing

| Arguments | Runs |
|-----------|------|
| `<prompt>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>"` |
| `<prompt> --mode chat` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --mode chat` |
| `<prompt> --mode adaptive` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --mode adaptive` |
| `<prompt> --model <model>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --model <model>` |
| `<prompt> --no-wait` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --no-wait` |
| `<prompt> --file <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --file <id>` |
| `<prompt> --url <url>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --url <url>` |
| `chat` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat` |
| `chat --mode chat` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat --mode chat` |
| `chat --no-wait` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat --no-wait` |
| `tasks` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py tasks` |
| `task <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py task <id>` |
| `delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py delete <id>` |
| `files` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py files` |
| `upload <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py upload "<path>"` |
| `projects` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py projects` |
| `local <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py local "<task>"` |
| `help` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py help` |

$ARGUMENTS

---

## Send a Task

Output streams in real time as Manus responds.

```
python manus.py send "<prompt>"
python manus.py send "<prompt>" --mode agent|chat|adaptive
python manus.py send "<prompt>" --model manus-1.6
python manus.py send "<prompt>" --no-wait
python manus.py send "<prompt>" --file <file_id>
python manus.py send "<prompt>" --url <url>
```

- Default mode: `agent` (full reasoning). `chat` = fast, `adaptive` = auto-select.
- `--no-wait`: fire-and-forget — prints task ID and URL only.
- `--file` / `--url`: attach a file or URL to the task.

---

## Interactive Chat

A persistent REPL — type tasks, get real-time responses, manage everything inline.

```
python manus.py chat
python manus.py chat --mode chat
python manus.py chat --no-wait
```

**In-chat commands:**
`/tasks` | `/task <id>` | `/delete <id>` | `/files` | `/upload <path>` | `/url <url>` | `/projects` | `/help` | `/exit`

- `/upload <path>` — uploads file and queues it for the next prompt
- `/url <url>` — queues a URL attachment for the next prompt

---

## Manage Tasks, Files, Projects

```
python manus.py tasks               # list last 20 tasks
python manus.py task <id>           # view task output
python manus.py delete <id>         # delete a task
python manus.py files               # list uploaded files
python manus.py upload <filepath>   # upload file (2-step: register + S3)
python manus.py projects            # list projects
```

---

## Local Task

Sends a task to Manus agent and streams the response in real time. Manus handles everything.

```
python manus.py local "<task>"
```

---

## Errors

| Error | Cause |
|-------|-------|
| `MANUS_API_KEY not set` | Missing key in `.env` |
| `Connection error` | No internet / API unreachable |
| `Error <status>: <detail>` | API request failed |
| `File not found: <path>` | Upload path is wrong |
| `S3 upload failed: <status>` | Second upload step failed |
