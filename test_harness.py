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
from dotenv import load_dotenv
from main import run_query

load_dotenv()

# Load injected DataFrames
injected_path = Path("injected_dfs.pkl")
if not injected_path.exists():
    print("❌ injected_dfs.pkl not found. Run prepare_injection.py first.")
    sys.exit(1)

with open(injected_path, "rb") as f:
    dfs = pickle.load(f)

# Simulate a natural language question
question = "What were the total expenses in July?"

print(f"❓ Question: {question}")

# Run through the run_query logic from main.py
answer, code = run_query(question, dfs)

print("📝 Generated Code:")
print(code)
print("\n💡 Answer:")
print(answer)

# Basic check for success
if answer is not None and "error" not in str(answer).lower():
    print("\n✅ Test passed.")
    sys.exit(0)
else:
    print("\n❌ Test failed.")
    sys.exit(1)
