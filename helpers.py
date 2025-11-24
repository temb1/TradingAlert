# Version 9
import json
import os
import datetime
from datetime import timezone
from supabase import create_client, Client
from config import BACKTEST_MEMORY_FILE, BACKTEST_STATS

# Initialize Supabase client from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("⚠️ Supabase credentials not found in environment variables")
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

def save_recommendation_to_db(alert_data, parsed_response):
    """Save trading recommendation to Supabase database for learning - FIXED DATA TYPES"""
    try:
        # Check if Supabase is configured
        if not supabase:
            print("⚠️ Supabase not configured - skipping database save")
            return {"success": False, "error": "Supabase not configured"}
        
        print("💾 Starting database save process...")
        
        # Extract basic data from alert with safe defaults
        ticker = str(alert_data.get("ticker", alert_data.get("symbol", "UNKNOWN"))).upper()
        pattern_name = str(alert_data.get("pattern", alert_data.get("strategy", "unknown"))).strip()
        
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
        
        # Safely parse AI response - handle both string and dict formats
        if isinstance(parsed_response, str):
            try:
                # Try to parse as JSON first
                response_data = json.loads(parsed_response)
            except json.JSONDecodeError:
                # If it's not JSON, try to extract from the text format
                response_data = {}
                import re
                
                # Extract direction from various formats
                direction_match = re.search(r'\*\*Direction:\*\*\s*(LONG|SHORT|IGNORE)', parsed_response, re.IGNORECASE)
                if direction_match:
                    response_data["direction"] = direction_match.group(1).upper()
                
                # Extract confidence from various formats
                confidence_match = re.search(r'\*\*Confidence:\*\*\s*(LOW|MEDIUM|HIGH)', parsed_response, re.IGNORECASE)
                if confidence_match:
                    response_data["confidence"] = confidence_match.group(1).upper()
                
                # ✅ ADDED: Extract trade levels
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
        else:
            response_data = parsed_response
            
        direction = str(response_data.get("direction", "ignore")).upper()
        confidence = str(response_data.get("confidence", "low")).upper()
        notes = str(response_data.get("notes", response_data.get("reasoning", "")))[:500]  # Limit length
        
        # ✅ FIXED: Extract trade levels from response with proper None handling
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
        
        # ✅ FIXED: Create the data payload with PROPER DATA TYPES and NULL handling
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
            "virtual_tp1": float(virtual_tp1),  # ⚠️ NOTE: Check if your schema has "virtual_tpl" instead!
            "virtual_sl": float(virtual_sl),
            # ✅ FIXED: Trade level fields with proper NULL handling
            "entry_price": float(entry_price) if entry_price is not None else None,
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
            "take_profit_1": float(take_profit_1) if take_profit_1 is not None else None,
            "take_profit_2": float(take_profit_2) if take_profit_2 is not None else None,
            "single_option": single_option,
            "vertical_spread": vertical_spread,
            "status": "PENDING",
            "strategy": extract_strategy_name(alert_data), 
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        # ✅ FIXED: Clean data - remove None values that might cause JSON issues
        clean_data = {k: v for k, v in recommendation_data.items() if v is not None}
        
        print(f"🔍 Attempting database insert for {ticker} {pattern_name}...")
        print(f"💰 Trade levels - Entry: {entry_price}, Stop: {stop_loss}, TP1: {take_profit_1}, TP2: {take_profit_2}")
        print(f"📊 Clean data prepared with {len(clean_data)} fields")
        
        # Test JSON serialization first
        try:
            test_json = json.dumps(clean_data, default=str)
            print(f"✅ JSON test passed: {len(test_json)} characters")
        except Exception as json_error:
            print(f"❌ JSON test failed: {json_error}")
            # Create emergency fallback data with guaranteed valid types
            clean_data = {
                "symbol": ticker,
                "pattern_name": "ERROR_RECOVERY",
                "timeframe": 5,
                "recommendation_direction": "IGNORE",
                "confidence": "LOW",
                "analysis_notes": f"Database save error - using fallback. Original: {str(json_error)[:100]}",
                "current_price": 1.0,
                "ib_high": 1.0,
                "ib_low": 1.0,
                "ib_range": 0.0,
                "virtual_entry": 1.0,
                "virtual_tp1": 1.01,
                "virtual_sl": 0.99,
                "single_option": "None",
                "vertical_spread": "None",
                "status": "PENDING",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        
        # Insert into Supabase
        response = supabase.table("trade_recommendations").insert(clean_data).execute()
        
        # Check response
        if hasattr(response, 'data') and response.data:
            record_id = response.data[0].get('id', 'unknown')
            print(f"✅ Successfully saved to database: {ticker} {pattern_name} (ID: {record_id})")
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

def test_supabase_connection():
    """Test if Supabase connection is working"""
    try:
        if not supabase:
            print("❌ Supabase client not initialized")
            return False
            
        # Simple test query
        response = supabase.table("trade_recommendations").select("count", count="exact").execute()
        
        if hasattr(response, 'count'):
            print(f"✅ Supabase connection working - found {response.count} records")
            return True
        else:
            print("❌ Supabase connection test failed")
            return False
            
    except Exception as e:
        print(f"❌ Supabase connection error: {e}")
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
