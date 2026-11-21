#!/usr/bin/env python3
"""S&P 500 trailing PE and Shiller PE (multpl monthly tables)."""
from __future__ import annotations

import io
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
SITE_DATA.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()


def clean_num(v) -> float:
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return float(s)
    except ValueError:
        return np.nan


def multpl(url: str) -> pd.Series:
    raw = fetch(url)
    tables = pd.read_html(io.BytesIO(raw))
    df = tables[0].copy()
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = df["value"].map(clean_num)
    df = df.dropna()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    df = df.sort_values("date").drop_duplicates("month", keep="last")
    s = df.set_index("month")["value"].sort_index()
    s.attrs["last_date"] = df["date"].max()
    return s


def main() -> None:
    try:
        pe = multpl("https://www.multpl.com/s-p-500-pe-ratio/table/by-month")
        cape = multpl("https://www.multpl.com/shiller-pe/table/by-month")
        pe = pe[pe.index >= "1980-01-01"]
        cape = cape[cape.index >= "1980-01-01"]
        pe_df = pd.concat({"pe": pe, "cape": cape}, axis=1).sort_index()
        pe_df[["pe", "cape"]] = pe_df[["pe", "cape"]].ffill()
        pe_rows = []
        for dt, r in pe_df.dropna().iterrows():
            pe_rows.append({"d": dt.strftime("%Y-%m-%d"), "pe": round(float(r["pe"]), 2), "cape": round(float(r["cape"]), 2)})
        if len(pe_rows) < 100:
            raise RuntimeError("too few PE rows")

        def stats(s: pd.Series) -> dict:
            return {
                "current": round(float(s.iloc[-1]), 2),
                "median": round(float(s.median()), 2),
                "p20": round(float(s.quantile(.2)), 2),
                "p80": round(float(s.quantile(.8)), 2),
                "percentile": round(float((s <= s.iloc[-1]).mean() * 100), 1),
            }

        payload = {
            "meta": {
                "as_of": (pe.attrs.get("last_date") or pe_df.index[-1]).strftime("%Y-%m-%d"),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "start": pe_df.dropna().index[0].strftime("%Y-%m-%d"),
                "observations": len(pe_rows),
                "stats": {"pe": stats(pe_df["pe"]), "cape": stats(pe_df["cape"])},
                "sources": [
                    {"label": "multpl · S&P 500 PE Ratio", "url": "https://www.multpl.com/s-p-500-pe-ratio"},
                    {"label": "multpl · Shiller PE Ratio", "url": "https://www.multpl.com/shiller-pe"},
                ],
                "notes": [
                    "S&P 500 滚动市盈率与席勒市盈率（10 年通胀调整）。",
                    "multpl 提供月度表；页面按月末值展示，最新月份为当前读数。",
                    "中线 = 1980 年以来全样本中位数；分位 = 当前值在全样本中的百分位。",
                ],
            },
            "series": pe_rows,
        }
        (SITE_DATA / "pe.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (SITE_DATA / "pe.js").write_text("window.PE_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
        print("PE", pe_rows[-1], payload["meta"]["stats"])
    except Exception as exc:  # keep the previous snapshot instead of blocking deploy
        print(f"PE refresh failed; keeping existing pe.json: {exc!r}")
        return


if __name__ == "__main__":
    main()
