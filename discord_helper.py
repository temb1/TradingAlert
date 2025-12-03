# Version: 27
import os
import json
import requests
from datetime import datetime
import re

from helpers import _to_float
from config import DISCORD_WEBHOOK_URL

def extract_from_plain_text(ai_response):
    """
    Extract structured data from plain text AI responses when JSON parsing fails.
    """
    # Default response
    response_data = {
        "reasoning": ai_response,
        "direction": "IGNORE",
        "confidence": "LOW"
    }
    
    # Convert to uppercase for easier matching
    text_upper = ai_response.upper()
    
    # Extract direction
    if "IGNORE" in text_upper:
        response_data["direction"] = "IGNORE"
    elif "BULLISH" in text_upper or "LONG" in text_upper:
        response_data["direction"] = "BULLISH"
    elif "BEARISH" in text_upper or "SHORT" in text_upper:
        response_data["direction"] = "BEARISH"
    
    # Extract confidence
    if "HIGH CONFIDENCE" in text_upper or "HIGH" in text_upper.split():
        response_data["confidence"] = "HIGH"
    elif "MEDIUM CONFIDENCE" in text_upper or "MEDIUM" in text_upper.split():
        response_data["confidence"] = "MEDIUM"
    elif "LOW CONFIDENCE" in text_upper or "LOW" in text_upper.split():
        response_data["confidence"] = "LOW"
    
    # Try to find model count
    model_match = re.search(r'(\d+)/(\d+)\s+models', text_upper)
    if model_match:
        response_data["model_count"] = int(model_match.group(1))
    
    # Try to extract entry, stop, tp levels if present
    entry_match = re.search(r'entry\s*[:=]\s*\$?([\d.]+)', ai_response, re.IGNORECASE)
    if entry_match:
        response_data["entry"] = entry_match.group(1)
    
    stop_match = re.search(r'stop\s*[:=]\s*\$?([\d.]+)', ai_response, re.IGNORECASE)
    if stop_match:
        response_data["stop"] = stop_match.group(1)
    
    return response_data

def get_best_reasoning(ensemble_decision, model_details):
    """
    Get the best reasoning from available models.
    """
    direction = ensemble_decision.get("direction", "IGNORE")
    confidence = ensemble_decision.get("confidence", "LOW")
    breakdown = ensemble_decision.get("consensus_breakdown", {})
    
    # Get counts from breakdown
    long_count = breakdown.get("LONG", breakdown.get("BULLISH", 0))
    short_count = breakdown.get("SHORT", breakdown.get("BEARISH", 0))
    ignore_count = breakdown.get("IGNORE", 0)
    total = long_count + short_count + ignore_count
    
    # If we have model details, use their reasoning
    if model_details:
        for model in model_details:
            reasoning = model.get("reasoning", "")
            if reasoning and len(reasoning) > 50:
                # Remove template headers
                lines = reasoning.strip().split('\n')
                cleaned_lines = []
                skip_next = False
                
                for line in lines:
                    # Skip template header lines
                    if line.startswith('###') or 'Decision:' in line or 'Confidence:' in line or 'Price:' in line:
                        skip_next = False
                        continue
                    if skip_next:
                        skip_next = False
                        continue
                    cleaned_lines.append(line)
                
                cleaned_text = '\n'.join(cleaned_lines).strip()
                if cleaned_text and len(cleaned_text) > 50:
                    return cleaned_text
    
    # If no model details, generate descriptive reasoning
    if total == 0:
        # Use the raw reasoning from response if available
        raw_reasoning = ensemble_decision.get("reasoning", "")
        if raw_reasoning and len(raw_reasoning) > 20:
            return raw_reasoning
        else:
            # Fallback to indicator-based reasoning
            return f"No model consensus available. Technical indicators suggest {direction.lower()} bias with {confidence.lower()} confidence."
    
    # Build reasoning based on consensus
    if direction == "LONG" or direction == "BULLISH":
        return f"{long_count}/{total} models recommend LONG with {confidence.lower()} confidence. Technical indicators suggest bullish momentum."
    elif direction == "SHORT" or direction == "BEARISH":
        return f"{short_count}/{total} models recommend SHORT with {confidence.lower()} confidence. Technical indicators suggest bearish momentum."
    elif direction == "IGNORE":
        return f"{ignore_count}/{total} models recommend IGNORE with {confidence.lower()} confidence. Mixed signals or unclear market direction."
    else:
        return f"Awaiting clearer market direction with {confidence.lower()} confidence."


