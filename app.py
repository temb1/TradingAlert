from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "TV webhook is running.", 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    data = request.get_json(force=True, silent=True) or {}

    # Extract fields ( TradingView can send more later, that's fine )
    ticker   = str(data.get("ticker", "UNKNOWN"))
    interval = str(data.get("interval", ""))
    pattern  = str(data.get("pattern", ""))
    hint     = str(data.get("direction_hint", ""))  # optional
    price    = data.get("close") or data.get("price")
    ib_high  = data.get("ib_high")
    ib_low   = data.get("ib_low")
    raw_msg  = str(data.get("message", ""))

    # Build a compact description of what we know
    context = f"""
    Alert data:
    - Ticker: {ticker}
    - Interval: {interval}
    - Pattern: {pattern}
    - Direction hint: {hint}
    - Current price: {price}
    - Inside bar high: {ib_high}
    - Inside bar low: {ib_low}
    - Raw message: {raw_msg}
    """

    # System prompt = your agent's personality & rules
    system_prompt = """
    You are an intraday options trading assistant for a human day trader.
    Goals:
    - Focus on QQQ, SPY, IWM (others: be conservative).
    - Use 3-1 / inside-bar breakout logic:
      * Long bias: entry ABOVE inside-bar high.
      * Short bias: entry BELOW inside-bar low.
      * Stop on the opposite side of inside bar.
      * If inside-bar levels missing, infer from context or say cannot compute.
    - Consider user risk: £10-20 per trade maximum.
      * If suggested option or spread costs more than that, say: "skip - too expensive."
    - For options:
      * Use nearest liquid weekly expiry (or next week if today is Thu/Fri).
      * For calls: slightly ITM or ATM for direction long.
      * For puts: slightly ITM or ATM for direction short.
      * For verticals: 2-4 strikes wide, defined risk.
    - Only give directional idea if pattern + levels justify.
      Otherwise, respond with direction='ignore'.

    Output format:
    Respond ONLY in compact JSON with these keys:
    {
      "direction": "long" | "short" | "ignore",
      "entry": "<number or null>",
      "stop": "<number or null>",
      "tp1": "<number or null>",
      "tp2": "<number or null>",
      "confidence": "<low|medium|high>",
      "single_option": "<very short description or 'n/a'>",
      "vertical_spread": "<very short description or 'n/a'>",
      "notes": "<1-2 short sentences max>"
    }
    No extra text.
    """

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=260,
            temperature=0.4,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        reply = '{"direction":"ignore","entry":null,"stop":null,"tp1":null,"tp2":null,"confidence":"low","single_option":"n/a","vertical_spread":"n/a","notes":"OpenAI error"}'

    # Log to Render so you can see decisions
    print("ALERT:", data)
    print("AGENT:", reply)

    # TradingView ignores response body, but you could consume this via another service
    return jsonify({"ok": True, "agent": reply})
