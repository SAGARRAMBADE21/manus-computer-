---
name: manus-unified
description: Operate the full Manus AI system — send tasks, manage files and projects, run a local machine agent with step-by-step command approval. Use /manus-unified <prompt> to send a task, or: tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task>
argument-hint: "<prompt> | tasks | task <id> | delete <id> | files | upload <path> | projects | chat | local <task>"
---

# Manus AI — Unified Skill

**API:** `https://api.manus.ai/v1` | **Auth:** `MANUS_API_KEY` in `.env`
**API reference:** `references/api.md`

## Arguments
$ARGUMENTS

---

## Command Routing

| Arguments | Command |
|-----------|---------|
| `<prompt>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>"` |
| `<prompt> --mode chat` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --mode chat` |
| `<prompt> --no-wait` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --no-wait` |
| `<prompt> --file <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --file <id>` |
| `<prompt> --url <url>` | `python ${CLAUDE_SKILL_DIR}/scripts/task.py "<prompt>" --url <url>` |
| `tasks` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py tasks` |
| `task <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py task <id>` |
| `delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py delete <id>` |
| `files` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py files` |
| `upload <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py upload "<path>"` |
| `projects` | `python ${CLAUDE_SKILL_DIR}/scripts/manage.py projects` |
| `chat` | `python manus_cli.py` |
| `local <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py "<task>"` |
| `local --yes <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py --yes "<task>"` |
| `local` | `python ${CLAUDE_SKILL_DIR}/scripts/local_agent.py` |

---

## scripts/task.py — Send a Task

```
python task.py "<prompt>"
python task.py "<prompt>" --mode chat|agent|adaptive
python task.py "<prompt>" --no-wait
python task.py "<prompt>" --file <file_id>
python task.py "<prompt>" --url <url>
```

Creates a task, polls until complete, prints title / status / URL / output.
`--no-wait` fires and forgets — prints task ID + URL only.

---

## scripts/manage.py — Manage Resources

```
python manage.py tasks               # list last 20 tasks
python manage.py task <id>           # view task output
python manage.py delete <id>         # delete a task
python manage.py files               # list uploaded files
python manage.py upload <filepath>   # upload file (2-step: Manus + S3)
python manage.py projects            # list projects
```

---

## scripts/local_agent.py — Local Machine Agent

Manus plans step by step. Each command requires approval before it runs.

```
python local_agent.py "<task>"
python local_agent.py "<task>" --yes      # auto-approve all
python local_agent.py "<task>" --cwd <d>
python local_agent.py                     # interactive shell
```

**Approval keys:** `y`/Enter = run | `a` = run + approve all | `n` = skip | `q` = quit

**Auto-approved:** `dir`, `ls`, `echo`, `type`, `cat`, `pwd`, `cd`, `python --version`, `pip list`, `git status`, `git log`, `whoami`, `hostname`

**Interactive built-ins:** `ls [path]` | `read <file>` | `cd <dir>` | `run <cmd>` | `exit`

**Max steps:** 10 — run again to continue if reached.

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
