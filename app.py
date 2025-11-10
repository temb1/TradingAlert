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

# if you want per-pattern learning later:
BACKTEST_MEMORY_FILE = "backtest_memory.json"


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
                f"**Stop:** {fmt(agent.get('stop'))}"
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
        "footer": {
            "text": "TradingView Agent"
        },
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


def get_backtest_context(ticker, pattern):
    """
    Look up stored summary for this ticker+pattern (if any)
    so the agent can be more/less picky.
    """
    mem = load_backtest_memory()
    key = f"{ticker}:{pattern}"
    return mem.get(key)


# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def root():
    print("🌐 Hit / from", request.remote_addr, "method:", request.method)
    return "TV webhook is running.\n", 200


# ===== TradingView live webhook =====
@app.route("/tvhook", methods=["POST"])
def tvhook():
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

    ticker = str(data.get("ticker", "UNKNOWN"))
    interval = str(data.get("interval", ""))
    pattern = str(data.get("pattern", "")).strip()
    price = _to_float(data.get("close"))
    ib_high = _to_float(data.get("ib_high"))
    ib_low = _to_float(data.get("ib_low"))
    raw_msg = str(data.get("message", ""))

    ib_range = (ib_high - ib_low) if (ib_high is not None and ib_low is not None) else None

    # pull any historical stats we have
    hist = get_backtest_context(ticker, pattern)
    hist_text = ""
    if hist:
        hist_text = (
            f"\n\nHistorical stats for this pattern:\n"
            f"- Total trades: {hist.get('total_trades')}\n"
            f"- Winrate: {hist.get('winrate_pct')}%\n"
            f"- Avg R:R: {hist.get('avg_rr')}"
        )

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

    system_prompt = """
You are an intraday trading assistant for a small account.
You receive alerts only when a 3-1 inside-bar style pattern or AMD-style A/M/D signal fires.

Your job:
- Decide if there is ONE quality trade (long or short) or if it should be ignored.
- Use reward-to-risk, volatility, and basic context.
- You may be picky. Fewer high-quality trades are better.

Rules:

1) Reward-to-Risk (R:R)
- For 3-1 style:
  * long_entry  = ib_high
  * long_stop   = ib_low
  * short_entry = ib_low
  * short_stop  = ib_high
  * risk = |entry - stop|
- Require realistic room for at least ~2R.
- If R:R is unclear or < 2:1, prefer "ignore".

2) Volatility / quality
- If inside bar range is extremely tiny relative to price, treat as noise → ignore.
- If range is huge (risk too wide for small size), ignore.
- Use any provided historical stats:
  * If avg_rr or winrate is poor, be stricter.
  * If strong, you can be more willing but still require clean setup.

3) Trend/context (lightweight)
- If price has clearly been trending up before the alert, favor longs above ib_high.
- If clearly trending down, favor shorts below ib_low.
- If totally unclear, lean to "ignore" unless R:R is excellent.

4) AMD A/M/D notes
- If pattern mentions AMD-style accumulation/manipulation/distribution:
  * "amd_amd_long": breakout from accumulation → bias long if R:R ok.
  * "amd_amd_short": breakdown from distribution → bias short if R:R ok.

5) XSP specifics
- Treat XSP as small-sized S&P exposure.
- Option suggestions must respect very small risk ($10–25).

Output:
- Respond ONLY with strict JSON, no markdown, no commentary.
- Schema:

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

If ignoring:
- Set all numeric fields to null.
- Explain briefly in notes (e.g. "R:R too low", "no clear trend", "range too small").
"""

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
            "notes": "OpenAI error"
        })

    print("AGENT decision:", reply_text)

    # send nicely formatted embed to Discord
    send_to_discord(data, reply_text)

    return jsonify({"ok": True, "agent": json.loads(reply_text)})


# ===== Backtest upload endpoint =====
@app.route("/backtest", methods=["POST"])
def backtest():
    """
    Accepts:
      - CSV file body (TradingView export)
      - or JSON array of trades
    Optional:
      - ?ticker=AMD to tag the dataset.

    Computes per-pattern:
      total_trades, wins, losses, winrate_pct, avg_rr (from run-up/drawdown)
    Stores into backtest_memory.json for use by /tvhook.
    """
    ticker_hint = request.args.get("ticker", "").upper().strip()

    # ---- Load rows from body ----
    rows = []

    ctype = request.headers.get("Content-Type", "")
    raw = request.data

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
        # assume CSV
        try:
            text = raw.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
        except Exception as e:
            print("❌ CSV parse error in /backtest:", e)
            return jsonify({"ok": False, "error": "bad_csv"}), 400

    if not rows:
        return jsonify({"ok": False, "error": "no_rows"}), 400

    # ---- Aggregate ----
    summary = {}
    for r in rows:
        # Ticker
        row_ticker = (r.get("ticker") or r.get("Ticker") or ticker_hint or "UNKNOWN").upper()

        # Pattern / signal
        pattern = (
            r.get("pattern")
            or r.get("Pattern")
            or r.get("Signal")
            or ""
        )
        pattern = str(pattern).strip()
        if not pattern:
            pattern = "unknown"

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

        # Win / loss from P&L
        pl = (
            _to_float(r.get("Net P&L USD"))
            if r.get("Net P&L USD") not in (None, "")
            else _to_float(r.get("Net P&L %"))
        )
        if pl is not None:
            if pl > 0:
                s["wins"] += 1
            elif pl < 0:
                s["losses"] += 1

        # Approximate R:R from run-up vs drawdown (if both available)
        runup = _to_float(r.get("Run-up %"))
        drawdown = _to_float(r.get("Drawdown %"))
        if runup is not None and drawdown is not None and runup > 0 and drawdown > 0:
            rr = runup / drawdown
            # sanity filter: ignore insane values
            if 0 < rr < 20:
                s["rr_values"].append(rr)

    # ---- Finalize + store memory ----
    mem = load_backtest_memory()
    out = []

    for key, s in summary.items():
        wins = s["wins"]
        total = s["total_trades"]
        winrate = round((wins / total) * 100, 2) if total > 0 else 0.0

        if s["rr_values"]:
            avg_rr = round(sum(s["rr_values"]) / len(s["rr_values"]), 2)
        else:
            avg_rr = None

        rec = {
            "ticker": s["ticker"],
            "pattern": s["pattern"],
            "total_trades": total,
            "wins": wins,
            "losses": s["losses"],
            "winrate_pct": winrate,
            "avg_rr": avg_rr,
        }
        out.append(rec)
        mem[key] = rec  # persist for /tvhook

    save_backtest_memory(mem)

    print("📊 Backtest summary:", out)
    return jsonify({"ok": True, "summary": out}), 200


# ---------- Main ----------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
