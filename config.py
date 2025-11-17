import os

# Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BACKTEST_MEMORY_FILE = "backtest_memory.json"

# Static Backtest Priors
BACKTEST_STATS = {
    "AMD": {
        "3-1_breakout_short": {"trades": 207, "winrate": 36.71, "avg_rr": 2.64},
        "3-1_breakout_long":  {"trades": 249, "winrate": 45.38, "avg_rr": 2.85},
    },
    "TSLA": {
        "3-1_breakout_short": {"trades": 234, "winrate": 35.47, "avg_rr": 2.39},
        "3-1_breakout_long":  {"trades": 258, "winrate": 47.67, "avg_rr": 3.12},
    },
    "QQQ": {
        "3-1_breakout_short": {"trades": 124, "winrate": 34.68, "avg_rr": 2.54},
        "3-1_breakout_long":  {"trades": 225, "winrate": 39.56, "avg_rr": 2.71},
    },
    "IWM": {
        "3-1_breakout_short": {"trades": 160, "winrate": 26.88, "avg_rr": 2.61},
        "3-1_breakout_long":  {"trades": 164, "winrate": 34.02, "avg_rr": 2.14},
    },
    "XSP": {
        "3-1_breakout_short": {"trades": 123, "winrate": 38.89, "avg_rr": 2.15},
        "3-1_breakout_long":  {"trades": 143, "winrate": 37.06, "avg_rr": 2.15},
    },
}

# System Prompt
SYSTEM_PROMPT = """
You are a professional intraday AI trading assistant (small account $10–25 risk).
You receive only *high-value* alerts from TradingView:
- 3-1 inside bar breakouts/breakdowns
- AMD accumulation/manipulation/distribution breakouts
- ETF-enhanced AMD alerts (QQQ/IWM/XSP)

Your job:
■ Approve **ONLY high-probability trades**
■ Output ONE direction (long/short) OR "ignore"
■ Compute entry/stop/TP1/TP2
■ Suggest ONE single option + ONE vertical spread
■ Use 100-multiplier equity options (TSLA/AMD/QQQ/IWM/XSP)
■ Maximum option cost = **$70**
■ Vertical spreads 1–5 strikes wide
■ Expiry allowed: **0–1 DTE (same day or next day)**

RULESET SUMMARY:
----------------
[Your full system prompt here...]
"""
