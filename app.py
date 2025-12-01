# Version 18
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

def initialize_database():
    """Initialize database tables - CONTROLLED for production"""
    try:
        from database_setup import setup_database
        print("🔍 Checking database status...")
        
        # ✅ PRODUCTION: Set this to True when you're ready to enable learning
        ENABLE_DATABASE_LEARNING = False  # Set to True when system is fully ready
        
        if ENABLE_DATABASE_LEARNING:
            print("🚀 Initializing production database...")
            if setup_database():
                print("✅ Database initialized successfully")
                return True
            else:
                print("❌ Database initialization failed")
                return False
        else:
            print("⏸️ Database learning DISABLED (system testing phase)")
            print("   Set ENABLE_DATABASE_LEARNING = True in app.py when ready")
            return None
            
    except Exception as e:
        print(f"⚠️ Database setup error: {e}")
        return False

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
        # ✅ FIXED: Actually use the trading ensemble instead of hardcoded response
        ticker = alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))
        strategy = alert_data.get('strategy', alert_data.get('pattern', ''))
        price = alert_data.get('price', alert_data.get('close', alert_data.get('current_price', 'N/A')))
        
        # Try to get real analysis from trading ensemble
        try:
            # Run trading cycle with the alert data
            market_data = {
                'price': _to_float(price),
                'volume': alert_data.get('volume', 0),
                'strategy': strategy,
                'pattern': alert_data.get('pattern', ''),
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Use the trading ensemble to analyze
            trade = trading_ensemble.run_trading_cycle(ticker, market_data)
            
            if trade:
                # If we got a trade decision, use it
                direction = "LONG" if trade.get('action') == 'BUY' else "SHORT" if trade.get('action') == 'SELL' else "IGNORE"
                confidence = "HIGH" if trade.get('confidence', 0) > 0.7 else "MEDIUM" if trade.get('confidence', 0) > 0.4 else "LOW"
                reasoning = f"Ensemble analysis: {direction} signal with {trade.get('confidence', 0):.1%} confidence"
            else:
                # Fallback to basic analysis
                direction, confidence, reasoning = await _get_basic_analysis(alert_data)
                
        except Exception as e:
            print(f"⚠️ Ensemble analysis failed, using basic analysis: {e}")
            direction, confidence, reasoning = await _get_basic_analysis(alert_data)
        
        # ✅ NEW: Add direction learning insights to output
        direction_learning_insight = ""
        if direction_learner and direction in ['LONG', 'SHORT']:
            try:
                # Extract signals for direction learning
                from helpers import extract_signals_for_learning
                ensemble_decision = {'direction': direction, 'confidence': confidence}
                signals = extract_signals_for_learning(alert_data, ensemble_decision)
                
                # Get direction learning confidence
                learning_direction = 'BULLISH' if direction == 'LONG' else 'BEARISH'
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
        
        formatted_output += f"{direction_emoji.get(direction, '⚫')} **Decision**: {direction}\n"
        formatted_output += f"{confidence_emoji.get(confidence, '💤')} **Confidence**: {confidence}\n"
        formatted_output += f"💰 **Price**: ${price}\n\n"
        
        # ✅ NEW: Add direction learning insight
        if direction_learning_insight:
            formatted_output += f"{direction_learning_insight}\n\n"
        
        formatted_output += "### 📊 Analysis\n"
        formatted_output += f"{reasoning}\n\n"
        
        # Check length and truncate if necessary (very unlikely but safe)
        if len(formatted_output) > 1900:
            formatted_output = formatted_output[:1897] + "..."
            
        return formatted_output
        
    except Exception as e:
        print(f"❌ Ensemble error: {e}")
        # Simple fallback that doesn't break formatting
        return f"## ⚠️ System Update\n\nEnsemble analysis temporarily unavailable.\n\n*Error: {str(e)[:100]}...*"

async def _get_basic_analysis(alert_data):
    """Basic analysis when ensemble is not available"""
    ticker = alert_data.get('ticker', 'UNKNOWN')
    strategy = alert_data.get('strategy', '')
    price = alert_data.get('price', 0)
    
    # Simple trend-based analysis
    if 'bullish' in strategy.lower():
        direction = "LONG"
        confidence = "MEDIUM"
        reasoning = f"Bullish trend pattern detected for {ticker}. Consider long position with tight stop loss."
    elif 'bearish' in strategy.lower():
        direction = "SHORT" 
        confidence = "MEDIUM"
        reasoning = f"Bearish trend pattern detected for {ticker}. Consider short position with tight stop loss."
    else:
        direction = "IGNORE"
        confidence = "LOW"
        reasoning = f"Unclear signal for {ticker}. Waiting for stronger confirmation."
    
    return direction, confidence, reasoning

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
    
    try:
        # ✅ ADDED: Extract strategy name properly
        from helpers import extract_strategy_name
        strategy = extract_strategy_name(data)
        data['strategy'] = strategy
        
        # ✅ ADDED: Check ETF mode with improved logic AND DEBUG
        from market_hours_manager import is_etf
        symbol = data.get('ticker', data.get('symbol', 'UNKNOWN')).upper()
        
        # ✅ ETF detection
        etf_mode = is_etf(symbol)
        data['etf_mode'] = etf_mode
        
        print(f"🔍 ENHANCED DATA - Symbol: {symbol}, Strategy: {strategy}, ETF Mode: {etf_mode}")

        # ✅ PRODUCTION: Control flags for learning and database
        ENABLE_DATABASE_LEARNING = False  # Set to True when system is fully ready
        ENABLE_TRADE_MONITORING = False   # Set to True when price feed is integrated
        
        # Check market hours
        print("📊 Checking market status...")
        market_output, market_result = check_market_status()
        print(f"📊 MARKET STATUS: {market_result['status']}")
        
        agent_reply = ""
        
        # Only process trades if markets are open
        if market_result['status'] in ['TRADING_BOT_STARTED', 'WITHIN_MARKET_HOURS']:
            print("✅ Markets are open - processing trade...")
            
            # ✅ Log strategy details
            print(f"📊 PROCESSING STRATEGY: {strategy}")
            
            # ✅ Extract trend-specific data if available
            additional_data = data.get('additional_data', {})
            if additional_data:
                print(f"📈 ADDITIONAL DATA: {json.dumps(additional_data, indent=2)[:500]}...")
            
            # Get ensemble decision
            print("🤖 Getting ensemble decision...")
            
            try:
                agent_reply = asyncio.run(get_agent_decision(data))
                print(f"🤖 ENSEMBLE DECISION MADE")
                
                # ✅ Parse the agent reply for logging
                if isinstance(agent_reply, dict):
                    direction = agent_reply.get('direction', 'UNKNOWN')
                    confidence = agent_reply.get('confidence', 'LOW')
                    consensus = agent_reply.get('consensus_breakdown', {})
                    print(f"   Direction: {direction}, Confidence: {confidence}")
                    print(f"   Consensus: {consensus}")
                else:
                    print(f"   Raw reply: {str(agent_reply)[:200]}...")
                    
            except Exception as e:
                print(f"❌ Error getting ensemble decision: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                agent_reply = {
                    "direction": "IGNORE",
                    "confidence": "LOW",
                    "reasoning": f"System error: {str(e)[:100]}",
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
            # Convert agent_reply to dictionary if it's a string
            if isinstance(agent_reply, str):
                try:
                    parsed = json.loads(agent_reply)
                except:
                    parsed = {"message": agent_reply, "raw": True}
            elif isinstance(agent_reply, dict):
                parsed = agent_reply
            else:
                parsed = {"message": str(agent_reply), "type": str(type(agent_reply))}
                
            # Add system metadata
            parsed["system"] = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "market_status": market_result['status'],
                "database_learning_enabled": ENABLE_DATABASE_LEARNING,
                "trade_monitoring_enabled": ENABLE_TRADE_MONITORING
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
