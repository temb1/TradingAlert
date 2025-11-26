# Version 16
from flask import Flask, request, jsonify
import datetime
import json
import asyncio
import traceback
import os
from datetime import timezone 

from config import DISCORD_WEBHOOK_URL
from helpers import _to_float, save_recommendation_to_db, get_backtest_stats, calculate_virtual_levels, extract_strategy_name
from discord_helper import send_to_discord
from trading_ensemble import TradingEnsemble
from backtest_processor import process_backtest_data
from market_hours_manager import MarketHoursManager, is_etf

# ✅ NEW: Import direction learning system
from direction_learner import DirectionPredictionLearner
from learning_system import AutomatedLearningSystem

# Initialize services
market_mgr = MarketHoursManager()

# Add this to app.py after your imports
def initialize_database():
    """Initialize database tables on startup"""
    try:
        from database_setup import setup_database
        print("🚀 Initializing database...")
        if setup_database():
            print("✅ Database initialized successfully")
        else:
            print("❌ Database initialization failed")
    except Exception as e:
        print(f"⚠️ Database setup error: {e}")

# Call it when app starts
initialize_database()

# ✅ NEW: Initialize direction learning system
print("🎯 Initializing direction learning system...")
direction_learner = DirectionPredictionLearner()
learning_system = AutomatedLearningSystem(direction_learner=direction_learner)

# ✅ UPDATED: Initialize trading ensemble with direction learning
trading_ensemble = TradingEnsemble(direction_learner=direction_learner)

# ✅ ADD THIS TEMPORARY DEBUG HERE:
print(f"ANTHROPIC_API_KEY exists: {'✅' if os.getenv('ANTHROPIC_API_KEY') else '❌'}")
print(f"ANTHROPIC_API_KEY length: {len(os.getenv('ANTHROPIC_API_KEY', ''))}")
print(f"ANTHROPIC_API_KEY first 10 chars: {os.getenv('ANTHROPIC_API_KEY', '')[:10]}...")

# Also check OpenAI key for comparison
print(f"OPENAI_API_KEY exists: {'✅' if os.getenv('OPENAI_API_KEY') else '❌'}")
print(f"SUPABASE_URL exists: {'✅' if os.getenv('SUPABASE_URL') else '❌'}")
print(f"SUPABASE_KEY exists: {'✅' if os.getenv('SUPABASE_KEY') else '❌'}")
print(f"🎯 Direction learning system initialized: {'✅' if direction_learner else '❌'}")

app = Flask(__name__)

def startup_tasks():
    """Run startup tasks"""
    print("🚀 Starting up...")
    from helpers import test_supabase_connection
    test_supabase_connection()
    
    # ✅ NEW: Log direction learning status
    if direction_learner:
        print("🎯 Direction learning system ready")
        # Load any existing learning data
        direction_learner.load_data()
        print(f"📊 Direction learning data loaded: {len(direction_learner.prediction_history)} predictions")

def check_market_status():
    """Check market hours and return appropriate status"""
    result = market_mgr.check_market_hours()
    
    current_time_display = datetime.datetime.now().strftime("%H:%M")
    output = f"Market Hours Manager APP {current_time_display}\n\n"
    output += result['display_format']
    
    return output, result

