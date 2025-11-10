import os
import json
import datetime
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ========= CONFIG =========

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__)

# ========= HELPERS =========

def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None

def safe_get_json():
    """Parse JSON body safely and log issues."""
    try:
        data = request.get_json(force=True, silent=False)
        if not isinstance(data, (dict, list)):
            raise ValueError("JSON root is not object/array")
        return data, None
    except Exception as e:
        return None, str(e)

def ensure_agent_dict(reply_raw):
    """
    We tell the model to return JSON.
    This turns the raw string into a dict, or falls back to ignore.
    """
    if isinstance(reply_raw, dict):
        return reply_raw

    try:
        parsed = json.loads(reply_raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Fallback: strict ignore
    return {
        "direction": "ignore",
        "entry": None,
        "stop": None,
        "tp1": None,
        "tp2": None,
        "confidence": "low",
        "single_option": "n/a",
        "vertical_spread": "n/a",
        "notes": "Model reply not valid JSON; defaulted to ignore."
    }

def format_discord_embed(alert_data, agent):
    """
    Create a clean Discord embed using both the alert and agent decision.
    """
    ticker   = str(alert_data.get("ticker", "UNKNOWN"))
    interval = str(alert_data.get("interval", ""))
    pattern  = str(alert_data.get("pattern", ""))
    price    = _to_float(alert_data.get("close"))
    ib_high  = _to_float(alert_data.get("ib_high"))
    ib_low   = _to_float(alert_data.get("ib_low"))

    direction   = (agent.get("direction") or "ignore").lower()
    confidence  = (agent.get("confidence") or "low").lower()
    tp1         = agent.get("tp1")
    tp2         = agent.get("tp2")
    stop        = agent.get("stop")
    notes       = agent.get("notes", "")

    # Direction styling
    if direction == "long":
        emoji = "🟢"
        color = 0x00ff00
    elif direction == "short":
        emoji = "🔴"
        color = 0xff0000
    else:
        emoji = "🟡"
        color = 0xffff00

    # Confidence styling
    confidence_emoji = {
        "high": "🎯",
        "medium": "⚠️",
        "low": "🔍",
    }.get(confidence, "❓")

    # Nice text helpers
    def fmt(x):
        return f"${x:,.2f}" if isinstance(x, (int, float)) else "n/a"

    title = f"{emoji} {ticker} {pattern}"

    details_value = (
        f"**Timeframe:** {interval}\n"
        f"**Current Price:** {fmt(price)}\n"
        f"**Inside Bar High:** {fmt(ib_high)}\n"
        f"**Inside Bar Low:** {fmt(ib_low)}"
    )

    rec_lines = [
        f"**Direction:** {direction.upper()}",
        f"**Confidence:** {confidence_emoji} {confidence.upper()}",
        f"**TP1:** {fmt(tp1)}",
        f"**TP2:** {fmt(tp2)}",
        f"**Stop:** {fmt(stop)}",
    ]

    embed = {
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": [
                    {
                        "name": "📊 Details",
                        "value": details_value,
                        "inline": False
                    },
                    {
                        "name": "🎯 Recommendation",
                        "value": "\n".join(rec_lines),
                        "inline": False
                    },
                    {
                        "name": "📝 Notes",
                        "value": notes or "—",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "TradingView Agent"
                },
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }

    return embed

def send_to_discord(alert_data, agent_dict):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No DISCORD_WEBHOOK_URL set; skipping Discord.")
        return

    try:
        payload = format_discord_embed(alert_data, agent_dict)
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if res.status_code in (200, 204):
            print("✅ Sent alert to Discord.")
        else:
            print(f"⚠️ Discord error {res.status_code}: {res.text}")
    except Exception as e:
        print("❌ Discord send exception:", e)

def run_agent(alert_data):
    """
    Core brain: builds prompt, calls OpenAI, returns agent dict.
    """
    if not client:
        print("⚠️ No OPENAI_API_KEY; forcing ignore.")
        return {
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": "Missing OPENAI_API_KEY on server."
        }

    ticker   = str(alert_data.get("ticker", "UNKNOWN"))
    interval = str(alert_data.get("interval", ""))
    pattern  = str(alert_data.get("pattern", ""))
    price    = _to_float(alert_data.get("close"))
    ib_high  = _to_float(alert_data.get("ib_high"))
    ib_low   = _to_float(alert_data.get("ib_low"))
    raw_msg  = str(alert_data.get("message", ""))

    ib_range = (ib_high - ib_low) if (ib_high is not None and ib_low is not None) else None

    context = f"""
Alert data:
- Ticker: {ticker}
- Interval: {interval}
- Pattern: {pattern}
- Close: {price}
- Inside bar high: {ib_high}
- Inside bar low: {ib_low}
- Inside bar range: {ib_range}
- Raw message: {raw_msg}
"""

    system_prompt = """
You are an intraday trading assistant for a small account trader.
You ONLY receive alerts for:

- 3-1 inside bar breakout style patterns
- Occasional AMD A/M/D (accumulation-manipulation-distribution) style alerts
- Underlyings like XSP, QQQ, IWM, AMD, TSLA, BTCUSD (for testing)

Your job:
- Decide if there is a clean, asymmetric trade or if it should be ignored.
- Consider both directions where relevant but PICK ONE or "ignore".
- You must be picky. Fewer strong trades > many weak ones.

Rules (apply strictly):

1) Reward/Risk filter:
   - Long idea: entry ≈ ib_high, stop ≈ ib_low.
   - Short idea: entry ≈ ib_low, stop ≈ ib_high.
   - Risk = |entry - stop|.
   - Only consider if realistic room for >= 2R.
   - If you cannot justify >= 2R, choose "ignore".

2) Trend / context filter:
   - If price/context suggests strong uptrend, favour longs; be strict on shorts.
   - If strong downtrend, favour shorts; be strict on longs.
   - If choppy/unclear, lean "ignore" unless R:R is exceptional.

3) Volatility / quality:
   - If inside bar range is extremely tiny relative to price -> noise -> "ignore".
   - If range is extremely huge -> stop too wide for small risk -> "ignore".

AMD-specific:
- If pattern contains "amd_amd_long", bias long using same R:R + sanity checks.
- If pattern contains "amd_amd_short", bias short using same checks.

XSP:
- Treat as small-sized S&P product. Same technical logic; just favour simple, defined-risk ideas.

Output:
Return ONLY valid JSON with exactly these keys:

{
  "direction": "long" | "short" | "ignore",
  "entry": <number or null>,
  "stop": <number or null>,
  "tp1": <number or null>,
  "tp2": <number or null>,
  "confidence": "low" | "medium" | "high",
  "single_option": "<short text or 'n/a'>",
  "vertical_spread": "<short text or 'n/a'>",
  "notes": "<1-2 short sentences>"
}

If you choose "ignore", all numeric fields must be null and notes must briefly say why.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ],
            max_tokens=260,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        return ensure_agent_dict(raw)
    except Exception as e:
        print("❌ OpenAI error:", e)
        return {
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": "OpenAI API error; ignoring setup."
        }

# ========= ROUTES =========

@app.route("/", methods=["GET"])
def root():
    return "TV webhook is running.\n", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "healthy"}), 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    data, err = safe_get_json()
    if err or not data:
        print("❌ /tvhook bad JSON:", err, "raw:", request.data)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    # Some people send stringified JSON from TradingView; handle that:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass

    if not isinstance(data, dict):
        print("⚠️ /tvhook payload not dict:", data)
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    print("✅ ALERT received:", data)

    agent = run_agent(data)
    print("AGENT decision:", json.dumps(agent, indent=2))

    send_to_discord(data, agent)

    return jsonify({"ok": True, "agent": agent}), 200

@app.route("/backtest", methods=["POST"])
def backtest():
    """
    Very simple endpoint:
    Expect JSON list of trades like:
    [
      {"ticker":"XSP","rr":2.3,"win":true},
      ...
    ]
    We'll compute summary stats.
    """
    trades, err = safe_get_json()
    if err or not isinstance(trades, list):
        return jsonify({"ok": False, "error": "expected_list"}), 400

    total = len(trades)
    wins = 0
    losses = 0
    rr_sum = 0.0
    rr_count = 0

    for t in trades:
        if not isinstance(t, dict):
            continue
        win = t.get("win")
        rr = t.get("rr") or t.get("R") or t.get("r")
        if isinstance(win, bool):
            if win:
                wins += 1
            else:
                losses += 1
        if isinstance(rr, (int, float)):
            rr_sum += rr
            rr_count += 1

    winrate = (wins / total * 100.0) if total > 0 else 0.0
    avg_rr = (rr_sum / rr_count) if rr_count > 0 else None

    summary = {
        "ok": True,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "winrate_pct": round(winrate, 2),
        "avg_rr": round(avg_rr, 2) if avg_rr is not None else None,
    }

    print("📊 Backtest summary:", summary)
    return jsonify(summary), 200

# ========= ENTRYPOINT =========

if __name__ == "__main__":
    # Run with Flask's built-in server (sufficient for this project).
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
