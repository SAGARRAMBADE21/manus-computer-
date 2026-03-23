#!/usr/bin/env python3
"""manus.py — Manus AI CLI: send tasks, manage resources, run local agent."""
import os, sys, re, time, base64, argparse, mimetypes, subprocess
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

# Enable ANSI colors on Windows
if sys.platform == "win32":
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

BASE_URL     = "https://api.manus.ai/v1"
MAX_STEPS    = 10
SAFE_CMDS    = {"dir","ls","echo","type","cat","pwd","cd","python --version",
                "pip list","git status","git log","whoami","hostname"}
always_allow = False

BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# ── Auth ───────────────────────────────────────────────────────────────────────

def headers():
    key = os.environ.get("MANUS_API_KEY", "")
    if not key:
        print(f"{RED}Error: MANUS_API_KEY not set in .env{RESET}"); sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}

def api(method, path, body=None):
    try:
        r = requests.request(method, BASE_URL + path, json=body, headers=headers())
        if r.status_code in (200, 201): return r.json()
        print(f"{RED}Error {r.status_code}: {r.text[:200]}{RESET}"); return None
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}"); return None

def fmt_time(ts):
    try: return datetime.fromtimestamp(int(ts)).strftime("%b %d %H:%M")
    except: return ts

def status_color(status):
    colors = {"completed": GREEN, "running": CYAN, "failed": RED, "cancelled": DIM}
    return colors.get(status, RESET) + status + RESET

# ── Real-time streaming poll ───────────────────────────────────────────────────

def stream_task(task_id):
    """Poll every 1s and print output incrementally as it arrives."""
    shown = 0
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers())
            if r.status_code != 200:
                print(f"\n{RED}Error {r.status_code}{RESET}"); return None
            task = r.json()

            # collect all current assistant text
            current = ""
            for item in task.get("output", []):
                if item.get("role") != "assistant": continue
                for c in item.get("content", []):
                    current += c.get("text", "")

            # print only new text since last check
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
    print(f"\n{BOLD}{'-'*55}{RESET}")
    if meta.get("task_title"): print(f"{BOLD}{meta['task_title']}{RESET}")
    print(f"Status : {status_color(task.get('status',''))}  |  Model: {DIM}{task.get('model','')}{RESET}")
    if meta.get("task_url"): print(f"URL    : {DIM}{meta['task_url']}{RESET}")
    print(f"{'-'*55}")

# ── Send ───────────────────────────────────────────────────────────────────────

def task_create(prompt, mode="agent", model="manus-1.6", attachments=None):
    body = {"prompt": prompt, "agent_profile": model, "task_mode": mode}
    if attachments:
        body["attachments"] = attachments
    try:
        r = requests.post(f"{BASE_URL}/tasks", json=body, headers=headers())
        if r.status_code not in (200, 201):
            print(f"{RED}Error {r.status_code}: {r.text[:200]}{RESET}"); sys.exit(1)
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}"); sys.exit(1)

def cmd_send(args):
    attachments = []
    if args.file: attachments.append({"file_id": args.file})
    if args.url:  attachments.append({"url": args.url})
    model = getattr(args, "model", "manus-1.6")
    resp = task_create(args.prompt, args.mode, model, attachments or None)
    task_id  = resp.get("task_id")
    task_url = resp.get("task_url", "")
    print(f"{DIM}Task: {task_id}  {task_url}{RESET}")
    if not args.no_wait:
        task = stream_task(task_id)
        if task: task_print_header(task)

# ── Chat REPL ──────────────────────────────────────────────────────────────────

