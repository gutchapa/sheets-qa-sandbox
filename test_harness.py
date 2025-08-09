#!/usr/bin/env python3
"""
Headless harness for testing main.py logic in CI (Jules).
- Loads injected_dfs.pkl
- Simulates a natural language question
- Runs through the run_query logic from main.py
"""

import pickle
import os
import sys
from pathlib import Path
import requests

# Load injected DataFrames
injected_path = Path("injected_dfs.pkl")
if not injected_path.exists():
    print("❌ injected_dfs.pkl not found. Run prepare_injection.py first.")
    sys.exit(
I
