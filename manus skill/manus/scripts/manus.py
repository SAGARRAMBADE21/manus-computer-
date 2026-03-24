#!/usr/bin/env python3
"""manus.py — Manus AI CLI: cloud tasks, local execution, desktop control, webhooks, projects."""
import os, sys, time, base64, argparse, mimetypes, subprocess, json, glob as globmod
from datetime import datetime

import requests
from dotenv import load_dotenv

# ── Platform & ANSI ──────────────────────────────────────────────────────────

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# Find .env by walking up from script directory
_dir = os.path.dirname(os.path.abspath(__file__))
for _ in range(6):
    _env = os.path.join(_dir, ".env")
    if os.path.exists(_env):
        load_dotenv(_env); break
    _dir = os.path.dirname(_dir)

BASE_URL = os.environ.get("MANUS_BASE_URL", "https://api.manus.ai/v1")
DEFAULT_MODEL = "manus-1.6"
SAFETY_LEVEL = os.environ.get("MANUS_SAFETY_LEVEL", "prompt")  # prompt | allowlist | unrestricted
AUDIT_LOG = os.environ.get("MANUS_AUDIT_LOG", os.path.join(os.path.expanduser("~"), ".manus", "audit.log"))

# Colors
BOLD    = "\033[1m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
DIM     = "\033[2m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"

# ── Auth & API ───────────────────────────────────────────────────────────────

def headers():
    key = os.environ.get("MANUS_API_KEY", "")
    if not key:
        print(f"{RED}Error: MANUS_API_KEY not set in .env{RESET}"); sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}

def api(method, path, body=None):
    try:
        r = requests.request(method, BASE_URL + path, json=body, headers=headers())
        if r.status_code in (200, 201):
            return r.json()
        print(f"{RED}Error {r.status_code}: {r.text[:300]}{RESET}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}"); return None

def fmt_time(ts):
    try: return datetime.fromtimestamp(int(ts)).strftime("%b %d %H:%M")
    except Exception: return str(ts)

def status_color(status):
    colors = {"completed": GREEN, "running": CYAN, "failed": RED, "cancelled": DIM}
    return colors.get(status, RESET) + status + RESET

# ── Streaming ────────────────────────────────────────────────────────────────

def stream_task(task_id):
    """Poll every 1s and print output incrementally."""
    shown = 0
    time.sleep(2)
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers())
            if r.status_code in (404, 429, 500, 502, 503):
                time.sleep(3); continue
            if r.status_code != 200:
                print(f"\n{RED}Error {r.status_code}{RESET}"); return None
            task = r.json()
            current = ""
            for item in task.get("output", []):
                if item.get("role") != "assistant": continue
                for c in item.get("content", []):
                    current += c.get("text", "")
            if len(current) > shown:
                print(current[shown:], end="", flush=True)
                shown = len(current)
            status = task.get("status")
            if status in ("completed", "failed", "cancelled"):
                print()
                return task
        except requests.exceptions.ConnectionError:
            print(f"\n{YELLOW}Network blip, retrying...{RESET}", end="", flush=True)
        time.sleep(1)

def task_print_header(task):
    meta = task.get("metadata", {})
    print(f"\n{BOLD}{'-' * 55}{RESET}")
    if meta.get("task_title"):
        print(f"{BOLD}{meta['task_title']}{RESET}")
    print(f"Status : {status_color(task.get('status', ''))}  |  Model: {DIM}{task.get('model', '')}{RESET}")
    if meta.get("task_url"):
        print(f"URL    : {DIM}{meta['task_url']}{RESET}")
    print(f"{'-' * 55}")

# ── Tasks: Create / Send ─────────────────────────────────────────────────────

def task_create(prompt, mode="agent", model=None, attachments=None, task_id=None, project_id=None):
    model = model or DEFAULT_MODEL
    body = {"prompt": prompt, "agent_profile": model, "task_mode": mode}
    if attachments:
        body["attachments"] = attachments
    if task_id:
        body["task_id"] = task_id
    if project_id:
        body["project_id"] = project_id
    try:
        r = requests.post(f"{BASE_URL}/tasks", json=body, headers=headers())
        if r.status_code not in (200, 201):
            print(f"{RED}Error {r.status_code}: {r.text[:300]}{RESET}"); return None
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}"); return None