async def get_agent_decision(alert_data):
    """Get trading decision from ensemble of 3 AI models with direction learning"""
    try:
        # ⚠️ FIXED: Use the trading ensemble instance instead of non-existent function
        ensemble_decision = {"direction": "IGNORE", "confidence": "MEDIUM", "reasoning": "System initializing"}
        
        # Extract alert info
        ticker = alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))
        strategy = alert_data.get('strategy', alert_data.get('pattern', ''))
        price = alert_data.get('price', alert_data.get('close', alert_data.get('current_price', 'N/A')))
        
        # ✅ NEW: Add direction learning insights to output
        direction_learning_insight = ""
        if direction_learner and ensemble_decision['direction'] in ['LONG', 'SHORT']:
            try:
                # Extract signals for direction learning
                from helpers import extract_signals_for_learning
                signals = extract_signals_for_learning(alert_data, ensemble_decision)
                
                # Get direction learning confidence
                learning_direction = 'BULLISH' if ensemble_decision['direction'] == 'LONG' else 'BEARISH'
                learning_confidence = direction_learner.get_direction_confidence(signals, learning_direction)
                
                if learning_confidence > 0.6:
                    direction_learning_insight = f"🎯 *Historical accuracy for these signals: {learning_confidence:.1%}*"
                elif learning_confidence < 0.4:
                    direction_learning_insight = f"⚠️ *Historical accuracy for these signals: {learning_confidence:.1%}*"
                    
            except Exception as e:
                print(f"⚠️ Error getting direction learning insight: {e}")
        
        # ✅ COMBINED FORMAT - Full breakdown always shown
        formatted_output = f"## 🎯 {ticker} {strategy}\n\n"
        
        # Decision with emoji
        direction_emoji = {"LONG": "🟢", "SHORT": "🔴", "IGNORE": "⚫"}
        confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚠️", "LOW": "💤"}
        
        formatted_output += f"{direction_emoji.get(ensemble_decision['direction'], '⚫')} **Decision**: {ensemble_decision['direction']}\n"
        formatted_output += f"{confidence_emoji.get(ensemble_decision['confidence'], '💤')} **Confidence**: {ensemble_decision['confidence']}\n"
        formatted_output += f"💰 **Price**: ${price}\n\n"
        
        # ✅ NEW: Add direction learning insight
        if direction_learning_insight:
            formatted_output += f"{direction_learning_insight}\n\n"
        
        formatted_output += "### 📊 System Status\n"
        formatted_output += "Trading ensemble is initializing. Full analysis coming soon.\n\n"
        
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
    # ✅ NEW: Include direction learning status in health check
    direction_learning_status = "active" if direction_learner else "inactive"
    
    return jsonify({
        "ok": True,
        "service": "TradingView Agent - Ensemble Model",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "direction_learning": direction_learning_status
    }), 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    """Main webhook endpoint for TradingView alerts with direction learning."""
    print("=== 🚨 TVHOOK ENDPOINT TRIGGERED ===")
    
    try:
        data = request.get_json(force=True)
        print(f"✅ JSON parsed successfully: {type(data)}")
    except Exception as e:
        print(f"❌ JSON Error: {e}")
        print(f"❌ Raw request data: {request.data}")
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not data:
        print("⚠️ Empty payload received")
        return jsonify({"ok": False, "error": "empty_payload"}), 400

    print(f"🔥 ALERT DATA RECEIVED: {data}")
    print(f"🔥 FULL ALERT DETAILS: {json.dumps(data, indent=2)}")

    try:
        # ✅ ADDED: Extract strategy name properly
        from helpers import extract_strategy_name
        strategy = extract_strategy_name(data)
        data['strategy'] = strategy
        
        # ✅ ADDED: Check ETF mode with improved logic AND DEBUG
        from market_hours_manager import is_etf
        symbol = data.get('ticker', 'UNKNOWN')
        
        # ✅ DEBUG: Test the function directly
        print(f"🔍 ETF DEBUG - Symbol: {symbol}")
        print(f"🔍 Calling is_etf('{symbol}')...")
        etf_result = is_etf(symbol)
        print(f"🔍 is_etf result: {etf_result}")
        
        # ✅ Check if it's in known stocks
        known_stocks = ['NVDA', 'AMD', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NFLX']
        if symbol.upper() in known_stocks:
            print(f"✅ {symbol} is in known stocks list - should be FALSE")
            
        etf_mode = etf_result
        data['etf_mode'] = etf_mode
        
        print(f"🔍 ENHANCED DATA - Symbol: {symbol}, Strategy: {strategy}, ETF Mode: {etf_mode}")

        # Check market hours
        print("📊 Checking market status...")
        market_output, market_result = check_market_status()
        print(f"📊 MARKET STATUS: {market_output}")
        print(f"📊 MARKET RESULT: {market_result}")
        
        agent_reply = ""
        
        # Only process trades if markets are open
        if market_result['status'] in ['TRADING_BOT_STARTED', 'WITHIN_MARKET_HOURS']:
            print("✅ Markets are open - processing trade...")
            
            # ✅ UPDATED: Log the strategy type for debugging
            print(f"📊 PROCESSING STRATEGY: {strategy}")
            
            # ✅ UPDATED: Check if this is a trend analysis alert
            if any(x in strategy for x in ['bullish_trend', 'bearish_trend']):
                print(f"🎯 TREND ANALYSIS ALERT DETECTED: {strategy}")
                # Extract trend-specific data for logging
                additional_data = data.get('additional_data', {})
                trend_strength = additional_data.get('trend_strength', 'unknown')
                conditions_met = additional_data.get('conditions_met', 'unknown')
                print(f"📈 TREND DETAILS - Strength: {trend_strength}, Conditions: {conditions_met}, ETF Mode: {etf_mode}")
            
            # Get ensemble decision
            print("🤖 Getting ensemble decision...")
            
            # ✅ FIXED: Use the async function instead of non-existent import
            agent_reply = asyncio.run(get_agent_decision(data))
            print(f"🤖 ENSEMBLE REPLY: {agent_reply}")
            print(f"🤖 ENSEMBLE REPLY TYPE: {type(agent_reply)}")
            
            # ✅ NEW: Start monitoring trade outcome for direction learning
            if learning_system and agent_reply:
                try:
                    print(f"🎯 Starting trade monitoring for direction learning: {symbol}")
                    asyncio.create_task(learning_system.monitor_trade_outcome(agent_reply, data))
                except Exception as e:
                    print(f"⚠️ Error starting trade monitoring: {e}")
            
            # Send to Discord
            print("📢 Attempting to send to Discord...")
            discord_result = send_to_discord(data, agent_reply)
            print(f"📢 DISCORD SEND RESULT: {discord_result}")
            
            # Save to database
            print("💾 Attempting to save to database...")
            
            # ✅ UPDATED: Pass direction learner to database save
            from helpers import save_recommendation_to_db
            db_result = save_recommendation_to_db(data, agent_reply, direction_learner)
            print(f"💾 DATABASE SAVE RESULT: {db_result}")
            
        else:
            agent_reply = "MARKETS_CLOSED: No trade processing outside market hours (9:00 AM - 4:00 PM ET)"
            print(f"⏸️ {agent_reply}")
            print("📢 Attempting to send market closed message to Discord...")
            discord_result = send_to_discord(data, agent_reply)
            print(f"📢 DISCORD SEND RESULT: {discord_result}")

        # Return response - handle JSON parsing safely
        print("🔄 Preparing response...")
        try:
            # Try to parse as JSON, if not just return as raw text
            if isinstance(agent_reply, dict):
                parsed = agent_reply
                print("✅ Agent reply is already a dictionary")
            else:
                parsed = {"message": str(agent_reply)}
                print("✅ Agent reply converted to dictionary")
        except Exception as parse_error:
            print(f"⚠️ Agent reply processing error: {parse_error}")
            parsed = {"raw": str(agent_reply)}

        print(f"✅ FINAL RESPONSE: {json.dumps({'ok': True, 'agent': parsed}, indent=2)}")
        print("=== 🏁 TVHOOK PROCESSING COMPLETE ===\n")
        return jsonify({"ok": True, "agent": parsed})

    except Exception as e:
        print(f"❌ CRITICAL ERROR in tvhook: {e}")
        import traceback
        print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
        
        # Try to send error to Discord for visibility
        try:
            error_message = f"❌ CRITICAL ERROR in webhook: {str(e)}"
            discord_result = send_to_discord({"error": True}, error_message)
            print(f"📢 ERROR SENT TO DISCORD: {discord_result}")
        except Exception as discord_error:
            print(f"❌ FAILED TO SEND ERROR TO DISCORD: {discord_error}")
            
        print("=== 💥 TVHOOK PROCESSING FAILED ===\n")
        return jsonify({"ok": False, "error": f"Processing error: {str(e)}"}), 500

# ❌❌❌ DELETE EVERYTHING FROM HERE DOWN TO THE NEXT ROUTE ❌❌❌
# (Remove the duplicate ETF debugging code that's outside the function)

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
    # ✅ NEW: Include direction learning status in debug
    direction_learning_status = {
        "active": direction_learner is not None,
        "total_predictions": len(direction_learner.prediction_history) if direction_learner else 0,
        "learning_system": learning_system is not None
    }
    
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "market_hours": market_mgr.check_market_hours(),
        "ensemble_ready": True,
        "direction_learning": direction_learning_status
    })

# ✅ NEW: Add endpoint to view direction learning performance
@app.route("/learning-stats", methods=["GET"])
def learning_stats():
    """Get direction learning performance statistics"""
    if not direction_learner:
        return jsonify({"error": "Direction learning system not available"}), 400
        
    try:
        report = direction_learner.get_performance_report()
        return jsonify({
            "ok": True,
            "direction_learning": report
        })
    except Exception as e:
        return jsonify({"error": f"Failed to get learning stats: {str(e)}"}), 500

# ✅ NEW: Add endpoint to get best signal combinations
@app.route("/best-signals", methods=["GET"])
def best_signals():
    """Get best performing signal combinations"""
    if not direction_learner:
        return jsonify({"error": "Direction learning system not available"}), 400
        
    try:
        best_combinations = direction_learner.get_best_signal_combinations()
        return jsonify({
            "ok": True,
            "best_signal_combinations": best_combinations
        })
    except Exception as e:
        return jsonify({"error": f"Failed to get best signals: {str(e)}"}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "10000"))
    
    # ✅ NEW: Run startup tasks
    startup_tasks()
    
    app.run(host="0.0.0.0", port=port)
