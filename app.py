import os
import json
import csv
import io
import datetime

import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ---------- Config ----------

app = Flask(__name__)
client = OpenAI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BACKTEST_MEMORY_FILE = "backtest_memory.json"

# ---------- Static backtest priors ----------
# Based on your uploaded 3-1 strategy exports.
# These are "priors" the agent can lean on when judging a new signal.
# They can be overridden/extended by /backtest uploads.

BACKTEST_STATS = {
    "AMD": {
        "3-1_breakout_short": {  # from 3-1 Short + 3-1S TP/SL
            "trades": 207,
            "winrate": 36.71,
            "avg_rr": 2.64,
        },
        "3-1_breakout_long": {   # from 3-1 Long + 3-1L TP/SL
            "trades": 249,
            "winrate": 45.38,
            "avg_rr": 2.85,
        },
    },
    "TSLA": {
        "3-1_breakout_short": {
            "trades": 234,
            "winrate": 35.47,
            "avg_rr": 2.39,
        },
        "3-1_breakout_long": {
            "trades": 258,
            "winrate": 47.67,
            "avg_rr": 3.12,
        },
    },
    "QQQ": {
        "3-1_breakout_short": {
            "trades": 124,
            "winrate": 34.68,
            "avg_rr": 2.54,
        },
        "3-1_breakout_long": {
            "trades": 225,
            "winrate": 39.56,
            "avg_rr": 2.71,
        },
    },
    "IWM": {
        "3-1_breakout_short": {
            "trades": 160,
            "winrate": 26.88,
            "avg_rr": 2.61,
        },
        "3-1_breakout_long": {
            "trades": 164,
            "winrate": 34.02,
            "avg_rr": 2.14,
        },
    },
    "XSP": {
        "3-1_breakout_short": {
            "trades": 123,
            "winrate": 38.89,
            "avg_rr": 2.15,
        },
        "3-1_breakout_long": {
            "trades": 143,
            "winrate": 37.06,
            "avg_rr": 2.15,
        },
    },
}

# ---------- Helpers ----------

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
    except Exception:
        return {}


def save_backtest_memory(mem):
    try:
        with open(BACKTEST_MEMORY_FILE, "w") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        print("⚠️ Failed to save backtest memory:", e)


def get_backtest_stats(ticker: str, pattern: str):
    """
    Return best-known historical stats for (ticker, pattern).

    Priority:
    1) Dynamic memory from /backtest uploads (exact key match).
    2) Static BACKTEST_STATS priors for 3-1_breakout_long/short.
    """
    ticker = (ticker or "").upper()
    pattern = (pattern or "").strip()

    # 1) Try dynamic memory
    mem = load_backtest_memory()
    key = f"{ticker}:{pattern}"
    rec = mem.get(key)
    if rec:
        return {
            "ticker": ticker,
            "pattern": pattern,
            "trades": rec.get("total_trades"),
            "winrate": rec.get("winrate_pct"),
            "avg_rr": rec.get("avg_rr"),
        }

    # 2) Fallback to static priors (for the breakout patterns)
    static = BACKTEST_STATS.get(ticker, {}).get(pattern)
    if static:
        return {
            "ticker": ticker,
            "pattern": pattern,
            "trades": static.get("trades"),
            "winrate": static.get("winrate"),
            "avg_rr": static.get("avg_rr"),
        }

    return None


