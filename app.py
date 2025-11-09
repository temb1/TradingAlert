import os
import json
import datetime

import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ---------- Setup ----------

app = Flask(__name__)
client = OpenAI()  # Uses OPENAI_API_KEY from env


# ---------- Helpers ----------

def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


# ---------- Root / Health Check ----------

@app.route("/", methods=["GET"])
def root():
    print("🌐 Health check from", request.remote_addr)
    return "TV webhook is running.\n", 200


# ---------- TradingView Webhook ----------

@app.route("/tvhook", methods=["POST"])
def tvhook():
    # 1) Parse JSON from TradingView
    try:
        data = request.get_json(force=True, silent=False)
    except Exception as e:
        print("❌ JSON parse error:", e)
        print("Raw body:", request.data)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not isinstance(data, dict):
        print("⚠️ Empty or non-dict payload:", data)
        return jsonify({"ok": False, "error": "empty_or_invalid_payload"}), 400

    print("✅ ALERT received:", data)

    # 2) Build agent decision using OpenAI
    agent_reply = build_agent_reply(data)

    print("AGENT decision:", json.dumps(agent_reply, indent=2))

    # 3) Send nicely formatted message to Discord
    send_to_discord(data, agent_reply)

    # 4) Return to TradingView / caller
    return jsonify({"ok": True, "agent": agent_reply}), 200


# ---------- Agent Logic (OpenAI) ----------

def build_agent_reply(alert_data: dict) -> dict:
    """
    Calls OpenAI to decide long / short / ignore for a 3-1 / AMD style alert.
    Returns a dict matching the required JSON schema.
    """

    ticker   = str(alert_data.get("ticker", "UNKNOWN"))
    interval = str(alert_data.get("interval", ""))
    pattern  = str(alert_data.get("pattern", ""))
    price    = _to_float(alert_data.get("close"))
    ib_high  = _to_float(alert_data.get("ib_high"))
    ib_low   = _to_float(alert_data.get("ib_low"))
    raw_msg  = str(alert_data.get("message", ""))

    ib_range = None
    if ib_high is not None and ib_low is not None:
        ib_range = ib_high - ib_low

    context = f"""
Alert data:
- Ticker: {ticker}
- Interval: {interval}
- Pattern: {pattern}
- Current close: {price}
- Inside bar high: {ib_high}
- Inside bar low: {ib_low}
- Inside bar range: {ib_range}
- Raw message: {raw_msg}
"""

    system_prompt = """
You are an intraday trading assistant for a small account trader (~$10-25 risk per trade).
You receive alerts primarily for:
- 3-1 inside bar breakout setups (on 5m)
- AMD-style accumulation/manipulation/distribution breakouts (pattern names may start with 'amd_').

Your job on each alert:
1. Decide if there is ONE high-quality trade (long OR short).
2. If nothing is clean, respond with direction="ignore".
3. Keep things simple, realistic, and picky.

CORE RULES:

1) Reward-to-Risk (R:R)
- For 3-1:
  * long_entry  = ib_high
  * long_stop   = ib_low
  * short_entry = ib_low
  * short_stop  = ib_high
- Use risk = |entry - stop|.
- Require realistic potential for at least 2R in that direction.
- If you cannot justify >= 2R, use direction="ignore".

2) Trend / Context
- Prefer trading in line with obvious momentum / trend if implied.
- If unclear or choppy, lean toward "ignore" unless R:R is excellent.

3) Volatility / Quality
- If inside bar range is extremely tiny relative to price, treat as noise → ignore.
- If range is extremely huge (stop too wide for small account), → ignore.

SPECIAL CASES:
- AMD / 'amd_amd_long' or similar:
  * Treat as breakout long from accumulation.
  * Start biased long, but still enforce R:R>=2:1 and sane volatility.
- AMD / 'amd_amd_short':
  * Treat as breakdown short from distribution.
  * Start biased short, same risk rules.
- XSP:
  * Just a smaller SPX; same logic, but remember user risk is small.

OPTIONS HINTS:
- Only suggest simple things:
  * single_option: brief idea (e.g. 'ATM weekly call ~1DTE') or 'n/a'
  * vertical_spread: brief defined-risk spread idea or 'n/a'
- If you are not confident an options structure fits small risk, use 'n/a'.

OUTPUT:
Return ONLY valid JSON (no markdown, no extra keys) with this schema:

{
  "direction": "long" | "short" | "ignore",
  "entry": number or null,
  "stop": number or null,
  "tp1": number or null,
  "tp2": number or null,
  "confidence": "low" | "medium" | "high",
  "single_option": "string",
  "vertical_spread": "string",
  "notes": "short explanation"
}

Rules:
- If direction is "ignore", all numeric fields must be null.
- Be conservative: it's ok to ignore most alerts.
"""

    fallback = {
        "direction": "ignore",
        "entry": None,
        "stop": None,
        "tp1": None,
        "tp2": None,
        "confidence": "low",
        "single_option": "n/a",
        "vertical_spread": "n/a",
        "notes": "Fallback: unable to evaluate."
    }

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=260,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        # Expect JSON; try to parse
        agent = json.loads(raw)
    except Exception as e:
        print("OpenAI / parse error:", e)
        agent = fallback

    # Ensure required keys exist + sane types
    for k, v in fallback.items():
        agent.setdefault(k, v)

    # Hard safety: if direction not valid, force ignore
    if agent.get("direction") not in ["long", "short", "ignore"]:
        agent = fallback

    return agent