def cmd_chat(args):
    model = getattr(args, "model", "manus-1.6")
    mode  = getattr(args, "mode",  "agent")
    wait  = not getattr(args, "no_wait", False)

    print(f"\n{BOLD}  Manus AI Chat{RESET}  {DIM}model={model} mode={mode}{RESET}")
    print(f"  {DIM}Commands: /tasks /files /upload <path> /url <url> /delete <id> /task <id> /projects /help /exit{RESET}\n")

    pending = []   # queued file_ids and URL attachments for next prompt

    while True:
        try:
            prompt = input(f"{CYAN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!"); break

        if not prompt: continue

        if prompt in ("/exit", "/quit", "exit", "quit"):
            print("Goodbye!"); break
        elif prompt == "/tasks":
            cmd_tasks(args); continue
        elif prompt == "/files":
            cmd_files(args); continue
        elif prompt == "/projects":
            cmd_projects(args); continue
        elif prompt == "/help":
            cmd_help(args); continue
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

        attachments = pending.copy() if pending else None
        pending.clear()

        task = task_create(prompt, mode, model, attachments)
        if not task: continue
        task_id  = task.get("task_id")
        task_url = task.get("task_url", "")
        print(f"{DIM}Task: {task_id}  {task_url}{RESET}")
        if wait:
            result = stream_task(task_id)
            if result: task_print_header(result)
        print()

# ── Manage ─────────────────────────────────────────────────────────────────────

def cmd_tasks(args):
    data  = api("GET", "/tasks?limit=20")
    tasks = data.get("data", []) if data else []
    if not tasks: print("No tasks found."); return
    print(f"\n{BOLD}{'ID':<25} {'Status':<12} {'Created':<14} Title{RESET}")
    print("-" * 75)
    for t in tasks:
        color = {"completed": GREEN, "running": CYAN, "failed": RED}.get(t.get("status",""), RESET)
        print(f"{t.get('id',''):<25} {color}{t.get('status',''):<12}{RESET} "
              f"{DIM}{fmt_time(t.get('created_at','0')):<14}{RESET} "
              f"{t.get('metadata',{}).get('task_title','')[:35]}")

def cmd_task(args):
    task = api("GET", f"/tasks/{args.id}")
    if not task: return
    meta = task.get("metadata", {})
    print(f"\n{BOLD}{'-'*55}{RESET}")
    if meta.get("task_title"): print(f"{BOLD}{meta['task_title']}{RESET}")
    print(f"Status : {status_color(task.get('status',''))}  |  Model: {DIM}{task.get('model','')}{RESET}")
    if meta.get("task_url"): print(f"URL    : {DIM}{meta['task_url']}{RESET}")
    print(f"{'-'*55}")
    for item in task.get("output", []):
        if item.get("role") != "assistant": continue
        for c in item.get("content", []):
            if c.get("text","").strip(): print(c["text"].strip())
    print()

def cmd_delete(args):
    data = api("DELETE", f"/tasks/{args.id}")
    if data and data.get("deleted"):
        print(f"{GREEN}Deleted: {args.id}{RESET}")
    else:
        print(f"{RED}Failed to delete: {args.id}{RESET}")

def cmd_files(args):
    data  = api("GET", "/files")
    files = data.get("data", []) if data else []
    if not files: print("No files uploaded yet."); return
    print(f"\n{BOLD}{'ID':<35} Name{RESET}")
    print("-" * 60)
    for f in files:
        fid  = f.get("id", str(f)) if isinstance(f, dict) else str(f)
        name = f.get("filename", "") if isinstance(f, dict) else ""
        print(f"{fid:<35} {name}")

def _upload_file(filepath):
    if not os.path.exists(filepath):
        print(f"{RED}File not found: {filepath}{RESET}"); return None
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    data = api("POST", "/files", {"filename": filename, "content": content, "encoding": "base64"})
    if not data: return None
    file_id    = data.get("id")
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

def cmd_projects(args):
    data     = api("GET", "/projects")
    projects = data.get("data", []) if data else []
    if not projects: print("No projects found."); return
    print(f"\n{BOLD}Projects:{RESET}")
    for p in projects: print(f"  {p}")

