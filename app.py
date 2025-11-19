from flask import Flask, request, jsonify
import datetime
import json

from config import DISCORD_WEBHOOK_URL
from helpers import _to_float
from discord_helper import send_to_discord
from openai_agent import get_agent_decision
from backtest_processor import process_backtest_data

# ===== ADD THIS: Import and initialize Market Hours Manager =====
from market_hours_manager import MarketHoursManager
market_mgr = MarketHoursManager()

app = Flask(__name__)

def startup_tasks():
    """Run startup tasks"""
    print("🚀 Starting up...")
    from helpers import test_supabase_connection
    test_supabase_connection()

def check_market_status():
    """
    NEW FUNCTION: Check market hours and return appropriate status
    This replaces your repetitive 'TRADING BOT STARTED' messages
    """
    result = market_mgr.check_market_hours()
    
    # Format the output to match your current display style
    current_time_display = datetime.datetime.now().strftime("%H:%M")
    output = f"Market Hours Manager APP {current_time_display}\n\n"
    output += result['display_format']
    
    return output, result

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

    # ===== ADD THIS: Check market hours before processing =====
    market_output, market_result = check_market_status()
    print(market_output)  # This will show either STARTUP (once) or WITHIN MARKET HOURS
    
    # Only process trades if markets are open
    if market_result['status'] in ['TRADING_BOT_STARTED', 'WITHIN_MARKET_HOURS']:
        # Get agent decision
        agent_reply = get_agent_decision(data)
        
        # Send to Discord
        send_to_discord(data, agent_reply)
    else:
        # Markets are closed - don't process the trade
        agent_reply = "MARKETS_CLOSED: No trade processing outside market hours (9:00 AM - 4:00 PM ET)"
        print(f"⏸️ {agent_reply}")

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
