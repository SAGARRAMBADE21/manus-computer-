---
name: manus
description: Control Manus AI — cloud tasks, local execution, desktop control, webhooks, projects, and hybrid mode.
argument-hint: "<prompt> | exec <cmd> | hybrid <task> | desktop-sysinfo | chat | tasks | projects | webhooks | files | help"
---

# Manus AI — Cloud + Local + Desktop

**Cloud API:** `https://api.manus.ai/v1`
**Auth:** Set `MANUS_API_KEY` in `.env`
**Local:** Set `MANUS_SAFETY_LEVEL=prompt|allowlist|unrestricted` in `.env`

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
| `<prompt> --thread <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --thread <id>` |
| `<prompt> --project <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py send "<prompt>" --project <id>` |
| `chat` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat` |
| `chat --mode chat` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat --mode chat` |
| `chat --project <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py chat --project <id>` |
| `tasks` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py tasks` |
| `tasks --limit <n>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py tasks --limit <n>` |
| `task <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py task <id>` |
| `update-task <id> --title <t>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py update-task <id> --title "<t>"` |
| `delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py delete <id>` |
| `files` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py files` |
| `file <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py file <id>` |
| `upload <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py upload "<path>"` |
| `file-delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py file-delete <id>` |
| `projects` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py projects` |
| `project-create <name>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py project-create "<name>"` |
| `project-create <name> --instructions <t>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py project-create "<name>" --instructions "<t>"` |
| `webhooks` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py webhooks` |
| `webhook-create <url>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py webhook-create "<url>"` |
| `webhook-create <url> --events <e>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py webhook-create "<url>" --events "<e>"` |
| `webhook-delete <id>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py webhook-delete <id>` |
| `exec "<command>"` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py exec "<command>"` |
| `exec "<command>" --cwd <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py exec "<command>" --cwd "<path>"` |
| `exec "<command>" --timeout <s>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py exec "<command>" --timeout <s>` |
| `file-read <path>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py file-read "<path>"` |
| `file-write <path> "<content>"` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py file-write "<path>" "<content>"` |
| `file-list [dir] [--pattern]` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py file-list <dir> --pattern "<p>"` |
| `run-python "<code>"` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py run-python "<code>"` |
| `desktop-apps` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-apps` |
| `desktop-launch "<app>"` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-launch "<app>"` |
| `desktop-kill <process>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-kill <process>` |
| `desktop-gpu` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-gpu` |
| `desktop-gpu-run "<cmd>"` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-gpu-run "<cmd>"` |
| `desktop-sysinfo` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-sysinfo` |
| `desktop-screenshot` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-screenshot` |
| `desktop-screenshot --output <p>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py desktop-screenshot --output "<p>"` |
| `hybrid <task>` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py hybrid <task>` |
| `help` | `python ${CLAUDE_SKILL_DIR}/scripts/manus.py help` |

$ARGUMENTS

---

## Cloud Tasks

Send tasks to Manus AI cloud with real-time streaming.

```
manus send "<prompt>"
manus send "<prompt>" --mode agent|chat|adaptive
manus send "<prompt>" --model manus-1.6
manus send "<prompt>" --no-wait
manus send "<prompt>" --file <file_id> --url <url>
manus send "<prompt>" --thread <task_id> --project <project_id>
```

---

## Task Management

```
manus tasks [--limit N]                List tasks (default: 20)
manus task <id>                        View task output
manus update-task <id> --title <t>     Update task metadata
manus delete <id>                      Delete a task
```

---

## Files

```
manus files                            List uploaded files
manus file <id>                        Get file details
manus upload <filepath>                Upload (2-step: register + S3)
manus file-delete <id>                 Delete a file
```

---

## Projects

```
manus projects                              List all projects
manus project-create <name>                 Create project
manus project-create <name> --instructions  With default instructions
```

---

## Webhooks

```
manus webhooks                                      List webhooks
manus webhook-create <url>                          Register webhook
manus webhook-create <url> --events "task.completed,task.failed"
manus webhook-delete <id>                           Remove webhook
```

---

## Local Execution

Run commands on your local machine with safety approval.

```
manus exec "<command>"                 Execute shell command
manus exec "<command>" --cwd /path     With working directory
manus exec "<command>" --timeout 60    With timeout
manus file-read <path>                 Read local file
manus file-write <path> "<content>"    Write local file
manus file-list [dir] [--pattern *]    List directory
manus run-python "<code_or_file>"      Run Python locally
```

---

## Desktop Control

```
manus desktop-apps                     List running applications
manus desktop-launch "<app>"           Launch application
manus desktop-kill <process|pid>       Kill process
manus desktop-gpu                      GPU information
manus desktop-gpu-run "<command>"      Run GPU command
manus desktop-sysinfo                  System information
manus desktop-screenshot [--output]    Take screenshot
```

---

## Hybrid Mode

Cloud AI plans the task, local machine executes.

```
manus hybrid <task description>
```

---

## Interactive Chat

```
manus chat [--mode agent|chat|adaptive] [--model] [--project <id>]
```

**In-chat commands:**
`/tasks` | `/files` | `/upload <path>` | `/url <url>` | `/delete <id>` | `/task <id>` | `/projects` | `/webhooks` | `/sysinfo` | `/exec <cmd>` | `/help` | `/exit`

---

## Safety Levels

Set `MANUS_SAFETY_LEVEL` in `.env`:

| Level | Behavior |
|-------|----------|
| `prompt` | Ask approval for every local command (default) |
| `allowlist` | Auto-approve safe commands, prompt for others |
| `unrestricted` | Auto-approve all, audit logged to `~/.manus/audit.log` |

---

## Errors

| Error | Cause |
|-------|-------|
| `MANUS_API_KEY not set` | Missing key in `.env` |
| `Connection error` | No internet / API unreachable |
| `Error <status>: <detail>` | API request failed |
| `File not found: <path>` | Upload/read path is wrong |
| `S3 upload failed: <status>` | Second upload step failed |
| `Command timed out` | Local exec exceeded timeout |
| `Command skipped` | User denied approval |
