import os
import json
import csv
import io
import datetime
import requests

from flask import Flask, request, jsonify
from openai import OpenAI

# ==========================================================
# CONFIG
# ==========================================================

app = Flask(__name__)
client = OpenAI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BACKTEST_MEMORY_FILE = "backtest_memory.json"

# ==========================================================
# STATIC 3–1 BACKTEST PRIORS
# (Ultra-selective: used to filter low-quality patterns fast)
# ==========================================================

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

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

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

# ==========================================================
# DISCORD EMBED BUILDER
# ==========================================================

def make_discord_embed(alert_data, agent_reply):
    """Generate a clean Discord embed with option suggestions."""

    if isinstance(agent_reply, str):
        try:
            agent = json.loads(agent_reply)
        except Exception:
            agent = {}
    else:
        agent = agent_reply or {}

    direction = (agent.get("direction") or "ignore").lower()
    confidence = (agent.get("confidence") or "low").lower()

    # Colors
    if direction == "long":
        emoji = "🟢"
        color = 0x00ff00
    elif direction == "short":
        emoji = "🔴"
        color = 0xff0000
    else:
        emoji = "🟡"
        color = 0xffff00

    conf_emoji = {"high": "🎯", "medium": "⚠️", "low": "🔍"}.get(confidence, "❓")

    ticker = alert_data.get("ticker", "UNKNOWN")
    interval = alert_data.get("interval", "?")
    pattern = alert_data.get("pattern", "?")

    price = _to_float(alert_data.get("close"))
    ib_high = _to_float(alert_data.get("ib_high"))
    ib_low = _to_float(alert_data.get("ib_low"))
    box_high = _to_float(alert_data.get("box_high"))
    box_low = _to_float(alert_data.get("box_low"))

    def fmt(v):
        return f"${v:,.2f}" if isinstance(v, (float, int)) else "n/a"

    fields = []

    # DETAILS SECTION
    detail_text = f"**Timeframe:** {interval}\n**Current Price:** {fmt(price)}"
    if ib_high is not None:
        detail_text += f"\n**IB High:** {fmt(ib_high)}\n**IB Low:** {fmt(ib_low)}"
    if box_high is not None:
        detail_text += f"\n**Box High:** {fmt(box_high)}\n**Box Low:** {fmt(box_low)}"
        
    fields.append({
        "name": "📊 Details",
        "value": detail_text,
        "inline": False
    })

    # RECOMMENDATION SECTION
    fields.append({
        "name": "🎯 Recommendation",
        "value": (
            f"**Direction:** {direction.upper()}\n"
            f"**Confidence:** {conf_emoji} {confidence.upper()}\n"
            f"**Entry:** {fmt(agent.get('entry'))}\n"
            f"**Stop:** {fmt(agent.get('stop'))}\n"
            f"**TP1:** {fmt(agent.get('tp1'))}\n"
            f"**TP2:** {fmt(agent.get('tp2'))}\n"
            f"**Single Option:** {agent.get('single_option')}\n"
            f"**Vertical Spread:** {agent.get('vertical_spread')}"
        ),
        "inline": False
    })

    # NOTES SECTION
    fields.append({
        "name": "📝 Notes",
        "value": agent.get("notes", "n/a"),
        "inline": False
    })

    embed = {
        "title": f"{emoji} {ticker} {pattern}",
        "color": color,
        "fields": fields,
        "footer": {"text": "TradingView AI Agent"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    return {"embeds": [embed]}


def send_to_discord(alert_data, agent_reply):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook set.")
        return

    try:
        payload = make_discord_embed(alert_data, agent_reply)
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=8)
        if res.status_code < 300:
            print("✅ Sent alert to Discord.")
        else:
            print("⚠️ Discord error:", res.status_code, res.text)
    except Exception as e:
        print("❌ Discord exception:", e)


# ==========================================================
# ROUTES
# ==========================================================

@app.route("/", methods=["GET", "POST"])
def root():
    return "TV webhook running.\n", 200


@app.route("/health", methods=["GET", "HEAD"])
def health_check():  # CHANGED FUNCTION NAME
    return jsonify({
        "ok": True,
        "service": "TradingView Agent",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200


# ==========================================================
# MAIN TRADINGVIEW WEBHOOK ENDPOINT
# ==========================================================

@app.route("/tvhook", methods=["POST"])
def tvhook():
    """Receives BOTH 3-1 and AMD alerts from TradingView."""
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print("❌ JSON Error:", e)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not data:
        print("⚠️ Empty payload")
        return jsonify({"ok": False, "error": "empty_payload"}), 400

    print("🔥 ALERT:", data)

    # Extract payload
    ticker = str(data.get("ticker", "UNKNOWN")).upper()
    interval = str(data.get("interval", ""))
    pattern = str(data.get("pattern", "")).strip()

    price = _to_float(data.get("close"))
    ib_high = _to_float(data.get("ib_high"))
    ib_low = _to_float(data.get("ib_low"))
    box_high = _to_float(data.get("box_high"))
    box_low = _to_float(data.get("box_low"))
    atr = _to_float(data.get("atr"))
    raw_msg = str(data.get("message", ""))

    # Basic ranges
    ib_range = None
    if ib_high is not None and ib_low is not None:
        ib_range = ib_high - ib_low

    # Pull backtest priors
    hist = get_backtest_stats(ticker, pattern)
    hist_text = ""
    if hist:
        hist_text = (
            f"\n\nHistorical stats:"
            f"\n- Trades: {hist.get('total_trades')}"
            f"\n- Winrate: {hist.get('winrate_pct')}%"
            f"\n- Avg R:R: {hist.get('avg_rr')}"
        )

    # ------------------------------------------------------
    # CONTEXT FOR THE MODEL
    # ------------------------------------------------------
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

    # ------------------------------------------------------
    # SYSTEM PROMPT (agent brain)
    # ------------------------------------------------------
    system_prompt = """
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
1) **3-1 Logic**
- long_entry = ib_high
- long_stop = ib_low
- short_entry = ib_low
- short_stop = ib_high
- Require clear room for **≥2R**
- Reject if IB range is:
  - Too tiny (noise)
  - Too wide (risk > user limit)

2) **AMD Logic (Stocks & ETFs)**
- amd_breakout_long → prefer long if structure OK
- amd_breakout_short → prefer short
- Use:
  - box_high, box_low
  - ATR
  - Box age
  - Volume spike
  - Spring strength
- Reject if sloppy, late, or low R:R

3) **Use Backtest Priors**
- If winrate < 35% or avg_rr < 1.5 → VERY strict  
- If winrate > 45% & avg_rr > 2 → take clean setups confidently  
- Priors cannot override bad structure

4) **Trend Filter**
- Trend up → prefer long  
- Trend down → prefer short  
- If unclear → be picky / ignore

5) **Options Logic**
- Single call/put only if cost ≤ $70  
- Vertical spreads: debit spreads only, 1–5 strikes wide  
- No far OTM  
- Expiry: same week (0–1 DTE)

OUTPUT (STRICT JSON):
{
 "direction": "long" | "short" | "ignore",
 "entry": number or null,
 "stop": number or null,
 "tp1": number or null,
 "tp2": number or null,
 "confidence": "low" | "medium" | "high",
 "single_option": "text or 'n/a'",
 "vertical_spread": "text or 'n/a'",
 "notes": "short explanation"
}
"""

    # ------------------------------------------------------
    # RUN OPENAI
    # ------------------------------------------------------
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=260,
            temperature=0.15,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
        )
        reply_text = resp.choices[0].message.content.strip()
    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        reply_text = json.dumps({
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": "OpenAI error"
        })

    print("AGENT:", reply_text)

    # Send to Discord
    send_to_discord(data, reply_text)

    # Return to TradingView
    try:
        parsed = json.loads(reply_text)
    except:
        parsed = {"raw": reply_text}

    return jsonify({"ok": True, "agent": parsed})


# ==========================================================
# /backtest — INGEST & LEARN FROM BACKTEST FILES
# ==========================================================

@app.route("/backtest", methods=["POST"])
def backtest():
    """
    Accepts:
      - CSV body (TradingView export)
      - or JSON body with { trades: [...] } or list of trades
    Optional:
      - ?ticker=AMD override
    Computes:
      - total trades
      - wins / losses
      - winrate pct
      - avg_rr (run-up / drawdown)
    Saves to backtest_memory.json
    """

    ticker_hint = request.args.get("ticker", "").upper().strip()
    content_type = request.headers.get("Content-Type", "")
    raw = request.data

    rows = []

    # 1) JSON upload
    if "application/json" in content_type:
        try:
            payload = json.loads(raw.decode("utf-8"))

            if isinstance(payload, dict) and "trades" in payload:
                rows = payload["trades"]

            elif isinstance(payload, list):
                rows = payload

            else:
                return jsonify({"ok": False, "error": "invalid_json_structure"}), 400

        except Exception as e:
            print("❌ JSON error in /backtest:", e)
            return jsonify({"ok": False, "error": "bad_json"}), 400

    # 2) CSV upload
    else:
        try:
            text = raw.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
        except Exception as e:
            print("❌ CSV error in /backtest:", e)
            return jsonify({"ok": False, "error": "bad_csv"}), 400

    if not rows:
        return jsonify({"ok": False, "error": "no_rows"}), 400

    # ======================================================
    # AGGREGATION
    # ======================================================

    summary = {}

    for r in rows:
        row_ticker = (r.get("ticker") or r.get("Ticker") or ticker_hint or "UNKNOWN").upper()

        pattern = (
            r.get("pattern")
            or r.get("Pattern")
            or r.get("Signal")
            or ""
        ).strip() or "unknown"

        key = f"{row_ticker}:{pattern}"

        if key not in summary:
            summary[key] = {
                "ticker": row_ticker,
                "pattern": pattern,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "rr_values": []
            }

        rec = summary[key]
        rec["total_trades"] += 1

        # --- Determine win/loss ---
        pl = None
        if r.get("Net P&L USD") not in (None, ""):
            pl = _to_float(r.get("Net P&L USD"))
        elif r.get("Net P&L %") not in (None, ""):
            pl = _to_float(r.get("Net P&L %"))

        if pl is not None:
            if pl > 0:
                rec["wins"] += 1
            elif pl < 0:
                rec["losses"] += 1

        # --- Compute run-up / drawdown R:R ---
        runup = _to_float(r.get("Run-up %") or r.get("Run up %") or r.get("Run-up%"))
        drawdown_raw = _to_float(r.get("Drawdown %") or r.get("Drawdown%"))

        if runup is not None and drawdown_raw not in (None, 0) and runup > 0:
            rr = runup / abs(drawdown_raw)
            if 0 < rr < 20:
                rec["rr_values"].append(rr)

    # ======================================================
    # FINALISE + SAVE MEMORY
    # ======================================================

    memory = load_backtest_memory()
    out = []

    for key, rec in summary.items():
        total = rec["total_trades"]
        wins = rec["wins"]
        losses = rec["losses"]

        winrate = round((wins / total) * 100, 2) if total > 0 else 0
        avg_rr = round(sum(rec["rr_values"]) / len(rec["rr_values"]), 2) if rec["rr_values"] else None

        result = {
            "ticker": rec["ticker"],
            "pattern": rec["pattern"],
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate,
            "avg_rr": avg_rr
        }

        out.append(result)
        memory[key] = result

    save_backtest_memory(memory)

    print("📊 Backtest summary:", out)
    return jsonify({"ok": True, "summary": out}), 200


# ==========================================================
# MAIN (RUN SERVER)
# ==========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
