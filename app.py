# Version: 21
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

# ✅ NEW: Import direction learning system AND ensemble core
from direction_learner import DirectionPredictionLearner
from learning_system import AutomatedLearningSystem
from ensemble_core import EnsembleCore  # NEW: Import the AI ensemble system

# Initialize services
market_mgr = MarketHoursManager()

# Feature flags - read from environment with safe defaults
ENABLE_DATABASE_LEARNING = os.getenv('ENABLE_DATABASE_LEARNING', 'False').lower() == 'true'
ENABLE_TRADE_MONITORING = os.getenv('ENABLE_TRADE_MONITORING', 'False').lower() == 'true'
ENABLE_REAL_AI_CALLS = os.getenv('ENABLE_REAL_AI_CALLS', 'False').lower() == 'true'

def initialize_database():
    """Initialize database tables - uses global feature flag"""
    try:
        from database_setup import setup_database
        
        print(f"🔍 Database status: {'ENABLED' if ENABLE_DATABASE_LEARNING else 'DISABLED'}")
        
        if ENABLE_DATABASE_LEARNING:
            print("🚀 Initializing database...")
            if setup_database():
                print("✅ Database initialized successfully")
                return True
            else:
                print("❌ Database initialization failed")
                return False
        else:
            print("⏸️ Database initialization disabled")
            print("   Set ENABLE_DATABASE_LEARNING=true in .env file to enable")
            return None
            
    except Exception as e:
        print(f"⚠️ Database setup error: {e}")
        return False

# Call it when app starts
initialize_database()

# ✅ NEW: Initialize direction learning system
print("🎯 Initializing direction learning system...")
direction_learner = DirectionPredictionLearner()

# ✅ NEW: Initialize AI Ensemble Core
print("🤖 Initializing AI Ensemble Core...")
ensemble_core = EnsembleCore(direction_learner=direction_learner)
print(f"✅ Ensemble Core initialized: {len(ensemble_core.models)} AI models configured")

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
print(f"🤖 AI Ensemble Core initialized: {'✅' if ensemble_core else '❌'}")

app = Flask(__name__)

def startup_tasks():
    """Run startup tasks"""
    print("🚀 Starting up...")
    
    # ✅ Show feature flag status
    print(f"\n🔧 FEATURE STATUS:")
    print(f"   Database Learning: {'🟢 ENABLED' if ENABLE_DATABASE_LEARNING else '🔴 DISABLED'}")
    print(f"   Trade Monitoring:  {'🟢 ENABLED' if ENABLE_TRADE_MONITORING else '🔴 DISABLED'}")
    print(f"   Real AI Calls:     {'🟢 ENABLED' if ENABLE_REAL_AI_CALLS else '🔴 DISABLED'}")
    
    # Test database connection
    from helpers import test_supabase_connection
    test_supabase_connection()
    
    # Load direction learner
    if direction_learner:
        print("🎯 Direction learning system ready")
        direction_learner.load_data()

def check_market_status():
    """Check market hours and return appropriate status"""
    result = market_mgr.check_market_hours()
    
    current_time_display = datetime.datetime.now().strftime("%H:%M")
    output = f"Market Hours Manager APP {current_time_display}\n\n"
    output += result['display_format']
    
    return output, result

