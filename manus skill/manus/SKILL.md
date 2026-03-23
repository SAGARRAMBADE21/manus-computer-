---
name: manus
description: Send tasks to Manus AI, chat interactively, manage tasks/files/projects, or run a local machine agent with step-by-step command approval.
argument-hint: "<prompt> | chat | tasks | task <id> | delete <id> | files | upload <path> | projects | local <task> | local --yes <task> | local | help"
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
| `local --yes <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py local --yes "<task>"` |
| `local` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py local` |
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

## Local Machine Agent

Manus generates commands step by step. Each requires approval before it executes.

```
python manus.py local "<task>"
python manus.py local --yes "<task>"       # auto-approve all commands
python manus.py local --cwd <dir> "<task>"
python manus.py local                      # interactive shell
```

**Approval:** `y` / Enter = run | `a` = approve all remaining | `n` = skip | `q` = quit

**Auto-approved:** `dir`, `ls`, `echo`, `type`, `cat`, `pwd`, `cd`, `python --version`, `pip list`, `git status`, `git log`, `whoami`, `hostname`

**Interactive built-ins:** `ls [path]` | `read <file>` | `cd <dir>` | `run <cmd>` | `exit`

Max steps per run: **10** — re-run to continue if limit is reached.

---

## Errors

| Error | Cause |
|-------|-------|
| `MANUS_API_KEY not set` | Missing key in `.env` |
| `Connection error` | No internet / API unreachable |
| `Error <status>: <detail>` | API request failed |
| `File not found: <path>` | Upload path is wrong |
| `S3 upload failed: <status>` | Second upload step failed |
| `No response from Manus.` | API returned empty result |
| `Error: timed out` | Shell command exceeded 60s |
| `Error: script timed out` | Python script exceeded 120s |
