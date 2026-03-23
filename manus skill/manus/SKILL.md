---
name: manus
description: Send tasks to Manus AI, manage tasks/files/projects, or run a local machine agent with step-by-step command approval.
argument-hint: "<prompt> | tasks | task <id> | delete <id> | files | upload <path> | projects | local <task> | local --yes <task> | local"
---

# Manus AI

**Base URL:** `https://api.manus.ai/v1`
**Auth:** Set `MANUS_API_KEY` in `.env`

## Routing

| Arguments | Runs |
|-----------|------|
| `<prompt>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>"` |
| `<prompt> --mode chat` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --mode chat` |
| `<prompt> --mode adaptive` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --mode adaptive` |
| `<prompt> --no-wait` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --no-wait` |
| `<prompt> --file <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --file <id>` |
| `<prompt> --url <url>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --url <url>` |
| `tasks` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py tasks` |
| `task <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py task <id>` |
| `delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py delete <id>` |
| `files` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py files` |
| `upload <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py upload "<path>"` |
| `projects` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py projects` |
| `local <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py "<task>"` |
| `local --yes <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py --yes "<task>"` |
| `local` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py` |

$ARGUMENTS

---

## Send a Task

```
python task.py "<prompt>"
python task.py "<prompt>" --mode agent|chat|adaptive
python task.py "<prompt>" --no-wait
python task.py "<prompt>" --file <file_id>
python task.py "<prompt>" --url <url>
```

- Default mode: `agent` (full reasoning). Use `chat` for fast responses, `adaptive` for auto-select.
- `--no-wait`: fire-and-forget — prints task ID and URL without polling.
- `--file` / `--url`: attach a file or URL to the task.

---

## Manage Tasks, Files, Projects

```
python manage.py tasks               # list last 20 tasks
python manage.py task <id>           # view task output
python manage.py delete <id>         # delete a task
python manage.py files               # list uploaded files
python manage.py upload <filepath>   # upload file (2-step: register + S3)
python manage.py projects            # list projects
```

---

## Local Machine Agent

Manus generates commands step by step. Each requires approval before it executes.

```
python local_agent.py "<task>"
python local_agent.py "<task>" --yes      # auto-approve all commands
python local_agent.py "<task>" --cwd <dir>
python local_agent.py                     # interactive shell
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
| `Error <status>: <detail>` | API request failed |
| `File not found: <path>` | Upload path is wrong |
| `S3 upload failed: <status>` | Second upload step failed |
| `No response from Manus.` | API returned empty result |
| `Error: timed out` | Shell command exceeded 60s |
| `Error: script timed out` | Python script exceeded 120s |
