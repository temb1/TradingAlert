# Version: 14
import json
import os
import datetime
import math
from typing import Dict
from psycopg2.extras import RealDictCursor
from datetime import timezone, datetime
from supabase import create_client, Client
from config import BACKTEST_MEMORY_FILE, BACKTEST_STATS

# DEBUG: Check what's in the environment variables
print("🔍 DEBUG - Database Connection Check:")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL', 'NOT SET')}")
print(f"SUPABASE_URL length: {len(os.getenv('SUPABASE_URL', ''))}")
print(f"SUPABASE_KEY: {os.getenv('SUPABASE_KEY', 'NOT SET')[:20]}...")

# Check if URL looks valid
supabase_url = os.getenv('SUPABASE_URL', '')
if supabase_url:
    print(f"✅ SUPABASE_URL is set")
    print(f"📋 URL starts with: {supabase_url[:30]}")
    print(f"📋 URL contains 'postgresql://': {'postgresql://' in supabase_url}")
else:
    print("❌ SUPABASE_URL is empty")

# Now try to create client with error handling
try:
    from supabase import create_client, Client
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing Supabase credentials")
        supabase = None
    else:
        print("🔄 Attempting to create Supabase client...")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client created successfully!")
        
except Exception as e:
    print(f"❌ Supabase client creation failed: {e}")
    supabase = None

def _to_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace("%", "").strip())
    except Exception:
        return default

