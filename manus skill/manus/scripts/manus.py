#!/usr/bin/env python3
"""manus.py — Manus AI CLI: send tasks, manage resources, run local agent."""
import os, sys, re, time, base64, argparse, mimetypes, subprocess
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

BASE_URL     = "https://api.manus.ai/v1"
MAX_STEPS    = 10
SAFE_CMDS    = {"dir","ls","echo","type","cat","pwd","cd","python --version",
                "pip list","git status","git log","whoami","hostname"}
always_allow = False

# ── Auth ───────────────────────────────────────────────────────────────────────

def headers():
    key = os.environ.get("MANUS_API_KEY", "")
    if not key:
        print("Error: MANUS_API_KEY not set in .env"); sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}

def api(method, path, body=None):
    r = requests.request(method, BASE_URL + path, json=body, headers=headers(), timeout=30)
    if r.status_code in (200, 201): return r.json()
    print(f"Error {r.status_code}: {r.text[:200]}"); return None

def fmt_time(ts):
    try: return datetime.fromtimestamp(int(ts)).strftime("%b %d %H:%M")
    except: return ts

# ── Task ───────────────────────────────────────────────────────────────────────

def task_create(prompt, mode="agent", attachments=None):
    body = {"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": mode}
    if attachments:
        body["attachments"] = attachments
    r = requests.post(f"{BASE_URL}/tasks", json=body, headers=headers(), timeout=30)
    if r.status_code not in (200, 201):
        print(f"Error {r.status_code}: {r.text[:200]}"); sys.exit(1)
    return r.json()

def task_poll(task_id):
    print("Waiting ", end="", flush=True)
    while True:
        r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers(), timeout=30)
        if r.status_code != 200:
            print(f"\nError {r.status_code}"); return None
        task = r.json()
        print(".", end="", flush=True)
        if task.get("status") in ("completed", "failed", "cancelled"):
            print(f" {task['status']}")
            return task
        time.sleep(5)

def task_print(task):
    meta = task.get("metadata", {})
    print("\n" + "-" * 55)
    if meta.get("task_title"): print(meta["task_title"])
    print(f"Status : {task.get('status')}  |  Model: {task.get('model','')}")
    if meta.get("task_url"): print(f"URL    : {meta['task_url']}")
    print("-" * 55)
    for item in task.get("output", []):
        if item.get("role") != "assistant": continue
        for c in item.get("content", []):
            if c.get("text","").strip(): print(c["text"].strip())
    print()

def cmd_send(args):
    attachments = []
    if args.file: attachments.append({"file_id": args.file})
    if args.url:  attachments.append({"url": args.url})
    resp = task_create(args.prompt, args.mode, attachments or None)
    task_id  = resp.get("task_id")
    task_url = resp.get("task_url", "")
    print(f"Task: {task_id}  {task_url}")
    if not args.no_wait:
        task = task_poll(task_id)
        if task: task_print(task)

# ── Manage ─────────────────────────────────────────────────────────────────────

def cmd_tasks(args):
    data  = api("GET", "/tasks?limit=20")
    tasks = data.get("data", []) if data else []
    if not tasks: print("No tasks found."); return
    print(f"\n{'ID':<25} {'Status':<12} {'Created':<14} Title")
    print("-" * 75)
    for t in tasks:
        print(f"{t.get('id',''):<25} {t.get('status',''):<12} "
              f"{fmt_time(t.get('created_at','0')):<14} "
              f"{t.get('metadata',{}).get('task_title','')[:35]}")

def cmd_task(args):
    task = api("GET", f"/tasks/{args.id}")
    if not task: return
    meta = task.get("metadata", {})
    print("\n" + "-" * 55)
    if meta.get("task_title"): print(meta["task_title"])
    print(f"Status : {task.get('status')}  |  Model: {task.get('model','')}")
    if meta.get("task_url"): print(f"URL    : {meta['task_url']}")
    print("-" * 55)
    for item in task.get("output", []):
        if item.get("role") != "assistant": continue
        for c in item.get("content", []):
            if c.get("text","").strip(): print(c["text"].strip())
    print()

def cmd_delete(args):
    data = api("DELETE", f"/tasks/{args.id}")
    if data and data.get("deleted"):
        print(f"Deleted: {args.id}")
    else:
        print(f"Failed to delete: {args.id}")

def cmd_files(args):
    data  = api("GET", "/files")
    files = data.get("data", []) if data else []
    if not files: print("No files uploaded yet."); return
    print(f"\n{'ID':<35} Name")
    print("-" * 60)
    for f in files:
        fid  = f.get("id", str(f)) if isinstance(f, dict) else str(f)
        name = f.get("filename", "") if isinstance(f, dict) else ""
        print(f"{fid:<35} {name}")

