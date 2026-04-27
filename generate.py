"""
Generate the daily TSLA regime monitor HTML page.
Runs in GitHub Actions at 5:30 AM CT each weekday.
Writes docs/index.html.
"""
import warnings
warnings.filterwarnings("ignore")

import base64
from datetime import datetime
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd


# ---------- regime classifier ----------

def classify(df):
    df = df.copy()
    df["sma20"] = df["Close"].rolling(20).mean()
    df["sma50"] = df["Close"].rolling(50).mean()
    df["sma20_5d"] = df["sma20"].shift(5)
    df["sma50_20d"] = df["sma50"].shift(20)

    def v1(r):
        if pd.isna(r["sma20"]) or pd.isna(r["sma20_5d"]): return "?"
        a = r["Close"] > r["sma20"]; rising = r["sma20"] > r["sma20_5d"]
        if a and rising: return "UP"
        if (not a) and (not rising): return "DOWN"
        return "SIDE"

    def v3(r):
        if pd.isna(r["sma50"]) or pd.isna(r["sma50_20d"]): return "?"
        a = r["Close"] > r["sma50"]; rising = r["sma50"] > r["sma50_20d"]
        if a and rising: return "UP"
        if (not a) and (not rising): return "DOWN"
        return "SIDE"

    df["v1"] = df.apply(v1, axis=1)
    df["v3"] = df.apply(v3, axis=1)
    return df


# ---------- chart ----------