def cmd_help(_args=None):
    print(f"""
{BOLD}Manus AI CLI{RESET}

{BOLD}Send a task:{RESET}
  manus.py send "<prompt>"
  manus.py send "<prompt>" --mode agent|chat|adaptive
  manus.py send "<prompt>" --model manus-1.6
  manus.py send "<prompt>" --no-wait
  manus.py send "<prompt>" --file <file_id>
  manus.py send "<prompt>" --url <url>

{BOLD}Interactive chat:{RESET}
  manus.py chat
  manus.py chat --mode chat --no-wait

  {DIM}In-chat commands:{RESET}
  /tasks              List tasks
  /task <id>          View task output
  /delete <id>        Delete a task
  /upload <path>      Upload file (queued for next prompt)
  /url <url>          Attach URL (queued for next prompt)
  /files              List uploaded files
  /projects           List projects
  /help               Show this help
  /exit               Quit

{BOLD}Manage:{RESET}
  manus.py tasks                List last 20 tasks
  manus.py task <id>            View task output
  manus.py delete <id>          Delete a task
  manus.py files                List uploaded files
  manus.py upload <filepath>    Upload a file
  manus.py projects             List projects

{BOLD}Local agent:{RESET}
  manus.py local "<task>"
  manus.py local --yes "<task>"        Auto-approve all commands
  manus.py local --cwd <dir> "<task>"
  manus.py local                       Interactive shell
""")

# ── Local agent ────────────────────────────────────────────────────────────────

def agent_poll(task_id):
    print(f"{DIM}Thinking", end="", flush=True)
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers())
            if r.status_code != 200: print(RESET); return ""
            task = r.json()
            print(".", end="", flush=True)
            if task.get("status") in ("completed", "failed", "cancelled"):
                print(f" {task['status']}{RESET}")
                return "\n".join(
                    c.get("text","").strip()
                    for item in task.get("output",[]) if item.get("role")=="assistant"
                    for c in item.get("content",[]) if c.get("text","").strip()
                )
        except requests.exceptions.ConnectionError:
            print(f"\n{YELLOW}Network blip, retrying...{RESET}", end="", flush=True)
        time.sleep(4)

def ask_manus(prompt):
    try:
        r = requests.post(f"{BASE_URL}/tasks",
            json={"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": "chat"},
            headers=headers())
        if r.status_code != 200:
            print(f"{RED}Manus API error: {r.text[:200]}{RESET}"); return ""
        data     = r.json()
        task_url = data.get("task_url", "")
        if task_url: print(f"{DIM}  {task_url}{RESET}")
        return agent_poll(data.get("task_id", ""))
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}"); return ""

def extract_commands(text):
    cmds = []
    for m in re.finditer(r"```(cmd|shell|bash|powershell|python|ps1)\n(.*?)```",
                         text, re.DOTALL | re.IGNORECASE):
        lang, code = m.group(1).lower(), m.group(2).strip()
        if not code: continue
        lines = [l for l in code.splitlines() if l.strip()]
        if lang != "python" and all(
            not any(kw in l for kw in ["mkdir","echo","copy","move","del","pip","python",
                                        "cd ","dir","type","import ","def ","print(","open(",
                                        "git ","npm ","node "])
            for l in lines): continue
        cmds.append({"type": "python" if lang=="python" else "shell", "code": code})
    for m in re.finditer(r"\*\*(?:File|Write to|Save as)[:\s]+`?([^\*\n`]+)`?\*\*\n```[^\n]*\n(.*?)```",
                         text, re.DOTALL):
        cmds.append({"type":"file","path":m.group(1).strip(),"content":m.group(2)})
    return cmds

def is_safe(cmd):
    return (cmd.strip().split()[0].lower() if cmd.strip() else "") in SAFE_CMDS

def approve(label, detail):
    global always_allow
    if always_allow: return True
    if is_safe(detail): print(f"{DIM}  [auto-approved]{RESET}"); return True
    print(f"\n{YELLOW}{BOLD}  Approval required:{RESET}")
    print(f"  {label}: {BOLD}{detail[:200]}{RESET}")
    print(f"  {DIM}[y] Yes  [a] Always  [n] Skip  [q] Quit{RESET} ", end="")
    try: ans = input().strip().lower()
    except (KeyboardInterrupt, EOFError): return False
    if ans == "a": always_allow = True; return True
    if ans == "q": sys.exit(0)
    return ans in ("y","yes","")

def run_shell(cmd):
    lines = [l.strip() for l in cmd.splitlines() if l.strip() and not l.strip().startswith("#")]
    out = []
    for line in lines:
        print(f"{CYAN}  > {line}{RESET}")
        try:
            r = subprocess.run(line, shell=True, capture_output=True, text=True,
                               cwd=os.getcwd())
            o = (r.stdout + r.stderr).strip()
            if o: print(f"{DIM}{o[:500]}{RESET}")
            out.append(f"> {line}\nOutput:\n{o}" if o else f"> {line}\n(ok)")
        except Exception as e: out.append(f"> {line}\nError: {e}")
    return "\n".join(out)

