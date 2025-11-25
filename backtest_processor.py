# Version: 3
import json
import csv
import io
from datetime import datetime
from helpers import _to_float, load_backtest_memory, save_backtest_memory

def get_backtest_stats(ticker, pattern):
    """Get historical performance for a specific ticker and pattern."""
    memory = load_backtest_memory()
    key = f"{ticker.upper()}:{pattern.strip()}"
    
    if key in memory:
        return memory[key]
    else:
        # Return default stats if no historical data
        return {
            "ticker": ticker,
            "pattern": pattern,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate_pct": 0,
            "avg_rr": 0
        }

def process_backtest_data(raw_data, content_type, ticker_hint=""):
    """Process backtest data from CSV or JSON."""
    rows = []

    if "application/json" in content_type:
        try:
            payload = json.loads(raw_data.decode("utf-8"))
            if isinstance(payload, dict) and "trades" in payload:
                rows = payload["trades"]
            elif isinstance(payload, list):
                rows = payload
            else:
                return None, "invalid_json_structure"
        except Exception as e:
            print("❌ JSON error:", e)
            return None, "bad_json"
    else:
        # CSV processing
        try:
            text = raw_data.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
        except Exception as e:
            print("❌ CSV error:", e)
            return None, "bad_csv"

    if not rows:
        return None, "no_rows"

    return process_trades(rows, ticker_hint)

def process_trades(rows, ticker_hint):
    """Process and aggregate trade data."""
    summary = {}

    for r in rows:
        row_ticker = (r.get("ticker") or r.get("Ticker") or ticker_hint or "UNKNOWN").upper()
        pattern = (r.get("pattern") or r.get("Pattern") or r.get("Signal") or "").strip() or "unknown"
        key = f"{row_ticker}:{pattern}"

        if key not in summary:
            summary[key] = {
                "ticker": row_ticker,
                "pattern": pattern,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "rr_values": []
            }

        rec = summary[key]
        rec["total_trades"] += 1

        # Determine win/loss
        pl = None
        if r.get("Net P&L USD") not in (None, ""):
            pl = _to_float(r.get("Net P&L USD"))
        elif r.get("Net P&L %") not in (None, ""):
            pl = _to_float(r.get("Net P&L %"))

        if pl is not None:
            if pl > 0:
                rec["wins"] += 1
            elif pl < 0:
                rec["losses"] += 1

        # Compute R:R
        runup = _to_float(r.get("Run-up %") or r.get("Run up %") or r.get("Run-up%"))
        drawdown_raw = _to_float(r.get("Drawdown %") or r.get("Drawdown%"))

        if runup is not None and drawdown_raw not in (None, 0) and runup > 0:
            rr = runup / abs(drawdown_raw)
            if 0 < rr < 20:
                rec["rr_values"].append(rr)

    return finalize_summary(summary)

def finalize_summary(summary):
    """Finalize summary statistics and save to memory."""
    memory = load_backtest_memory()
    out = []

    for key, rec in summary.items():
        total = rec["total_trades"]
        wins = rec["wins"]
        losses = rec["losses"]

        winrate = round((wins / total) * 100, 2) if total > 0 else 0
        avg_rr = round(sum(rec["rr_values"]) / len(rec["rr_values"]), 2) if rec["rr_values"] else None

        result = {
            "ticker": rec["ticker"],
            "pattern": rec["pattern"],
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate,
            "avg_rr": avg_rr
        }

        out.append(result)
        memory[key] = result

    save_backtest_memory(memory)
    print("📊 Backtest summary:", out)
    return out

