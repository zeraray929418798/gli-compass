#!/usr/bin/env python3
"""Patch the generated GLI data with TQQQ history from Nasdaq.

Yahoo Finance is not reachable from some networks (HTTP 403). Nasdaq's public
quote endpoint provides ~10 years of TQQQ daily closes, which is enough to
replace the QQQ/NDX comparison. Run after update_data.py if needed.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data" / "gli.json"
RAW = ROOT / "data" / "raw" / "TQQQ_nasdaq.json"
URL = (
    "https://api.nasdaq.com/api/quote/TQQQ/historical"
    "?assetclass=etf&fromdate=2016-01-01&todate=2026-12-31&limit=5000"
)


def fetch_tqqq() -> pd.Series:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    RAW.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
    rows = obj["data"]["tradesTable"]["rows"]
    pairs = []
    for r in rows:
        try:
            pairs.append((pd.to_datetime(r["date"], format="%m/%d/%Y"), float(str(r["close"]).replace("$", "").replace(",", ""))))
        except Exception:
            continue
    s = pd.Series(dict(pairs), dtype="float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def state(s: float, m: float) -> tuple[str, str]:
    if s >= 55 and m >= 50:
        return "全面宽松", "expansion"
    if s >= 55:
        return "高位收缩", "slowdown"
    if s < 45 and m < 50:
        return "流动性紧缩", "stress"
    if s < 45:
        return "流动性复苏", "recovery"
    if m < 50:
        return "温和收紧", "tight"
    return "温和改善", "easing"


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    tq = fetch_tqqq()
    by_date = {d.strftime("%Y-%m-%d"): float(v) for d, v in tq.items()}

    for row in payload["series"]:
        row["n"] = round(by_date[row["d"]], 4) if row["d"] in by_date else None
        row["nn"] = row["n"]
        row["rc"] = None

    df = pd.DataFrame(payload["series"])
    df["dt"] = pd.to_datetime(df["d"])
    s = df.set_index("dt")["s"].astype(float)
    n = df.set_index("dt")["n"]
    roll = s.diff().rolling(60).corr(np.log(n.astype(float)).diff())
    for row in payload["series"]:
        dt = pd.Timestamp(row["d"])
        if dt in roll.index and pd.notna(roll.loc[dt]):
            row["rc"] = round(float(roll.loc[dt]), 3)

    # TQQQ comparison metrics.
    n_valid = n.dropna()
    daily_corr = s.diff().corr(np.log(n_valid).diff())
    month = pd.DataFrame({"s": s, "n": n}).resample("ME").last().dropna()
    monthly_corr = month["s"].diff().corr(month["n"].pct_change())
    payload["ndx_compare"] = {
        "start": n_valid.index[0].strftime("%Y-%m-%d"),
        "daily_corr": round(float(daily_corr), 3),
        "monthly_corr": round(float(monthly_corr), 3),
        "current_60d": round(float(roll.dropna().iloc[-1]), 3) if roll.notna().any() else None,
        "ndx_current": round(float(n_valid.iloc[-1]), 2),
        "ndx_1y": round(float(n_valid.iloc[-1] / n_valid.iloc[-253] - 1) * 100, 1),
    }

    # Asset table row.
    for row in payload["assets"]:
        if row["key"] != "ndx":
            continue
        row["name"] = "TQQQ"
        row["price"] = round(float(n_valid.iloc[-1]), 2)
        one_y = (n_valid.iloc[-1] / n_valid.iloc[-253] - 1) * 100
        row["one_y"] = f"{one_y:+.1f}%"
        row["one_y_num"] = round(float(one_y), 1)
        ret = np.log(n_valid / n_valid.shift(1))
        row["corr"] = round(float(ret.corr(s.diff().reindex(n_valid.index))), 2)

    # Monthly log.
    month = pd.DataFrame({"s": s, "m": df.set_index("dt")["m"], "n": n}).resample("ME").last().dropna()
    month["tqqq_ret"] = month["n"].pct_change() * 100
    month["chg1"] = month["s"].diff()
    monthly_rows = []
    for dt, r in month.tail(30).iterrows():
        reg, reg_en = state(float(r["s"]), float(r["m"]))
        monthly_rows.append({
            "month": dt.strftime("%Y-%m"),
            "s": round(float(r["s"]), 1),
            "m": round(float(r["m"]), 1),
            "regime": reg,
            "regime_en": reg_en,
            "tqqq": None if pd.isna(r["tqqq_ret"]) else round(float(r["tqqq_ret"]), 1),
            "chg": None if pd.isna(r["chg1"]) else round(float(r["chg1"]), 1),
        })
    payload["monthly"] = monthly_rows

    payload["meta"]["sources"] = [
        {"label": "Yahoo Finance · S&P 500 / Gold / DXY / Rates", "url": "https://finance.yahoo.com/quote/%5EGSPC/"},
        {"label": "Yahoo Finance · VIX / MOVE / 3M / TLT / HYG / LQD / KRE / SPY / EEM / UUP", "url": "https://finance.yahoo.com/quote/TLT/"},
        {"label": "Nasdaq · TQQQ（3倍做多纳指100）日线", "url": "https://www.nasdaq.com/market-activity/etf/tqqq/historical"},
    ]
    payload["meta"]["source_note"] = "Yahoo Finance 日频行情 + Nasdaq TQQQ 日线；GLI 为五模块市场代理版，不是央行资产负债表完整核算。"

    DATA.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "site" / "data" / "gli.js").write_text("window.GLI_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    with open(ROOT / "site" / "data" / "gli_daily.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "gli_s", "gli_m", "policy", "usd", "credit", "cross", "fin"])
        for r in payload["series"]:
            w.writerow([r["d"], r["s"], r["m"], r["policy"], r["usd"], r["credit"], r["cross"], r["fin"]])
    print(f"TQQQ {len(tq)} rows · {tq.index[0].date()} → {tq.index[-1].date()}")
    print(payload["ndx_compare"])
    print("monthly", len(monthly_rows), monthly_rows[-1])


if __name__ == "__main__":
    main()