def cmd_upload(args):
    filepath = args.filepath
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}"); return
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    data = api("POST", "/files", {"filename": filename, "content": content, "encoding": "base64"})
    if not data: return
    file_id    = data.get("id")
    upload_url = data.get("upload_url")
    if upload_url:
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            s3 = requests.put(upload_url, data=f, headers={"Content-Type": mime}, timeout=60)
        if s3.status_code not in (200, 204):
            print(f"S3 upload failed: {s3.status_code}"); return
    print(f"Uploaded: {filename}  (file_id: {file_id})")

def cmd_projects(args):
    data     = api("GET", "/projects")
    projects = data.get("data", []) if data else []
    if not projects: print("No projects found."); return
    print("\nProjects:")
    for p in projects: print(f"  {p}")

# ── Local agent ────────────────────────────────────────────────────────────────

def agent_poll(task_id):
    print("Thinking", end="", flush=True)
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers(), timeout=20)
            if r.status_code != 200: print(); return ""
            task = r.json()
            print(".", end="", flush=True)
            if task.get("status") in ("completed", "failed", "cancelled"):
                print(f" {task['status']}")
                return "\n".join(
                    c.get("text","").strip()
                    for item in task.get("output",[]) if item.get("role")=="assistant"
                    for c in item.get("content",[]) if c.get("text","").strip()
                )
        except requests.exceptions.ConnectionError:
            print("\nNetwork blip, retrying...", end="", flush=True)
        time.sleep(4)

def ask_manus(prompt):
    r = requests.post(f"{BASE_URL}/tasks",
        json={"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": "chat"},
        headers=headers(), timeout=30)
    if r.status_code != 200:
        print(f"Manus API error: {r.text[:200]}"); return ""
    data     = r.json()
    task_url = data.get("task_url","")
    if task_url: print(f"  {task_url}")
    return agent_poll(data.get("task_id",""))

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
    if is_safe(detail): print("  [auto-approved]"); return True
    print(f"\n  Approval required -- {label}: {detail[:200]}")
    print("  [y] Yes  [a] Always  [n] Skip  [q] Quit ", end="")
    try: ans = input().strip().lower()
    except (KeyboardInterrupt, EOFError): return False
    if ans == "a": always_allow = True; return True
    if ans == "q": sys.exit(0)
    return ans in ("y","yes","")

def run_shell(cmd):
    lines = [l.strip() for l in cmd.splitlines() if l.strip() and not l.strip().startswith("#")]
    out = []
    for line in lines:
        print(f"  > {line}")
        try:
            r = subprocess.run(line, shell=True, capture_output=True, text=True,
                               timeout=60, cwd=os.getcwd())
            o = (r.stdout + r.stderr).strip()
            if o: print(f"  {o[:500]}")
            out.append(f"> {line}\n{o}" if o else f"> {line}\n(ok)")
        except subprocess.TimeoutExpired: out.append(f"> {line}\nError: timed out")
        except Exception as e:            out.append(f"> {line}\nError: {e}")
    return "\n".join(out)

def run_python(code):
    tmp = Path(os.environ.get("TEMP","/tmp")) / "manus_script.py"
    tmp.write_text(code, encoding="utf-8")
    print(f"  [python] {tmp}")
    try:
        r = subprocess.run([sys.executable, str(tmp)], capture_output=True,
                           text=True, timeout=120, cwd=os.getcwd())
        o = (r.stdout + r.stderr).strip()
        if o: print(f"  {o[:1000]}")
        return o or "(no output)"
    except subprocess.TimeoutExpired: return "Error: script timed out"
    except Exception as e:            return f"Error: {e}"

def write_file(path, content):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  Written: {path}"); return f"File written: {path}"

def local_ls(path="."):
    try:
        lines = []
        for i in Path(path).iterdir():
            tag  = "[DIR]" if i.is_dir() else "     "
            size = i.stat().st_size if i.is_file() else 0
            lines.append(f"{tag} {i.name}  ({size} bytes)")
        return "\n".join(lines) or "(empty)"
    except Exception as e: return f"Error: {e}"

SYSTEM = """You are a COMMAND GENERATOR for a Windows machine. You do NOT execute commands yourself.
RULES:
1. NEVER say "I have done X" -- you cannot execute anything
2. ALWAYS provide commands in ```cmd``` blocks
3. No fake output -- wait for real results
4. One ```cmd``` block per response
FORMAT: Shell -> ```cmd```, Python -> ```python```, OS: Windows CMD, CWD: {cwd}"""

