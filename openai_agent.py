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
    http_client=httpx.Client()
)

def extract_notes_from_text(full_text):
    """Extract meaningful notes from the AI's text response following the expected format."""
    lines = full_text.split('\n')
    notes_lines = []
    in_notes_section = False
    
    for line in lines:
        line = line.strip()
        
        # Skip JSON-like lines and empty lines
        if (re.match(r'^["\*].*:', line) or  # Lines with colons (field labels)
            line.startswith('{') or 
            line.startswith('}') or
            line in ['```', '---', '***'] or
            not line):
            continue
            
        # Detect notes section
        if 'notes' in line.lower() or '###' in line:
            in_notes_section = True
            continue
            
        # Skip confidence/direction headers but capture their content
        if any(header in line.lower() for header in ['direction:', 'confidence:', 'entry:', 'stop:', 'tp1:', 'tp2:', 'single option:', 'vertical spread:']):
            # Extract the value after the colon
            if ':' in line:
                value = line.split(':', 1)[1].strip()
                if value and value.lower() not in ['n/a', 'none']:
                    notes_lines.append(f"{line}")
            continue
            
        # Capture all other meaningful content
        if line and not line.startswith('**') and not line.endswith('**'):
            notes_lines.append(line)
    
    notes = ' '.join(notes_lines).strip()
    
    # If no notes extracted, create meaningful fallback
    if not notes:
        # Try to extract any reasoning from the text
        reasoning_lines = []
        for line in lines:
            clean_line = line.strip()
            if (clean_line and 
                not clean_line.startswith('**') and 
                not clean_line.endswith('**') and
                ':' not in clean_line and
                len(clean_line) > 10):
                reasoning_lines.append(clean_line)
        
        notes = ' '.join(reasoning_lines) if reasoning_lines else "AI provided analysis - review pattern setup and levels above"
    
    return notes

def parse_structured_response(raw_text):
    """Parse the structured format from SYSTEM_PROMPT into JSON."""
    data = {
        "direction": "ignore",
        "confidence": "low",
        "entry": None,
        "stop": None,
        "tp1": None,
        "tp2": None,
        "single_option": "None",
        "vertical_spread": "None",
        "notes": ""
    }
    
    lines = raw_text.split('\n')
    current_field = None
    
    for line in lines:
        line = line.strip()
        
        # Extract field values
        if line.startswith('**Direction:**'):
            value = line.replace('**Direction:**', '').strip()
            if value.upper() in ['LONG', 'SHORT']:
                data["direction"] = value.lower()
        elif line.startswith('**Confidence:**'):
            value = line.replace('**Confidence:**', '').strip()
            if value.upper() in ['LOW', 'MEDIUM', 'HIGH']:
                data["confidence"] = value.lower()
        elif line.startswith('**Entry:**'):
            value = line.replace('**Entry:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["entry"] = value
        elif line.startswith('**Stop:**'):
            value = line.replace('**Stop:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["stop"] = value
        elif line.startswith('**TP1:**'):
            value = line.replace('**TP1:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["tp1"] = value
        elif line.startswith('**TP2:**'):
            value = line.replace('**TP2:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["tp2"] = value
        elif line.startswith('**Single Option:**'):
            value = line.replace('**Single Option:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["single_option"] = value
        elif line.startswith('**Vertical Spread:**'):
            value = line.replace('**Vertical Spread:**', '').strip()
            if value.lower() not in ['n/a', 'none']:
                data["vertical_spread"] = value
    
    # Extract notes using the dedicated function
    data["notes"] = extract_notes_from_text(raw_text)
    
    return json.dumps(data)

def parse_ai_response(raw_response):
    """Parse the AI's response into structured JSON data."""
    try:
        # First try to parse as structured text (from SYSTEM_PROMPT format)
        if any(field in raw_response for field in ['**Direction:**', '**Confidence:**', '**Entry:**']):
            return parse_structured_response(raw_response)
        
        # Then try JSON extraction
        json_match = re.search(r'\{[^{}]*\{?[^{}]*\}?[^{}]*\}', raw_response, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            data = json.loads(json_str)
            
            # Ensure all required fields exist
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
            # Fallback: create structured response from text
            return parse_structured_response(raw_response)
            
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        # Final fallback with notes extraction
        return json.dumps({
            "direction": "ignore",
            "confidence": "low",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "single_option": "None",
            "vertical_spread": "None",
            "notes": extract_notes_from_text(raw_response)
        })

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
