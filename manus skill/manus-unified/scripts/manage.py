#!/usr/bin/env python3
"""
manage.py — Manage Manus tasks, files, and projects.
Usage:
  python manage.py tasks
  python manage.py task <id>
  python manage.py delete <id>
  python manage.py files
  python manage.py upload <filepath>
  python manage.py projects
"""
import os, sys, base64, argparse, mimetypes
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

BASE_URL = "https://api.manus.ai/v1"

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

# ── Tasks ──────────────────────────────────────────────────────────────────────

def cmd_tasks():
    data = api("GET", "/tasks?limit=20")
    tasks = data.get("data", []) if data else []
    if not tasks: print("No tasks found."); return
    print(f"\n{'ID':<25} {'Status':<12} {'Created':<14} Title")
    print("-" * 75)
    for t in tasks:
        print(f"{t.get('id',''):<25} {t.get('status',''):<12} "
              f"{fmt_time(t.get('created_at','0')):<14} "
              f"{t.get('metadata',{}).get('task_title','')[:35]}")

def cmd_task(task_id):
    task = api("GET", f"/tasks/{task_id}")
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

def cmd_delete(task_id):
    data = api("DELETE", f"/tasks/{task_id}")
    if data and data.get("deleted"):
        print(f"Deleted: {task_id}")
    else:
        print(f"Failed to delete: {task_id}")

# ── Files ──────────────────────────────────────────────────────────────────────

def cmd_files():
    data = api("GET", "/files")
    files = data.get("data", []) if data else []
    if not files: print("No files uploaded yet."); return
    print(f"\n{'ID':<35} Name")
    print("-" * 60)
    for f in files:
        fid  = f.get("id", str(f)) if isinstance(f, dict) else str(f)
        name = f.get("filename", "") if isinstance(f, dict) else ""
        print(f"{fid:<35} {name}")

def cmd_upload(filepath):
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

# ── Projects ───────────────────────────────────────────────────────────────────

def cmd_projects():
    data = api("GET", "/projects")
    projects = data.get("data", []) if data else []
    if not projects: print("No projects found."); return
    print("\nProjects:")
    for p in projects: print(f"  {p}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("tasks")
    t = sub.add_parser("task"); t.add_argument("id")
    d = sub.add_parser("delete"); d.add_argument("id")
    sub.add_parser("files")
    u = sub.add_parser("upload"); u.add_argument("filepath")
    sub.add_parser("projects")
    args = p.parse_args()

    if   args.cmd == "tasks":    cmd_tasks()
    elif args.cmd == "task":     cmd_task(args.id)
    elif args.cmd == "delete":   cmd_delete(args.id)
    elif args.cmd == "files":    cmd_files()
    elif args.cmd == "upload":   cmd_upload(args.filepath)
    elif args.cmd == "projects": cmd_projects()
    else: p.print_help()

if __name__ == "__main__":
    main()
