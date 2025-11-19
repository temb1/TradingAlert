from flask import Flask, request, jsonify
import datetime
import json

from config import DISCORD_WEBHOOK_URL
from helpers import _to_float
from discord_helper import send_to_discord
from openai_agent import get_agent_decision
from backtest_processor import process_backtest_data

app = Flask(__name__)

def startup_tasks():
    """Run startup tasks"""
    print("🚀 Starting up...")
    from helpers import test_supabase_connection
    test_supabase_connection()

@app.route("/", methods=["GET", "POST"])
def root():
    return "TV webhook running.\n", 200

@app.route("/health", methods=["GET", "HEAD"])
def health_check():
    return jsonify({
        "ok": True,
        "service": "TradingView Agent",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    """Main webhook endpoint for TradingView alerts."""
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print("❌ JSON Error:", e)
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not data:
        print("⚠️ Empty payload")
        return jsonify({"ok": False, "error": "empty_payload"}), 400

    print("🔥 ALERT:", data)

    # Get agent decision
    agent_reply = get_agent_decision(data)
    
    # Send to Discord
    send_to_discord(data, agent_reply)

    # Return response
    try:
        parsed = json.loads(agent_reply)
    except:
        parsed = {"raw": agent_reply}

    return jsonify({"ok": True, "agent": parsed})

@app.route("/backtest", methods=["POST"])
def backtest():
    """Process backtest data uploads."""
    ticker_hint = request.args.get("ticker", "").upper().strip()
    content_type = request.headers.get("Content-Type", "")
    raw_data = request.data

    result, error = process_backtest_data(raw_data, content_type, ticker_hint)
    
    if error:
        return jsonify({"ok": False, "error": error}), 400

    return jsonify({"ok": True, "summary": result}), 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
