#!/usr/bin/env python3
"""Cash / US equity market value ratio — long-history chart data.

Sources
-------
- Federal Reserve Z.1 via DBnomics:
  FL634090005.Q  money market funds, total financial assets ($m)
  LM103164105.Q  nonfinancial corporate equities, market value ($m)
- Federal Reserve H.8 via DBnomics:
  B1058NCBA      deposits, all commercial banks ($m, weekly)
- Robert Shiller / Yale:
  ie_data.xls    monthly S&P 500 (used as a SPY proxy, /10)
"""
from __future__ import annotations

import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
RAW = ROOT / "data" / "raw"
SITE_DATA.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
BASE = "https://api.db.nomics.world/v22/series/FED/"


def dbnomics(code: str) -> pd.Series:
    url = BASE + code + "?observations=1"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    doc = obj["series"]["docs"][0]
    periods = doc.get("period", [])
    values = doc.get("value", [])
    index = pd.to_datetime(periods, errors="coerce")
    s = pd.Series(values, index=index, dtype="float64").dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def shiller_sp500() -> pd.Series:
    url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    (RAW / "shiller_ie_data.xls").write_bytes(raw)
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data", header=None)
    rows = []
    for _, r in df.iloc[8:].iterrows():
        try:
            date = float(r.iloc[0])
            value = float(r.iloc[1])
        except (TypeError, ValueError):
            continue
        if not (1870 < date < 2100):
            continue
        year = int(date)
        month = int(round((date - year) * 100))
        if not 1 <= month <= 12:
            continue
        rows.append((pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0), value))
    s = pd.Series(dict(rows), dtype="float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def nasdaq_spy() -> pd.Series:
    url = (
        "https://api.nasdaq.com/api/quote/SPY/historical"
        "?assetclass=etf&fromdate=2016-01-01&todate=2026-12-31&limit=5000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    (RAW / "SPY_nasdaq.json").write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
    rows = obj["data"]["tradesTable"]["rows"]
    pairs = []
    for r in rows:
        try:
            date = pd.to_datetime(r["date"], format="%m/%d/%Y")
            close = float(str(r["close"]).replace("$", "").replace(",", ""))
            pairs.append((date, close))
        except (TypeError, ValueError):
            continue
    s = pd.Series(dict(pairs), dtype="float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def main() -> None:
    mmf = dbnomics("Z1/FL634090005.Q")
    market = dbnomics("Z1/LM103164105.Q")
    deposits = dbnomics("H8/B1058NCBA")

    deposits_q = deposits.resample("QE").last()
    df = pd.concat({"mmf": mmf, "market": market, "deposits": deposits_q}, axis=1).sort_index()
    df = df.dropna()
    df = df[(df["mmf"] > 0) & (df["market"] > 0)]
    df["ratio"] = (df["mmf"] + df["deposits"]) / df["market"]
    df["avg4"] = df["ratio"].rolling(4).mean()

    sp = shiller_sp500()
    sp_q = sp.resample("QE").last()
    spy_daily = nasdaq_spy()
    spy_q = spy_daily.resample("QE").last()
    spy_proxy = (sp_q / 10).rename("spy")
    spy = spy_q.combine_first(spy_proxy).rename("spy")
    df = df.join(spy, how="left")
    df = df[df.index >= "1975-01-01"]

    # Estimated weekly series. Numerator: MMF interpolated from quarterly
    # Z.1 plus weekly H.8 deposits. Denominator: latest quarterly Z.1 market
    # value scaled by a weekly equity index (Shiller pre-2016, SPY 2016+).
    sp_m = sp.resample("ME").last()
    spy_m = spy_daily.resample("ME").last()
    ret_m = sp_m.pct_change()
    ret_m.update(spy_m.pct_change())
    sp_level_m = (1 + ret_m.fillna(0)).cumprod() * 100

    last_day = deposits.index[-1]
    weeks = pd.date_range("1975-01-03", last_day, freq="W-FRI")
    sp_week = sp_level_m.resample("W-FRI").ffill().reindex(weeks).ffill()
    spy_week = spy_daily.resample("W-FRI").last().reindex(weeks)
    ret_w = sp_week.pct_change()
    ret_w.update(spy_week.pct_change())
    sp_level_w = (1 + ret_w.fillna(0)).cumprod() * 100
    sp_q_w = sp_level_w.resample("QE").last().reindex(weeks, method="ffill")
    market_w = market.reindex(weeks, method="ffill")
    mmf_w = mmf.reindex(weeks).interpolate(method="time").ffill()
    dep_w = deposits.reindex(weeks, method="ffill")
    market_est = market_w * sp_level_w / sp_q_w
    ratio_w = (mmf_w + dep_w) / market_est
    avg13 = ratio_w.rolling(13).mean()
    spy_w = (sp_level_w / 10)
    spy_w.update(spy_week)

    weekly_rows = []
    for dt in weeks:
        weekly_rows.append({
            "d": dt.strftime("%Y-%m-%d"),
            "ratio": round(float(ratio_w.loc[dt]), 4),
            "avg13": None if pd.isna(avg13.loc[dt]) else round(float(avg13.loc[dt]), 4),
            "spy": None if pd.isna(spy_w.loc[dt]) else round(float(spy_w.loc[dt]), 2),
        })
    rows = []
    for dt, r in df.iterrows():
        rows.append({
            "d": dt.strftime("%Y-%m-%d"),
            "ratio": round(float(r["ratio"]), 4),
            "avg4": None if pd.isna(r["avg4"]) else round(float(r["avg4"]), 4),
            "spy": None if pd.isna(r["spy"]) else round(float(r["spy"]), 2),
        })

    latest = df.iloc[-1]
    payload = {
        "meta": {
            "as_of": df.index[-1].strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "start": df.index[0].strftime("%Y-%m-%d"),
            "observations": int(len(df)),
            "latest_ratio": round(float(latest["ratio"]), 4),
            "latest_avg4": round(float(latest["avg4"]), 4),
            "latest_spy": round(float(latest["spy"]), 2) if pd.notna(latest["spy"]) else None,
            "sources": [
                {"label": "FRED / Z.1 · 货币市场基金总资产（FL634090005.Q）", "url": "https://fred.stlouisfed.org/series/FL634090005Q"},
                {"label": "FRED / Z.1 · 非金融企业股票市值（LM103164105.Q）", "url": "https://fred.stlouisfed.org/series/LM103164105Q"},
                {"label": "FRED / H.8 · 全部商业银行存款（B1058NCBA）", "url": "https://fred.stlouisfed.org/series/DPSACBW027SBOG"},
                {"label": "Robert Shiller / Yale · S&P 500 月线（2016 年前 SPY 代理）", "url": "http://www.econ.yale.edu/~shiller/data.htm"},
                {"label": "Nasdaq · SPY 日线（2016 年后）", "url": "https://www.nasdaq.com/market-activity/etf/spy/historical"},
            ],
            "notes": [
                "现金 = 货币市场基金总资产 + 全部商业银行存款；分母 = 美国非金融企业股票市值。",
                "比率为季度末数据；4 季度平均用于平滑。",
                "SPY 线：2016 年前用 Shiller S&P 500 / 10 代理，2016 年后用 Nasdaq 的实际 SPY 收盘价。",
                "最新季度为非金融企业股票市值的最新 Z.1 观测，可能滞后于当周 H.8 存款。",
            ],
        },
        "series": rows,
        "weekly": weekly_rows,
        "estimated": {
            "as_of": weeks[-1].strftime("%Y-%m-%d"),
            "latest_ratio": round(float(ratio_w.iloc[-1]), 4),
            "latest_avg13": round(float(avg13.iloc[-1]), 4),
            "latest_spy": round(float(spy_w.iloc[-1]), 2) if pd.notna(spy_w.iloc[-1]) else None,
            "note": "Estimated: MMF interpolated from quarterly Z.1, deposits weekly H.8, market value scaled from quarterly Z.1 by a weekly equity index. Not an official weekly series.",
        },
    }
    (SITE_DATA / "cash_equity.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SITE_DATA / "cash_equity.js").write_text("window.CASH_EQUITY = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    print(f"{len(rows)} quarters · {rows[0]['d']} → {rows[-1]['d']}")
    print(f"ratio {latest['ratio']:.3f} · avg4 {latest['avg4']:.3f} · spy {latest['spy']:.2f}")
    print(f"estimated weekly {weeks[0].date()} → {weeks[-1].date()} · {ratio_w.iloc[-1]:.3f}")


if __name__ == "__main__":
    main()