def run_python(code):
    tmp = Path(os.environ.get("TEMP","/tmp")) / "manus_script.py"
    tmp.write_text(code, encoding="utf-8")
    print(f"{CYAN}  [python] {tmp}{RESET}")
    print(f"{DIM}{code[:400]}{RESET}")
    try:
        r = subprocess.run([sys.executable, str(tmp)], capture_output=True,
                           text=True, cwd=os.getcwd())
        o = (r.stdout + r.stderr).strip()
        if o: print(f"{DIM}{o[:1000]}{RESET}")
        return o or "(no output)"
    except Exception as e: return f"Error: {e}"

def write_file(path, content):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"{GREEN}  Written: {path}  ({len(content)} bytes){RESET}")
    return f"File written: {path}"

def local_ls(path="."):
    try:
        lines = []
        for i in Path(path).iterdir():
            tag  = "[DIR]" if i.is_dir() else "     "
            size = i.stat().st_size if i.is_file() else 0
            lines.append(f"{tag} {i.name}  ({size} bytes)")
        return "\n".join(lines) or "(empty)"
    except Exception as e: return f"Error: {e}"

SYSTEM = """IMPORTANT RULES - READ CAREFULLY:
You are a COMMAND GENERATOR for a Windows machine. You do NOT execute commands yourself.
A local CLI will execute your commands and send you the output.

RULES:
1. NEVER say "I have done X" or "I've created X" - you cannot do anything yourself
2. ALWAYS provide the actual commands to run in ```cmd``` blocks
3. ONLY output what needs to be executed - no fake output, no assumed results
4. Wait for real output before saying something is done
5. One ```cmd``` block per response with all commands for that step

FORMAT:
- Shell commands -> ```cmd\\n<commands>\\n```
- Python scripts -> ```python\\n<code>\\n```
- Write a file   -> use a cmd block: echo content > filename

Current working directory: {cwd}
OS: Windows CMD"""

def agent_loop(task):
    cwd = os.getcwd()
    print(f"\n{BOLD}Manus Local Agent{RESET}  {DIM}cwd={cwd}{RESET}")
    print(f"{DIM}Task: {task}{RESET}\n")
    prompt = "\n".join([
        f"Task: {task}",
        f"CWD: {cwd}",
        f"Directory listing:\n{local_ls(cwd)}",
        "",
        SYSTEM.format(cwd=cwd),
    ])
    for step in range(1, MAX_STEPS + 1):
        print(f"\n{BOLD}--- Step {step} ---{RESET}")
        response = ask_manus(prompt)
        if not response: print(f"{RED}No response from Manus.{RESET}"); break
        print(f"\n{BOLD}Manus:{RESET}\n{response}\n")
        if any(kw in response.lower() for kw in
               ["task complete","done!","finished","all done","completed successfully",
                "no more steps","task is complete"]):
            print(f"{GREEN}Task completed!{RESET}"); break
        commands = extract_commands(response)
        if not commands:
            print(f"{DIM}No commands found. Task may be complete.{RESET}"); break
        outputs = []
        for cmd in commands:
            if cmd["type"] == "shell":
                if approve("Shell command", cmd["code"]):
                    outputs.append(f"$ {cmd['code']}\nOutput:\n{run_shell(cmd['code'])}")
                else: outputs.append(f"$ {cmd['code']}\n[skipped]")
            elif cmd["type"] == "python":
                if approve("Python script", cmd["code"][:100] + "..."):
                    outputs.append(f"[python script]\nOutput:\n{run_python(cmd['code'])}")
                else: outputs.append("[python script skipped]")
            elif cmd["type"] == "file":
                if approve("Write file", cmd["path"]):
                    outputs.append(write_file(cmd["path"], cmd["content"]))
                else: outputs.append(f"File write skipped: {cmd['path']}")
        prompt = (f"Previous step outputs:\n" + "\n\n".join(outputs) +
                  f"\n\nCurrent directory: {os.getcwd()}\nDirectory listing:\n{local_ls()}\n\n"
                  "Continue with the next step, or say 'Task complete' if done.")
    else:
        print(f"{YELLOW}Reached max steps ({MAX_STEPS}). Run again to continue.{RESET}")