# New function for direction learning integration
def extract_direction_signals(trade_data, agent_recommendation):
    """
    Extract direction prediction signals from trade data for learning system
    """
    signals = {
        "inside_bar_3_1": False,
        "accumulation": False,
        "manipulation": False,
        "distribution": False,
        "bullish_trend": False,
        "bearish_trend": False
    }
    
    # Extract from pattern name
    pattern = trade_data.get('pattern', '').lower()
    if any(term in pattern for term in ['3-1', 'three one', 'inside bar']):
        signals["inside_bar_3_1"] = True
    
    # Extract from agent reasoning if available
    reasoning = agent_recommendation.get('reasoning', '').lower()
    if 'accumulation' in reasoning:
        signals["accumulation"] = True
    if 'manipulation' in reasoning:
        signals["manipulation"] = True
    if 'distribution' in reasoning:
        signals["distribution"] = True
    if any(term in reasoning for term in ['bullish', 'uptrend', 'rising']):
        signals["bullish_trend"] = True
    if any(term in reasoning for term in ['bearish', 'downtrend', 'falling']):
        signals["bearish_trend"] = True
    
    return signals

def calculate_direction_accuracy(trade_data, predicted_direction):
    """
    Calculate if the direction prediction was accurate
    """
    actual_pl = trade_data.get('Net P&L %') or trade_data.get('Net P&L USD')
    if actual_pl is None:
        return None
    
    # Determine actual direction based on P&L
    if predicted_direction.upper() == 'LONG':
        correct = actual_pl > 0
    elif predicted_direction.upper() == 'SHORT':
        correct = actual_pl < 0
    else:
        return None
    
    return {
        'predicted_direction': predicted_direction,
        'actual_direction': 'BULLISH' if actual_pl > 0 else 'BEARISH',
        'correct': correct,
        'pnl_percent': actual_pl,
        'timestamp': datetime.now().isoformat()
    }

# New function to update direction learning data
def update_direction_learning(trade_data, agent_recommendation, direction_learning_file="direction_learning.json"):
    """
    Update direction learning data with trade outcomes
    """
    try:
        # Load existing direction learning data
        try:
            with open(direction_learning_file, 'r') as f:
                direction_data = json.load(f)
        except FileNotFoundError:
            direction_data = {
                "signal_accuracy": {},
                "prediction_history": [],
                "last_updated": datetime.now().isoformat()
            }
        
        # Extract signals and direction accuracy
        signals = extract_direction_signals(trade_data, agent_recommendation)
        direction_accuracy = calculate_direction_accuracy(
            trade_data, 
            agent_recommendation.get('direction', 'UNKNOWN')
        )
        
        if direction_accuracy:
            # Update prediction history
            direction_data["prediction_history"].append({
                **direction_accuracy,
                "signals": signals,
                "symbol": trade_data.get('ticker', 'UNKNOWN'),
                "pattern": trade_data.get('pattern', 'unknown')
            })
            
            # Update signal accuracy
            for signal_name, is_present in signals.items():
                if is_present:
                    if signal_name not in direction_data["signal_accuracy"]:
                        direction_data["signal_accuracy"][signal_name] = {
                            "correct": 0,
                            "total": 0,
                            "accuracy": 0.0
                        }
                    
                    stats = direction_data["signal_accuracy"][signal_name]
                    stats["total"] += 1
                    if direction_accuracy["correct"]:
                        stats["correct"] += 1
                    stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        
        # Save updated data
        direction_data["last_updated"] = datetime.now().isoformat()
        with open(direction_learning_file, 'w') as f:
            json.dump(direction_data, f, indent=2)
        
        print(f"✅ Updated direction learning data for {trade_data.get('ticker', 'UNKNOWN')}")
        return direction_data
        
    except Exception as e:
        print(f"❌ Error updating direction learning: {e}")
        return None

def get_direction_confidence(signals, direction_learning_file="direction_learning.json"):
    """
    Get confidence score for direction prediction based on historical accuracy
    """
    try:
        with open(direction_learning_file, 'r') as f:
            direction_data = json.load(f)
        
        signal_accuracy = direction_data.get("signal_accuracy", {})
        confidence_scores = []
        
        for signal_name, is_present in signals.items():
            if is_present and signal_name in signal_accuracy:
                accuracy = signal_accuracy[signal_name].get("accuracy", 0)
                if accuracy > 0:  # Only consider signals with historical data
                    confidence_scores.append(accuracy)
        
        # Return average confidence, or neutral if no data
        return sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        
    except FileNotFoundError:
        return 0.5  # Neutral confidence if no learning data yet
    except Exception as e:
        print(f"❌ Error getting direction confidence: {e}")
        return 0.5
