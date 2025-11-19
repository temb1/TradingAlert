from flask import Flask, request, jsonify
import datetime
import json
import asyncio
from datetime import timezone  # ADD THIS

from config import DISCORD_WEBHOOK_URL
from helpers import _to_float
from discord_helper import send_to_discord
from trading_ensemble import TradingEnsemble
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
        
        # Extract alert info
        ticker = alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))
        strategy = alert_data.get('strategy', alert_data.get('pattern', ''))
        price = alert_data.get('price', alert_data.get('close', alert_data.get('current_price', 'N/A')))
        
        # ✅ COMBINED FORMAT - Full breakdown always shown
        formatted_output = f"## 🎯 {ticker} {strategy}\n\n"
        
        # Decision with emoji
        direction_emoji = {"LONG": "🟢", "SHORT": "🔴", "IGNORE": "⚫"}
        confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚠️", "LOW": "💤"}
        
        formatted_output += f"{direction_emoji.get(ensemble_decision['direction'], '⚫')} **Decision**: {ensemble_decision['direction']}\n"
        formatted_output += f"{confidence_emoji.get(ensemble_decision['confidence'], '💤')} **Confidence**: {ensemble_decision['confidence']}\n"
        formatted_output += f"💰 **Price**: ${price}\n"
        formatted_output += f"🤝 **Consensus**: {len(ensemble_decision['model_details'])}/3 models\n\n"
        
        formatted_output += "### 📊 Ensemble Analysis\n"
        formatted_output += f"{ensemble_decision['reasoning']}\n\n"
        
        # ✅ ALWAYS SHOW FULL MODEL BREAKDOWN
        formatted_output += "### 🤖 Model Breakdown\n\n"
        
        for i, model_decision in enumerate(ensemble_decision['model_details'], 1):
            model_name = model_decision['model']
            # Clean model names for display
            if 'gpt-4o' in model_name:
                display_name = "GPT-4o"
            elif 'gpt-4-turbo' in model_name:
                display_name = "GPT-4 Turbo"
            elif 'claude' in model_name:
                display_name = "Claude 3.5"
            else:
                display_name = model_name
                
            direction_emoji = {"LONG": "🟢", "SHORT": "🔴", "IGNORE": "⚫"}.get(model_decision['direction'], '⚫')
            confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚠️", "LOW": "💤"}.get(model_decision['confidence'], '💤')
            
            formatted_output += f"**{i}. {display_name}**\n"
            formatted_output += f"{direction_emoji} **Decision**: {model_decision['direction']} {confidence_emoji} **Confidence**: {model_decision['confidence']}\n"
            formatted_output += f"**Reasoning**: {model_decision['reasoning']}\n\n"
        
        # Add consensus breakdown
        direction_counts = ensemble_decision.get('consensus_breakdown', {})
        if direction_counts:
            formatted_output += "### 🗳️ Consensus Breakdown\n"
            for direction, count in direction_counts.items():
                formatted_output += f"• **{direction}**: {count}/3 models\n"
        
        # Check length and truncate if necessary (very unlikely but safe)
        if len(formatted_output) > 1900:
            formatted_output = formatted_output[:1897] + "..."
            
        return formatted_output
        
    except Exception as e:
        print(f"❌ Ensemble error: {e}")
        # Simple fallback that doesn't break formatting
        return f"## ⚠️ System Update\n\nEnsemble analysis temporarily unavailable.\n\n*Error: {str(e)[:100]}...*"

@app.route("/", methods=["GET", "POST"])
def root():
    return "TV webhook running.\n", 200

@app.route("/health", methods=["GET", "HEAD"])
def health_check():
    return jsonify({
        "ok": True,
        "service": "TradingView Agent - Ensemble Model",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()  # FIXED
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

    try:
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

        # Return response - handle JSON parsing safely
        try:
            # Try to parse as JSON, if not just return as raw text
            parsed = json.loads(agent_reply)
        except:
            parsed = {"raw": agent_reply}

        return jsonify({"ok": True, "agent": parsed})

    except Exception as e:
        print(f"❌ Critical error in tvhook: {e}")
        return jsonify({"ok": False, "error": f"Processing error: {str(e)}"}), 500

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

@app.route("/debug", methods=["GET"])
def debug():
    """Debug endpoint to check system status"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "market_hours": market_mgr.check_market_hours(),
        "ensemble_ready": True
    })

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
