import json
import os
from supabase import create_client, Client
from config import BACKTEST_MEMORY_FILE, BACKTEST_STATS, SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        current_price = _to_float(alert_data.get("close"))
        ib_high = _to_float(alert_data.get("ib_high"))
        ib_low = _to_float(alert_data.get("ib_low"))
        
        # Parse the AI response
        response_data = json.loads(parsed_response)
        direction = response_data.get("direction", "ignore")
        ai_entry = _to_float(response_data.get("entry"))
        ai_tp1 = _to_float(response_data.get("tp1"))
        ai_sl = _to_float(response_data.get("stop"))
        
        # Calculate IB range for risk calculation
        ib_range = ib_high - ib_low if ib_high and ib_low else None
        
        # If AI provided specific levels, use them
        if ai_entry and ai_tp1 and ai_sl:
            return ai_entry, ai_tp1, ai_sl
        
        # For ignored trades or missing levels, calculate virtual levels
        if direction == "long" and ib_low and ib_high:
            # Long breakout: entry at IB high, TP1 = entry + 1R, SL = IB low
            virtual_entry = ib_high
            virtual_tp1 = virtual_entry + ib_range if ib_range else virtual_entry * 1.01
            virtual_sl = ib_low
        elif direction == "short" and ib_low and ib_high:
            # Short breakout: entry at IB low, TP1 = entry - 1R, SL = IB high
            virtual_entry = ib_low
            virtual_tp1 = virtual_entry - ib_range if ib_range else virtual_entry * 0.99
            virtual_sl = ib_high
        else:
            # For ignore direction or missing data, use current price with default 1% move
            virtual_entry = current_price
            if direction == "long":
                virtual_tp1 = current_price * 1.01
                virtual_sl = current_price * 0.99
            elif direction == "short":
                virtual_tp1 = current_price * 0.99
                virtual_sl = current_price * 1.01
            else:  # ignore or unknown
                virtual_tp1 = current_price * 1.01  # 1% target
                virtual_sl = current_price * 0.99   # 1% stop
        
        return virtual_entry, virtual_tp1, virtual_sl
        
    except Exception as e:
        print(f"❌ Error calculating virtual levels: {e}")
        # Fallback to current price with safe defaults
        current_price = _to_float(alert_data.get("close"), 0)
        return current_price, current_price * 1.01, current_price * 0.99

def save_recommendation_to_db(alert_data, parsed_response):
    """Save trading recommendation to Supabase database for learning"""
    try:
        # Extract data from alert
        ticker = str(alert_data.get("ticker", "UNKNOWN")).upper()
        pattern_name = str(alert_data.get("pattern", "")).strip()
        timeframe = _to_float(alert_data.get("interval", 5))
        current_price = _to_float(alert_data.get("close"))
        ib_high = _to_float(alert_data.get("ib_high"))
        ib_low = _to_float(alert_data.get("ib_low"))
        ib_range = ib_high - ib_low if ib_high and ib_low else None
        
        # Parse AI response
        response_data = json.loads(parsed_response)
        direction = response_data.get("direction", "ignore")
        confidence = response_data.get("confidence", "low")
        notes = response_data.get("notes", "")
        
        # Calculate virtual levels for database tracking
        virtual_entry, virtual_tp1, virtual_sl = calculate_virtual_levels(alert_data, parsed_response)
        
        # Prepare data for Supabase
        recommendation_data = {
            "symbol": ticker,
            "pattern_name": pattern_name,
            "timeframe": timeframe,
            "recommendation_direction": direction.upper(),
            "confidence": confidence.upper(),
            "analysis_notes": notes,
            "current_price": current_price,
            "ib_high": ib_high,
            "ib_low": ib_low,
            "ib_range": ib_range,
            "virtual_entry": virtual_entry,
            "virtual_tp1": virtual_tp1,
            "virtual_sl": virtual_sl,
            "status": "PENDING"
        }
        
        # Insert into Supabase
        response = supabase.table("trade_recommendations").insert(recommendation_data).execute()
        
        if response.data:
            print(f"✅ Saved recommendation to database: {ticker} {pattern_name} - {direction}")
            return True
        else:
            print(f"❌ Failed to save recommendation: {response.error}")
            return False
            
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
        return False

def get_pattern_performance(pattern_name, symbol, timeframe=5):
    """Get historical performance for a pattern to help agent learn"""
    try:
        # Query the pattern_performance view we created
        response = supabase.from_("pattern_performance").select("*").eq("pattern_name", pattern_name).eq("symbol", symbol).eq("timeframe", timeframe).execute()
        
        if response.data:
            return response.data[0]  # Return the first matching record
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error fetching pattern performance: {e}")
        return None