def make_discord_embed(alert_data, agent_reply):
    """
    Build a nice embed from alert + agent.
    agent_reply can be JSON text or dict.
    """
    if isinstance(agent_reply, str):
        try:
            agent = json.loads(agent_reply)
        except Exception:
            agent = {}
    else:
        agent = agent_reply or {}

    direction = (agent.get("direction") or "ignore").lower()
    confidence = (agent.get("confidence") or "low").lower()

    if direction == "long":
        emoji = "🟢"
        color = 0x00ff00
    elif direction == "short":
        emoji = "🔴"
        color = 0xff0000
    else:
        emoji = "🟡"
        color = 0xffff00

    conf_emoji = {
        "high": "🎯",
        "medium": "⚠️",
        "low": "🔍"
    }.get(confidence, "❓")

    ticker = alert_data.get("ticker", "UNKNOWN")
    pattern = alert_data.get("pattern", "")
    interval = alert_data.get("interval", "")
    price = _to_float(alert_data.get("close"), default=None)
    ib_high = _to_float(alert_data.get("ib_high"), default=None)
    ib_low = _to_float(alert_data.get("ib_low"), default=None)

    def fmt(x):
        return f"${x:,.2f}" if isinstance(x, (int, float)) else "n/a"

    single_opt = agent.get("single_option") or "n/a"
    vert_spread = agent.get("vertical_spread") or "n/a"
    
    fields = [
        {
            "name": "📊 Details",
            "value": (
                f"**Timeframe:** {interval}\n"
                f"**Current Price:** {fmt(price)}\n"
                f"**Inside Bar High:** {fmt(ib_high)}\n"
                f"**Inside Bar Low:** {fmt(ib_low)}"
            ),
            "inline": False,
        },

{
    "name": "🎯 Recommendation",
    "value": (
        f"**Direction:** {direction.upper()}\n"
        f"**Confidence:** {conf_emoji} {confidence.upper()}\n"
        f"**TP1:** {fmt(agent.get('tp1'))}\n"
        f"**TP2:** {fmt(agent.get('tp2'))}\n"
        f"**Stop:** {fmt(agent.get('stop'))}\n"
        f"**Single option:** {single_opt}\n"
        f"**Vertical spread:** {vert_spread}"
    ),
    "inline": False,
},

        {
            "name": "📝 Notes",
            "value": agent.get("notes", "n/a"),
            "inline": False,
        },
    ]

    embed = {
        "title": f"{emoji} {ticker} {pattern}",
        "color": color,
        "fields": fields,
        "footer": {"text": "TradingView Agent"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    return {"embeds": [embed]}


def send_to_discord(alert_data, agent_reply):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook set.")
        return

    try:
        payload = make_discord_embed(alert_data, agent_reply)
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if 200 <= res.status_code < 300:
            print("✅ Sent alert to Discord.")
        else:
            print(f"⚠️ Discord error {res.status_code}: {res.text}")
    except Exception as e:
        print("❌ Discord exception:", e)


# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def root():
    print("🌐 Hit / from", request.remote_addr, "method:", request.method)
    return "TV webhook is running.\n", 200


# ===== TradingView live webhook =====
@app.route("/tvhook", methods=["POST"])
def tvhook():
    # ---- Parse input ----
    try:
        data = request.get_json(force=True, silent=False)
    except Exception as e:
        print("❌ JSON parse error:", e)
        print("Raw body:", request.data)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not data:
        print("⚠️ Empty payload.")
        return jsonify({"ok": False, "error": "empty_payload"}), 400

    print("✅ ALERT received:", data)

    ticker = str(data.get("ticker", "UNKNOWN")).upper()
    interval = str(data.get("interval", ""))
    pattern = str(data.get("pattern", "")).strip()
    price = _to_float(data.get("close"))
    ib_high = _to_float(data.get("ib_high"))
    ib_low = _to_float(data.get("ib_low"))
    raw_msg = str(data.get("message", ""))

    ib_range = (ib_high - ib_low) if (ib_high is not None and ib_low is not None) else None

    # ---- Historical stats for this setup ----
    hist = get_backtest_stats(ticker, pattern)
    hist_text = ""
    if hist:
        trades = hist.get("trades")
        winrate = hist.get("winrate")
        avg_rr = hist.get("avg_rr")
        hist_text = (
            "\n\nHistorical performance snapshot for this setup:"
            f"\n- Trades: {trades}"
            f"\n- Winrate: {winrate}%"
            f"\n- Avg R:R: {avg_rr}"
        )

    # ---- Build context for the model ----
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
{hist_text}
"""

    # ---- System prompt with explicit use of stats ----
    system_prompt = """
You are an intraday trading assistant for a small account (~$10–25 risk per trade).

You receive alerts only when:
- A 3-1 inside-bar breakout/breakdown pattern triggers, or
- An AMD-style accumulation/manipulation/distribution pattern triggers.

Your job:
- Decide if there is exactly ONE high-quality trade (long or short), or "ignore".
- You must be selective. Fewer strong trades are better than many weak ones.

Use this decision process:

1) Reward-to-Risk (R:R)
- For 3-1 breakouts:
  * long_entry  = ib_high
  * long_stop   = ib_low
  * short_entry = ib_low
  * short_stop  = ib_high
  * risk = |entry - stop|
- Require realistic room for at least about 2R based on recent price behavior.
- If you cannot see >= 2R potential in that direction, prefer "ignore".

2) Volatility / Quality
- If inside bar range is extremely small relative to price (tiny noise bar), ignore.
- If the range is huge (risk too wide for a tiny account), ignore.
- Avoid random-looking chop.

3) Trend / Context (simple)
- If price has been trending up (higher highs/lows, strong green thrust), favor long above ib_high; be strict with shorts.
- If trending down, favor short below ib_low; be strict with longs.
- If unclear, lean to "ignore" unless R:R and stats are excellent.

4) Use Historical Stats (from the context, if provided)
- Treat them as priors, not guarantees:
  * If winrate >= 45% AND avg_rr >= 2.0 with a decent sample (e.g. >= 100 trades),
    you may be slightly more willing to take a clean setup.
  * If winrate < 35% OR avg_rr < 1.5,
    be much stricter; only approve if the live setup is exceptionally clean.
- Never recommend a trade that has bad live R:R or terrible structure,
  even if historical stats look good.

5) AMD A/M/D Patterns
- If pattern suggests "amd_amd_long": breakout from accumulation → bias long if R:R and context agree.
- If "amd_amd_short": breakdown from distribution → bias short if R:R and context agree.
- Still apply all R:R and volatility rules.

6) XSP specifics
- Treat XSP as a small-sized S&P product.
- Any option suggestion must keep total risk roughly $10–25.

