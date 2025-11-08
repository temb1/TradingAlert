from flask import Flask, request, jsonify
import os
from openai import OpenAI
import requests

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "TV webhook is running.", 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    data = request.get_json(force=True, silent=True) or {}

    # Extract fields sent from TradingView
    ticker   = str(data.get("ticker", "UNKNOWN"))
    interval = str(data.get("interval", ""))
    pattern  = str(data.get("pattern", ""))
    price    = _to_float(data.get("close"))
    ib_high  = _to_float(data.get("ib_high"))
    ib_low   = _to_float(data.get("ib_low"))
    raw_msg  = str(data.get("message", ""))

    # Pre-calc simple stuff for the model
    ib_range = (ib_high - ib_low) if (ib_high is not None and ib_low is not None) else None

    context = f"""
    Alert data:
    - Ticker: {ticker}
    - Interval: {interval}
    - Pattern: {pattern}
    - Current price (close): {price}
    - Inside bar high: {ib_high}
    - Inside bar low: {ib_low}
    - Inside bar range: {ib_range}
    - Raw message: {raw_msg}
    """

    # System prompt with 3 tightened rules:
    system_prompt = """
    You are an intraday trading assistant for a human day trader with small size (£10-20 risk per trade).
    You receive alerts ONLY when a 3-1 inside-bar setup has formed on a 5-minute chart.

    Your job:
    - Decide if there is a QUALITY trade or if it should be ignored.
    - Consider BOTH long (above inside bar) and short (below inside bar), but choose only the better one.
    - If nothing is clean, return direction="ignore".

    Apply these rules STRICTLY:

    1) REWARD-TO-RISK (R:R) FILTER
       - Define:
         * long_entry  = inside_bar_high (ib_high)
         * long_stop   = inside_bar_low  (ib_low)
         * short_entry = inside_bar_low
         * short_stop  = inside_bar_high
         * risk_per_side = abs(entry - stop)
       - Assume a conservative target:
         * tp1 ≈ entry ± risk (1R)
         * tp2 ≈ entry ± 2 * risk (2R)
       - Only consider trades where:
         * There is realistic room (based on recent price behavior) for AT LEAST 2R.
         * If you cannot see at least 2R potential in that direction, set direction="ignore".

    2) TREND / CONTEXT FILTER
       - If possible, infer trend using:
         * Relative position of price vs ib_high/ib_low.
         * Message content or any hints (e.g. "strong up move", "heavy selling").
       - Simple rules:
         * If instrument is clearly in an intraday uptrend (higher highs/lows, strong prior green impulsive move),
           PREFER long setups above ib_high and be VERY strict with shorts.
         * If clearly in a downtrend, PREFER short setups below ib_low and be VERY strict with longs.
         * If context suggests chop or no clear direction, lean toward direction="ignore" unless R:R is extremely strong.

       - If you are unsure of higher timeframe trend, DO NOT force a trade; bias to "ignore".

    3) VOLATILITY / QUALITY FILTER
       - Ignore garbage signals:
         * If inside bar range is extremely tiny (e.g. less than 0.05% of price), it's noise → direction="ignore".
         * If inside bar range is absurdly large (e.g. > 1.5-2.0% of price), risk is too wide for £10-20 → direction="ignore".
       - Avoid trades if:
         * The setup appears in obviously low-liquidity / random conditions implied by the message/context.
       - You are allowed to be picky. Fewer good trades > many bad ones.

    OPTIONS LOGIC (for liquid ETFs like QQQ, SPY, IWM):
    - User risk per trade: about £10–20 (assume ≈ $10–25).
    - If you DO like a direction:
      * For LONG:
         - Suggest ONE simple single call:
           - ATM or slightly ITM call, nearest weekly expiry.
           - Note: only if approximate premium can fit ≈ $10–25 (1 contract or defined spread).
         - Suggest ONE simple vertical call spread:
           - Buy ATM/small ITM call, sell 2-4 strikes above, same expiry.
           - Must be a defined-risk structure that could reasonably fit $10–25 debit.
      * For SHORT:
         - Mirror logic with puts / put verticals.
    - If you cannot confidently suggest an option within that risk, set fields to "n/a" and mention that in notes.

    OUTPUT FORMAT (STRICT):
    Respond ONLY as valid JSON, no explanation, no markdown, no extra keys.
    Use this exact schema:

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

    - If you choose "ignore", set all numeric fields to null and explain briefly in 'notes' (e.g. 'R:R too low', 'against trend', 'range too small/large').
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
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        reply = '{"direction":"ignore","entry":null,"stop":null,"tp1":null,"tp2":null,"confidence":"low","single_option":"n/a","vertical_spread":"n/a","notes":"OpenAI error"}'

    print("ALERT:", data)
    print("AGENT:", reply)

    # ✅ send to Discord
    send_to_discord(data, reply)

    return jsonify({"ok": True, "agent": reply})


# === Discord integration helper ===
def send_to_discord(alert_data, agent_reply):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ No Discord webhook set.")
        return

    try:
        # Format a nice message
        alert = f"📢 **{alert_data.get('ticker', 'Unknown')} {alert_data.get('pattern', '')}**"
        agent_json = agent_reply if isinstance(agent_reply, str) else str(agent_reply)
        message = f"{alert}\n```json\n{agent_json}\n```"

        payload = {"content": message}
        requests.post(webhook_url, json=payload)
        print("✅ Sent alert to Discord.")
    except Exception as e:
        print("❌ Discord error:", e)

    return jsonify({"ok": True, "agent": reply})


def _to_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None
