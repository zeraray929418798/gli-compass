#!/usr/bin/env python3
"""Build the daily Global Liquidity Index market-proxy dashboard."""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SITE_DATA = ROOT / "site" / "data"
RAW.mkdir(parents=True, exist_ok=True)
SITE_DATA.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

SYMBOLS = {
    "spx": "^GSPC", "ndx": "TQQQ", "gold": "GC=F", "btc": "BTC-USD",
    "dxy": "DX-Y.NYB", "ust10y": "^TNX", "vix": "^VIX", "move": "^MOVE",
    "irx": "^IRX", "tlt": "TLT", "hyg": "HYG", "lqd": "LQD",
    "kre": "KRE", "spy": "SPY", "eem": "EEM", "uup": "UUP",
}
LABELS = {
    "spx": "标普500", "ndx": "TQQQ", "gold": "黄金", "btc": "比特币",
    "dxy": "美元指数", "ust10y": "10Y 美债", "vix": "VIX", "move": "MOVE",
    "irx": "3M 美债", "tlt": "TLT", "hyg": "HYG", "lqd": "LQD",
    "kre": "KRE", "spy": "SPY", "eem": "EEM", "uup": "UUP",
}
MODULES = [
    {"key": "policy", "name": "政策与久期", "weight": .25, "desc": "短端利率、长端利率、长久期债券"},
    {"key": "usd", "name": "美元流动性", "weight": .25, "desc": "美元指数与美元多头代理"},
    {"key": "credit", "name": "银行信用", "weight": .20, "desc": "高收益/投资级、区域银行/宽基"},
    {"key": "cross", "name": "跨境资金", "weight": .15, "desc": "新兴市场/美国、美元"},
    {"key": "fin", "name": "融资条件", "weight": .15, "desc": "VIX、MOVE、高收益债"},
]


def fetch(symbol: str) -> pd.Series:
    hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
    encoded = urllib.parse.quote(symbol, safe="")
    last = None
    for attempt in range(6):
        host = hosts[attempt % 2]
        url = f"https://{host}/v8/finance/chart/{encoded}?range=20y&interval=1d&events=div%2Csplits"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
            result = obj["chart"]["result"][0]
            idx = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
            vals = result["indicators"]["quote"][0]["close"]
            s = pd.Series(vals, index=idx, dtype="float64").dropna()
            s = s[~s.index.duplicated(keep="last")].sort_index()
            if len(s) > 200:
                return s
            last = RuntimeError("too few rows")
        except Exception as exc:  # noqa: BLE001
            last = exc
        print(f"  [retry {attempt + 1}] {symbol}: {last}")
    raise RuntimeError(f"download failed {symbol}: {last}")


def zscore(s: pd.Series, window: int = 1260, min_periods: int = 1260) -> pd.Series:
    mean = s.rolling(window, min_periods=min_periods).mean()
    std = s.rolling(window, min_periods=min_periods).std()
    z = (s - mean) / std.replace(0, np.nan)
    return z.clip(-3, 3)


def signed_z(s: pd.Series, sign: int, mode: str) -> pd.Series:
    x = np.log(s) if mode == "log" else s
    return sign * zscore(x)