# ---------- Discord Formatting & Send ----------

def format_tradingview_embed(alert_data: dict, agent_reply: dict) -> dict:
    """
    Build a clean Discord embed showing alert + agent decision.
    """

    ticker   = str(alert_data.get("ticker", "UNKNOWN"))
    interval = str(alert_data.get("interval", ""))
    pattern  = str(alert_data.get("pattern", ""))
    price    = _to_float(alert_data.get("close"))
    ib_high  = _to_float(alert_data.get("ib_high"))
    ib_low   = _to_float(alert_data.get("ib_low"))

    direction  = str(agent_reply.get("direction", "ignore")).lower()
    confidence = str(agent_reply.get("confidence", "low")).lower()
    notes      = str(agent_reply.get("notes", "") or "")

    # Direction → emoji / color
    if direction == "long":
        emoji = "🟢"
        color = 0x00ff00
    elif direction == "short":
        emoji = "🔴"
        color = 0xff0000
    else:
        emoji = "🟡"
        color = 0xffff00

    # Confidence → emoji
    confidence_emoji = {
        "high": "🎯",
        "medium": "⚠️",
        "low": "🔍"
    }.get(confidence, "❓")

    def fmt(v):
        return f"${v:,.2f}" if isinstance(v, (int, float)) else "n/a"

    details = "\n".join([
        f"**Timeframe:** {interval or 'n/a'}",
        f"**Current Price:** {fmt(price)}",
        f"**Inside Bar High:** {fmt(ib_high)}",
        f"**Inside Bar Low:** {fmt(ib_low)}",
    ])

    reco = "\n".join([
        f"**Direction:** {direction.upper()}",
        f"**Confidence:** {confidence_emoji} {confidence.upper()}",
        f"**TP1:** {agent_reply.get('tp1')}",
        f"**TP2:** {agent_reply.get('tp2')}",
        f"**Stop:** {agent_reply.get('stop')}",
    ])

    title = f"{emoji} {ticker} {pattern}".strip()

    embed = {
        "title": title,
        "color": color,
        "fields": [
            {"name": "📊 Details", "value": details, "inline": False},
            {"name": "🎯 Recommendation", "value": reco, "inline": False},
            {
                "name": "📝 Notes",
                "value": notes[:300] or "No additional notes.",
                "inline": False
            }
        ],
        "footer": {
            "text": "TradingView Agent"
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    return {"embeds": [embed]}


def send_to_discord(alert_data: dict, agent_reply: dict):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ No Discord webhook set (DISCORD_WEBHOOK_URL).")
        return

    try:
        payload = format_tradingview_embed(alert_data, agent_reply)
        res = requests.post(webhook_url, json=payload, timeout=5)
        if res.status_code in (200, 201, 204):
            print("✅ Sent alert to Discord.")
        else:
            print(f"⚠️ Discord HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print("❌ Discord error:", e)


# ---------- Simple Backtest Endpoint ----------

@app.route("/backtest", methods=["POST"])
def backtest():
    """
    Very simple endpoint to ingest historical trade results
    and compute summary stats.

    Expected JSON:
    - either a list of trade objects
    - or {"trades": [ ... ]}

    Each trade may contain:
      - "profit": numeric (positive/negative)
      - "rr": numeric reward:risk (optional)
      - "win": bool (optional; else derived from profit>0)
      - "ticker": string (optional)
    """

    try:
        body = request.get_json(force=True, silent=False)
    except Exception as e:
        print("❌ Backtest JSON parse error:", e)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if isinstance(body, dict) and "trades" in body:
        trades = body["trades"]
    else:
        trades = body

    if not isinstance(trades, list) or not trades:
        return jsonify({"ok": False, "error": "no_trades"}), 400

    total = len(trades)
    wins = 0
    losses = 0
    rr_sum = 0.0
    rr_count = 0

    for t in trades:
        if not isinstance(t, dict):
            continue
        profit = _to_float(t.get("profit"))
        rr     = _to_float(t.get("rr"))
        win    = t.get("win")

        if rr is not None:
            rr_sum += rr
            rr_count += 1

        if win is True:
            wins += 1
        elif win is False:
            losses += 1
        elif profit is not None:
            if profit > 0:
                wins += 1
            elif profit < 0:
                losses += 1

    winrate = (wins / total * 100.0) if total > 0 else 0.0
    avg_rr  = (rr_sum / rr_count) if rr_count > 0 else None

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


# ---------- Run (local dev) ----------

if __name__ == "__main__":
    # For local testing only; Render will use gunicorn.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