async def get_agent_decision(alert_data):
    """Get trading decision from ensemble of 3 AI models with direction learning - UPDATED"""
    try:
        ticker = alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))
        
        print(f"🤖 Getting AI ensemble decision for {ticker}...")
        
        # ✅ NEW: Use the EnsembleCore system instead of old method
        ai_result = ensemble_core.get_ensemble_decision_sync(ticker, alert_data)
        
        print(f"✅ AI Ensemble result: {ai_result.get('direction')} with {ai_result.get('confidence')} confidence")
        print(f"   Model details: {len(ai_result.get('model_details', []))} models")
        print(f"   Consensus breakdown: {ai_result.get('consensus_breakdown')}")
        
        # Return the formatted result directly (it's already in the correct format for Discord)
        return ai_result
        
    except Exception as e:
        print(f"❌ Error in get_agent_decision: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        
        # Return fallback decision
        return {
            "direction": "IGNORE",
            "confidence": "LOW",
            "reasoning": f"AI ensemble system error: {str(e)[:100]}",
            "model_details": [],
            "consensus_breakdown": {"IGNORE": 0},
            "error": True
        }

@app.route("/", methods=["GET", "POST"])
def root():
    return "TV webhook running.\n", 200

@app.route("/health", methods=["GET", "HEAD"])
def health_check():
    # ✅ NEW: Include AI ensemble status in health check
    ai_ensemble_status = "active" if ensemble_core else "inactive"
    direction_learning_status = "active" if direction_learner else "inactive"
    
    return jsonify({
        "ok": True,
        "service": "TradingView Agent - Ensemble Model",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "direction_learning": direction_learning_status,
        "ai_ensemble": ai_ensemble_status,
        "ai_models": len(ensemble_core.models) if ensemble_core else 0
    }), 200

@app.route("/tvhook", methods=["POST"])
def tvhook():
    """Main webhook endpoint for TradingView alerts with direction learning."""
    print("=== 🚨 TVHOOK ENDPOINT TRIGGERED ===")

    # ✅ Uses global variables defined at top
    print(f"🔧 CONFIG: DB={ENABLE_DATABASE_LEARNING}, TRACK={ENABLE_TRADE_MONITORING}, AI={ENABLE_REAL_AI_CALLS}")
    
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
    
    try:
        # ✅ Extract strategy name properly
        from helpers import extract_strategy_name
        strategy = extract_strategy_name(data)
        data['strategy'] = strategy
        
        # ✅ Check ETF mode
        from market_hours_manager import is_etf
        symbol = data.get('ticker', data.get('symbol', 'UNKNOWN')).upper()
        
        # ETF detection
        etf_mode = is_etf(symbol)
        data['etf_mode'] = etf_mode
        
        print(f"🔍 ENHANCED DATA - Symbol: {symbol}, Strategy: {strategy}, ETF Mode: {etf_mode}")

        # Check market hours
        print("📊 Checking market status...")
        market_output, market_result = check_market_status()
        print(f"📊 MARKET STATUS: {market_result['status']}")
        
        agent_reply = {}
        
        # Only process trades if markets are open
        if market_result['status'] in ['TRADING_BOT_STARTED', 'WITHIN_MARKET_HOURS']:
            print("✅ Markets are open - processing trade...")
            
            # Log strategy details
            print(f"📊 PROCESSING STRATEGY: {strategy}")
            
            # Extract trend-specific data if available
            additional_data = data.get('additional_data', {})
            if additional_data:
                print(f"📈 ADDITIONAL DATA: {json.dumps(additional_data, indent=2)[:500]}...")
            
            # Get ensemble decision
            print("🤖 Getting AI ensemble decision...")
            
            try:
                agent_reply = asyncio.run(get_agent_decision(data))
                print(f"🤖 AI ENSEMBLE DECISION MADE")
                
                # Log the decision
                direction = agent_reply.get('direction', 'UNKNOWN')
                confidence = agent_reply.get('confidence', 'LOW')
                consensus = agent_reply.get('consensus_breakdown', {})
                model_count = len(agent_reply.get('model_details', []))
                
                print(f"   Direction: {direction}, Confidence: {confidence}")
                print(f"   Consensus: {consensus}")
                print(f"   Models analyzed: {model_count}")
                
            except Exception as e:
                print(f"❌ Error getting ensemble decision: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                agent_reply = {
                    "direction": "IGNORE",
                    "confidence": "LOW",
                    "reasoning": f"System error: {str(e)[:100]}",
                    "model_details": [],
                    "consensus_breakdown": {"IGNORE": 0},
                    "error": True
                }
            
            # ✅ Send to Discord with exact screenshot formatting
            print("📢 Sending to Discord...")
            from discord_helper import send_to_discord
            discord_result = send_to_discord(data, agent_reply)
            
            if discord_result:
                print("✅ Discord notification sent successfully")
            else:
                print("❌ Discord notification failed")
            
            # ✅ CONDITIONAL: Save to database only if learning is enabled
            if ENABLE_DATABASE_LEARNING:
                print("💾 Attempting to save to database...")
                from helpers import save_recommendation_to_db
                db_result = save_recommendation_to_db(data, agent_reply, direction_learner)
                print(f"💾 DATABASE SAVE RESULT: {db_result}")
            else:
                print("⏸️ Database saving disabled (ENABLE_DATABASE_LEARNING = False)")
                db_result = {"success": False, "message": "Database learning disabled"}
            
            # ✅ CONDITIONAL: Start trade monitoring only if enabled
            if ENABLE_TRADE_MONITORING and learning_system and agent_reply:
                try:
                    print(f"🎯 Starting trade monitoring for learning: {symbol}")
                    asyncio.run(learning_system.monitor_trade_outcome(agent_reply, data))
                except Exception as e:
                    print(f"⚠️ Error starting trade monitoring: {e}")
            else:
                print("⏸️ Trade monitoring disabled (ENABLE_TRADE_MONITORING = False)")
            
        else:
            # Markets are closed
            agent_reply = {
                "direction": "IGNORE",
                "confidence": "LOW", 
                "reasoning": "MARKETS_CLOSED: No trade processing outside market hours (9:00 AM - 4:00 PM ET)",
                "model_details": [],
                "consensus_breakdown": {"IGNORE": 0},
                "market_closed": True
            }
            
            print(f"⏸️ {agent_reply['reasoning']}")
            
            # Still send to Discord for visibility
            print("📢 Sending market closed message to Discord...")
            from discord_helper import send_to_discord
            discord_result = send_to_discord(data, agent_reply)
            print(f"📢 DISCORD SEND RESULT: {'Success' if discord_result else 'Failed'}")

        # ✅ Prepare response - ensure it's always valid JSON
        print("🔄 Preparing response...")
        
        try:
            # agent_reply is already a dictionary from get_agent_decision
            parsed = agent_reply if isinstance(agent_reply, dict) else {"message": str(agent_reply), "raw": True}
                
            # Add system metadata
            parsed["system"] = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "market_status": market_result['status'],
                "database_learning_enabled": ENABLE_DATABASE_LEARNING,
                "trade_monitoring_enabled": ENABLE_TRADE_MONITORING,
                "ai_ensemble_models": len(ensemble_core.models) if ensemble_core else 0
            }
            
            print(f"✅ FINAL RESPONSE prepared")
            
        except Exception as parse_error:
            print(f"⚠️ Agent reply processing error: {parse_error}")
            parsed = {
                "raw_response": str(agent_reply),
                "error": f"Processing error: {parse_error}",
                "system": {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "market_status": market_result['status']
                }
            }

        print("=== 🏁 TVHOOK PROCESSING COMPLETE ===\n")
        return jsonify({"ok": True, "agent": parsed})

    except Exception as e:
        print(f"❌ CRITICAL ERROR in tvhook: {e}")
        import traceback
        print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
        
        # Try to send error to Discord for visibility
        try:
            error_message = f"❌ CRITICAL ERROR in webhook: {str(e)[:200]}"
            from discord_helper import send_to_discord
            discord_result = send_to_discord({"error": True, "symbol": "ERROR"}, error_message)
            print(f"📢 ERROR SENT TO DISCORD: {'Success' if discord_result else 'Failed'}")
        except Exception as discord_error:
            print(f"❌ FAILED TO SEND ERROR TO DISCORD: {discord_error}")
            
        print("=== 💥 TVHOOK PROCESSING FAILED ===\n")
        return jsonify({"ok": False, "error": f"Processing error: {str(e)[:200]}"}), 500

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
    # ✅ NEW: Include AI ensemble status in debug
    ai_ensemble_status = {
        "active": ensemble_core is not None,
        "models": len(ensemble_core.models) if ensemble_core else 0,
        "use_real_api": ensemble_core.use_real_api if ensemble_core else False
    }
    
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
        "ai_ensemble": ai_ensemble_status,
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

# ✅ NEW: Add endpoint to test AI ensemble
@app.route("/test-ensemble", methods=["GET"])
def test_ensemble():
    """Test the AI ensemble system"""
    try:
        test_alert = {
            "ticker": "AAPL",
            "strategy": "bullish_trend",
            "price": 150.50,
            "rsi": 65.5,
            "additional_data": {
                "rsi": 65.5,
                "volume_ratio": 1.8,
                "trend_strength": "strong",
                "etf_mode": False
            }
        }
        
        result = ensemble_core.get_ensemble_decision_sync("AAPL", test_alert)
        
        return jsonify({
            "ok": True,
            "test_result": {
                "direction": result.get("direction"),
                "confidence": result.get("confidence"),
                "model_count": len(result.get("model_details", [])),
                "consensus_breakdown": result.get("consensus_breakdown"),
                "use_real_api": ensemble_core.use_real_api
            }
        })
    except Exception as e:
        return jsonify({"error": f"Ensemble test failed: {str(e)}"}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "10000"))
    
    # ✅ NEW: Run startup tasks
    startup_tasks()
    
    app.run(host="0.0.0.0", port=port)
