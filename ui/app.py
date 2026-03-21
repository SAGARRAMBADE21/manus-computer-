"""
Manus Local Agent — Web UI Server
Run: python ui/app.py
"""

import os
import sys
import re
import uuid
import subprocess
import base64
import mimetypes
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests as http

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
BASE_URL = "https://api.manus.ai/v1"

# In-memory store for pending command steps
pending_steps: dict[str, dict] = {}
task_history: list[dict] = []


# ── Manus API ──────────────────────────────────────────────────────────────────

def manus_headers():
    key = os.environ.get("MANUS_API_KEY", "")
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}


def manus_ask(prompt: str) -> str:
    r = http.post(f"{BASE_URL}/tasks",
        json={"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": "chat"},
        headers=manus_headers(), timeout=30)
    if r.status_code != 200:
        return ""
    task_id = r.json().get("task_id", "")
    task_url = r.json().get("task_url", "")

    # Poll for result
    for _ in range(120):
        time.sleep(3)
        try:
            r2 = http.get(f"{BASE_URL}/tasks/{task_id}", headers=manus_headers(), timeout=20)
        except http.exceptions.ConnectionError:
            continue  # network blip — retry
        if r2.status_code != 200:
            break
        task = r2.json()
        if task.get("status") in ("completed", "failed", "cancelled"):
            # Store in history
            title = task.get("metadata", {}).get("task_title", prompt[:40])
            task_history.insert(0, {"title": title, "id": task_id, "url": task_url})
            return extract_text(task)

    return ""


