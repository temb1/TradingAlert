import json
import os
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

def save_recommendation_to_db(alert_data, parsed_response):
    """Save trading recommendation to Supabase database for learning"""
    try:
        # Check if Supabase is configured
        if not supabase:
            print("⚠️ Supabase not configured - skipping database save")
            return False
            
        # Extract data from alert
        ticker = str(alert_data.get("ticker", "UNKNOWN")).upper()
        pattern_name = str(alert_data.get("pattern", "")).strip()
        timeframe = _to_float(alert_data.get("interval", 5))
        current_price = _to_float(alert_data.get("close"))
        ib_high = _to_float(alert_data.get("ib_high"))
        ib_low = _to_float(alert_data.get("ib_low"))
        ib_range = ib_high - ib_low if ib_high and ib_low else None
        
        # Parse AI response - handle both string and dict
        if isinstance(parsed_response, str):
            try:
                response_data = json.loads(parsed_response)
            except json.JSONDecodeError:
                # If it's not valid JSON, create a basic response
                response_data = {
                    "direction": "ignore", 
                    "confidence": "low",
                    "notes": parsed_response[:500] if parsed_response else "No analysis provided"
                }
        else:
            response_data = parsed_response
            
        direction = response_data.get("direction", "ignore")
        confidence = response_data.get("confidence", "low")
        notes = response_data.get("notes", "")
        
        # Calculate virtual levels for database tracking
        virtual_entry, virtual_tp1, virtual_sl = calculate_virtual_levels(alert_data, parsed_response)
        
        # Prepare data for Supabase - ensure ALL values are JSON serializable
        recommendation_data = {
            "symbol": ticker,
            "pattern_name": pattern_name,
            "timeframe": int(timeframe) if timeframe else 5,
            "recommendation_direction": str(direction).upper(),
            "confidence": str(confidence).upper(),
            "analysis_notes": str(notes)[:1000] if notes else "No analysis notes",  # Limit length and ensure string
            "current_price": float(current_price) if current_price is not None else 0.0,
            "ib_high": float(ib_high) if ib_high is not None else None,
            "ib_low": float(ib_low) if ib_low is not None else None,
            "ib_range": float(ib_range) if ib_range is not None else None,
            "virtual_entry": float(virtual_entry) if virtual_entry is not None else 0.0,
            "virtual_tp1": float(virtual_tp1) if virtual_tp1 is not None else 0.0,
            "virtual_sl": float(virtual_sl) if virtual_sl is not None else 0.0,
            "status": "PENDING"
        }
        
        # Debug: Print what we're about to insert
        print(f"🔍 Attempting to insert: {json.dumps(recommendation_data, default=str, indent=2)}")
        
        # Insert into Supabase
        response = supabase.table("trade_recommendations").insert(recommendation_data).execute()
        
        if hasattr(response, 'data') and response.data:
            print(f"✅ Saved recommendation to database: {ticker} {pattern_name} - {direction}")
            return True
        else:
            error_msg = getattr(response, 'error', 'Unknown error')
            print(f"❌ Failed to save recommendation: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        
        # Debug: Try to identify which field is causing the issue
        try:
            test_data = recommendation_data.copy()
            for key, value in test_data.items():
                print(f"🔍 Testing {key}: {value} (type: {type(value)})")
                json.dumps({key: value})  # This will fail on the problematic field
        except Exception as debug_e:
            print(f"🔍 Problematic field: {key} - {debug_e}")
            
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