def agent_loop(task):
    cwd = os.getcwd()
    print(f"\nManus Local Agent  cwd={cwd}\nTask: {task}\n")
    prompt = f"Task: {task}\nCWD: {cwd}\nDirectory:\n{local_ls(cwd)}\n\n{SYSTEM.format(cwd=cwd)}"
    for step in range(1, MAX_STEPS + 1):
        print(f"\n-- Step {step} --")
        response = ask_manus(prompt)
        if not response: print("No response from Manus."); break
        print(f"\nManus:\n{response}\n")
        if any(kw in response.lower() for kw in
               ["task complete","done!","finished","all done","completed successfully",
                "no more steps","task is complete"]):
            print("Task completed!"); break
        commands = extract_commands(response)
        if not commands: break
        outputs = []
        for cmd in commands:
            if cmd["type"] == "shell":
                if approve("Shell", cmd["code"]):
                    outputs.append(f"$ {cmd['code']}\n{run_shell(cmd['code'])}")
                else: outputs.append(f"$ {cmd['code']}\n[skipped]")
            elif cmd["type"] == "python":
                if approve("Python", cmd["code"][:100]):
                    outputs.append(f"[python]\n{run_python(cmd['code'])}")
                else: outputs.append("[python skipped]")
            elif cmd["type"] == "file":
                if approve("Write file", cmd["path"]):
                    outputs.append(write_file(cmd["path"], cmd["content"]))
                else: outputs.append(f"File write skipped: {cmd['path']}")
        prompt = (f"Previous outputs:\n" + "\n\n".join(outputs) +
                  f"\n\nCWD: {os.getcwd()}\nDirectory:\n{local_ls()}\n\n"
                  "Continue or say 'Task complete' if done.")
    else:
        print(f"Reached max steps ({MAX_STEPS}). Run again to continue.")

def interactive():
    print("\n  Manus Local Agent -- Interactive")
    print("  Built-ins: ls [path] | read <file> | cd <dir> | run <cmd> | exit\n")
    while True:
        try: inp = input("Task> ").strip()
        except (KeyboardInterrupt, EOFError): print("\nGoodbye!"); break
        if not inp: continue
        if inp in ("exit","quit"): print("Goodbye!"); break
        elif inp.startswith(("ls","dir")):
            path = inp.split(" ",1)[1].strip() if " " in inp else "."
            print(local_ls(path))
        elif inp.startswith("read "):
            try: print(Path(inp[5:].strip()).read_text(encoding="utf-8",errors="replace")[:3000])
            except Exception as e: print(f"Error: {e}")
        elif inp.startswith("cd "):
            try: os.chdir(inp[3:].strip()); print(f"cwd: {os.getcwd()}")
            except Exception as e: print(f"Error: {e}")
        elif inp.startswith("run "):
            if approve("Shell", inp[4:].strip()): run_shell(inp[4:].strip())
        else: agent_loop(inp)

def cmd_local(args):
    global always_allow
    if args.yes: always_allow = True; print("Warning: auto-approving all commands")
    if args.cwd: os.chdir(args.cwd)
    if args.task: agent_loop(" ".join(args.task))
    else: interactive()

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="manus", description="Manus AI CLI")
    sub = p.add_subparsers(dest="cmd")

    # send task (default)
    s = sub.add_parser("send", help="Send a task to Manus")
    s.add_argument("prompt")
    s.add_argument("--mode", default="agent", choices=["agent","chat","adaptive"])
    s.add_argument("--no-wait", action="store_true")
    s.add_argument("--file", help="file_id to attach")
    s.add_argument("--url",  help="URL to attach")

    # manage
    sub.add_parser("tasks",    help="List last 20 tasks")
    tk = sub.add_parser("task",   help="View task output")
    tk.add_argument("id")
    dl = sub.add_parser("delete", help="Delete a task")
    dl.add_argument("id")
    sub.add_parser("files",    help="List uploaded files")
    ul = sub.add_parser("upload",  help="Upload a file")
    ul.add_argument("filepath")
    sub.add_parser("projects", help="List projects")

    # local agent
    la = sub.add_parser("local", help="Run local machine agent")
    la.add_argument("task", nargs="*")
    la.add_argument("--yes", "-y", action="store_true", help="Auto-approve all commands")
    la.add_argument("--cwd", help="Working directory")

    args = p.parse_args()

    # default: treat bare args as a prompt if no subcommand given
    if args.cmd is None:
        if len(sys.argv) > 1:
            s_args = argparse.Namespace(
                prompt=" ".join(sys.argv[1:]),
                mode="agent", no_wait=False, file=None, url=None
            )
            cmd_send(s_args)
        else:
            p.print_help()
        return

    dispatch = {
        "send":     cmd_send,
        "tasks":    cmd_tasks,
        "task":     cmd_task,
        "delete":   cmd_delete,
        "files":    cmd_files,
        "upload":   cmd_upload,
        "projects": cmd_projects,
        "local":    cmd_local,
    }
    dispatch[args.cmd](args)

if __name__ == "__main__":
    main()