def main() -> int:
    data = {}
    for key, symbol in SYMBOLS.items():
        data[key] = fetch(symbol)
        print(f"{LABELS[key]}: {len(data[key])} rows, {data[key].index[0].date()} → {data[key].index[-1].date()}")

    core = [k for k in SYMBOLS if k != "btc"]
    df = pd.concat({k: data[k] for k in core}, axis=1, sort=True).dropna()
    df = df.sort_index()
    if len(df) < 600:
        raise RuntimeError("not enough common observations")

    # Ratios, all positive.
    df["hyg_lqd"] = df["hyg"] / df["lqd"]
    df["kre_spy"] = df["kre"] / df["spy"]
    df["eem_spy"] = df["eem"] / df["spy"]
    df["tlt_log"] = np.log(df["tlt"])
    df["dxy_log"] = np.log(df["dxy"])
    df["uup_log"] = np.log(df["uup"])
    df["hyg_log"] = np.log(df["hyg"])
    df["gold_log"] = np.log(df["gold"])

    # Each entry: (series, sign, mode). Positive sign = more liquidity when higher.
    specs = {
        "policy": [("irx", -1, "level"), ("ust10y", -1, "level"), ("tlt_log", 1, "level")],
        "usd": [("dxy_log", -1, "level"), ("uup_log", -1, "level")],
        "credit": [("hyg_lqd", 1, "log"), ("kre_spy", 1, "log")],
        "cross": [("eem_spy", 1, "log"), ("dxy_log", -1, "level")],
        "fin": [("vix", -1, "level"), ("move", -1, "level"), ("hyg_log", 1, "level")],
    }
    module_scores = {}
    for module, parts in specs.items():
        zs = []
        for col, sign, mode in parts:
            zs.append(signed_z(df[col], sign, mode))
        module_scores[module] = pd.concat(zs, axis=1).mean(axis=1)
        df[module] = module_scores[module]

    raw = sum(module_scores[m["key"]] * m["weight"] for m in MODULES)
    gli_s = (50 + 10 * raw).clip(0, 100)
    gli_m_raw = 0.5 * zscore(gli_s.diff(63)) + 0.3 * zscore(gli_s.diff(21)) + 0.2 * zscore(gli_s.diff(126))
    gli_m = (50 + 10 * gli_m_raw).clip(0, 100)

    df["gli_s"] = gli_s
    df["gli_m"] = gli_m
    df = df.dropna(subset=["gli_s"])
    if len(df) < 200:
        raise RuntimeError("not enough GLI observations")

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

    last = df.iloc[-1]
    prev_1m = df["gli_s"].iloc[-21] if len(df) > 21 else np.nan
    prev_3m = df["gli_s"].iloc[-63] if len(df) > 63 else np.nan
    regime, regime_en = state(float(last["gli_s"]), float(last["gli_m"]))

    ndx_norm = df["ndx"] / df["ndx"].iloc[0] * 100
    gli_norm = df["gli_s"] / df["gli_s"].iloc[0] * 100
    roll_corr = df["gli_s"].diff().rolling(60).corr(np.log(df["ndx"]).diff())

    series = []
    for dt, row in df.iterrows():
        series.append({
            "d": dt.strftime("%Y-%m-%d"),
            "s": round(float(row["gli_s"]), 2),
            "m": None if pd.isna(row["gli_m"]) else round(float(row["gli_m"]), 2),
            "policy": round(float(row["policy"]), 3),
            "usd": round(float(row["usd"]), 3),
            "credit": round(float(row["credit"]), 3),
            "cross": round(float(row["cross"]), 3),
            "fin": round(float(row["fin"]), 3),
            "n": round(float(row["ndx"]), 2),
            "gn": round(float(gli_norm.loc[dt]), 2),
            "nn": round(float(ndx_norm.loc[dt]), 2),
            "rc": None if pd.isna(roll_corr.loc[dt]) else round(float(roll_corr.loc[dt]), 3),
        })

    # Assets for the linkage table. BTC is not part of the GLI core because its
    # history starts in 2014; it is still compared separately.
    assets = ["spx", "ndx", "gold", "btc", "dxy", "ust10y"]
    asset_rows = []
    for key in assets:
        src = data["btc"].reindex(df.index).dropna() if key == "btc" else df[key]
        if key == "ust10y":
            ret = src.diff()
            one_y = float(src.iloc[-1] - src.iloc[-253]) * 100
            one_y_text = f"{one_y:+.1f}bp"
        else:
            ret = np.log(src / src.shift(1))
            one_y = (src.iloc[-1] / src.iloc[-253] - 1) * 100
            one_y_text = f"{one_y:+.1f}%"
        gli_chg = df["gli_s"].diff().reindex(src.index)
        corr = float(ret.corr(gli_chg))
        asset_rows.append({
            "key": key, "name": LABELS[key], "one_y": one_y_text,
            "one_y_num": round(one_y, 1),
            "corr": round(corr, 2),
            "price": round(float(src.iloc[-1]), 2),
        })

    month = df[["gli_s", "ndx"]].resample("ME").last().dropna()
    month_corr = float(month["gli_s"].diff().corr(month["ndx"].pct_change()))
    ndx_compare = {
        "start": df.index[0].strftime("%Y-%m-%d"),
        "daily_corr": round(float(df["gli_s"].diff().corr(np.log(df["ndx"]).diff())), 3),
        "monthly_corr": round(month_corr, 3),
        "current_60d": round(float(roll_corr.dropna().iloc[-1]), 3) if roll_corr.notna().any() else None,
        "ndx_current": round(float(df["ndx"].iloc[-1]), 2),
        "ndx_1y": round(float(df["ndx"].iloc[-1] / df["ndx"].iloc[-253] - 1) * 100, 1),
    }

    # Module contribution in GLI points (10 * weight * module z).
    contributions = []
    for m in MODULES:
        z = float(last[m["key"]])
        contributions.append({
            "key": m["key"], "name": m["name"], "weight": m["weight"],
            "z": round(z, 2), "points": round(10 * m["weight"] * z, 2),
        })

    quadrant = [
        {"d": dt.strftime("%Y-%m-%d"), "x": round(float(r["gli_s"]), 2), "y": round(float(r["gli_m"]), 2)}
        for dt, r in df.tail(504).iterrows()
    ]

    month = df[["gli_s", "gli_m", "ndx"]].resample("ME").last().dropna()
    month["tqqq_ret"] = month["ndx"].pct_change() * 100
    month["chg1"] = month["gli_s"].diff()
    monthly_rows = []
    for dt, r in month.tail(30).iterrows():
        reg, reg_en = state(float(r["gli_s"]), float(r["gli_m"]))
        monthly_rows.append({
            "month": dt.strftime("%Y-%m"),
            "s": round(float(r["gli_s"]), 1),
            "m": round(float(r["gli_m"]), 1),
            "regime": reg,
            "regime_en": reg_en,
            "tqqq": None if pd.isna(r["tqqq_ret"]) else round(float(r["tqqq_ret"]), 1),
            "chg": None if pd.isna(r["chg1"]) else round(float(r["chg1"]), 1),
        })

    payload = {
        "meta": {
            "as_of": df.index[-1].strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "start": df.index[0].strftime("%Y-%m-%d"),
            "observations": int(len(df)),
            "source_note": "Yahoo Finance 日频行情；GLI 为五模块市场代理版，不是央行资产负债表完整核算。",
            "sources": [
                {"label": "Yahoo Finance · S&P 500 / Nasdaq 100", "url": "https://finance.yahoo.com/quote/%5EGSPC/"},
                {"label": "Yahoo Finance · Gold / Brent / BTC / DXY", "url": "https://finance.yahoo.com/quote/GC%3DF/"},
                {"label": "Yahoo Finance · 10Y / VIX / MOVE / 3M", "url": "https://finance.yahoo.com/quote/%5ETNX/"},
                {"label": "Yahoo Finance · TLT / HYG / LQD / KRE / SPY / EEM / UUP", "url": "https://finance.yahoo.com/quote/TLT/"},
            ],
            "notes": [
                "PDF 完整版要求央行资产负债表、BIS 跨境债权、IMF COFER 等；免费日频源无法完整覆盖。",
                "本站用政策利率/久期、美元、信用、跨境 ETF、融资条件五组日频市场代理构建 GLI-Market。",
                "每个代理先做 5 年滚动 Z-Score（±3 截断），再加权合成；GLI-S = 50 + 10 × 综合 Z。",
                "GLI-M = 1M/3M/6M 边际变化的加权 Z-Score，再映射到 0–100；四象限以 50 为分界。",
                "代理变量不是央行资产负债表本身，不能把 GLI 绝对值当成“全球流动性总量”。",
            ],
        },
        "current": {
            "gli_s": round(float(last["gli_s"]), 1),
            "gli_m": round(float(last["gli_m"]), 1),
            "regime": regime,
            "regime_en": regime_en,
            "one_m": round(float(last["gli_s"] - prev_1m), 1) if pd.notna(prev_1m) else None,
            "three_m": round(float(last["gli_s"] - prev_3m), 1) if pd.notna(prev_3m) else None,
            "modules": contributions,
        },
        "assets": asset_rows,
        "ndx_compare": ndx_compare,
        "series": series,
        "quadrant": quadrant,
        "monthly": monthly_rows,
    }
    (SITE_DATA / "gli.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SITE_DATA / "gli.js").write_text("window.GLI_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    with open(SITE_DATA / "gli_daily.csv", "w", newline="", encoding="utf-8") as fh:
        import csv
        w = csv.writer(fh)
        w.writerow(["date", "gli_s", "gli_m", "policy", "usd", "credit", "cross", "fin"])
        for row in series:
            w.writerow([row["d"], row["s"], row["m"], row["policy"], row["usd"], row["credit"], row["cross"], row["fin"]])

    print(f"GLI-S {payload['current']['gli_s']} · GLI-M {payload['current']['gli_m']} · {regime} · {len(series)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
