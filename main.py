#!/usr/bin/env python3
import os
import streamlit as st
import gspread
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAIError
import requests
import matplotlib.pyplot as plt

# ---- Load environment variables ----
load_dotenv()
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ---- Streamlit page config ----
st.set_page_config(page_title="📊 Google Sheets Q&A Agent", layout="wide")
st.title("📊 Google Sheets Q&A Agent")

# ---- Data init ----
try:
    if "dfs" in globals() and isinstance(dfs, list):
        st.success("📦 Using injected dataframes from sandbox.")
    else:
        dfs = []
except Exception as e:
    st.error(f"Data init error: {e}")
    dfs = []

# ---- Validate secrets ----
if not SERVICE_ACCOUNT_JSON and not dfs:
    st.error("🚫 Missing GOOGLE_SERVICE_ACCOUNT in `.env` and no injected data.")
    st.stop()
if not OPENROUTER_API_KEY:
    st.error("🚫 Missing OPENROUTER_API_KEY in `.env`.")
    st.stop()

# ---- DeepSeek/OpenRouter call ----
def call_llm(prompt, model="mistralai/mistral-7b-instruct"):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=data
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        return f"❌ API request error: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"

# ---- If no injected dfs, load from Google Sheets ----
if not dfs:
    try:
        gc = gspread.service_account_from_dict(eval(SERVICE_ACCOUNT_JSON))
        sheet_ids = st.text_area(
            "📎 Enter comma-separated Google Sheet IDs:",
            placeholder="1abcXyz..., 1defPqr..."
        )
        if sheet_ids.strip():
            for sid in [s.strip() for s in sheet_ids.split(",") if s.strip()]:
                try:
                    sh = gc.open_by_key(sid)
                    st.success(f"📄 Opened: {sh.title}")
                    for ws in sh.worksheets():
                        values = ws.get_all_values()
                        if not values or len(values) < 2:
                            continue
                        header = [str(c).strip() for c in values[0]]
                        rows = [r for r in values[1:] if len(r) == len(header)]
                        df = pd.DataFrame(rows, columns=header)
                        if not df.empty:
                            dfs.append((sh.title + " → " + ws.title, df))
                except Exception as e:
                    st.error(f"❌ Could not open sheet {sid}: {e}")
    except Exception as e:
        st.error(f"❌ Google Sheets auth failed: {e}")
        st.stop()

if not dfs:
    st.warning("⚠️ No dataframes loaded.")
    st.stop()

# ---- Show loaded data ----
st.subheader("🗃️ Available Data")
for name, df in dfs:
    st.markdown(f"**{name}**")
    st.dataframe(df.head(3), use_container_width=True)

# ---- Ask a question ----
st.subheader("💬 Ask a question about your data")
query = st.text_input("Ask a question (e.g., 'Total expense in August')")

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
    return call_llm(prompt)

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
        return local_vars.get("result", "⚠️ No result variable."), code
    except Exception as e:
        return f"⚠️ Error running code: {e}", code

if query:
    with st.spinner("Generating and running analysis..."):
        answer, code = run_query(query, dfs)
    st.markdown("### 📝 Generated Pandas Code")
    st.code(code, language="python")
    st.markdown("### 💡 Answer")
    st.write(answer)