def cmd_send(args):
    attachments = []
    if getattr(args, "file", None):
        attachments.append({"file_id": args.file})
    if getattr(args, "url", None):
        attachments.append({"url": args.url})
    model = getattr(args, "model", DEFAULT_MODEL)
    thread = getattr(args, "thread", None)
    project = getattr(args, "project", None)
    resp = task_create(args.prompt, args.mode, model, attachments or None, task_id=thread, project_id=project)
    if not resp: return
    task_id = resp.get("task_id")
    task_url = resp.get("task_url", "")
    print(f"{DIM}Task: {task_id}  {task_url}{RESET}")
    if not args.no_wait:
        task = stream_task(task_id)
        if task: task_print_header(task)

# ── Tasks: List / Get / Update / Delete ───────────────────────────────────────

def cmd_tasks(args):
    limit = getattr(args, "limit", 20) or 20
    data = api("GET", f"/tasks?limit={limit}")
    tasks = data.get("data", []) if data else []
    if not tasks:
        print("No tasks found."); return
    print(f"\n{BOLD}{'ID':<25} {'Status':<12} {'Created':<14} Title{RESET}")
    print("-" * 75)
    for t in tasks:
        color = {"completed": GREEN, "running": CYAN, "failed": RED}.get(t.get("status", ""), RESET)
        print(f"{t.get('id', ''):<25} {color}{t.get('status', ''):<12}{RESET} "
              f"{DIM}{fmt_time(t.get('created_at', '0')):<14}{RESET} "
              f"{t.get('metadata', {}).get('task_title', '')[:35]}")

def cmd_task(args):
    task = api("GET", f"/tasks/{args.id}")
    if not task: return
    task_print_header(task)
    for item in task.get("output", []):
        if item.get("role") != "assistant": continue
        for c in item.get("content", []):
            if c.get("text", "").strip():
                print(c["text"].strip())
    print()

def cmd_update_task(args):
    """PUT /v1/tasks/{task_id} — update task metadata."""
    body = {}
    if getattr(args, "title", None):
        body["title"] = args.title
    if not body:
        print(f"{YELLOW}Nothing to update. Use --title <new_title>{RESET}"); return
    # Try multiple field formats the API might accept
    data = api("PUT", f"/tasks/{args.id}", body)
    if data is None:
        # Retry with nested metadata format
        data = api("PUT", f"/tasks/{args.id}", {"metadata": {"task_title": args.title}})
    if data:
        print(f"{GREEN}Updated task: {args.id}{RESET}")
    else:
        print(f"{RED}Failed to update task. The API may not support this field.{RESET}")

def cmd_delete(args):
    data = api("DELETE", f"/tasks/{args.id}")
    if data and data.get("deleted"):
        print(f"{GREEN}Deleted: {args.id}{RESET}")
    else:
        print(f"{RED}Failed to delete: {args.id}{RESET}")

# ── Files: Create / List / Get / Delete ───────────────────────────────────────

def _upload_file(filepath):
    if not os.path.exists(filepath):
        print(f"{RED}File not found: {filepath}{RESET}"); return None
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    data = api("POST", "/files", {"filename": filename, "content": content, "encoding": "base64"})
    if not data: return None
    file_id = data.get("id")
    upload_url = data.get("upload_url")
    if upload_url:
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            s3 = requests.put(upload_url, data=f, headers={"Content-Type": mime})
        if s3.status_code not in (200, 204):
            print(f"{RED}S3 upload failed: {s3.status_code}{RESET}"); return None
    print(f"{GREEN}Uploaded: {filename}  (file_id: {file_id}){RESET}")
    return file_id

def cmd_upload(args):
    fid = _upload_file(args.filepath)
    if fid:
        print(f"Use this file_id in tasks: {BOLD}{fid}{RESET}")

def cmd_files(args):
    data = api("GET", "/files")
    files = data.get("data", []) if data else []
    if not files:
        print("No files uploaded yet."); return
    print(f"\n{BOLD}{'ID':<40} {'Filename':<25}{RESET}")
    print("-" * 65)
    for f in files:
        fid = f.get("id", str(f)) if isinstance(f, dict) else str(f)
        name = f.get("filename", "") if isinstance(f, dict) else ""
        print(f"{fid:<40} {name}")

def cmd_file_get(args):
    """GET /v1/files/{file_id} — get single file details."""
    data = api("GET", f"/files/{args.id}")
    if not data: return
    print(f"\n{BOLD}File Details{RESET}")
    print(f"{'-' * 40}")
    for k, v in data.items():
        print(f"  {k}: {v}")

