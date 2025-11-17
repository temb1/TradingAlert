import json
import os
import httpx
from openai import OpenAI
from helpers import get_backtest_stats, _to_float
from config import SYSTEM_PROMPT

# Initialize OpenAI client with API key from environment
# Fixed: Using httpx.Client to avoid proxies issue and proper API key handling
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(
    api_key=api_key,
    http_client=httpx.Client()  # Explicit HTTP client to avoid proxies issue
)

def build_agent_context(alert_data):
    """Build context for the AI agent from alert data."""
    ticker = str(alert_data.get("ticker", "UNKNOWN")).upper()
    interval = str(alert_data.get("interval", ""))
    pattern = str(alert_data.get("pattern", "")).strip()

    # Extract numeric data
    price = _to_float(alert_data.get("close"))
    ib_high = _to_float(alert_data.get("ib_high"))
    ib_low = _to_float(alert_data.get("ib_low"))
    box_high = _to_float(alert_data.get("box_high"))
    box_low = _to_float(alert_data.get("box_low"))
    atr = _to_float(alert_data.get("atr"))
    raw_msg = str(alert_data.get("message", ""))

    # Calculate ranges
    ib_range = ib_high - ib_low if ib_high and ib_low else None

    # Get historical stats
    hist = get_backtest_stats(ticker, pattern)
    hist_text = ""
    if hist:
        hist_text = f"\n\nHistorical stats:\n- Trades: {hist.get('total_trades', 'N/A')}\n- Winrate: {hist.get('winrate_pct', 'N/A')}%\n- Avg R:R: {hist.get('avg_rr', 'N/A')}"

    context = f"""
Alert data:
- Ticker: {ticker}
- Interval: {interval}
- Pattern: {pattern}
- Price: {price}
- IB High: {ib_high}
- IB Low: {ib_low}
- IB Range: {ib_range}
- Box High: {box_high}
- Box Low: {box_low}
- ATR: {atr}
- Raw message: {raw_msg}
{hist_text}

Make a decision using ultra-selective mode.
"""
    return context

def get_agent_decision(alert_data):
    """Get trading decision from OpenAI agent."""
    try:
        context = build_agent_context(alert_data)
        
        # Fixed: Using correct model name and proper error handling
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # Fixed model name - was "gpt-4.1-mini"
            max_tokens=260,
            temperature=0.15,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ]
        )
        reply_text = resp.choices[0].message.content.strip()
        print("AGENT:", reply_text)
        return reply_text
        
    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        return json.dumps({
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": f"OpenAI error: {str(e)}"
        })
