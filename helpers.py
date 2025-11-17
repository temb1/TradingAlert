import json
import os
from config import BACKTEST_MEMORY_FILE, BACKTEST_STATS

def _to_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace("%", "").strip())
    except Exception:
        return default

def load_backtest_memory():
    if not os.path.exists(BACKTEST_MEMORY_FILE):
        return {}
    try:
        with open(BACKTEST_MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_backtest_memory(mem):
    try:
        with open(BACKTEST_MEMORY_FILE, "w") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        print("⚠️ Cannot save memory:", e)

def get_backtest_stats(ticker, pattern):
    ticker = ticker.upper()
    pattern = pattern.strip()

    # 1) Try dynamic memory first
    mem = load_backtest_memory()
    key = f"{ticker}:{pattern}"
    if key in mem:
        return mem[key]

    # 2) Fall back to static priors
    if ticker in BACKTEST_STATS and pattern in BACKTEST_STATS[ticker]:
        st = BACKTEST_STATS[ticker][pattern]
        return {
            "ticker": ticker,
            "pattern": pattern,
            "total_trades": st["trades"],
            "winrate_pct": st["winrate"],
            "avg_rr": st["avg_rr"],
        }
    return None
