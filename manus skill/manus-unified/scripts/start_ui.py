#!/usr/bin/env python3
"""
start_ui.py — Launch the Manus Web UI.
Usage:
  python start_ui.py
  python start_ui.py --port 8080
  python start_ui.py --cwd <dir>
"""
import os, sys, argparse, subprocess

def main():
    p = argparse.ArgumentParser(description="Start Manus Web UI")
    p.add_argument("--port", default="5000", help="Port (default: 5000)")
    p.add_argument("--cwd",  help="Working directory for the agent")
    args = p.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    ui_script    = os.path.join(project_root, "ui", "app.py")

    if not os.path.exists(ui_script):
        print(f"Error: ui/app.py not found at {ui_script}"); sys.exit(1)

    if args.cwd:
        os.chdir(args.cwd)

    print(f"\n  Manus Web UI")
    print(f"  Open: http://localhost:{args.port}\n")

    env = os.environ.copy()
    env["FLASK_RUN_PORT"] = args.port

    subprocess.run([sys.executable, ui_script], env=env, cwd=args.cwd or os.getcwd())

if __name__ == "__main__":
    main()