7) Options strategy mapping
- For high-confidence LONG setups:
    * Use a single CALL if the inside-bar range is tight (<1% of price).
    * Use a CALL DEBIT SPREAD if the range is wider or volatility is elevated.
- For high-confidence SHORT setups:
    * Use a single PUT if the range is tight (<1%).
    * Use a PUT DEBIT SPREAD if range is wider or volatility is high.
- For low-confidence setups: "n/a"
- Always use the nearest expiry (same week) unless setup is on a higher timeframe.
- Position sizing rule of thumb: 1–2 contracts max for small accounts ($10–25 risk).

Output format (STRICT):
Return ONLY valid JSON, no markdown, no extra keys:

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

If you choose "ignore":
- Set all numeric fields to null.
- Briefly explain why in 'notes' (e.g. "R:R too low", "range too small", "stats poor", "no clear trend").
"""

    # ---- Call OpenAI ----
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
        reply_text = resp.choices[0].message.content.strip()
    except Exception as e:
        print("❌ OpenAI error:", e)
        reply_text = json.dumps({
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": "OpenAI error",
        })

    print("AGENT decision:", reply_text)

    # ---- Send to Discord ----
    send_to_discord(data, reply_text)

    # ---- Return JSON to caller ----
    try:
        parsed = json.loads(reply_text)
    except Exception:
        parsed = {"raw": reply_text}

    return jsonify({"ok": True, "agent": parsed})


# ===== Backtest upload endpoint =====
@app.route("/backtest", methods=["POST"])
def backtest():
    """
    Accepts:
      - CSV body (TradingView export)
      - or JSON array/dict
    Optional:
      - ?ticker=AMD etc (tag if CSV doesn't include it)

    Computes per-pattern:
      total_trades, wins, losses, winrate_pct, avg_rr
    and stores them in backtest_memory.json.
    """
    ticker_hint = request.args.get("ticker", "").upper().strip()

    ctype = request.headers.get("Content-Type", "")
    raw = request.data
    rows = []

    # ---- Parse body ----
    if "application/json" in ctype:
        try:
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, dict) and "trades" in payload:
                rows = payload["trades"]
            elif isinstance(payload, list):
                rows = payload
            else:
                return jsonify({"ok": False, "error": "invalid_json_structure"}), 400
        except Exception as e:
            print("❌ JSON parse error in /backtest:", e)
            return jsonify({"ok": False, "error": "bad_json"}), 400
    else:
        try:
            text = raw.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
        except Exception as e:
            print("❌ CSV parse error in /backtest:", e)
            return jsonify({"ok": False, "error": "bad_csv"}), 400

    if not rows:
        return jsonify({"ok": False, "error": "no_rows"}), 400

    # ---- Aggregate stats ----
    summary = {}

    for r in rows:
        row_ticker = (r.get("ticker") or r.get("Ticker") or ticker_hint or "UNKNOWN").upper()

        pattern = (
            r.get("pattern")
            or r.get("Pattern")
            or r.get("Signal")
            or ""
        )
        pattern = str(pattern).strip() or "unknown"

        key = f"{row_ticker}:{pattern}"
        if key not in summary:
            summary[key] = {
                "ticker": row_ticker,
                "pattern": pattern,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "rr_values": [],
            }

        s = summary[key]
        s["total_trades"] += 1

        # Win / loss from P&L (USD or %)
        pl = None
        if r.get("Net P&L USD") not in (None, ""):
            pl = _to_float(r.get("Net P&L USD"))
        elif r.get("Net P&L %") not in (None, ""):
            pl = _to_float(r.get("Net P&L %"))

        if pl is not None:
            if pl > 0:
                s["wins"] += 1
            elif pl < 0:
                s["losses"] += 1

        # Approximate R:R from run-up vs drawdown
        runup = _to_float(r.get("Run-up %") or r.get("Run up %") or r.get("Run-up%"))
        drawdown_raw = _to_float(r.get("Drawdown %") or r.get("Drawdown%"))
        if runup is not None and drawdown_raw not in (None, 0) and runup > 0:
            dd = abs(drawdown_raw)
            rr = runup / dd
            if 0 < rr < 20:
                s["rr_values"].append(rr)

    # ---- Finalize + persist ----
    mem = load_backtest_memory()
    out = []

    for key, s in summary.items():
        total = s["total_trades"]
        wins = s["wins"]
        losses = s["losses"]
        winrate = round((wins / total) * 100, 2) if total > 0 else 0.0
        avg_rr = round(sum(s["rr_values"]) / len(s["rr_values"]), 2) if s["rr_values"] else None

        rec = {
            "ticker": s["ticker"],
            "pattern": s["pattern"],
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate,
            "avg_rr": avg_rr,
        }
        out.append(rec)
        mem[key] = rec

    save_backtest_memory(mem)

    print("📊 Backtest summary:", out)
    return jsonify({"ok": True, "summary": out}), 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    """Lightweight endpoint for UptimeRobot"""
    return jsonify({
        "ok": True,
        "service": "TradingView Agent",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200

# ---------- Main ----------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
