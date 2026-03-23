---
name: manus-unified
description: Operate the full Manus AI system — send tasks, manage files and projects, run a local machine agent with step-by-step command approval, or launch the browser-based web UI. Use /manus-unified <prompt> to send a task, or: tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task> | ui
argument-hint: "<prompt> | tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task> | ui"
---

# Manus AI — Unified Skill

Controls the Manus AI system via three scripts and a web UI.

**API:** `https://api.manus.ai/v1` | **Auth:** `MANUS_API_KEY` in `.env`
**API reference:** `references/api.md`

## Arguments
$ARGUMENTS

---

## Command Routing

Parse `$ARGUMENTS` and run the matching command:

| Arguments | Script | Command |
|-----------|--------|---------|
| `<prompt>` | scripts/task.py | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>"` |
| `<prompt> --mode chat` | scripts/task.py | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --mode chat` |
| `<prompt> --no-wait` | scripts/task.py | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --no-wait` |
| `<prompt> --file <id>` | scripts/task.py | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --file <id>` |
| `<prompt> --url <url>` | scripts/task.py | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --url <url>` |
| `tasks` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py tasks` |
| `task <id>` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py task <id>` |
| `delete <id>` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py delete <id>` |
| `files` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py files` |
| `upload <path>` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py upload "<path>"` |
| `projects` | scripts/manage.py | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py projects` |
| `chat` | manus_cli.py | `python manus_cli.py` |
| `local <task>` | scripts/local_agent.py | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py "<task>"` |
| `local --yes <task>` | scripts/local_agent.py | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py --yes "<task>"` |
| `local` | scripts/local_agent.py | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py` |
| `ui` | scripts/start_ui.py | `python ${CLAUDE_SKILL_DIR}/scripts/start_ui.py` |

---

## Scripts

### scripts/task.py — Send a Task

```
python task.py "<prompt>"
python task.py "<prompt>" --mode chat|agent|adaptive
python task.py "<prompt>" --no-wait
python task.py "<prompt>" --file <file_id>
python task.py "<prompt>" --url <url>
```

Creates a task, polls until complete, prints title/status/URL/output.
Use `--no-wait` to fire and forget (prints task ID + URL only).
Attach a previously uploaded file with `--file` or a web URL with `--url`.

---

### scripts/manage.py — Manage Resources

```
python manage.py tasks               # list last 20 tasks
python manage.py task <id>           # view task output
python manage.py delete <id>         # delete a task
python manage.py files               # list uploaded files
python manage.py upload <filepath>   # upload file (2-step: Manus + S3)
python manage.py projects            # list projects
```

---

### scripts/local_agent.py — Local Machine Agent

Manus plans the task step by step. Each command requires approval before running.

```
python local_agent.py "<task>"           # run task
python local_agent.py "<task>" --yes     # auto-approve all commands
python local_agent.py "<task>" --cwd <d> # set working directory
python local_agent.py                    # interactive shell
```

**Approval keys:**

| Key | Action |
|-----|--------|
| `y` / Enter | Run |
| `a` | Run + auto-approve all future |
| `n` | Skip |
| `q` | Quit |

**Auto-approved (safe reads):** `dir`, `ls`, `echo`, `type`, `cat`, `pwd`, `cd`, `python --version`, `pip list`, `git status`, `git log`, `whoami`, `hostname`

**Interactive built-ins:** `ls [path]`, `read <file>`, `cd <dir>`, `run <cmd>`, `exit`

**Max steps:** 10 — if reached, run again to continue.

---

### scripts/start_ui.py — Web UI

```
python start_ui.py                  # starts at http://localhost:5000
python start_ui.py --port 8080
python start_ui.py --cwd <dir>
```

Launches `ui/app.py` (Flask). Browser UI with chat, file browser, task history, and command approval (Run / Run All / Skip).

**Web UI routes:**

| Route | Description |
|-------|-------------|
| `GET /` | Web UI |
| `POST /api/task` | Submit task → `{type, text, commands, step_id}` |
| `POST /api/approve` | Approve/skip step → `{output, error, next}` |
| `GET /api/files` | List directory |
| `POST /api/read` | Read file or navigate folder |
| `POST /api/cd` | Change directory |
| `GET /api/cwd` | Current directory |
| `GET /api/history` | Last 20 tasks |

---

## Errors

| Message | Cause |
|---------|-------|
| `MANUS_API_KEY not set` | Missing `.env` key |
| `Error <status>: <detail>` | API failure |
| `Connection error. Check your internet.` | No network |
| `File not found: <path>` | Upload path wrong |
| `S3 upload failed: <status>` | S3 step failed |
| `No response from Manus.` | API returned nothing |
| `Error: timed out` | Shell command exceeded 60s |
| `Error: script timed out` | Python script exceeded 120s |
