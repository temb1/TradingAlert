import json
import os
import httpx
import re
from openai import OpenAI
from helpers import get_backtest_stats, _to_float
from config import SYSTEM_PROMPT

# Initialize OpenAI client with API key from environment
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(
    api_key=api_key,
    http_client=httpx.Client()  # Explicit HTTP client to avoid proxies issue
)

def extract_notes_from_text(full_text):
    """Extract meaningful notes from the AI's text response."""
    # Remove potential JSON parts and get the reasoning text
    lines = full_text.split('\n')
    notes_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip lines that look like JSON fields or are empty
        if (line.startswith('{') or line.startswith('}') or 
            re.match(r'"[^"]*"\s*:', line) or
            line.lower() in ['json', '```'] or
            not line):
            continue
        notes_lines.append(line)
    
    notes = ' '.join(notes_lines).strip()
    return notes if notes else "AI analysis completed - review trade setup details above"

def create_structured_response(raw_text):
    """Create a structured response when JSON parsing fails."""
    # Extract direction and confidence from text
    direction = "ignore"
    confidence = "low"
    raw_lower = raw_text.lower()
    
    if "long" in raw_lower and "short" not in raw_lower:
        direction = "long"
    elif "short" in raw_lower and "long" not in raw_lower:
        direction = "short"
        
    if "high confidence" in raw_lower:
        confidence = "high"
    elif "medium confidence" in raw_lower:
        confidence = "medium"
    
    notes = extract_notes_from_text(raw_text)
    
    return json.dumps({
        "direction": direction,
        "confidence": confidence,
        "entry": None,
        "stop": None,
        "tp1": None,
        "tp2": None,
        "single_option": "None",
        "vertical_spread": "None",
        "notes": notes
    })

def parse_ai_response(raw_response):
    """Parse the AI's text response into structured JSON data."""
    try:
        # Try to extract JSON if it exists in the response
        json_match = re.search(r'\{[^{}]*\{?[^{}]*\}?[^{}]*\}', raw_response, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            # Clean up the JSON string
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
            
            data = json.loads(json_str)
            
            # Ensure all required fields exist with proper defaults
            required_fields = {
                "direction": "ignore",
                "confidence": "low", 
                "entry": None,
                "stop": None,
                "tp1": None,
                "tp2": None,
                "single_option": "None",
                "vertical_spread": "None",
                "notes": extract_notes_from_text(raw_response)
            }
            
            for field, default in required_fields.items():
                if field not in data or data[field] is None:
                    data[field] = default
            
            # Ensure notes is never empty
            if not data.get("notes") or data["notes"] in ["n/a", "None", ""]:
                data["notes"] = extract_notes_from_text(raw_response)
                
            return json.dumps(data)
        else:
            # If no JSON found, create structured response from text
            return create_structured_response(raw_response)
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        print(f"❌ Problematic JSON: {json_str if 'json_str' in locals() else 'None'}")
        return create_structured_response(raw_response)
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        return create_structured_response(raw_response)

def build_agent_context(alert_data):
    """Build context for the AI agent from alert data."""
    ticker = str(alert_data.get("ticker", "UNKNOWN")).upper()
    interval = str(alert_data.get("interval", ""))
    pattern = str(alert_data.get("pattern", "")).strip()

    # Extract numeric data
    price = _to_float(alert_data.get("close"))
    ib_high = _to_float(alert_data.get("ib_high"))
    ib_low = _to_float(alert_data.get("ib_low"))
    box_high = _to_float(alert_data.get("box_high"))
    box_low = _to_float(alert_data.get("box_low"))
    atr = _to_float(alert_data.get("atr"))
    raw_msg = str(alert_data.get("message", ""))

    # Calculate ranges and percentages
    ib_range = ib_high - ib_low if ib_high and ib_low else None
    range_percentage = (ib_range / price * 100) if ib_range and price else None

    # Get historical stats
    hist = get_backtest_stats(ticker, pattern)
    print(f"🔍 Historical data for {ticker} {pattern}: {hist}")
    hist_text = ""
    if hist:
        total_trades = hist.get('total_trades', 0)
        winrate = hist.get('winrate_pct', 0)
        avg_rr = hist.get('avg_rr', 0)
        
        hist_text = f"""

Historical Performance for {pattern} on {ticker}:
- Total Trades: {total_trades}
- Win Rate: {winrate}%
- Average Risk/Reward: {avg_rr}
- Edge: {'POSITIVE' if winrate > 50 and avg_rr > 1.2 else 'NEGATIVE' if winrate < 40 else 'NEUTRAL'}"""

    context = f"""
TRADING ALERT ANALYSIS REQUEST

STOCK: {ticker}
PATTERN: {pattern} 
TIMEFRAME: {interval}
CURRENT PRICE: ${price}

KEY LEVELS:
- Inside Bar High: ${ib_high}
- Inside Bar Low: ${ib_low} 
- Inside Bar Range: ${ib_range} ({range_percentage:.2f}% of price)
- ATR (Volatility): ${atr}
- Box High: ${box_high}
- Box Low: ${box_low}

RAW ALERT: {raw_msg}
{hist_text}

ANALYSIS INSTRUCTIONS:
1. Evaluate if this setup meets our ultra-selective criteria
2. Consider historical performance data
3. Assess risk/reward based on price levels and volatility
4. Provide SPECIFIC reasoning for your decision
5. If rejecting, explain exactly why it fails our criteria

Remember: We only take high-probability setups with clear edges.
"""
    return context

def get_agent_decision(alert_data):
    """Get trading decision from OpenAI agent."""
    try:
        context = build_agent_context(alert_data)
        print(f"🔍 Sending context to AI: {context}")
        
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500,
            temperature=0.15,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ]
        )
        reply_text = resp.choices[0].message.content.strip()
        print(f"🔍 RAW AI RESPONSE: {reply_text}")
        
        # Parse the response before returning
        parsed_response = parse_ai_response(reply_text)
        print(f"🔍 PARSED RESPONSE: {parsed_response}")
        
        return parsed_response
        
    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        return json.dumps({
            "direction": "ignore",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "confidence": "low",
            "single_option": "n/a",
            "vertical_spread": "n/a",
            "notes": f"OpenAI error: {str(e)}"
        })