def cmd_file_delete(args):
    """DELETE /v1/files/{file_id} — delete a file."""
    data = api("DELETE", f"/files/{args.id}")
    if data:
        print(f"{GREEN}Deleted file: {args.id}{RESET}")
    else:
        print(f"{RED}Failed to delete file: {args.id}{RESET}")

# ── Projects: Create / List ──────────────────────────────────────────────────

def cmd_projects(args):
    data = api("GET", "/projects")
    projects = data.get("data", []) if data else []
    if not projects:
        print("No projects found."); return
    print(f"\n{BOLD}{'ID':<30} {'Name':<25} Instructions{RESET}")
    print("-" * 75)
    for p in projects:
        if isinstance(p, dict):
            pid = p.get("id", "")
            name = p.get("name", "")
            inst = (p.get("instructions", "") or "")[:30]
            print(f"{pid:<30} {name:<25} {DIM}{inst}{RESET}")
        else:
            print(f"  {p}")

def cmd_project_create(args):
    """POST /v1/projects — create a new project."""
    body = {"name": args.name}
    if getattr(args, "instructions", None):
        body["instructions"] = args.instructions
    data = api("POST", "/projects", body)
    if data:
        pid = data.get("id", data.get("project_id", ""))
        print(f"{GREEN}Project created: {pid}{RESET}")
        print(f"  Name: {args.name}")
        if getattr(args, "instructions", None):
            print(f"  Instructions: {args.instructions[:60]}")

# ── Webhooks: Create / List / Delete (local store since API has no GET) ───────

WEBHOOKS_FILE = os.path.join(os.path.expanduser("~"), ".manus", "webhooks.json")

def _load_webhooks():
    try:
        with open(WEBHOOKS_FILE, "r") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save_webhooks(hooks):
    os.makedirs(os.path.dirname(WEBHOOKS_FILE), exist_ok=True)
    with open(WEBHOOKS_FILE, "w") as f:
        f.write(json.dumps(hooks, indent=2))

