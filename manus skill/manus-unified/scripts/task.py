#!/usr/bin/env python3
"""
task.py — Create a Manus task and wait for the result.
Usage:
  python task.py "<prompt>"
  python task.py "<prompt>" --mode chat
  python task.py "<prompt>" --no-wait
  python task.py "<prompt>" --file <file_id>
  python task.py "<prompt>" --url <url>
"""
import os, sys, time, argparse
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

BASE_URL = "https://api.manus.ai/v1"

def headers():
    key = os.environ.get("MANUS_API_KEY", "")
    if not key:
        print("Error: MANUS_API_KEY not set in .env"); sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}

def create(prompt, mode="agent", attachments=None):
    body = {"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": mode}
    if attachments:
        body["attachments"] = attachments
    r = requests.post(f"{BASE_URL}/tasks", json=body, headers=headers(), timeout=30)
    if r.status_code not in (200, 201):
        print(f"Error {r.status_code}: {r.text[:200]}"); sys.exit(1)
    return r.json()

def poll(task_id):
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

def print_output(task):
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

def main():
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--mode", default="agent", help="agent | chat | adaptive")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--file", help="file_id to attach")
    p.add_argument("--url", help="URL to attach")
    args = p.parse_args()

    attachments = []
    if args.file: attachments.append({"file_id": args.file})
    if args.url:  attachments.append({"url": args.url})

    resp = create(args.prompt, args.mode, attachments or None)
    task_id = resp.get("task_id")
    task_url = resp.get("task_url", "")
    print(f"Task: {task_id}  {task_url}")

    if not args.no_wait:
        task = poll(task_id)
        if task: print_output(task)

if __name__ == "__main__":
    main()
