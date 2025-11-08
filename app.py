from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

# Get your OpenAI API key from environment variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "TV webhook is running.", 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    data = request.get_json(force=True, silent=True) or {}
    # TradingView can send whatever; we grab a few fields if present
    ticker = data.get("ticker", "UNKNOWN")
    message = data.get("message", "")

    # Simple prompt for now – we’ll get fancier later
    prompt = f"TradingView alert for {ticker}: {message}. " \
             f"Summarise in one line and propose a basic trade idea."

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a concise trading assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
        )
        reply = resp.choices[0].message.content
    except Exception as e:
        # Log error and return simple ok so TradingView doesn’t complain
        print("OpenAI error:", e)
        reply = "Received alert."

    # Log to server console so you can see it on Render
    print("ALERT:", data)
    print("GPT:", reply)

    # Respond with JSON (optional; TradingView ignores it)
    return jsonify({"status": "ok", "reply": reply})
