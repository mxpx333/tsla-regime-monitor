# TSLA Regime Monitor

Daily auto-updated page that tells me which trading patterns to take or skip today, based on TSLA's current regime.

Live page: https://mxpx333.github.io/tsla-regime-monitor/

## How it works

1. GitHub Actions runs `generate.py` every weekday at 5:30 AM CT.
2. The script pulls TSLA daily OHLC from Yahoo Finance.
3. It computes two regimes:
   - **v1** (short-term): position vs 20-SMA, plus 5-day slope of 20-SMA
   - **v3** (long-term): position vs 50-SMA, plus 20-day slope of 50-SMA
4. It applies the four S11 skip rules and writes `docs/index.html`.
5. GitHub Pages serves the page from `docs/`.

## The S11 skip rules

| Pattern | Skip when... |
|---|---|
| 1-min PLTR | v1 is UP |
| 1-min Cross-In Long | v1 is DOWN |
| 1-min Cross-In Short | v1 is SIDE |
| 1-min Low Break | v3 is UP AND v1 is UP or DOWN |
| Everything else | Never skip |

Backtested over 201 trades, 1/3/2025 to 4/27/2026: WR rises from 74.1 percent to 78.4 percent, max drawdown drops from 15.4 percent to 8.2 percent.

## Local run

```
pip install -r requirements.txt
python generate.py
open docs/index.html
```
