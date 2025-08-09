#!/usr/bin/env python3
"""
Sandbox controller:
  python3 sandbox.py path/to/untrusted_script.py [path/to/injected_dfs.pkl]

Copies files into a temp directory and runs child_runner.py there.
Captures stdout/stderr and enforces wall timeout.
"""
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import os

WALL_TIMEOUT = 20  # seconds
PYTHON_BIN = sys.executable

if len(sys.argv) < 2:
    print("Usage: python3 sandbox.py <script.py> [injected_dfs.pkl]")
    sys.exit(2)

target = Path(sys.argv[1]).resolve()
if not target.exists():
    print("Target script not found:", target)
    sys.exit(2)

inject_src = None
if len(sys.argv) >= 3:
    inject_src = Path(sys.argv[2]).resolve()
    if not inject_src.exists():
        print("Injection file not found:", inject_src)
        sys.exit(2)

tmpdir = Path(tempfile.mkdtemp(prefix="runsandbox_"))
try:
    target_copy = tmpdir / target.name
    shutil.copy2(target, target_copy)

    if inject_src:
        inject_dest = tmpdir / "injected_dfs.pkl"
        shutil.copy2(inject_src, inject_dest)

    child_runner = Path(__file__).parent.resolve() / "child_runner.py"
    cmd = [PYTHON_BIN, str(child_runner), str(target_copy)]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=WALL_TIMEOUT,
            text=True,
        )
    except subprocess.TimeoutExpired:
        print(f"[sandbox] Execution exceeded wall timeout of {WALL_TIMEOUT}s — killed.")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(124)

    if proc.stdout:
        print("--- child stdout ---")
        print(proc.stdout.rstrip())
    if proc.stderr:
        print("--- child stderr ---")
        print(proc.stderr.rstrip(), file=sys.stderr)

    sys.exit(proc.returncode if proc.returncode is not None else 0)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
