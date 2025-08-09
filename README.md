# sheets-qa-sandbox

# Sheet-QA (Sandboxed)

This repository contains a Streamlit Google Sheets Q&A app wired to a sandbox runner that
executes generated Pandas code safely.

## Files
- `main.py` — Streamlit app (uses injected `dfs` when present; otherwise loads sheets via gspread)
- `prepare_injection.py` — create `injected_dfs.pkl` from Sheets or Excel (trusted step)
- `sandbox.py` — parent controller to run `main.py` inside the sandbox
- `child_runner.py` — sandbox enforcing resource limits, disabling networking, injecting `dfs`
- `requirements.txt` — dependencies

## Quick local workflow

1. Install dependencies
```bash
python3 -m pip install -r requirements.txt
