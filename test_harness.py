
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

# ---- Load injected DataFrames ----
injected_path = Path("injected_dfs.pkl")
if not injected_path.exists():
    print("❌ injected_dfs.pkl not found. Run prepare_injection.py first.")
    sys.exit(1)

with open(injected_path, "rb") as f:
    dfs = pickle.load(f)

# ---- Functions from main.py ----
def ask_llm_for_code(question, dfs):
    schema_parts = []
    for name, df in dfs:
        schema_parts.append(
            f"### {name}\nColumns: {list(df.columns)}\nSample:\n{df.head(5).to_markdown(index=False)}"
        )
    schema = "\n\n".join(schema_parts)

    prompt = f"""
You are a Python data analyst.
Given the following table schemas and sample data, write Python Pandas code to answer the question.
- Use only the dataframes provided in variable `dfs` (list of (name, df) tuples).
- Your final result must be stored in a variable named `result`.
- Do NOT import anything or access the internet.
- Do NOT write explanations or markdown formatting, only valid Python code.

Schema and sample data:
{schema}

Question:
{question}
"""

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in env")

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mistral-7b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0
        }
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def is_safe_code(code):
    banned = ["import", "os.", "system(", "open(", "eval(", "exec(", "subprocess"]
    return not any(b in code.lower() for b in banned)

def run_query(question, dfs):
    code = ask_llm_for_code(question, dfs)
    if not is_safe_code(code):
        return "⚠️ Unsafe code generated.", code

    try:
        local_vars = {"dfs": dfs}
        exec(code, {}, local_vars)
        return local_vars.get("result", "⚠️ No result variable in code."), code
    except Exception as e:
        return f"⚠️ Error running code: {e}", code

# ---- Main test ----
if __name__ == "__main__":
    question = os.getenv("TEST_QUESTION", "Total expense in August")
    print(f"💬 Question: {question}")

    answer, code = run_query(question, dfs)

    print("\n📝 Generated Pandas Code:\n")
    print(code)

    print("\n💡 Answer:\n")
    print(answer)
