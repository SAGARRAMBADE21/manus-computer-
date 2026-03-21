#!/usr/bin/env python3
"""
Manus AI Terminal CLI
Commands: chat | tasks | task <id> | delete <id> | projects | files | upload | help
"""

import os
import sys
import time
import base64
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://api.manus.ai/v1"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
DIM   = "\033[2m"
RESET = "\033[0m"


# -- auth -----------------------------------------------------------------------

def headers() -> dict:
    key = os.environ.get("MANUS_API_KEY")
    if not key:
        print(f"{RED}Error: MANUS_API_KEY not set. Add it to your .env file.{RESET}")
        sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}


# -- api calls ------------------------------------------------------------------

def api(method: str, path: str, body: dict = None) -> dict | None:
    try:
        r = requests.request(method, BASE_URL + path, json=body, headers=headers(), timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        print(f"{RED}API Error {r.status_code}: {r.text[:200]}{RESET}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection error. Check your internet.{RESET}")
        return None


def create_task(prompt: str, model: str = "manus-1.6", mode: str = "agent",
                attachments: list = None) -> dict | None:
    body = {"prompt": prompt, "agent_profile": model, "task_mode": mode}
    if attachments:
        body["attachments"] = attachments
    return api("POST", "/tasks", body)


def get_task(task_id: str) -> dict | None:
    return api("GET", f"/tasks/{task_id}")


def list_tasks(limit: int = 20) -> list:
    data = api("GET", f"/tasks?limit={limit}")
    return data.get("data", []) if data else []


def delete_task(task_id: str) -> bool:
    data = api("DELETE", f"/tasks/{task_id}")
    return bool(data and data.get("deleted"))


def list_projects() -> list:
    data = api("GET", "/projects")
    return data.get("data", []) if data else []


def list_files() -> list:
    data = api("GET", "/files")
    return data.get("data", []) if data else []


def upload_file(filepath: str) -> str | None:
    """Upload a local file to Manus. Returns file_id."""
    if not os.path.exists(filepath):
        print(f"{RED}File not found: {filepath}{RESET}")
        return None

    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    # Step 1: Register file with Manus
    data = api("POST", "/files", {"filename": filename, "content": content, "encoding": "base64"})
    if not data:
        return None

    file_id    = data.get("id")
    upload_url = data.get("upload_url")

    # Step 2: Upload actual bytes to S3
    if upload_url:
        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            s3 = requests.put(upload_url, data=f, headers={"Content-Type": mime}, timeout=60)
        if s3.status_code not in (200, 204):
            print(f"{RED}S3 upload failed: {s3.status_code}{RESET}")
            return None

    print(f"{GREEN}Uploaded: {filename}  (id: {file_id}){RESET}")
    return file_id


# -- display --------------------------------------------------------------------

def fmt_time(ts: str) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%b %d %H:%M")
    except Exception:
        return ts


def status_color(status: str) -> str:
    colors = {"completed": GREEN, "running": CYAN, "failed": RED, "cancelled": DIM}
    return colors.get(status, RESET) + status + RESET


def print_task_output(task: dict) -> None:
    status = task.get("status", "?")
    url    = task.get("metadata", {}).get("task_url", "")
    title  = task.get("metadata", {}).get("task_title", "")
    model  = task.get("model", "")

    print(f"\n{BOLD}{'-'*55}{RESET}")
    if title:
        print(f"{BOLD}{title}{RESET}")
    print(f"Status : {status_color(status)}  |  Model: {DIM}{model}{RESET}")
    if url:
        print(f"URL    : {DIM}{url}{RESET}")
    print(f"{'-'*55}{RESET}")

    for item in task.get("output", []):
        if item.get("role") != "assistant":
            continue
        for content in item.get("content", []):
            text = content.get("text", "").strip()
            if text:
                print(f"\n{text}")
    print()


def wait_for_task(task_id: str, poll: int = 5) -> dict | None:
    print(f"Waiting ", end="", flush=True)
    while True:
        task = get_task(task_id)
        if not task:
            return None
        status = task.get("status", "")
        print(f".", end="", flush=True)
        if status in ("completed", "failed", "cancelled"):
            print(f" {status_color(status)}")
            return task
        time.sleep(poll)


# -- commands -------------------------------------------------------------------

def cmd_chat(model: str, mode: str, wait: bool) -> None:
    print(f"\n{BOLD}  Manus AI Terminal{RESET}  {DIM}model={model} mode={mode}{RESET}")
    print(f"  {DIM}Commands: /tasks /files /upload <path> /delete <id> /help /exit{RESET}\n")

    pending_files: list[str] = []   # file_ids queued for next prompt

    while True:
        try:
            prompt = input(f"{CYAN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not prompt:
            continue

        # ── inline commands ──────────────────────────────────────────────────
        if prompt in ("/exit", "/quit", "exit", "quit"):
            print("Goodbye!")
            break

        elif prompt == "/tasks":
            cmd_tasks(); continue

        elif prompt == "/files":
            cmd_files(); continue

        elif prompt == "/projects":
            cmd_projects(); continue

        elif prompt == "/help":
            cmd_help(); continue

        elif prompt.startswith("/upload "):
            path = prompt.split(" ", 1)[1].strip().strip('"')
            fid = upload_file(path)
            if fid:
                pending_files.append(fid)
                print(f"{DIM}File queued. Type your prompt and it will be attached.{RESET}")
            continue

        elif prompt.startswith("/delete "):
            tid = prompt.split(" ", 1)[1].strip()
            cmd_delete(tid); continue

        elif prompt.startswith("/task "):
            tid = prompt.split(" ", 1)[1].strip()
            task = get_task(tid)
            if task:
                print_task_output(task)
            continue

        elif prompt.startswith("/url "):
            # attach a URL to next prompt: /url https://example.com
            url = prompt.split(" ", 1)[1].strip()
            pending_files.append({"url": url})
            print(f"{DIM}URL queued. Type your prompt and it will be attached.{RESET}")
            continue

        # ── build attachments ────────────────────────────────────────────────
        attachments = None
        if pending_files:
            attachments = []
            for item in pending_files:
                if isinstance(item, dict):
                    attachments.append(item)          # URL attachment
                else:
                    attachments.append({"file_id": item})  # file_id attachment
            pending_files.clear()

        # ── send task ────────────────────────────────────────────────────────
        task = create_task(prompt, model, mode, attachments)
        if not task:
            continue

        task_id  = task.get("task_id")
        task_url = task.get("task_url", "")
        print(f"{DIM}Task: {task_id}  {task_url}{RESET}")

        if wait:
            result = wait_for_task(task_id)
            if result:
                print_task_output(result)
        print()


def cmd_tasks() -> None:
    tasks = list_tasks()
    if not tasks:
        print("No tasks found.")
        return
    print(f"\n{BOLD}{'ID':<25} {'Status':<12} {'Created':<14} Title{RESET}")
    print("-" * 75)
    for t in tasks:
        tid    = t.get("id", "?")
        status = t.get("status", "?")
        ts     = fmt_time(t.get("created_at", "0"))
        title  = t.get("metadata", {}).get("task_title", "")[:30]
        color  = {"completed": GREEN, "running": CYAN, "failed": RED}.get(status, RESET)
        print(f"{tid:<25} {color}{status:<12}{RESET} {DIM}{ts:<14}{RESET} {title}")
    print()


def cmd_files() -> None:
    files = list_files()
    if not files:
        print("No files uploaded yet.")
        return
    print(f"\n{BOLD}{'ID':<35} {'Name'}{RESET}")
    print("-" * 60)
    for f in files:
        fid  = f.get("id", "?") if isinstance(f, dict) else str(f)
        name = f.get("filename", "") if isinstance(f, dict) else ""
        print(f"{fid:<35} {name}")
    print()


def cmd_projects() -> None:
    projects = list_projects()
    if not projects:
        print("No projects found.")
        return
    print(f"\n{BOLD}Projects:{RESET}")
    for p in projects:
        print(f"  {p}")
    print()


def cmd_delete(task_id: str) -> None:
    ok = delete_task(task_id)
    if ok:
        print(f"{GREEN}Deleted task {task_id}{RESET}")
    else:
        print(f"{RED}Failed to delete {task_id}{RESET}")


def cmd_upload(filepath: str) -> None:
    fid = upload_file(filepath)
    if fid:
        print(f"Use this file_id in tasks: {BOLD}{fid}{RESET}")


def cmd_help() -> None:
    print(f"""
{BOLD}Manus AI Terminal — Help{RESET}

{BOLD}Startup:{RESET}
  python manus_cli.py                     Interactive chat (default)
  python manus_cli.py --mode chat         Faster chat mode (no full agent)
  python manus_cli.py --no-wait           Fire and forget (don't wait for result)
  python manus_cli.py --tasks             List all past tasks
  python manus_cli.py --task <id>         Show a specific task result
  python manus_cli.py --delete <id>       Delete a task
  python manus_cli.py --upload <file>     Upload a file
  python manus_cli.py --files             List uploaded files
  python manus_cli.py --projects          List projects

{BOLD}In-chat commands:{RESET}
  /tasks                 List all past tasks
  /task <id>             Show a specific task result
  /delete <id>           Delete a task
  /upload <path>         Upload a file, then type prompt to send it
  /url <https://...>     Attach a URL, then type prompt to send it
  /files                 List uploaded files
  /projects              List projects
  /help                  Show this help
  /exit                  Quit

{BOLD}What works via API:{RESET}
  Tasks (create/list/view/delete)     YES
  File upload & attach to task        YES
  URL attach to task                  YES
  Projects                            YES (listing)
  Browser / Computer control          NO  (web UI only)
  Connectors (My Browser etc.)        NO  (not in API yet)
""")


# -- main -----------------------------------------------------------------------

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Manus AI Terminal CLI", add_help=False)
    p.add_argument("--model",    default="manus-1.6", help="Agent model profile")
    p.add_argument("--mode",     default="agent",      help="Task mode: agent | chat | adaptive")
    p.add_argument("--no-wait",  action="store_true",  help="Don't wait for task result")
    p.add_argument("--tasks",    action="store_true",  help="List all tasks")
    p.add_argument("--task",     metavar="ID",         help="Show a specific task")
    p.add_argument("--delete",   metavar="ID",         help="Delete a task")
    p.add_argument("--upload",   metavar="FILE",       help="Upload a file")
    p.add_argument("--projects", action="store_true",  help="List projects")
    p.add_argument("--files",    action="store_true",  help="List uploaded files")
    p.add_argument("--help","-h",action="store_true",  help="Show help")
    args = p.parse_args()

    if args.help:       cmd_help()
    elif args.tasks:    cmd_tasks()
    elif args.task:
        task = get_task(args.task)
        if task: print_task_output(task)
    elif args.delete:   cmd_delete(args.delete)
    elif args.upload:   cmd_upload(args.upload)
    elif args.projects: cmd_projects()
    elif args.files:    cmd_files()
    else:               cmd_chat(model=args.model, mode=args.mode, wait=not args.no_wait)


if __name__ == "__main__":
    main()