def cmd_webhook_create(args):
    """POST /v1/webhooks — register a webhook for task notifications."""
    body = {"url": args.webhook_url}
    if getattr(args, "events", None):
        body["events"] = args.events.split(",")
    data = api("POST", "/webhooks", body)
    if data:
        wid = data.get("id", data.get("webhook_id", ""))
        secret = data.get("secret", "")
        events = args.events.split(",") if getattr(args, "events", None) else []
        print(f"{GREEN}Webhook created: {wid}{RESET}")
        print(f"  URL: {args.webhook_url}")
        if events:
            print(f"  Events: {', '.join(events)}")
        if secret:
            print(f"  Secret: {BOLD}{secret}{RESET}")
            print(f"  {YELLOW}Save this secret — it won't be shown again.{RESET}")
        # Save locally for listing
        hooks = _load_webhooks()
        hooks.append({
            "id": wid,
            "url": args.webhook_url,
            "events": events,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        _save_webhooks(hooks)

def cmd_webhook_delete(args):
    """DELETE /v1/webhooks/{webhook_id} — remove a webhook."""
    data = api("DELETE", f"/webhooks/{args.id}")
    if data:
        print(f"{GREEN}Deleted webhook: {args.id}{RESET}")
        # Remove from local store
        hooks = _load_webhooks()
        hooks = [h for h in hooks if h.get("id") != args.id]
        _save_webhooks(hooks)
    else:
        print(f"{RED}Failed to delete webhook: {args.id}{RESET}")

def cmd_webhooks(args):
    """List webhooks from local store."""
    hooks = _load_webhooks()
    if not hooks:
        print("No webhooks registered. Use webhook-create to add one."); return
    print(f"\n{BOLD}{'ID':<30} {'URL':<35} {'Events':<25} Created{RESET}")
    print("-" * 95)
    for h in hooks:
        hid = h.get("id", "")
        url = h.get("url", "")
        events = ", ".join(h.get("events", [])) or "all"
        created = h.get("created_at", "")
        print(f"{hid:<30} {url:<35} {DIM}{events:<25}{RESET} {DIM}{created}{RESET}")

# ── Safety Engine ─────────────────────────────────────────────────────────────

SAFE_COMMANDS = {
    "ls", "dir", "cat", "type", "head", "tail", "pwd", "cd", "echo", "whoami",
    "hostname", "date", "which", "where", "git status", "git log", "git diff",
    "git branch", "python --version", "python3 --version", "node --version",
    "npm --version", "nvidia-smi", "systeminfo", "uname", "lscpu", "free",
    "df", "du", "wmic", "tasklist", "ps", "env", "set", "printenv",
}

DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf ~", "del /s /q C:\\", "format ", "mkfs",
    "sudo rm", ":(){:|:&};:", "dd if=", "shutdown", "reboot",
    "reg delete", "net stop", "net user", "> /dev/sda",
]

def classify_risk(command):
    cmd_lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in cmd_lower:
            return "dangerous"
    for safe in SAFE_COMMANDS:
        if cmd_lower.startswith(safe):
            return "safe"
    if any(kw in cmd_lower for kw in ["rm ", "del ", "kill ", "taskkill", "sudo ", "pip install",
                                        "npm install", "chmod", "chown", "mv ", "cp ", "mkdir"]):
        return "moderate"
    return "moderate"

def request_approval(command, risk):
    if SAFETY_LEVEL == "unrestricted":
        audit_log(command, risk, "auto-approved")
        return True
    if SAFETY_LEVEL == "allowlist" and risk == "safe":
        audit_log(command, risk, "auto-approved")
        return True
    color = {
        "safe": GREEN, "moderate": YELLOW, "dangerous": RED
    }.get(risk, RESET)
    print(f"\n{color}[{risk.upper()}]{RESET} Execute: {BOLD}{command}{RESET}")
    if risk == "dangerous":
        print(f"{RED}  ⚠ This command is potentially destructive!{RESET}")
    try:
        answer = input(f"  Approve? [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nDenied."); return False
    approved = answer in ("y", "yes")
    audit_log(command, risk, "approved" if approved else "denied")
    return approved

def audit_log(command, risk, decision):
    try:
        log_dir = os.path.dirname(AUDIT_LOG)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{ts} | {decision.upper():<13} | {risk:<9} | {command}\n")
    except Exception:
        pass

# ── Local Execution ──────────────────────────────────────────────────────────

def local_exec(command, cwd=None, timeout=120):
    """Execute a shell command locally with safety approval."""
    risk = classify_risk(command)
    if not request_approval(command, risk):
        print(f"{YELLOW}Command skipped.{RESET}")
        return None
    shell_cmd = command
    try:
        proc = subprocess.Popen(
            shell_cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        output_lines = []
        for line in proc.stdout:
            print(f"  {line}", end="")
            output_lines.append(line)
        proc.wait(timeout=timeout)
        rc = proc.returncode
        if rc != 0:
            print(f"{YELLOW}Exit code: {rc}{RESET}")
        return "".join(output_lines)
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"{RED}Command timed out after {timeout}s{RESET}")
        return None
    except Exception as e:
        print(f"{RED}Execution error: {e}{RESET}")
        return None

def cmd_exec(args):
    command = args.command
    cwd = getattr(args, "cwd", None)
    timeout = int(getattr(args, "timeout", 120) or 120)
    print(f"{BLUE}[LOCAL]{RESET} Executing: {BOLD}{command}{RESET}")
    local_exec(command, cwd=cwd, timeout=timeout)

def cmd_local_file_read(args):
    path = args.path
    if not os.path.exists(path):
        print(f"{RED}File not found: {path}{RESET}"); return
    print(f"{BLUE}[LOCAL]{RESET} Reading: {path}")
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read()
        print(content)
    except PermissionError:
        print(f"{RED}Permission denied: {path}{RESET}")
    except Exception as e:
        print(f"{RED}Error reading file: {e}{RESET}")

def cmd_local_file_write(args):
    path = args.path
    content = args.content
    if not request_approval(f"Write file: {path}", "moderate"):
        return
    print(f"{BLUE}[LOCAL]{RESET} Writing: {path}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"{GREEN}Written: {path}{RESET}")

def cmd_local_file_list(args):
    directory = getattr(args, "directory", ".") or "."
    pattern = getattr(args, "pattern", "*") or "*"
    if not os.path.isdir(directory):
        print(f"{RED}Not a directory: {directory}{RESET}"); return
    print(f"{BLUE}[LOCAL]{RESET} Listing: {directory}  (pattern: {pattern})")
    matches = globmod.glob(os.path.join(directory, pattern))
    for m in sorted(matches):
        is_dir = os.path.isdir(m)
        size = os.path.getsize(m) if not is_dir else ""
        name = os.path.basename(m) + ("/" if is_dir else "")
        print(f"  {name:<40} {DIM}{size}{RESET}")
    print(f"{DIM}{len(matches)} items{RESET}")

def cmd_local_python(args):
    code = args.code
    is_file = os.path.exists(code) and code.endswith(".py")
    if is_file:
        cmd = f'python "{code}"'
    else:
        # Escape for shell: write to temp file to avoid quote issues
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".")
        tmp.write(code)
        tmp.close()
        cmd = f'python "{tmp.name}"'
    print(f"{BLUE}[LOCAL]{RESET} Running Python: {BOLD}{code[:60]}{RESET}")
    local_exec(cmd)
    if not is_file:
        try: os.unlink(tmp.name)
        except Exception: pass

def cmd_local_shell(args):
    """Natural-language task: send to cloud for planning, execute locally."""
    task_desc = " ".join(args.task) if isinstance(args.task, list) else args.task
    if not task_desc:
        print(f"{RED}Usage: manus local shell \"<task>\"{RESET}"); return

    print(f"{MAGENTA}[HYBRID]{RESET} Sending to Manus for planning...")
    platform_info = "Windows 11" if IS_WINDOWS else "Linux/Mac"
    planning_prompt = (
        f"Break this task into numbered shell commands for a {platform_info} machine. "
        f"Output ONLY the commands, one per line, prefixed with CMD: \n\n"
        f"Task: {task_desc}"
    )
    resp = task_create(planning_prompt, mode="chat")
    if not resp: return
    task_id = resp.get("task_id")
    print(f"{DIM}Planning task: {task_id}{RESET}")
    result = stream_task(task_id)
    if not result: return

    # Extract CMD: lines from output
    commands = []
    for item in result.get("output", []):
        if item.get("role") != "assistant": continue
        for c in item.get("content", []):
            text = c.get("text", "")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("CMD:"):
                    commands.append(line[4:].strip())

    if not commands:
        print(f"{YELLOW}No executable commands found in Manus response.{RESET}")
        return

    print(f"\n{BOLD}Plan ({len(commands)} commands):{RESET}")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")

    try:
        answer = input(f"\n{CYAN}Execute all? [y/N/select]: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted."); return

    if answer in ("y", "yes"):
        for i, cmd in enumerate(commands, 1):
            print(f"\n{BLUE}[{i}/{len(commands)}]{RESET} {cmd}")
            output = local_exec(cmd)
            if output is None:
                try:
                    cont = input(f"{YELLOW}Continue? [y/N]: {RESET}").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    break
                if cont not in ("y", "yes"):
                    break
    elif answer == "select":
        for i, cmd in enumerate(commands, 1):
            try:
                pick = input(f"  Run #{i} ({cmd})? [y/N]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if pick in ("y", "yes"):
                local_exec(cmd)
    else:
        print("Aborted.")

# ── Desktop Control ──────────────────────────────────────────────────────────

def cmd_desktop_apps(args):
    """List running applications/processes."""
    print(f"{MAGENTA}[DESKTOP]{RESET} Running applications:")
    if IS_WINDOWS:
        local_exec('tasklist /FO TABLE /NH | findstr /V "svchost csrss conhost"')
    else:
        local_exec("ps aux --sort=-%mem | head -25")

def cmd_desktop_launch(args):
    """Launch an application."""
    app = args.app
    print(f"{MAGENTA}[DESKTOP]{RESET} Launching: {app}")
    if IS_WINDOWS:
        local_exec(f'start "" "{app}"')
    elif sys.platform == "darwin":
        local_exec(f'open "{app}"')
    else:
        local_exec(f'xdg-open "{app}" &')

def cmd_desktop_kill(args):
    """Kill a process."""
    target = args.process
    print(f"{MAGENTA}[DESKTOP]{RESET} Killing: {target}")
    if IS_WINDOWS:
        if target.isdigit():
            local_exec(f"taskkill /PID {target} /F")
        else:
            local_exec(f"taskkill /IM {target} /F")
    else:
        if target.isdigit():
            local_exec(f"kill -9 {target}")
        else:
            local_exec(f"pkill -f {target}")

def cmd_desktop_gpu(args):
    """Show GPU information."""
    print(f"{MAGENTA}[DESKTOP]{RESET} GPU Information:")
    result = local_exec("nvidia-smi")
    if result is not None and result.strip() == "":
        # nvidia-smi ran but returned nothing useful, try fallback
        print(f"{YELLOW}nvidia-smi returned empty. Trying alternatives...{RESET}")
        if IS_WINDOWS:
            local_exec('wmic path win32_VideoController get Name,AdapterRAM,DriverVersion /format:list')
        else:
            local_exec("lspci | grep -i vga")

def cmd_desktop_gpu_run(args):
    """Run a GPU-accelerated command."""
    command = args.command
    print(f"{MAGENTA}[DESKTOP]{RESET} GPU Run: {command}")
    local_exec(command)

def cmd_desktop_sysinfo(args):
    """Show system information."""
    print(f"{MAGENTA}[DESKTOP]{RESET} System Information:")
    if IS_WINDOWS:
        local_exec("systeminfo | findstr /B /C:\"OS\" /C:\"System\" /C:\"Total Physical\" /C:\"Processor\"")
    else:
        local_exec("uname -a && echo '---' && lscpu | head -15 && echo '---' && free -h && echo '---' && df -h /")

def cmd_desktop_screenshot(args):
    """Take a screenshot."""
    output = getattr(args, "output", None) or os.path.join(os.path.expanduser("~"), "Desktop", "screenshot.png")
    print(f"{MAGENTA}[DESKTOP]{RESET} Taking screenshot → {output}")
    if IS_WINDOWS:
        # Use PowerShell to capture screen via encoded command to avoid quote issues
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms;"
            f"Add-Type -AssemblyName System.Drawing;"
            f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            f"$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height);"
            f"$graphics = [System.Drawing.Graphics]::FromImage($bitmap);"
            f"$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size);"
            f"$bitmap.Save('{output}');"
            f"Write-Host 'Screenshot saved: {output}'"
        )
        import base64 as b64enc
        encoded = b64enc.b64encode(ps_script.encode("utf-16-le")).decode()
        local_exec(f"powershell -EncodedCommand {encoded}")
    elif sys.platform == "darwin":
        local_exec(f'screencapture "{output}"')
    else:
        local_exec(f'import -window root "{output}" 2>/dev/null || scrot "{output}"')

# ── Chat REPL ────────────────────────────────────────────────────────────────

def cmd_chat(args):
    model = getattr(args, "model", DEFAULT_MODEL)
    mode = getattr(args, "mode", "agent")
    wait = not getattr(args, "no_wait", False)
    project = getattr(args, "project", None)

    print(f"\n{BOLD}  Manus AI Chat{RESET}  {DIM}model={model} mode={mode}{RESET}")
    print(f"  {DIM}Commands: /tasks /files /upload <path> /url <url> /delete <id>")
    print(f"           /task <id> /projects /webhooks /sysinfo /exec <cmd>")
    print(f"           /help /exit{RESET}\n")

    pending = []
    last_task_id = None

    while True:
        try:
            prompt = input(f"{CYAN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!"); break

        if not prompt: continue

        if prompt in ("/exit", "/quit", "exit", "quit"):
            print("Goodbye!"); break
        elif prompt == "/tasks":
            cmd_tasks(argparse.Namespace(limit=20)); continue
        elif prompt == "/files":
            cmd_files(argparse.Namespace()); continue
        elif prompt == "/projects":
            cmd_projects(argparse.Namespace()); continue
        elif prompt == "/webhooks":
            cmd_webhooks(argparse.Namespace()); continue
        elif prompt == "/sysinfo":
            cmd_desktop_sysinfo(argparse.Namespace()); continue
        elif prompt == "/help":
            cmd_help(None); continue
        elif prompt.startswith("/upload "):
            path = prompt.split(" ", 1)[1].strip().strip('"')
            fid = _upload_file(path)
            if fid:
                pending.append({"file_id": fid})
                print(f"{DIM}File queued. Type your prompt to attach it.{RESET}")
            continue
        elif prompt.startswith("/url "):
            url = prompt.split(" ", 1)[1].strip()
            pending.append({"url": url})
            print(f"{DIM}URL queued. Type your prompt to attach it.{RESET}")
            continue
        elif prompt.startswith("/delete "):
            cmd_delete(argparse.Namespace(id=prompt.split(" ", 1)[1].strip())); continue
        elif prompt.startswith("/task "):
            cmd_task(argparse.Namespace(id=prompt.split(" ", 1)[1].strip())); continue
        elif prompt.startswith("/exec "):
            cmd = prompt.split(" ", 1)[1].strip()
            local_exec(cmd)
            continue

        attachments = pending.copy() if pending else None
        pending.clear()

        task = task_create(prompt, mode, model, attachments, task_id=last_task_id, project_id=project)
        if not task: continue
        task_id = task.get("task_id")
        last_task_id = task_id
        task_url = task.get("task_url", "")
        print(f"{DIM}Task: {task_id}  {task_url}{RESET}")
        if wait:
            result = stream_task(task_id)
            if result: task_print_header(result)
        print()

# ── Help ──────────────────────────────────────────────────────────────────────

def cmd_help(_args=None):
    print(f"""
{BOLD}Manus AI CLI — Cloud + Local + Desktop{RESET}

{BOLD}Cloud Tasks:{RESET}
  manus send "<prompt>"                     Send a task
    --mode agent|chat|adaptive              Execution mode (default: agent)
    --model manus-1.6                       Model selection
    --no-wait                               Fire-and-forget
    --file <file_id>                        Attach uploaded file
    --url <url>                             Attach URL
    --thread <task_id>                      Continue existing thread
    --project <project_id>                  Assign to project

{BOLD}Task Management:{RESET}
  manus tasks [--limit N]                   List tasks (default: 20)
  manus task <id>                           View task output
  manus update-task <id> --title <title>    Update task metadata
  manus delete <id>                         Delete a task

{BOLD}Files:{RESET}
  manus files                               List uploaded files
  manus file <id>                           Get file details
  manus upload <filepath>                   Upload a file
  manus file-delete <id>                    Delete a file

{BOLD}Projects:{RESET}
  manus projects                            List projects
  manus project-create <name>               Create a project
    --instructions "<text>"                 Default instructions

{BOLD}Webhooks:{RESET}
  manus webhooks                            List webhooks
  manus webhook-create <url>                Register webhook
    --events "task.completed,task.failed"   Event filter
  manus webhook-delete <id>                 Remove webhook

{BOLD}Local Execution:{RESET}
  manus exec "<command>"                    Run shell command locally
    --cwd <path>                            Working directory
    --timeout <seconds>                     Timeout (default: 120)
  manus file-read <path>                    Read a local file
  manus file-write <path> "<content>"       Write a local file
  manus file-list [directory] [--pattern]   List directory contents
  manus run-python "<code_or_file>"         Run Python locally

{BOLD}Desktop Control:{RESET}
  manus desktop-apps                        List running apps
  manus desktop-launch "<app>"              Launch application
  manus desktop-kill <process|pid>          Kill a process
  manus desktop-gpu                         Show GPU info
  manus desktop-gpu-run "<command>"         Run GPU command
  manus desktop-sysinfo                     System information
  manus desktop-screenshot [--output path]  Take screenshot

{BOLD}Hybrid Mode:{RESET}
  manus hybrid "<task>"                     Cloud plans, local executes

{BOLD}Interactive Chat:{RESET}
  manus chat [--mode] [--model] [--project]
  {DIM}In-chat: /tasks /files /upload /url /delete /task /projects
           /webhooks /sysinfo /exec <cmd> /help /exit{RESET}

{BOLD}Safety Levels:{RESET} Set MANUS_SAFETY_LEVEL in .env
  prompt       Ask approval for every local command (default)
  allowlist    Auto-approve safe commands, prompt for others
  unrestricted Auto-approve all (with audit logging)
""")

# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="manus", description="Manus AI CLI — Cloud + Local + Desktop")
    sub = p.add_subparsers(dest="cmd")

    # ── Cloud: send
    s = sub.add_parser("send", help="Send a task to Manus")
    s.add_argument("prompt")
    s.add_argument("--mode", default="agent", choices=["agent", "chat", "adaptive"])
    s.add_argument("--model", default=DEFAULT_MODEL)
    s.add_argument("--no-wait", action="store_true")
    s.add_argument("--file", help="file_id to attach")
    s.add_argument("--url", help="URL to attach")
    s.add_argument("--thread", help="Continue existing task thread")
    s.add_argument("--project", help="Project ID to assign task to")

    # ── Cloud: chat
    c = sub.add_parser("chat", help="Interactive chat with Manus")
    c.add_argument("--mode", default="agent", choices=["agent", "chat", "adaptive"])
    c.add_argument("--model", default=DEFAULT_MODEL)
    c.add_argument("--no-wait", action="store_true")
    c.add_argument("--project", help="Project ID for all chat tasks")

    # ── Tasks
    tl = sub.add_parser("tasks", help="List tasks")
    tl.add_argument("--limit", type=int, default=20)
    tk = sub.add_parser("task", help="View task output"); tk.add_argument("id")
    ut = sub.add_parser("update-task", help="Update task metadata"); ut.add_argument("id"); ut.add_argument("--title")
    dl = sub.add_parser("delete", help="Delete a task"); dl.add_argument("id")

    # ── Files
    sub.add_parser("files", help="List uploaded files")
    fg = sub.add_parser("file", help="Get file details"); fg.add_argument("id")
    ul = sub.add_parser("upload", help="Upload a file"); ul.add_argument("filepath")
    fd = sub.add_parser("file-delete", help="Delete a file"); fd.add_argument("id")

    # ── Projects
    sub.add_parser("projects", help="List projects")
    pc = sub.add_parser("project-create", help="Create a project")
    pc.add_argument("name")
    pc.add_argument("--instructions", help="Default project instructions")

    # ── Webhooks
    sub.add_parser("webhooks", help="List webhooks")
    wc = sub.add_parser("webhook-create", help="Create a webhook")
    wc.add_argument("webhook_url", help="Webhook endpoint URL")
    wc.add_argument("--events", help="Comma-separated events: task.completed,task.failed")
    wd = sub.add_parser("webhook-delete", help="Delete a webhook"); wd.add_argument("id")

    # ── Local execution
    ex = sub.add_parser("exec", help="Execute shell command locally")
    ex.add_argument("command")
    ex.add_argument("--cwd", help="Working directory")
    ex.add_argument("--timeout", type=int, default=120)

    fr = sub.add_parser("file-read", help="Read a local file"); fr.add_argument("path")
    fw = sub.add_parser("file-write", help="Write a local file"); fw.add_argument("path"); fw.add_argument("content")
    fl = sub.add_parser("file-list", help="List directory"); fl.add_argument("directory", nargs="?", default=".")
    fl.add_argument("--pattern", default="*")
    rp = sub.add_parser("run-python", help="Run Python locally"); rp.add_argument("code")

    # ── Desktop
    sub.add_parser("desktop-apps", help="List running apps")
    dla = sub.add_parser("desktop-launch", help="Launch app"); dla.add_argument("app")
    dk = sub.add_parser("desktop-kill", help="Kill process"); dk.add_argument("process")
    sub.add_parser("desktop-gpu", help="GPU info")
    dgr = sub.add_parser("desktop-gpu-run", help="Run GPU command"); dgr.add_argument("command")
    sub.add_parser("desktop-sysinfo", help="System info")
    dss = sub.add_parser("desktop-screenshot", help="Take screenshot")
    dss.add_argument("--output", help="Output path")

    # ── Hybrid
    hy = sub.add_parser("hybrid", help="Cloud plans, local executes")
    hy.add_argument("task", nargs="+")

    # ── Help
    sub.add_parser("help", help="Show help")

    args = p.parse_args()

    if args.cmd is None:
        if len(sys.argv) > 1:
            cmd_send(argparse.Namespace(
                prompt=" ".join(sys.argv[1:]),
                mode="agent", model=DEFAULT_MODEL, no_wait=False,
                file=None, url=None, thread=None, project=None
            ))
        else:
            p.print_help()
        return

    dispatch = {
        "send":              cmd_send,
        "chat":              cmd_chat,
        "tasks":             cmd_tasks,
        "task":              cmd_task,
        "update-task":       cmd_update_task,
        "delete":            cmd_delete,
        "files":             cmd_files,
        "file":              cmd_file_get,
        "upload":            cmd_upload,
        "file-delete":       cmd_file_delete,
        "projects":          cmd_projects,
        "project-create":    cmd_project_create,
        "webhooks":          cmd_webhooks,
        "webhook-create":    cmd_webhook_create,
        "webhook-delete":    cmd_webhook_delete,
        "exec":              cmd_exec,
        "file-read":         cmd_local_file_read,
        "file-write":        cmd_local_file_write,
        "file-list":         cmd_local_file_list,
        "run-python":        cmd_local_python,
        "desktop-apps":      cmd_desktop_apps,
        "desktop-launch":    cmd_desktop_launch,
        "desktop-kill":      cmd_desktop_kill,
        "desktop-gpu":       cmd_desktop_gpu,
        "desktop-gpu-run":   cmd_desktop_gpu_run,
        "desktop-sysinfo":   cmd_desktop_sysinfo,
        "desktop-screenshot": cmd_desktop_screenshot,
        "hybrid":            lambda a: cmd_local_shell(a),
        "help":              cmd_help,
    }
    dispatch[args.cmd](args)

if __name__ == "__main__":
    main()
