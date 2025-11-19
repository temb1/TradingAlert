from flask import Flask, request, jsonify
import datetime
import json
import asyncio

from config import DISCORD_WEBHOOK_URL
from helpers import _to_float
from discord_helper import send_to_discord
from trading_ensemble import TradingEnsemble  # NEW IMPORT
from backtest_processor import process_backtest_data
from market_hours_manager import MarketHoursManager

# Initialize services
market_mgr = MarketHoursManager()
trading_ensemble = TradingEnsemble()  # NEW INIT

app = Flask(__name__)

def startup_tasks():
    """Run startup tasks"""
    print("🚀 Starting up...")
    from helpers import test_supabase_connection
    test_supabase_connection()

def check_market_status():
    """Check market hours and return appropriate status"""
    result = market_mgr.check_market_hours()
    
    current_time_display = datetime.datetime.now().strftime("%H:%M")
    output = f"Market Hours Manager APP {current_time_display}\n\n"
    output += result['display_format']
    
    return output, result

async def get_agent_decision(alert_data):
    """Get trading decision from ensemble of 3 AI models"""
    try:
        ensemble_decision = await trading_ensemble.get_ensemble_decision(alert_data)
        
        # Format for display
        ticker = alert_data.get('ticker', 'UNKNOWN')
        strategy = alert_data.get('strategy', '')
        
        formatted_output = f"# {ticker} {strategy}\n\n"
        formatted_output += "| Direction | Confidence | Consensus |\n"
        formatted_output += "|---|---|---|\n"
        formatted_output += f"| {ensemble_decision['direction']} | {ensemble_decision['confidence']} | {len(ensemble_decision['model_details'])}/3 models |\n\n"
        
        formatted_output += "**Analysis**\n"
        formatted_output += f"{ensemble_decision['reasoning']}\n\n"
        
        formatted_output += "**Model Breakdown:**\n"
        for model_decision in ensemble_decision['model_details']:
            formatted_output += f"- **{model_decision['model']}**: {model_decision['direction']} ({model_decision['confidence']})\n"
            formatted_output += f"  *{model_decision['reasoning'][:100]}...*\n"
        
        return formatted_output
        
    except Exception as e:
        return f"# Error in Ensemble Analysis\n\n**Error**: {str(e)}\n\nFalling back to single model analysis."

@app.route("/", methods=["GET", "POST"])
def root():
    return "TV webhook running.\n", 200

@app.route("/health", methods=["GET", "HEAD"])
def health_check():
    return jsonify({
        "ok": True,
        "service": "TradingView Agent - Ensemble Model",
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

    # Check market hours
    market_output, market_result = check_market_status()
    print(market_output)
    
    agent_reply = ""
    
    # Only process trades if markets are open
    if market_result['status'] in ['TRADING_BOT_STARTED', 'WITHIN_MARKET_HOURS']:
        # Get ensemble decision
        agent_reply = asyncio.run(get_agent_decision(data))
        
        # Send to Discord
        send_to_discord(data, agent_reply)
    else:
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