def interactive():
    print(f"\n{BOLD}  Manus Local Agent{RESET}")
    print(f"  {DIM}Controls your local machine. Type a task or a command.{RESET}")
    print(f"  {DIM}Built-ins: ls [path] | read <file> | cd <dir> | run <cmd> | exit{RESET}\n")
    while True:
        try: inp = input(f"{CYAN}Task>{RESET} ").strip()
        except (KeyboardInterrupt, EOFError): print("\nGoodbye!"); break
        if not inp: continue
        if inp in ("exit","quit"): print("Goodbye!"); break
        elif inp.startswith(("ls","dir")):
            path = inp.split(" ",1)[1].strip() if " " in inp else "."
            print(local_ls(path))
        elif inp.startswith("read "):
            try: print(Path(inp[5:].strip()).read_text(encoding="utf-8",errors="replace")[:3000])
            except Exception as e: print(f"{RED}Error: {e}{RESET}")
        elif inp.startswith("cd "):
            try: os.chdir(inp[3:].strip()); print(f"{GREEN}cwd: {os.getcwd()}{RESET}")
            except Exception as e: print(f"{RED}Error: {e}{RESET}")
        elif inp.startswith("run "):
            if approve("Shell command", inp[4:].strip()): run_shell(inp[4:].strip())
        else: agent_loop(inp)

def cmd_local(args):
    global always_allow
    if args.yes: always_allow = True; print(f"{YELLOW}Warning: auto-approving all commands{RESET}")
    if args.cwd: os.chdir(args.cwd)
    if args.task: agent_loop(" ".join(args.task))
    else: interactive()

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="manus", description="Manus AI CLI")
    sub = p.add_subparsers(dest="cmd")

    # send
    s = sub.add_parser("send", help="Send a task to Manus")
    s.add_argument("prompt")
    s.add_argument("--mode",    default="agent", choices=["agent","chat","adaptive"])
    s.add_argument("--model",   default="manus-1.6")
    s.add_argument("--no-wait", action="store_true")
    s.add_argument("--file",    help="file_id to attach")
    s.add_argument("--url",     help="URL to attach")

    # chat
    c = sub.add_parser("chat", help="Interactive chat with Manus")
    c.add_argument("--mode",    default="agent", choices=["agent","chat","adaptive"])
    c.add_argument("--model",   default="manus-1.6")
    c.add_argument("--no-wait", action="store_true")

    # manage
    sub.add_parser("tasks",    help="List last 20 tasks")
    tk = sub.add_parser("task",    help="View task output");  tk.add_argument("id")
    dl = sub.add_parser("delete",  help="Delete a task");     dl.add_argument("id")
    sub.add_parser("files",    help="List uploaded files")
    ul = sub.add_parser("upload",  help="Upload a file");     ul.add_argument("filepath")
    sub.add_parser("projects", help="List projects")
    sub.add_parser("help",     help="Show help")

    # local agent
    la = sub.add_parser("local", help="Run local machine agent")
    la.add_argument("task", nargs="*")
    la.add_argument("--yes", "-y", action="store_true")
    la.add_argument("--cwd", help="Working directory")

    args = p.parse_args()

    if args.cmd is None:
        if len(sys.argv) > 1:
            cmd_send(argparse.Namespace(
                prompt=" ".join(sys.argv[1:]),
                mode="agent", model="manus-1.6", no_wait=False, file=None, url=None
            ))
        else:
            p.print_help()
        return

    dispatch = {
        "send":     cmd_send,
        "chat":     cmd_chat,
        "tasks":    cmd_tasks,
        "task":     cmd_task,
        "delete":   cmd_delete,
        "files":    cmd_files,
        "upload":   cmd_upload,
        "projects": cmd_projects,
        "help":     cmd_help,
        "local":    cmd_local,
    }
    dispatch[args.cmd](args)

if __name__ == "__main__":
    main()