def send_to_discord(alert_data, ai_response, webhook_url=None):
    """
    Send trading alert to Discord.
    """
    try:
        # Webhook
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or DISCORD_WEBHOOK_URL

        if not webhook_url:
            print("❌ No Discord webhook URL configured")
            return False

        # --- Debug logging ---
        print("\n" + "="*50)
        print("🔍 DISCORD SENDER DEBUG INFO")
        print("="*50)

        # Parse ai_response
        response_data = {}
        if isinstance(ai_response, str):
            ai_response = ai_response.strip()
            if ai_response:
                try:
                    response_data = json.loads(ai_response)
                    print("✅ Parsed JSON response_data")
                except Exception:
                    print("⚠️ ai_response is not JSON, treating as plain text")
                    # Try to extract structured data from plain text
                    response_data = extract_from_plain_text(ai_response)
                    print(f"✅ Extracted from plain text: {response_data}")
        elif isinstance(ai_response, dict):
            response_data = ai_response
            print("✅ Using dict response_data")
        else:
            print(f"⚠️ Unexpected ai_response type: {type(ai_response)}")
            response_data = {"reasoning": str(ai_response)}
        
        # REMOVED THE EARLY RETURN STATEMENT THAT WAS HERE!
        # The bug was: "return response_data" which prevented Discord sending

        alert_data = alert_data or {}
        print(f"📊 alert_data keys: {list(alert_data.keys())}")
        if response_data:
            print(f"📊 response_data keys: {list(response_data.keys())}")

        # --- Extract data with better defaults ---
        ticker = alert_data.get("ticker", "UNKNOWN").upper()
        strategy = alert_data.get("strategy", alert_data.get("pattern", "unknown"))
        
        # DEBUG: Check what's available
        print(f"\n🔍 DATA EXTRACTION:")
        print(f"  Ticker: {ticker}")
        print(f"  Strategy: {strategy}")
        print(f"  alert_data direction: {alert_data.get('direction')}")
        print(f"  alert_data confidence: {alert_data.get('confidence')}")
        print(f"  response_data direction: {response_data.get('direction')}")
        print(f"  response_data confidence: {response_data.get('confidence')}")

        # Get direction - FIXED: Default to IGNORE if not specified
        direction = "IGNORE"  # Default for safety
        if alert_data.get("direction"):
            direction = alert_data.get("direction", "IGNORE").upper()
        elif response_data.get("direction"):
            direction = response_data.get("direction", "IGNORE").upper()
        
        # Get confidence
        confidence = "LOW"
        if alert_data.get("confidence"):
            confidence = alert_data.get("confidence", "LOW").upper()
        elif response_data.get("confidence"):
            confidence = response_data.get("confidence", "LOW").upper()
        
        print(f"  FINAL: direction={direction}, confidence={confidence}")

        # Current price
        current_price = alert_data.get("price", alert_data.get("close", "N/A"))
        try:
            current_price_val = _to_float(current_price)
            current_price_str = f"${current_price_val:.2f}"
        except Exception:
            current_price_str = f"${current_price}"

        # Trade levels
        entry = response_data.get("entry") or alert_data.get("entry")
        stop = response_data.get("stop") or alert_data.get("stop")
        tp1 = response_data.get("tp1") or alert_data.get("tp1")
        tp2 = response_data.get("tp2") or alert_data.get("tp2")

        # Model details & consensus - CRITICAL FIX
        model_details = []
        consensus_breakdown = {}
        
        # Check multiple possible locations
        if alert_data.get("model_details"):
            model_details = alert_data.get("model_details", [])
            print(f"✅ Got model_details from alert_data: {len(model_details)} models")
        elif response_data.get("model_details"):
            model_details = response_data.get("model_details", [])
            print(f"✅ Got model_details from response_data: {len(model_details)} models")
        
        if alert_data.get("consensus_breakdown"):
            consensus_breakdown = alert_data.get("consensus_breakdown", {})
            print(f"✅ Got consensus_breakdown from alert_data: {consensus_breakdown}")
        elif response_data.get("consensus_breakdown"):
            consensus_breakdown = response_data.get("consensus_breakdown", {})
            print(f"✅ Got consensus_breakdown from response_data: {consensus_breakdown}")
        
        # If still no consensus breakdown, create from model details
        if not consensus_breakdown and model_details:
            consensus_breakdown = {}
            for model in model_details:
                model_dir = model.get("direction", "IGNORE").upper()
                consensus_breakdown[model_dir] = consensus_breakdown.get(model_dir, 0) + 1
            print(f"🔄 Created consensus_breakdown from model_details: {consensus_breakdown}")

        # Ensemble decision for reasoning
        ensemble_decision = {
            "direction": direction,
            "confidence": confidence,
            "consensus_breakdown": consensus_breakdown,
            "reasoning": response_data.get("reasoning") or alert_data.get("reasoning", ""),
        }

        reasoning = get_best_reasoning(ensemble_decision, model_details)
        print(f"📝 Reasoning: {reasoning[:100]}...")

        # --- Consensus text ---
        if consensus_breakdown:
            consensus_parts = [f"{k}: {v}" for k, v in consensus_breakdown.items()]
            consensus_text = ", ".join(consensus_parts)
            print(f"✅ Consensus: {consensus_text}")
        else:
            consensus_text = "Calculating..."
            print(f"⚠️ No consensus breakdown available")

        # --- Trend data ---
        additional_data = alert_data.get("additional_data", {}) or {}
        print(f"📈 additional_data keys: {list(additional_data.keys())}")
        
        trend_parts = []

        # RSI
        rsi = additional_data.get("rsi")
        if rsi is not None:
            try:
                trend_parts.append(f"RSI: {float(rsi):.2f}")
            except Exception:
                trend_parts.append(f"RSI: {rsi}")

        # Volume ratio
        volume_ratio = additional_data.get("volume_ratio") or additional_data.get("volume")
        if volume_ratio is not None:
            try:
                trend_parts.append(f"Volume: {float(volume_ratio):.1f}x")
            except Exception:
                trend_parts.append(f"Volume: {volume_ratio}")

        # Trend strength
        trend_strength = additional_data.get("trend_strength") or additional_data.get("strength")
        if trend_strength:
            trend_parts.append(f"Strength: {trend_strength}")

        # ETF mode - FIXED: Only show ETF for actual ETFs
        etf_tickers = ["QQQ", "SPY", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV", "XLI", "XLB", "XLU", "XLP", "XLY"]
        is_etf = ticker in etf_tickers
        etf_mode = additional_data.get("etf_mode")
        
        if etf_mode is not None:
            trend_parts.append(f"ETF: {'✅' if etf_mode else '❌'}")
        else:
            trend_parts.append(f"ETF: {'✅' if is_etf else '❌'}")

        trend_text = "\n".join(trend_parts) if trend_parts else "No trend data available"
        print(f"📊 Trend data: {trend_text}")

        # --- Model breakdown ---
        model_lines = []
        if model_details:
            for i, model in enumerate(model_details[:3], 1):
                model_name = model.get("model", f"Model {i}")
                lower = model_name.lower()
                
                # Clean model name
                if "claude" in lower:
                    display = "Claude"
                elif "gpt-4o" in lower:
                    display = "GPT-4o"
                elif "gpt-4-turbo" in lower:
                    display = "GPT-4-turbo"
                elif "gpt-4" in lower:
                    display = "GPT-4"
                elif "deepseek" in lower:
                    display = "DeepSeek"
                else:
                    display = model_name
                
                m_dir = model.get("direction", "IGNORE").upper()
                m_conf = model.get("confidence", "LOW").upper()
                
                model_lines.append(f"• {display}: {m_dir} ({m_conf})")
            
            model_breakdown_text = "\n".join(model_lines)
            print(f"🤖 Model breakdown: {len(model_details)} models")
        else:
            model_breakdown_text = "No model data received"
            print(f"⚠️ No model details available")

        # --- Trade levels ---
        trade_lines = []
        if direction in ["LONG", "SHORT"]:
            if entry is not None:
                try:
                    trade_lines.append(f"**Entry:** ${float(entry):.2f}")
                except Exception:
                    trade_lines.append(f"**Entry:** ${entry}")
            if stop is not None:
                try:
                    trade_lines.append(f"**Stop:** ${float(stop):.2f}")
                except Exception:
                    trade_lines.append(f"**Stop:** ${stop}")
            if tp1 is not None:
                try:
                    trade_lines.append(f"**TP1:** ${float(tp1):.2f}")
                except Exception:
                    trade_lines.append(f"**TP1:** ${tp1}")
            if tp2 is not None:
                try:
                    trade_lines.append(f"**TP2:** ${float(tp2):.2f}")
                except Exception:
                    trade_lines.append(f"**TP2:** ${tp2}")

            # Risk/Reward
            if entry is not None and stop is not None and tp1 is not None:
                try:
                    risk = abs(float(entry) - float(stop))
                    reward = abs(float(tp1) - float(entry))
                    if risk > 0:
                        rr = round(reward / risk, 2)
                        trade_lines.append("")
                        trade_lines.append(f"**Risk/Reward:** {rr}:1")
                        trade_lines.append(f"**Risk:** ${risk:.2f} | **Reward:** ${reward:.2f}")
                except Exception:
                    pass

        trade_text = "\n".join(trade_lines) if trade_lines else None

        # --- Color based on confidence ---
        if confidence == "HIGH":
            color = 0x2ECC71  # green
        elif confidence == "MEDIUM":
            color = 0xF1C40F  # amber
        else:
            color = 0xE74C3C  # red

        # --- Analysis text ---
        analysis_text = reasoning.strip()
        if len(analysis_text) > 1024:
            analysis_text = analysis_text[:1020] + "..."

        # --- Build Discord embed ---
        fields = []

        # Strategy
        fields.append({
            "name": "Strategy",
            "value": f"```{strategy}```",
            "inline": True
        })

        # Direction - FIXED: Show IGNORE not UNKNOWN
        fields.append({
            "name": "Direction",
            "value": direction,
            "inline": True
        })

        # Confidence
        fields.append({
            "name": "Confidence",
            "value": confidence,
            "inline": True
        })

        # Current Price
        fields.append({
            "name": "Current Price",
            "value": current_price_str,
            "inline": False
        })

        # Consensus - FIXED: Show actual consensus
        fields.append({
            "name": "Consensus",
            "value": consensus_text,
            "inline": True
        })

        # Trend Data
        fields.append({
            "name": "Trend Data",
            "value": trend_text,
            "inline": False
        })

        # Trade Levels (if available)
        if trade_text:
            fields.append({
                "name": "Trade Levels",
                "value": trade_text,
                "inline": False
            })

        # Model Breakdown - FIXED: Show actual models
        fields.append({
            "name": "Model Breakdown",
            "value": model_breakdown_text,
            "inline": False
        })

        # Analysis
        fields.append({
            "name": "Analysis",
            "value": analysis_text,
            "inline": False
        })

        # Title
        title_prefix = "TRADE SIGNAL" if direction in ["LONG", "SHORT"] else "IGNORE"
        embed = {
            "title": f"{title_prefix}: {ticker}",
            "color": color,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat(),
        }

        payload = {
            "embeds": [embed],
            "username": "Trading Agent",
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png",
        }

        print(f"\n🚀 FINAL: Sending {ticker} - {direction} ({confidence})")
        print("="*50 + "\n")

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 204:
            print(f"✅ Successfully sent to Discord: {ticker}")
            return True
        else:
            print(f"❌ Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        import traceback
        print("❌ Full traceback:", traceback.format_exc())
        return False


# Backwards compatibility
def make_discord_embed(alert_data, agent_reply):
    return send_to_discord(alert_data, agent_reply)
