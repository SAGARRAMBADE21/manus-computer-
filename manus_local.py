#!/usr/bin/env python3
"""
Manus Local Agent — Controls your local machine via Manus AI
- Manus plans the task
- CLI parses commands from the response
- You approve each command before it runs
- Output is sent back to Manus for next steps
"""

import os
import sys
import re
import subprocess
import shutil
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://api.manus.ai/v1"

BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
DIM   = "\033[2m"
RESET = "\033[0m"

# Commands always auto-approved (safe read-only ops)
SAFE_COMMANDS = {"dir", "ls", "echo", "type", "cat", "pwd", "cd", "python --version",
                 "pip list", "git status", "git log", "whoami", "hostname"}

always_allow = False   # set to True to skip all approvals


# ── Manus API ──────────────────────────────────────────────────────────────────

def manus_headers() -> dict:
    key = os.environ.get("MANUS_API_KEY")
    if not key:
        print(f"{RED}MANUS_API_KEY not set in .env{RESET}")
        sys.exit(1)
    return {"accept": "application/json", "content-type": "application/json", "API_KEY": key}


def manus_task(prompt: str) -> tuple[str, str]:
    """Create a Manus task. Returns (task_id, task_url)."""
    r = requests.post(f"{BASE_URL}/tasks",
        json={"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": "chat"},
        headers=manus_headers(), timeout=30)
    if r.status_code != 200:
        print(f"{RED}Manus API error: {r.text[:200]}{RESET}")
        return "", ""
    d = r.json()
    return d.get("task_id", ""), d.get("task_url", "")


def manus_wait(task_id: str, poll: int = 4) -> str:
    """Wait for task completion and return full assistant text output."""
    print(f"{DIM}Thinking", end="", flush=True)
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}",
                headers=manus_headers(), timeout=20)
            if r.status_code != 200:
                print()
                return ""
            task = r.json()
            status = task.get("status", "")
            print(".", end="", flush=True)
            if status in ("completed", "failed", "cancelled"):
                print(f" {status}{RESET}")
                return extract_text(task)
        except requests.exceptions.ConnectionError:
            print(f"\n{YELLOW}Network blip, retrying...{RESET}", end="", flush=True)
        time.sleep(poll)


