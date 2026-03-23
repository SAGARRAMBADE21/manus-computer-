#!/usr/bin/env python3
"""
local_agent.py — Run Manus as a local machine agent.
Manus plans steps, generates commands, you approve each before it runs.

Usage:
  python local_agent.py "<task>"
  python local_agent.py "<task>" --yes       # auto-approve all
  python local_agent.py "<task>" --cwd <dir>
  python local_agent.py                      # interactive shell
"""
import os, sys, re, subprocess, time, argparse
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

BASE_URL     = "https://api.manus.ai/v1"
MAX_STEPS    = 10
SAFE_CMDS    = {"dir","ls","echo","type","cat","pwd","cd","python --version",
                "pip list","git status","git log","whoami","hostname"}
always_allow = False

# ── API ────────────────────────────────────────────────────────────────────────

def headers():
    key = os.environ.get("MANUS_API_KEY", "")
    if not key:
        print("Error: MANUS_API_KEY not set in .env"); sys.exit(1)
    return {"accept":"application/json","content-type":"application/json","API_KEY":key}

def ask_manus(prompt):
    r = requests.post(f"{BASE_URL}/tasks",
        json={"prompt": prompt, "agent_profile": "manus-1.6", "task_mode": "chat"},
        headers=headers(), timeout=30)
    if r.status_code != 200:
        print(f"Manus API error: {r.text[:200]}"); return ""
    task_id  = r.json().get("task_id","")
    task_url = r.json().get("task_url","")
    if task_url: print(f"  {task_url}")
    return poll(task_id)

def poll(task_id):
    print("Thinking", end="", flush=True)
    while True:
        try:
            r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers(), timeout=20)
            if r.status_code != 200: print(); return ""
            task = r.json()
            print(".", end="", flush=True)
            if task.get("status") in ("completed","failed","cancelled"):
                print(f" {task['status']}")
                return "\n".join(
                    c.get("text","").strip()
                    for item in task.get("output",[]) if item.get("role")=="assistant"
                    for c in item.get("content",[]) if c.get("text","").strip()
                )
        except requests.exceptions.ConnectionError:
            print("\nNetwork blip, retrying...", end="", flush=True)
        time.sleep(4)

# ── Command extraction ─────────────────────────────────────────────────────────

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

# ── Execution ──────────────────────────────────────────────────────────────────

def is_safe(cmd):
    return (cmd.strip().split()[0].lower() if cmd.strip() else "") in SAFE_CMDS

def approve(label, detail):
    global always_allow
    if always_allow: return True
    if is_safe(detail): print("  [auto-approved]"); return True
    print(f"\n  Approval required — {label}: {detail[:200]}")
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

# ── Agent loop ─────────────────────────────────────────────────────────────────

SYSTEM = """You are a COMMAND GENERATOR for a Windows machine. You do NOT execute commands yourself.
RULES:
1. NEVER say "I have done X" — you cannot execute anything
2. ALWAYS provide commands in ```cmd``` blocks
3. No fake output — wait for real results
4. One ```cmd``` block per response
FORMAT: Shell → ```cmd```, Python → ```python```, OS: Windows CMD, CWD: {cwd}"""

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

# ── Interactive shell ──────────────────────────────────────────────────────────

def interactive():
    print("\n  Manus Local Agent — Interactive")
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

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    global always_allow
    p = argparse.ArgumentParser(description="Manus Local Agent")
    p.add_argument("task", nargs="*")
    p.add_argument("--yes","-y", action="store_true")
    p.add_argument("--cwd", help="Working directory")
    args = p.parse_args()
    if args.yes: always_allow = True; print("Warning: auto-approving all commands")
    if args.cwd: os.chdir(args.cwd)
    if args.task: agent_loop(" ".join(args.task))
    else: interactive()

if __name__ == "__main__":
    main()