def make_chart_b64(df):
    last = df.iloc[-90:]
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
    ax.plot(last.index, last["Close"], color="#000000", linewidth=1.6, label="TSLA close")
    ax.plot(last.index, last["sma20"], color="#FE5C02", linewidth=1.4, label="20-day SMA")
    ax.plot(last.index, last["sma50"], color="#2B7FFF", linewidth=1.4, label="50-day SMA")

    cur = last.iloc[-1]
    ax.scatter([last.index[-1]], [float(cur["Close"])],
               color="#000000", s=70, zorder=5)
    ax.annotate(f"  ${float(cur['Close']):.2f}",
                (last.index[-1], float(cur["Close"])),
                fontsize=10, fontweight="bold")

    ax.set_title("TSLA, last 90 trading days", fontsize=13, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    ax.grid(True, alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return base64.b64encode(buf.read()).decode("ascii")


# ---------- rules ----------

PATTERN_LIBRARY = [
    {"name": "3-min W",            "direction": "long",    "always_take": True},
    {"name": "3-min W200",         "direction": "long",    "always_take": True},
    {"name": "3-min 50T",          "direction": "long",    "always_take": True},
    {"name": "3-min M3",           "direction": "long",    "always_take": True},
    {"name": "3-min dW",           "direction": "long",    "always_take": True},
    {"name": "3-min dM",           "direction": "long",    "always_take": True},
    {"name": "3-min DownShelf",    "direction": "short",   "always_take": True},
    {"name": "3-min C",            "direction": "bi",      "always_take": True},
    {"name": "1-min Low Break",    "direction": "short",   "always_take": False, "rule": "low_break"},
    {"name": "1-min Cross-In Long",  "direction": "long",  "always_take": False, "rule": "xlong"},
    {"name": "1-min Cross-In Short", "direction": "short", "always_take": False, "rule": "xshort"},
    {"name": "1-min PLTR",         "direction": "bi",      "always_take": False, "rule": "pltr"},
]


def verdict(p, v1, v3):
    if p.get("always_take"):
        return ("TAKE", "no regime restriction")
    rule = p["rule"]
    if rule == "pltr":
        if v1 == "UP":
            return ("SKIP", "v1 is UP, PLTR cell here is 43% WR (3W/4L)")
        return ("TAKE", f"v1 is {v1}, PLTR runs at 73% outside UP")
    if rule == "xlong":
        if v1 == "DOWN":
            return ("SKIP", "v1 is DOWN, Cross-In Long cell here is 50% (1W/1L)")
        return ("TAKE", f"v1 is {v1}, Cross-In Long is 100% outside DOWN")
    if rule == "xshort":
        if v1 == "SIDE":
            return ("SKIP", "v1 is SIDE, Cross-In Short cell here is 50% (1W/1L)")
        return ("TAKE", f"v1 is {v1}, Cross-In Short is 100% outside SIDE")
    if rule == "low_break":
        if v3 == "UP" and v1 in ("UP", "DOWN"):
            return ("SKIP", f"v3 is UP and v1 is {v1}, Low Break cell here is 43% (6W/8L)")
        return ("TAKE", f"v3 is {v3} and v1 is {v1}, Low Break safe in this combo")
    return ("TAKE", "")


# ---------- HTML ----------

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TSLA Regime Monitor</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    margin: 0; padding: 0; background: #f7f7f8; color: #1a1a1a;
  }}
  .container {{ max-width: 980px; margin: 0 auto; padding: 24px 16px 60px; }}
  header {{ border-bottom: 1px solid #e5e5e7; padding-bottom: 16px; margin-bottom: 24px; }}
  h1 {{ margin: 0 0 6px 0; font-size: 28px; color: #FE5C02; letter-spacing: -0.5px; }}
  .date {{ font-size: 18px; font-weight: 600; margin: 0; color: #1a1a1a; }}
  .updated {{ font-size: 13px; color: #6c6c70; margin: 4px 0 0 0; }}
  h2 {{ font-size: 18px; margin: 24px 0 10px 0; color: #FE5C02; text-transform: uppercase; letter-spacing: 0.5px; }}
  .snapshot {{
    background: white; border-radius: 10px; padding: 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 8px; }}
  .stat {{ }}
  .stat .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c6c70; }}
  .stat .value {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}
  .stat .sub {{ font-size: 12px; color: #6c6c70; margin-top: 2px; }}

  .regimes {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0 0 0; }}
  .card {{
    background: white; border-radius: 10px; padding: 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    border-top: 4px solid #ccc;
  }}
  .card.UP {{ border-top-color: #0b8040; }}
  .card.DOWN {{ border-top-color: #c0392b; }}
  .card.SIDE {{ border-top-color: #FE5C02; }}
  .card .lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c6c70; margin: 0 0 4px 0; }}
  .card .reg {{ font-size: 36px; font-weight: 800; letter-spacing: -1px; margin: 0; }}
  .card.UP .reg {{ color: #0b8040; }}
  .card.DOWN .reg {{ color: #c0392b; }}
  .card.SIDE .reg {{ color: #FE5C02; }}
  .card .desc {{ font-size: 13px; color: #6c6c70; margin: 6px 0 0 0; }}

  .chart {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-top: 16px; }}
  .chart img {{ width: 100%; height: auto; display: block; }}

  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
  th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid #f0f0f2; font-size: 14px; }}
  th {{ background: #f7f7f8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c6c70; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }}
  .badge.TAKE {{ background: #dcf5e6; color: #0b8040; }}
  .badge.SKIP {{ background: #fde2dd; color: #c0392b; }}
  .dir {{ font-size: 12px; color: #6c6c70; }}

  .footer {{ margin-top: 30px; padding-top: 16px; border-top: 1px solid #e5e5e7; font-size: 12px; color: #6c6c70; }}
  .footer code {{ background: #f0f0f2; padding: 1px 5px; border-radius: 3px; font-size: 11px; }}
  @media (max-width: 600px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .regimes {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">

<header>
  <h1>TSLA Regime Monitor</h1>
  <p class="date">{long_date}</p>
  <p class="updated">Updated {update_time} ET, based on TSLA close {asof_close}</p>
</header>

<section class="snapshot">
  <div class="stats">
    <div class="stat"><div class="label">TSLA Close</div><div class="value">${close:.2f}</div></div>
    <div class="stat">
      <div class="label">20-day SMA</div>
      <div class="value">${sma20:.2f}</div>
      <div class="sub">{slope20} (was ${sma20_5d:.2f} 5d ago)</div>
    </div>
    <div class="stat">
      <div class="label">50-day SMA</div>
      <div class="value">${sma50:.2f}</div>
      <div class="sub">{slope50} (was ${sma50_20d:.2f} 20d ago)</div>
    </div>
    <div class="stat">
      <div class="label">Position</div>
      <div class="value">{pos20} 20</div>
      <div class="sub">{pos50} 50</div>
    </div>
  </div>
</section>

<div class="regimes">
  <div class="card {v1}">
    <p class="lbl">Short-term regime (v1)</p>
    <p class="reg">{v1}</p>
    <p class="desc">Position vs 20-SMA, plus 5-day slope of the 20-SMA</p>
  </div>
  <div class="card {v3}">
    <p class="lbl">Long-term regime (v3)</p>
    <p class="reg">{v3}</p>
    <p class="desc">Position vs 50-SMA, plus 20-day slope of the 50-SMA</p>
  </div>
</div>

<div class="chart">
  <img alt="TSLA chart with 20-SMA and 50-SMA" src="data:image/png;base64,{chart_b64}" />
</div>

<h2>Today's pattern verdicts</h2>
<table>
  <thead>
    <tr><th>Pattern</th><th>Direction</th><th>Verdict</th><th>Reason</th></tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>

<h2>Reference: how each rule works</h2>
<table>
  <thead>
    <tr><th>Pattern</th><th>Skip when...</th><th>Always trade when...</th></tr>
  </thead>
  <tbody>
    <tr><td>1-min PLTR</td><td>v1 = UP</td><td>v1 is DOWN or SIDE</td></tr>
    <tr><td>1-min Cross-In Long</td><td>v1 = DOWN</td><td>v1 is UP or SIDE</td></tr>
    <tr><td>1-min Cross-In Short</td><td>v1 = SIDE</td><td>v1 is UP or DOWN</td></tr>
    <tr><td>1-min Low Break</td><td>v3 = UP and v1 is UP or DOWN</td><td>all other regime combos</td></tr>
    <tr><td>3-min W, W200, 50T, M3, dW, dM, DownShelf, C</td><td>(never skip)</td><td>always take if signal triggers</td></tr>
  </tbody>
</table>

<div class="footer">
  <p>Page auto-updates each weekday at 5:30 AM CT via GitHub Actions, before market open at 8:30 AM CT. Source: <code>generate.py</code> in this repo.</p>
  <p>S11 surgical regime filter, baseline backtest 1/3/2025 to 4/27/2026, 201 trades, 78.4% WR with these filters applied vs 74.1% baseline.</p>
</div>

</div>
</body>
</html>
"""


def main():
    df = yf.download("TSLA", period="9mo", progress=False, auto_adjust=False)
    if df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = classify(df)
    cur = df.iloc[-1]
    d5 = df.iloc[-6]
    d20 = df.iloc[-21]

    asof = df.index[-1].strftime("%Y-%m-%d")
    long_date = datetime.now().strftime("%A, %B %-d, %Y")
    update_time = datetime.now().strftime("%I:%M %p")

    rows = []
    for p in PATTERN_LIBRARY:
        v, why = verdict(p, cur["v1"], cur["v3"])
        dir_label = {"long": "long", "short": "short", "bi": "bidirectional"}[p["direction"]]
        rows.append(
            f'<tr><td><strong>{p["name"]}</strong></td>'
            f'<td class="dir">{dir_label}</td>'
            f'<td><span class="badge {v}">{v}</span></td>'
            f'<td>{why}</td></tr>'
        )

    chart_b64 = make_chart_b64(df)

    html = PAGE.format(
        long_date=long_date,
        update_time=update_time,
        asof_close=asof,
        close=float(cur["Close"]),
        sma20=float(cur["sma20"]),
        sma50=float(cur["sma50"]),
        sma20_5d=float(d5["sma20"]),
        sma50_20d=float(d20["sma50"]),
        slope20="RISING" if cur["sma20"] > d5["sma20"] else "FALLING",
        slope50="RISING" if cur["sma50"] > d20["sma50"] else "FALLING",
        pos20="ABOVE" if cur["Close"] > cur["sma20"] else "BELOW",
        pos50="ABOVE" if cur["Close"] > cur["sma50"] else "BELOW",
        v1=cur["v1"],
        v3=cur["v3"],
        chart_b64=chart_b64,
        rows="\n    ".join(rows),
    )

    out_path = "docs/index.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Wrote {out_path}: regime v1={cur['v1']}, v3={cur['v3']}, asof close={asof}")

if __name__ == "__main__":
    main()
