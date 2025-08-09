#!/usr/bin/env python3
"""
prepare_injection.py
Create injected_dfs.pkl from Google Sheets or local Excel.

Usage:
  # from Google Sheets (trusted env; set GOOGLE_SERVICE_ACCOUNT JSON in env or .env)
  python3 prepare_injection.py --sheets "SHEETID1,SHEETID2"

  # from local Excel
  python3 prepare_injection.py --excel "./OMR Monthly Expense 2025-26.xlsx"
"""
import os
import argparse
import json
from dotenv import load_dotenv
load_dotenv()
import pandas as pd
import gspread

def sheets_to_dfs(sheet_ids, service_account_json):
    gc = gspread.service_account_from_dict(json.loads(service_account_json))
    dfs = []
    for sid in [s.strip() for s in sheet_ids.split(",") if s.strip()]:
        sh = gc.open_by_key(sid)
        for ws in sh.worksheets():
            vals = ws.get_all_values()
            if not vals or len(vals) < 2:
                continue
            header = [str(c).strip() for c in vals[0]]
            if len(set(header)) != len(header) or '' in header:
                continue
            rows = [r for r in vals[1:] if len(r) == len(header)]
            df = pd.DataFrame(rows, columns=header)
            dfs.append((sh.title + " → " + ws.title, df))
    return dfs

def excel_to_dfs(path):
    xls = pd.ExcelFile(path)
    dfs = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        dfs.append((sheet, df))
    return dfs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheets", help="comma separated sheet ids")
    parser.add_argument("--excel", help="local excel file path")
    parser.add_argument("--out", help="output json path", default="injected_dfs.json")
    args = parser.parse_args()

    if not args.sheets and not args.excel:
        print("Provide --sheets or --excel")
        raise SystemExit(2)

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")

    if args.sheets:
        if not service_account_json:
            print("Set GOOGLE_SERVICE_ACCOUNT env")
            raise SystemExit(2)
        dfs = sheets_to_dfs(args.sheets, service_account_json)
    else:
        dfs = excel_to_dfs(args.excel)

    # Convert dataframes to JSON serializable format
    json_dfs = [(name, df.to_dict(orient="split")) for name, df in dfs]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(json_dfs, f, indent=2)

    print("Wrote", args.out, "with", len(dfs), "worksheets")

if __name__ == "__main__":
    main()