def extract_text(task: dict) -> str:
    parts = []
    for item in task.get("output", []):
        if item.get("role") != "assistant":
            continue
        for c in item.get("content", []):
            t = c.get("text", "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts)


# ── Command extraction ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """IMPORTANT: You are a COMMAND GENERATOR for a Windows machine.
You do NOT execute commands yourself — a local app will execute them.

RULES:
1. NEVER say "I have done X" or assume commands ran
2. Always provide commands in ```cmd``` blocks (one block per response)
3. Python code goes in ```python``` blocks
4. Do NOT show fake output or example results

Current working directory: {cwd}
OS: Windows CMD

Respond with a brief explanation then the commands in a code block."""


def extract_commands(text: str) -> list[dict]:
    commands = []
    pattern = r"```(cmd|shell|bash|powershell|python|ps1)\n(.*?)```"
    for m in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
        lang = m.group(1).lower()
        code = m.group(2).strip()
        if not code:
            continue
        lines = [l for l in code.splitlines() if l.strip()]
        looks_like_output = lang != "python" and all(
            not any(kw in l.lower() for kw in [
                "mkdir", "echo", "copy", "move", "del", "rmdir",
                "pip", "python", "cd ", "dir", "type", "set ",
                "import ", "def ", "print(", "open(", "with ",
                "git ", "npm ", "node ", "curl", "wget", "powershell",
                "xcopy", "robocopy", "ren ", "attrib", "tasklist",
                "systeminfo", "ipconfig", "netstat", "ping",
            ])
            for l in lines
        )
        if looks_like_output:
            continue
        ctype = "python" if lang == "python" else "shell"
        commands.append({"type": ctype, "code": code})
    return commands


def strip_explanation(text: str) -> str:
    """Return only the non-code explanation part."""
    return re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL).strip()


# ── Local executor ─────────────────────────────────────────────────────────────

def run_shell(cmd: str) -> tuple[str, bool]:
    lines = [l.strip() for l in cmd.splitlines() if l.strip() and not l.strip().startswith("#")]
    outputs = []
    has_error = False
    for line in lines:
        try:
            result = subprocess.run(
                line, shell=True, capture_output=True, text=True,
                timeout=60, cwd=os.getcwd()
            )
            out = (result.stdout + result.stderr).strip()
            outputs.append(f"> {line}\n{out}" if out else f"> {line}\n(ok)")
            if result.returncode != 0:
                has_error = True
        except subprocess.TimeoutExpired:
            outputs.append(f"> {line}\nError: timed out"); has_error = True
        except Exception as e:
            outputs.append(f"> {line}\nError: {e}"); has_error = True
    return "\n".join(outputs), has_error


def run_python(code: str) -> tuple[str, bool]:
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "manus_ui_script.py"
    tmp.write_text(code, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(tmp)],
            capture_output=True, text=True, timeout=120, cwd=os.getcwd()
        )
        out = (result.stdout + result.stderr).strip()
        return out or "(no output)", result.returncode != 0
    except subprocess.TimeoutExpired:
        return "Error: timed out", True
    except Exception as e:
        return f"Error: {e}", True


def execute_cmd(cmd: dict) -> tuple[str, bool]:
    if cmd["type"] == "python":
        return run_python(cmd["code"])
    return run_shell(cmd["code"])


# ── Flask routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cwd")
def api_cwd():
    return jsonify({"cwd": os.getcwd()})


@app.route("/api/task", methods=["POST"])
def api_task():
    data = request.json
    task = data.get("task", "").strip()
    if not task:
        return jsonify({"error": "Empty task"})

    cwd = os.getcwd()
    prompt = f"{SYSTEM_PROMPT.format(cwd=cwd)}\n\nTask: {task}\n\nDirectory listing:\n{local_ls(cwd)}"

    response_text = manus_ask(prompt)
    if not response_text:
        return jsonify({"error": "No response from Manus API"})

    commands = extract_commands(response_text)
    explanation = strip_explanation(response_text)

    if not commands:
        return jsonify({"type": "done", "text": explanation or response_text})

    # Store step for approval
    step_id = str(uuid.uuid4())[:8]
    pending_steps[step_id] = {
        "commands": commands,
        "original_task": task,
        "executed": [],
    }

    return jsonify({
        "type": "plan",
        "text": explanation,
        "commands": commands,
        "step_id": step_id,
    })


@app.route("/api/approve", methods=["POST"])
def api_approve():
    data = request.json
    step_id  = data.get("step_id")
    cmd_index = data.get("cmd_index", 0)
    action   = data.get("action", "approve")  # approve | skip | always

    step = pending_steps.get(step_id)
    if not step:
        return jsonify({"error": "Step not found"})

    cmd = step["commands"][cmd_index]
    output = ""
    is_error = False

    if action in ("approve", "always"):
        output, is_error = execute_cmd(cmd)
        step["executed"].append({"cmd": cmd, "output": output, "error": is_error})
    else:
        output = "[skipped]"
        step["executed"].append({"cmd": cmd, "output": output, "error": False})

    # Check if there are more commands in this step
    next_cmd_index = cmd_index + 1
    if next_cmd_index < len(step["commands"]):
        return jsonify({
            "output": output,
            "error": is_error,
            "next": {
                "type": "plan",
                "text": "",
                "commands": [step["commands"][next_cmd_index]],
                "step_id": step_id,
                "cmd_offset": next_cmd_index,
            }
        })

    # All commands in step done — ask Manus for next step
    cwd = os.getcwd()
    executed_summary = "\n\n".join(
        f"Command: {e['cmd']['code']}\nOutput: {e['output']}"
        for e in step["executed"]
    )

    follow_up = (
        f"Previous step outputs:\n{executed_summary}\n\n"
        f"Current directory: {cwd}\n"
        f"Directory listing:\n{local_ls(cwd)}\n\n"
        f"Original task: {step['original_task']}\n\n"
        "Continue with the next step, or say 'Task complete' if everything is done."
    )

    next_response = manus_ask(follow_up)
    if not next_response:
        return jsonify({"output": output, "error": is_error, "next": {"type": "done", "text": "Done."}})

    next_commands = extract_commands(next_response)
    next_explanation = strip_explanation(next_response)

    is_done = not next_commands or any(
        kw in next_response.lower()
        for kw in ["task complete", "task is complete", "all done", "done!", "completed successfully", "no more steps"]
    )

    if is_done:
        del pending_steps[step_id]
        return jsonify({
            "output": output,
            "error": is_error,
            "next": {"type": "done", "text": next_explanation or next_response}
        })

    new_step_id = str(uuid.uuid4())[:8]
    pending_steps[new_step_id] = {
        "commands": next_commands,
        "original_task": step["original_task"],
        "executed": [],
    }

    return jsonify({
        "output": output,
        "error": is_error,
        "next": {
            "type": "plan",
            "text": next_explanation,
            "commands": next_commands,
            "step_id": new_step_id,
        }
    })


@app.route("/api/files")
def api_files():
    cwd = os.getcwd()
    try:
        items = []
        for p in sorted(Path(cwd).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            items.append({
                "name": p.name,
                "path": str(p),
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return jsonify({"items": items, "cwd": cwd})
    except Exception as e:
        return jsonify({"items": [], "error": str(e)})


@app.route("/api/read", methods=["POST"])
def api_read():
    path = request.json.get("path", "")
    p = Path(path)
    if p.is_dir():
        return jsonify({"is_dir": True, "path": str(p)})
    try:
        content = p.read_text(encoding="utf-8", errors="replace")[:4000]
        return jsonify({"is_dir": False, "path": str(p), "content": content})
    except Exception as e:
        return jsonify({"is_dir": False, "path": str(p), "content": f"Error: {e}"})


@app.route("/api/cd", methods=["POST"])
def api_cd():
    path = request.json.get("path", "")
    try:
        os.chdir(path)
        return jsonify({"cwd": os.getcwd()})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/history")
def api_history():
    return jsonify({"tasks": task_history[:20]})


def local_ls(path: str = ".") -> str:
    try:
        items = list(Path(path).iterdir())
        lines = []
        for i in sorted(items, key=lambda x: (not x.is_dir(), x.name)):
            tag  = "[DIR]" if i.is_dir() else "     "
            size = i.stat().st_size if i.is_file() else 0
            lines.append(f"{tag} {i.name}  ({size} bytes)")
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    print("\n  Manus Local Agent UI")
    print("  Open: http://localhost:5000\n")
    app.run(debug=False, port=5000)