def extract_text(task: dict) -> str:
    """Pull all assistant text from task output."""
    parts = []
    for item in task.get("output", []):
        if item.get("role") != "assistant":
            continue
        for c in item.get("content", []):
            t = c.get("text", "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts)


def ask_manus(prompt: str) -> str:
    """Send prompt to Manus and return response text."""
    tid, url = manus_task(prompt)
    if not tid:
        return ""
    if url:
        print(f"{DIM}  {url}{RESET}")
    return manus_wait(tid)


# ── Command parser ─────────────────────────────────────────────────────────────

def extract_commands(text: str) -> list[dict]:
    """
    Extract executable commands from Manus response.
    Only picks up tagged code blocks (cmd/shell/bash/powershell/python).
    Ignores untagged blocks (likely output examples).
    """
    commands = []

    # Only extract TAGGED code blocks — untagged are assumed to be output examples
    pattern = r"```(cmd|shell|bash|powershell|python|ps1)\n(.*?)```"
    for m in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
        lang = m.group(1).lower()
        code = m.group(2).strip()
        if not code:
            continue

        # Skip if it looks like output (has lines like "  file1.txt  file2.txt")
        lines = [l for l in code.splitlines() if l.strip()]
        looks_like_output = all(
            not any(kw in l for kw in ["mkdir", "echo", "copy", "move", "del",
                                        "pip", "python", "cd ", "dir", "type",
                                        "import ", "def ", "print(", "open(",
                                        "git ", "npm ", "node "])
            for l in lines
        )
        if looks_like_output and lang != "python":
            continue

        ctype = "python" if lang == "python" else "shell"
        commands.append({"type": ctype, "code": code})

    # File write pattern: **File: path** or **Write to: path**
    file_pattern = r"\*\*(?:File|Write to|Save as)[:\s]+`?([^\*\n`]+)`?\*\*\n```[^\n]*\n(.*?)```"
    for m in re.finditer(file_pattern, text, re.DOTALL):
        commands.append({"type": "file", "path": m.group(1).strip(), "content": m.group(2)})

    return commands


# ── Local executor ─────────────────────────────────────────────────────────────

def is_safe(cmd: str) -> bool:
    base = cmd.strip().split()[0].lower() if cmd.strip() else ""
    return base in SAFE_COMMANDS


def approve(label: str, detail: str) -> bool:
    """Ask user to approve an action."""
    global always_allow
    if always_allow:
        return True
    if is_safe(detail):
        print(f"{DIM}  [auto-approved: safe read]{RESET}")
        return True

    print(f"\n{YELLOW}{BOLD}  Approval required:{RESET}")
    print(f"  {label}: {BOLD}{detail[:200]}{RESET}")
    print(f"  {DIM}[y] Yes   [a] Always allow   [n] Skip   [q] Quit{RESET}", end=" ")
    try:
        ans = input().strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False

    if ans == "a":
        always_allow = True
        return True
    elif ans == "q":
        print("Aborted.")
        sys.exit(0)
    return ans in ("y", "yes", "")


def run_shell(cmd: str) -> str:
    """Run shell command(s) and return output. Handles multi-line blocks."""
    # Split multi-line into individual commands and join with &&
    lines = [l.strip() for l in cmd.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return "(empty)"

    all_output = []
    for line in lines:
        print(f"{CYAN}  > {line}{RESET}")
        try:
            result = subprocess.run(
                line, shell=True, capture_output=True, text=True, timeout=60,
                cwd=os.getcwd()
            )
            out = (result.stdout + result.stderr).strip()
            if out:
                print(f"{DIM}{out[:500]}{RESET}")
            all_output.append(f"> {line}\n{out}" if out else f"> {line}\n(ok)")
        except subprocess.TimeoutExpired:
            all_output.append(f"> {line}\nError: timed out")
        except Exception as e:
            all_output.append(f"> {line}\nError: {e}")

    return "\n".join(all_output)


def run_python(code: str) -> str:
    """Write code to temp file and run it."""
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "manus_script.py"
    tmp.write_text(code, encoding="utf-8")
    print(f"{CYAN}  [python] {tmp}{RESET}")
    print(f"{DIM}{code[:400]}{RESET}")
    try:
        result = subprocess.run(
            [sys.executable, str(tmp)],
            capture_output=True, text=True, timeout=120, cwd=os.getcwd()
        )
        out = (result.stdout + result.stderr).strip()
        if out:
            print(f"{DIM}{out[:1000]}{RESET}")
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: script timed out"
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a local file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"{GREEN}  Written: {path}  ({len(content)} bytes){RESET}")
    return f"File written: {path}"


def local_ls(path: str = ".") -> str:
    """List local directory."""
    try:
        items = list(Path(path).iterdir())
        lines = []
        for i in items:
            tag = "[DIR] " if i.is_dir() else "      "
            size = i.stat().st_size if i.is_file() else 0
            lines.append(f"{tag}{i.name}  ({size} bytes)")
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


def local_read(path: str) -> str:
    """Read a local file."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:3000]
    except Exception as e:
        return f"Error reading file: {e}"


# ── Agent loop ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """IMPORTANT RULES - READ CAREFULLY:
You are a COMMAND GENERATOR for a Windows machine. You do NOT execute commands yourself.
A local CLI will execute your commands and send you the output.

RULES:
1. NEVER say "I have done X" or "I've created X" - you cannot do anything yourself
2. ALWAYS provide the actual commands to run in ```cmd``` blocks
3. ONLY output what needs to be executed - no fake output, no assumed results
4. Wait for real output before saying something is done
5. One ```cmd``` block per response with all commands for that step

FORMAT:
- Shell commands → ```cmd\\n<commands>\\n```
- Python scripts → ```python\\n<code>\\n```
- Write a file → use a cmd block: echo content > filename

Current working directory: {cwd}
OS: Windows CMD

Example response format:
"I will create the folder and files. Here are the commands:"
```cmd
mkdir test_manus
echo Hello > test_manus\\file1.txt
dir test_manus
```
"""


def agent_loop(user_task: str) -> None:
    cwd = os.getcwd()
    print(f"\n{BOLD}Manus Local Agent{RESET}  {DIM}cwd={cwd}{RESET}")
    print(f"{DIM}Task: {user_task}{RESET}\n")

    # Build initial prompt with context
    context = [
        f"Task: {user_task}",
        f"CWD: {cwd}",
        f"Directory listing:\n{local_ls(cwd)}",
        "",
        SYSTEM_PROMPT.format(cwd=cwd),
    ]
    prompt = "\n".join(context)

    step = 0
    max_steps = 10

    while step < max_steps:
        step += 1
        print(f"\n{BOLD}--- Step {step} ---{RESET}")

        response = ask_manus(prompt)
        if not response:
            print(f"{RED}No response from Manus.{RESET}")
            break

        print(f"\n{BOLD}Manus:{RESET}\n{response}\n")

        # Check if task is done
        if any(kw in response.lower() for kw in
               ["task complete", "done!", "finished", "all done", "completed successfully",
                "no more steps", "task is complete"]):
            print(f"{GREEN}Task completed!{RESET}")
            break

        # Extract and execute commands
        commands = extract_commands(response)
        if not commands:
            # No commands found — task may be done or needs clarification
            print(f"{DIM}No commands to execute. Checking if task is done...{RESET}")
            break

        outputs = []
        for cmd in commands:
            ctype = cmd["type"]

            if ctype == "shell":
                code = cmd["code"]
                if approve("Shell command", code):
                    out = run_shell(code)
                    outputs.append(f"$ {code}\nOutput:\n{out}")
                else:
                    outputs.append(f"$ {code}\n[skipped by user]")

            elif ctype == "python":
                code = cmd["code"]
                if approve("Python script", code[:100] + "..."):
                    out = run_python(code)
                    outputs.append(f"[python script]\nOutput:\n{out}")
                else:
                    outputs.append("[python script skipped]")

            elif ctype == "file":
                path    = cmd["path"]
                content = cmd["content"]
                if approve("Write file", path):
                    out = write_file(path, content)
                    outputs.append(out)
                else:
                    outputs.append(f"File write skipped: {path}")

        # Build next prompt with outputs
        prompt = (
            f"Previous step outputs:\n"
            + "\n\n".join(outputs)
            + f"\n\nCurrent directory: {os.getcwd()}\n"
            + f"Directory listing:\n{local_ls()}\n\n"
            + "Continue with the next step of the task, or say 'Task complete' if done."
        )

    if step >= max_steps:
        print(f"{YELLOW}Reached max steps ({max_steps}). Use /local again to continue.{RESET}")


# ── Interactive shell ──────────────────────────────────────────────────────────

def interactive() -> None:
    print(f"\n{BOLD}  Manus Local Agent{RESET}")
    print(f"  {DIM}Controls your local machine. Type a task or a command.{RESET}")
    print(f"  {DIM}Built-in: ls [path] | read <file> | cd <dir> | exit{RESET}\n")

    while True:
        try:
            inp = input(f"{CYAN}Task>{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not inp:
            continue

        if inp in ("exit", "quit"):
            print("Goodbye!")
            break

        # Built-in local commands (no Manus needed)
        elif inp.startswith("ls") or inp.startswith("dir"):
            path = inp.split(" ", 1)[1].strip() if " " in inp else "."
            print(local_ls(path))

        elif inp.startswith("read "):
            path = inp[5:].strip()
            print(local_read(path))

        elif inp.startswith("cd "):
            path = inp[3:].strip()
            try:
                os.chdir(path)
                print(f"{GREEN}cwd: {os.getcwd()}{RESET}")
            except Exception as e:
                print(f"{RED}{e}{RESET}")

        elif inp.startswith("run "):
            cmd = inp[4:].strip()
            if approve("Shell command", cmd):
                run_shell(cmd)

        else:
            # Send to Manus agent loop
            agent_loop(inp)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Manus Local Agent")
    p.add_argument("task", nargs="*", help="Task to perform (or interactive if omitted)")
    p.add_argument("--yes", "-y", action="store_true", help="Auto-approve all commands")
    p.add_argument("--cwd", help="Working directory")
    args = p.parse_args()

    global always_allow
    if args.yes:
        always_allow = True
        print(f"{YELLOW}Warning: auto-approving all commands{RESET}")

    if args.cwd:
        os.chdir(args.cwd)

    if args.task:
        agent_loop(" ".join(args.task))
    else:
        interactive()


if __name__ == "__main__":
    main()