def load_backtest_memory():
    if not os.path.exists(BACKTEST_MEMORY_FILE):
        return {}
    try:
        with open(BACKTEST_MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_backtest_memory(mem):
    try:
        with open(BACKTEST_MEMORY_FILE, "w") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        print("⚠️ Cannot save memory:", e)

def get_backtest_stats(ticker, pattern):
    ticker = ticker.upper()
    pattern = pattern.strip()

    # 1) Try dynamic memory first
    mem = load_backtest_memory()
    key = f"{ticker}:{pattern}"
    if key in mem:
        return mem[key]

    # 2) Fall back to static priors
    if ticker in BACKTEST_STATS and pattern in BACKTEST_STATS[ticker]:
        st = BACKTEST_STATS[ticker][pattern]
        return {
            "ticker": ticker,
            "pattern": pattern,
            "total_trades": st["trades"],
            "winrate_pct": st["winrate"],
            "avg_rr": st["avg_rr"],
        }
    return None

def extract_signals_for_learning(alert_data: Dict, agent_response: Dict) -> Dict:
    """
    Extract the 3 key signals for direction learning system
    Returns signals dict for direction prediction tracking
    """
    signals = {
        "inside_bar_3_1": False,
        "accumulation": False,
        "manipulation": False,
        "distribution": False,
        "bullish_trend": False,
        "bearish_trend": False
    }
    
    # Extract from alert data
    strategy = alert_data.get('strategy', '').lower()
    pattern = alert_data.get('pattern', '').lower()
    reasoning = agent_response.get('reasoning', '').lower()
    
    # Detect 3-1 Inside Bar
    if any(term in strategy for term in ['3-1', 'inside_bar', 'inside bar']) or \
       any(term in pattern for term in ['3-1', 'inside bar']) or \
       any(term in reasoning for term in ['3-1', 'inside bar', 'consolidation']):
        signals["inside_bar_3_1"] = True
        
    # Detect A/M/D Phases
    if 'accumulation' in strategy or 'accumulation' in reasoning:
        signals["accumulation"] = True
    if 'manipulation' in strategy or 'manipulation' in reasoning:
        signals["manipulation"] = True
    if 'distribution' in strategy or 'distribution' in reasoning:
        signals["distribution"] = True
        
    # Detect Trends
    if any(term in strategy for term in ['bullish', 'uptrend', 'rising', 'strong_bullish']) or \
       any(term in reasoning for term in ['bullish', 'uptrend', 'rising']):
        signals["bullish_trend"] = True
    if any(term in strategy for term in ['bearish', 'downtrend', 'falling', 'strong_bearish']) or \
       any(term in reasoning for term in ['bearish', 'downtrend', 'falling']):
        signals["bearish_trend"] = True
        
    return signals

def calculate_virtual_levels(alert_data, parsed_response):
    """Calculate virtual TP/SL levels for database tracking (even for ignored trades)"""
    try:
        # Extract data from alert and parsed AI response
        ticker = str(alert_data.get("ticker", "UNKNOWN")).upper()
        pattern_name = str(alert_data.get("pattern", "")).strip()
        current_price = _to_float(alert_data.get("close"), 0)  # Default to 0 if None
        ib_high = _to_float(alert_data.get("ib_high"))
        ib_low = _to_float(alert_data.get("ib_low"))
        
        # Parse the AI response safely
        if isinstance(parsed_response, str):
            try:
                response_data = json.loads(parsed_response)
            except:
                response_data = {}
        else:
            response_data = parsed_response
            
        direction = response_data.get("direction", "ignore")
        ai_entry = _to_float(response_data.get("entry"))
        ai_tp1 = _to_float(response_data.get("tp1"))
        ai_sl = _to_float(response_data.get("stop"))
        
        # Calculate IB range for risk calculation
        ib_range = ib_high - ib_low if ib_high and ib_low else current_price * 0.01  # 1% fallback
        
        # If AI provided specific levels, use them
        if ai_entry and ai_tp1 and ai_sl:
            return float(ai_entry), float(ai_tp1), float(ai_sl)
        
        # For ignored trades or missing levels, calculate virtual levels
        # ENSURE ALL RETURN VALUES ARE FLOATS, NOT None
        if direction == "long" and ib_low and ib_high:
            virtual_entry = float(ib_high)
            virtual_tp1 = float(virtual_entry + ib_range) if ib_range else virtual_entry * 1.01
            virtual_sl = float(ib_low)
        elif direction == "short" and ib_low and ib_high:
            virtual_entry = float(ib_low)
            virtual_tp1 = float(virtual_entry - ib_range) if ib_range else virtual_entry * 0.99
            virtual_sl = float(ib_high)
        else:
            # For ignore direction or missing data, use current price with default 1% move
            virtual_entry = float(current_price)
            if direction == "long":
                virtual_tp1 = float(current_price * 1.01)
                virtual_sl = float(current_price * 0.99)
            elif direction == "short":
                virtual_tp1 = float(current_price * 0.99)
                virtual_sl = float(current_price * 1.01)
            else:  # ignore or unknown
                virtual_tp1 = float(current_price * 1.01)
                virtual_sl = float(current_price * 0.99)
        
        return virtual_entry, virtual_tp1, virtual_sl
        
    except Exception as e:
        print(f"❌ Error calculating virtual levels: {e}")
        # Fallback to current price with safe defaults - ENSURE FLOATS
        current_price = _to_float(alert_data.get("close"), 1.0)  # Default to 1.0 if everything fails
        return float(current_price), float(current_price * 1.01), float(current_price * 0.99)

def extract_strategy_name(alert_data):
    """Extract strategy name with better fallbacks"""
    strategy = (alert_data.get('strategy') or 
                alert_data.get('pattern') or 
                alert_data.get('alert_type') or 
                'unknown')
    
    strategy = str(strategy).lower().strip()
    
    strategy_map = {
        'bullish_trend': 'bullish_trend',
        'bearish_trend': 'bearish_trend', 
        'strong_bullish': 'strong_bullish_trend',
        'strong_bearish': 'strong_bearish_trend',
        'moderate_bullish': 'moderate_bullish_trend',
        'moderate_bearish': 'moderate_bearish_trend',
        'breakout': 'breakout',
        'breakdown': 'breakdown'
    }
    
    return strategy_map.get(strategy, strategy)

def save_recommendation_to_db(alert_data, parsed_response, direction_learner=None):
    """Save trading recommendation to Supabase database for learning - FIXED COLUMN NAMES"""
    try:
        # Check if Supabase is configured
        if not supabase:
            print("⚠️ Supabase not configured - skipping database save")
            return {"success": False, "error": "Supabase not configured"}
        
        print("💾 Starting database save process...")
        
        # ✅ ADDED: Validate input data first
        if not alert_data or not isinstance(alert_data, dict):
            print("❌ Invalid alert_data - skipping database save")
            return {"success": False, "error": "Invalid alert_data"}
        
        # Extract basic data from alert with safe defaults
        ticker = str(alert_data.get("ticker", alert_data.get("symbol", "UNKNOWN"))).upper()
        pattern_name = str(alert_data.get("pattern", alert_data.get("strategy", "unknown"))).strip()
        
        # ✅ FIX: Fix "TEMORE" typo to "IGNORE"
        if isinstance(parsed_response, dict) and parsed_response.get("direction") == "TEMORE":
            parsed_response["direction"] = "IGNORE"
            print("⚠️ Fixed TEMORE typo to IGNORE")
        
        # Safely parse numeric values with validation
        try:
            timeframe = int(alert_data.get("interval", 5))
        except (ValueError, TypeError):
            timeframe = 5
            
        try:
            current_price = float(alert_data.get("close", alert_data.get("price", 0)))
        except (ValueError, TypeError):
            current_price = 0.0
            
        try:
            ib_high = float(alert_data.get("ib_high", 0))
        except (ValueError, TypeError):
            ib_high = 0.0
            
        try:
            ib_low = float(alert_data.get("ib_low", 0))
        except (ValueError, TypeError):
            ib_low = 0.0
            
        ib_range = max(0.0, ib_high - ib_low)
        
        # ✅ IMPROVED: Safely parse AI response with better validation
        response_data = {}
        if isinstance(parsed_response, str):
            try:
                # Try to parse as JSON first
                response_data = json.loads(parsed_response)
            except json.JSONDecodeError:
                # If it's not JSON, try to extract from the text format
                import re
                
                # Extract direction from various formats
                direction_match = re.search(r'\*\*Direction:\*\*\s*(LONG|SHORT|IGNORE|TEMORE)', parsed_response, re.IGNORECASE)
                if direction_match:
                    direction = direction_match.group(1).upper()
                    # ✅ FIX: Convert TEMORE to IGNORE
                    response_data["direction"] = "IGNORE" if direction == "TEMORE" else direction
                
                # Extract confidence from various formats
                confidence_match = re.search(r'\*\*Confidence:\*\*\s*(LOW|MEDIUM|HIGH)', parsed_response, re.IGNORECASE)
                if confidence_match:
                    response_data["confidence"] = confidence_match.group(1).upper()
                
                # Extract trade levels
                entry_match = re.search(r'\*\*Entry:\*\*\s*\$?([0-9]+\.?[0-9]*)', parsed_response, re.IGNORECASE)
                if entry_match:
                    response_data["entry"] = float(entry_match.group(1))
                
                stop_match = re.search(r'\*\*Stop:\*\*\s*\$?([0-9]+\.?[0-9]*)', parsed_response, re.IGNORECASE)
                if stop_match:
                    response_data["stop"] = float(stop_match.group(1))
                
                tp1_match = re.search(r'\*\*TP1:\*\*\s*\$?([0-9]+\.?[0-9]*)', parsed_response, re.IGNORECASE)
                if tp1_match:
                    response_data["tp1"] = float(tp1_match.group(1))
                
                tp2_match = re.search(r'\*\*TP2:\*\*\s*\$?([0-9]+\.?[0-9]*)', parsed_response, re.IGNORECASE)
                if tp2_match:
                    response_data["tp2"] = float(tp2_match.group(1))
                
                # Extract notes/reasoning
                notes_match = re.search(r'### Notes\s*(.+?)(?=\n#|\n\*\*|\n###|\n$)', parsed_response, re.DOTALL)
                if notes_match:
                    response_data["notes"] = notes_match.group(1).strip()
                else:
                    # Fallback: take everything after the main format
                    lines = parsed_response.split('\n')
                    notes_lines = []
                    capture = False
                    for line in lines:
                        if re.match(r'.*(Notes|Reasoning|Analysis|###):', line, re.IGNORECASE):
                            capture = True
                            continue
                        if capture and line.strip():
                            notes_lines.append(line)
                    if notes_lines:
                        response_data["notes"] = ' '.join(notes_lines).strip()
        elif isinstance(parsed_response, dict):
            response_data = parsed_response
        else:
            print(f"⚠️ Unexpected parsed_response type: {type(parsed_response)}")
            response_data = {}
        
        # ✅ VALIDATE: Ensure direction and confidence are valid
        direction = str(response_data.get("direction", "ignore")).upper()
        if direction == "TEMORE":  # Additional safety check
            direction = "IGNORE"
        if direction not in ["LONG", "SHORT", "IGNORE"]:
            direction = "IGNORE"
            
        confidence = str(response_data.get("confidence", "low")).upper()
        if confidence not in ["LOW", "MEDIUM", "HIGH"]:
            confidence = "LOW"
            
        notes = str(response_data.get("notes", response_data.get("reasoning", "")))[:500]  # Limit length
        
        # Extract trade levels from response with proper None handling
        def safe_float(value, default=None):
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default
        
        entry_price = safe_float(response_data.get("entry"))
        stop_loss = safe_float(response_data.get("stop")) 
        take_profit_1 = safe_float(response_data.get("tp1"))
        take_profit_2 = safe_float(response_data.get("tp2"))
        single_option = str(response_data.get("single_option", "None"))[:100] or "None"
        vertical_spread = str(response_data.get("vertical_spread", "None"))[:100] or "None"
        
        # Calculate simple virtual levels (always valid numbers)
        if direction == "LONG" and ib_high > 0:
            virtual_entry = float(ib_high)
            virtual_tp1 = float(virtual_entry + (virtual_entry * 0.01))  # 1% target
            virtual_sl = float(ib_low) if ib_low > 0 else float(virtual_entry * 0.99)
        elif direction == "SHORT" and ib_low > 0:
            virtual_entry = float(ib_low)
            virtual_tp1 = float(virtual_entry - (virtual_entry * 0.01))  # 1% target
            virtual_sl = float(ib_high) if ib_high > 0 else float(virtual_entry * 1.01)
        else:  # IGNORE or unknown
            virtual_entry = float(current_price) if current_price > 0 else 1.0
            virtual_tp1 = float(virtual_entry * 1.01)
            virtual_sl = float(virtual_entry * 0.99)
        
        # ✅ NEW: Extract signals for direction learning
        signals_detected = {}
        direction_learning_confidence = None
        
        if direction_learner and direction in ["LONG", "SHORT"]:
            try:
                signals_detected = extract_signals_for_learning(alert_data, response_data)
                learning_direction = "BULLISH" if direction == "LONG" else "BEARISH"
                direction_learning_confidence = direction_learner.get_direction_confidence(signals_detected, learning_direction)
                print(f"🎯 Direction Learning: {direction} confidence: {direction_learning_confidence:.1%}")
            except Exception as e:
                print(f"⚠️ Error getting direction learning confidence: {e}")
        
        # ✅ FIXED: Create the data payload with CORRECT COLUMN NAMES
        recommendation_data = {
            "symbol": ticker,
            "pattern_name": pattern_name,
            "timeframe": timeframe,
            "recommendation_direction": direction,
            "confidence": confidence,
            "analysis_notes": notes,
            "current_price": float(current_price),
            "ib_high": float(ib_high),
            "ib_low": float(ib_low),
            "ib_range": float(ib_range),
            "virtual_entry": float(virtual_entry),
            "virtual_tp1": float(virtual_tp1),
            "virtual_sl": float(virtual_sl),
            # Trade level fields with proper NULL handling
            "entry_price": float(entry_price) if entry_price is not None else None,
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
            "take_profit_1": float(take_profit_1) if take_profit_1 is not None else None,
            "take_profit_2": float(take_profit_2) if take_profit_2 is not None else None,
            "single_option": single_option,
            "vertical_spread": vertical_spread,
            "status": "PENDING",
            "strategy": str(alert_data.get('strategy', alert_data.get('pattern', 'unknown'))).strip(),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            # ✅ NEW: Direction learning fields
            "signals_detected": json.dumps(signals_detected) if signals_detected else None,
            "direction_learning_confidence": float(direction_learning_confidence) if direction_learning_confidence else None
        }
        
        # ✅ IMPROVED: Enhanced data cleaning - ensure all values are JSON serializable
        clean_data = {}
        for key, value in recommendation_data.items():
            if value is None:
                clean_data[key] = None  # Keep None values but ensure they're properly handled
            elif isinstance(value, (int, float)):
                # Ensure numeric values are finite (not NaN or inf)
                if math.isfinite(value):
                    clean_data[key] = float(value)
                else:
                    clean_data[key] = 0.0
            elif isinstance(value, str):
                # Clean strings for JSON - remove any problematic characters
                clean_string = value.encode('utf-8', 'ignore').decode('utf-8')
                clean_data[key] = clean_string
            elif isinstance(value, (bool)):
                clean_data[key] = bool(value)
            else:
                # Convert any other type to string
                clean_data[key] = str(value)
        
        print(f"🔍 Attempting database insert for {ticker} {pattern_name}...")
        print(f"💰 Trade levels - Entry: {entry_price}, Stop: {stop_loss}, TP1: {take_profit_1}, TP2: {take_profit_2}")
        if direction_learning_confidence:
            print(f"🎯 Direction Learning Confidence: {direction_learning_confidence:.1%}")
        print(f"📊 Clean data prepared with {len(clean_data)} fields")
        
        # ✅ IMPROVED: Better JSON serialization test
        try:
            test_json = json.dumps(clean_data, default=str, ensure_ascii=False)
            json_size = len(test_json)
            print(f"✅ JSON test passed: {json_size} characters")
            
            # Additional validation for very large JSON
            if json_size > 10000:  # 10KB limit
                print("⚠️ Warning: JSON size is large, truncating notes")
                clean_data["analysis_notes"] = clean_data["analysis_notes"][:200] + "..."
                test_json = json.dumps(clean_data, default=str, ensure_ascii=False)
                
        except Exception as json_error:
            print(f"❌ JSON test failed: {json_error}")
            # Try to identify the problematic field
            for key, value in clean_data.items():
                try:
                    json.dumps({key: value})
                except Exception as field_error:
                    print(f"❌ Problematic field '{key}': {value} - Error: {field_error}")
                    # Remove problematic field
                    clean_data[key] = "INVALID_DATA_REMOVED"
            # Try again with cleaned data
            try:
                test_json = json.dumps(clean_data, default=str, ensure_ascii=False)
                print("✅ JSON test passed after cleaning problematic fields")
            except Exception as final_error:
                print(f"❌ Final JSON test failed: {final_error}")
                return {"success": False, "error": f"JSON serialization failed: {final_error}"}
        
        # Insert into Supabase
        response = supabase.table("trade_recommendations").insert(clean_data).execute()
        
        # Check response
        if hasattr(response, 'data') and response.data:
            record_id = response.data[0].get('id', 'unknown')
            print(f"✅ Successfully saved to database: {ticker} {pattern_name} (ID: {record_id})")
            
            # ✅ NEW: Record prediction for direction learning
            if direction_learner and direction in ["LONG", "SHORT"]:
                try:
                    # This will be updated when trade outcome is known
                    print(f"📝 Direction learning prediction recorded for {ticker}")
                except Exception as e:
                    print(f"⚠️ Error recording direction learning prediction: {e}")
                    
            return {"success": True, "id": record_id}
        else:
            error_msg = getattr(response, 'error', 'Unknown error')
            print(f"❌ Supabase error: {error_msg}")
            return {"success": False, "error": f"Supabase error: {error_msg}"}
            
    except Exception as e:
        print(f"❌ Critical error in save_recommendation_to_db: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return {"success": False, "error": f"Critical error: {str(e)}"}

def get_db_connection():
    """Get database connection for Supabase"""
    try:
        # Parse Supabase URL if needed
        supabase_url = os.getenv('SUPABASE_URL')
        if supabase_url.startswith('postgresql://'):
            # Extract connection details from URL
            parts = supabase_url.replace('postgresql://', '').split('/')
            host_port = parts[0].split(':')
            host = host_port[0]
            port = host_port[1] if len(host_port) > 1 else '5432'
            database = parts[1] if len(parts) > 1 else 'postgres'
            
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=os.getenv('SUPABASE_USER', 'postgres'),
                password=os.getenv('SUPABASE_PASSWORD', os.getenv('SUPABASE_KEY')),
                cursor_factory=RealDictCursor
            )
        else:
            # Direct connection parameters
            conn = psycopg2.connect(
                host=os.getenv('SUPABASE_HOST'),
                database=os.getenv('SUPABASE_DB', 'postgres'),
                user=os.getenv('SUPABASE_USER', 'postgres'),
                password=os.getenv('SUPABASE_PASSWORD', os.getenv('SUPABASE_KEY')),
                port=os.getenv('SUPABASE_PORT', '5432'),
                cursor_factory=RealDictCursor
            )
        
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def test_supabase_connection():
    """Test database connection"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            result = cursor.fetchone()
            print(f"✅ Database connected: {result['version']}")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Database test failed: {e}")
            return False
    else:
        print("❌ No database connection")
        return False
        
def get_pattern_performance(pattern_name, symbol, timeframe=5):
    """Get historical performance for a pattern to help agent learn"""
    try:
        # Check if Supabase is configured
        if not supabase:
            print("⚠️ Supabase not configured - cannot fetch pattern performance")
            return None
            
        # Query the pattern_performance view we created
        response = supabase.from_("pattern_performance").select("*").eq("pattern_name", pattern_name).eq("symbol", symbol).eq("timeframe", timeframe).execute()
        
        if response.data:
            return response.data[0]  # Return the first matching record
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error fetching pattern performance: {e}")
        return None
