#!/usr/bin/env python3
"""US Treasury constant-maturity yields, 1994-present, via DBnomics/Fed H.15."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SITE_DATA = ROOT / "site" / "data"
RAW.mkdir(parents=True, exist_ok=True)
SITE_DATA.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
BASE = "https://api.db.nomics.world/v22/series/FED/H15/"
SERIES = {
    "y1": ("RIFLGFCY01_N.B", "1年"),
    "y5": ("RIFLGFCY05_N.B", "5年"),
    "y10": ("RIFLGFCY10_N.B", "10年"),
    "y20": ("RIFLGFCY20_N.B", "20年"),
    "y30": ("RIFLGFCY30_N.B", "30年"),
}


def fetch(code: str) -> pd.Series:
    url = BASE + code + "?observations=1"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    doc = obj["series"]["docs"][0]
    s = pd.Series(pd.to_numeric(doc["value"], errors="coerce"), index=pd.to_datetime(doc["period"])).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def main() -> None:
    data = {}
    for key, (code, label) in SERIES.items():
        data[key] = fetch(code)
        print(f"{label}: {len(data[key])} rows, {data[key].index[0].date()} → {data[key].index[-1].date()}")

    df = pd.concat(data, axis=1).dropna()
    df = df[df.index >= "1994-01-01"].sort_index()
    df["median"] = df[["y1", "y5", "y10", "y20", "y30"]].median(axis=1)

    rows = []
    for dt, r in df.iterrows():
        rows.append({
            "d": dt.strftime("%Y-%m-%d"),
            **{k: round(float(r[k]), 3) for k in ["y1", "y5", "y10", "y20", "y30", "median"]},
        })

    stats = {}
    for key, (_, label) in SERIES.items():
        s = df[key]
        cur = float(s.iloc[-1])
        stats[key] = {
            "label": label,
            "current": round(cur, 3),
            "median": round(float(s.median()), 3),
            "p20": round(float(s.quantile(.2)), 3),
            "p80": round(float(s.quantile(.8)), 3),
            "percentile": round(float((s <= cur).mean() * 100), 1),
        }

    payload = {
        "meta": {
            "as_of": df.index[-1].strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "start": df.index[0].strftime("%Y-%m-%d"),
            "observations": int(len(df)),
            "stats": stats,
            "sources": [
                {"label": "Federal Reserve H.15 via DBnomics · 1Y/5Y/10Y/20Y/30Y", "url": "https://fred.stlouisfed.org/categories/115"},
                {"label": "U.S. Treasury · Daily Treasury Par Yield Curve", "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"},
            ],
            "notes": [
                "美国国债恒定到期收益率（constant maturity），日频。",
                "中线 = 1/5/10/20/30 年收益率的当日中位数。",
                "分位 = 当前值在 1994 年以来全样本中的百分位；20/80 分位为全样本分位。",
            ],
        },
        "series": rows,
    }
    (SITE_DATA / "yields.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SITE_DATA / "yields.js").write_text("window.YIELDS = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    print(f"{len(rows)} rows · {rows[0]['d']} → {rows[-1]['d']}")
    print({k: v["current"] for k, v in stats.items()})


if __name__ == "__main__":
    main()
