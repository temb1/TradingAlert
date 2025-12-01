# Version: 14
import requests
import datetime
import json
import os
from helpers import _to_float
from config import DISCORD_WEBHOOK_URL
from datetime import datetime

def get_best_reasoning(ensemble_decision, model_details):
    """Get the best reasoning from available models - prioritize detailed analysis"""
    
    # If we have model details, use the most detailed reasoning
    if model_details:
        # Try to get Claude's reasoning first (usually most detailed)
        for model in model_details:
            if 'claude' in model.get('model', '').lower():
                reasoning = model.get('reasoning', '')
                if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                    return reasoning
        
        # Then try GPT-4o
        for model in model_details:
            if 'gpt-4o' in model.get('model', '').lower():
                reasoning = model.get('reasoning', '')
                if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                    return reasoning
        
        # Then try any model with good reasoning
        for model in model_details:
            reasoning = model.get('reasoning', '')
            if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                return reasoning
    
    # Fallback to consensus reasoning if no detailed reasoning found
    consensus_reasoning = ensemble_decision.get('reasoning', '')
    if "ENSEMBLE CONSENSUS" in consensus_reasoning:
        # Create a more descriptive message from consensus data
        direction = ensemble_decision.get('direction', 'UNKNOWN')
        confidence = ensemble_decision.get('confidence', 'LOW')
        breakdown = ensemble_decision.get('consensus_breakdown', {})
        
        if direction == "LONG":
            return f"Bullish consensus with {breakdown.get('LONG', 0)}/3 models recommending LONG. Technical indicators suggest upward momentum with {confidence.lower()} confidence."
        elif direction == "SHORT":
            return f"Bearish consensus with {breakdown.get('SHORT', 0)}/3 models recommending SHORT. Technical indicators suggest downward pressure with {confidence.lower()} confidence."
        else:
            return f"Mixed signals with {breakdown}. Awaiting clearer market direction with {confidence.lower()} confidence."
    
    return consensus_reasoning or "No analysis available"

def make_discord_embed(alert_data, agent_reply):
    """Generate a clean Discord embed with option suggestions."""
    if isinstance(agent_reply, str):
        try:
            agent = json.loads(agent_reply)
        except Exception:
            agent = {}
    else:
        agent = agent_reply or {}

    direction = (agent.get("direction") or "ignore").lower()
    confidence = (agent.get("confidence") or "low").lower()

    # Colors and emojis
    if direction == "long":
        emoji = "🟢"; color = 0x00ff00
    elif direction == "short":
        emoji = "🔴"; color = 0xff0000
    else:
        emoji = "🟡"; color = 0xffff00

    conf_emoji = {"high": "🎯", "medium": "⚠️", "low": "🔍"}.get(confidence, "❓")
    ticker = alert_data.get("ticker", "UNKNOWN")
    interval = alert_data.get("interval", "?")
    pattern = alert_data.get("pattern", "?")

    def fmt(v):
        return f"${v:,.2f}" if isinstance(v, (float, int)) else "n/a"

    # Build fields
    fields = []
    
    # Details section
    detail_text = f"**Timeframe:** {interval}\n**Current Price:** {fmt(_to_float(alert_data.get('close')))}"
    if alert_data.get('ib_high'):
        detail_text += f"\n**IB High:** {fmt(_to_float(alert_data.get('ib_high')))}\n**IB Low:** {fmt(_to_float(alert_data.get('ib_low')))}"
    if alert_data.get('box_high'):
        detail_text += f"\n**Box High:** {fmt(_to_float(alert_data.get('box_high')))}\n**Box Low:** {fmt(_to_float(alert_data.get('box_low')))}"
        
    fields.append({"name": "📊 Details", "value": detail_text, "inline": False})
    
    # Recommendation section
    fields.append({
        "name": "🎯 Recommendation",
        "value": f"**Direction:** {direction.upper()}\n**Confidence:** {conf_emoji} {confidence.upper()}\n**Entry:** {fmt(agent.get('entry'))}\n**Stop:** {fmt(agent.get('stop'))}\n**TP1:** {fmt(agent.get('tp1'))}\n**TP2:** {fmt(agent.get('tp2'))}",
        "inline": False
    })
    
    # Notes section - UPDATED: Use best reasoning
    model_details = agent.get("model_details", [])
    best_reasoning = get_best_reasoning(agent, model_details)
    fields.append({"name": "📝 Analysis", "value": best_reasoning, "inline": False})

    embed = {
        "title": f"{emoji} {ticker} {pattern}",
        "color": color,
        "fields": fields,
        "footer": {"text": "Trading Agent"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    return {"embeds": [embed]}

def send_to_discord(alert_data, ai_response, webhook_url=None):
    """Send trading alert to Discord with clean formatting - UPDATED FORMAT"""
    try:
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
            
        if not webhook_url:
            print("❌ No Discord webhook URL configured")
            return False

        # Parse AI response
        if isinstance(ai_response, str):
            try:
                response_data = json.loads(ai_response)
            except:
                # If it's not JSON, check if it's an ensemble dict string
                if 'direction' in ai_response and 'confidence' in ai_response:
                    response_data = {
                        "direction": "unknown", 
                        "confidence": "unknown", 
                        "reasoning": ai_response
                    }
                else:
                    response_data = {"direction": "unknown", "confidence": "unknown", "reasoning": ai_response}
        else:
            response_data = ai_response

        # Extract data
        ticker = alert_data.get("ticker", "UNKNOWN").upper()
        strategy = alert_data.get("strategy", alert_data.get("pattern", "unknown"))
        
        # Handle ensemble response structure
        direction = response_data.get("direction", "ignore").upper()
        confidence = response_data.get("confidence", "low").upper()
        
        # Use best reasoning
        model_details = response_data.get("model_details", [])
        reasoning = get_best_reasoning(response_data, model_details)
        
        # Extract trade levels
        entry = response_data.get("entry")
        stop = response_data.get("stop") 
        tp1 = response_data.get("tp1")
        tp2 = response_data.get("tp2")
        
        # Get consensus breakdown
        consensus_breakdown = response_data.get("consensus_breakdown", {})

        # Color coding based on CONFIDENCE levels - MATCHING YOUR EXAMPLES
        if direction in ["LONG", "SHORT"]:
            if confidence == "HIGH":
                color = 3066993  # Green - High confidence trade
            elif confidence == "MEDIUM":
                color = 15105570  # Orange/Yellow - Medium confidence
            else:  # LOW
                color = 15158332  # Red - Low confidence
        else:  # IGNORE
            color = 10070709  # Gray - Ignore signal

        # Title based on direction - MATCHING YOUR EXAMPLES
        if direction in ["LONG", "SHORT"]:
            title = f"# TRADE SIGNAL: {ticker}"
        else:
            title = f"# IGNORE: {ticker}"

        # Start building the message content
        content_parts = []
        
        # Add title and strategy table
        strategy_table = f"| Strategy | Direction | Confidence |\n"
        strategy_table += f"|---|---|---|\n"
        strategy_table += f"| {strategy} | {direction} | {confidence} |"
        
        # Create the main embed
        embed = {
            "title": title,
            "description": strategy_table,
            "color": color,
            "fields": []
        }

        # Current Price - as a separate section
        current_price = alert_data.get('price', alert_data.get('close', 'N/A'))
        embed["fields"].append({
            "name": "**Current Price**",
            "value": f"${current_price}",
            "inline": False
        })

        # Add separator
        embed["fields"].append({
            "name": "\u200b",
            "value": "---",
            "inline": False
        })

        # TRADE LEVELS SECTION (only for LONG/SHORT)
        if direction in ["LONG", "SHORT"] and any([entry, stop, tp1, tp2]):
            # Trade Levels
            trade_levels_text = ""
            if entry:
                trade_levels_text += f"**Entry:** `${entry:.2f}` | "
            if stop:
                trade_levels_text += f"**Stop:** `${stop:.2f}` | "
            if tp1:
                trade_levels_text += f"**TP1:** `${tp1:.2f}` | "
            if tp2:
                trade_levels_text += f"**TP2:** `${tp2:.2f}`"
            
            # Clean up trailing separator
            if trade_levels_text.endswith(" | "):
                trade_levels_text = trade_levels_text[:-3]
            
            if trade_levels_text:
                embed["fields"].append({
                    "name": "**Trade Levels**",
                    "value": trade_levels_text,
                    "inline": False
                })
            
            # Risk/Reward Calculation
            if entry and stop and tp1:
                try:
                    risk = abs(float(entry) - float(stop))
                    reward = abs(float(tp1) - float(entry))
                    if risk > 0:
                        rr_ratio = round(reward / risk, 2)
                        rr_text = f"{rr_ratio}:1 (Risk: ${risk:.2f} | Reward: ${reward:.2f})"
                        
                        embed["fields"].append({
                            "name": "**Risk/Reward**",
                            "value": rr_text,
                            "inline": False
                        })
                except (ValueError, TypeError):
                    pass  # Skip if calculation fails

        # Consensus breakdown - SIMPLIFIED FORMAT
        if consensus_breakdown:
            consensus_items = []
            for key, value in consensus_breakdown.items():
                consensus_items.append(f"{key}: {value}")
            consensus_text = ", ".join(consensus_items)
            
            embed["fields"].append({
                "name": "**Consensus**",
                "value": consensus_text,
                "inline": False
            })

        # Include trend-specific data if available - MATCHING YOUR EXAMPLE FORMAT
        additional_data = alert_data.get('additional_data', {})
        if additional_data:
            trend_info = []
            
            # Add RSI if available
            rsi = additional_data.get('rsi')
            if rsi:
                try:
                    rsi_rounded = round(float(rsi), 2)
                    trend_info.append(f"RSI: {rsi_rounded}")
                except (ValueError, TypeError):
                    trend_info.append(f"RSI: {rsi}")
            
            # Add volume ratio if available
            volume_ratio = additional_data.get('volume_ratio')
            if volume_ratio:
                try:
                    volume_text = f"{float(volume_ratio):.1f}x"
                    trend_info.append(f"Volume: {volume_text}")
                except (ValueError, TypeError):
                    trend_info.append(f"Volume: {volume_ratio}")
            
            # Add trend strength if available
            trend_strength = additional_data.get('trend_strength')
            if trend_strength:
                trend_info.append(f"Strength: {trend_strength}")
            
            # Add ETF mode if available
            etf_mode = additional_data.get('etf_mode')
            if etf_mode is not None:
                trend_info.append(f"ETF: {'✅' if etf_mode else '❌'}")
            
            if trend_info:
                embed["fields"].append({
                    "name": "**Trend Data**",
                    "value": " | ".join(trend_info),
                    "inline": False
                })

        # Model breakdown - MATCHING YOUR EXAMPLE FORMAT
        if model_details and len(model_details) > 0:
            model_texts = []
            for model in model_details[:3]:  # Limit to 3 models
                # Clean model names to match your examples
                model_name = model.get('model', 'Unknown')
                if 'claude' in model_name.lower():
                    model_display = 'Claude'
                elif 'gpt-4o' in model_name.lower():
                    model_display = 'GPT-4o'
                elif 'gpt-4-turbo' in model_name.lower():
                    model_display = 'GPT-4-turbo'
                else:
                    model_display = model_name
                
                model_dir = model.get('direction', 'UNKNOWN').upper()
                model_conf = model.get('confidence', 'UNKNOWN').upper()
                
                model_texts.append(f"- {model_display}: {model_dir} ({model_conf})")
            
            if model_texts:
                embed["fields"].append({
                    "name": "**Model Breakdown**",
                    "value": "\n".join(model_texts),
                    "inline": False
                })

        # Analysis section - clean and truncate if needed
        if reasoning and reasoning.strip() and reasoning != "No analysis available":
            # Clean up the reasoning text
            clean_reasoning = reasoning.strip()
            
            # Truncate if too long but keep it meaningful
            if len(clean_reasoning) > 1000:
                # Try to find a good truncation point at a sentence end
                trunc_point = clean_reasoning[:997].rfind('.')
                if trunc_point > 500:  # Ensure we keep substantial content
                    clean_reasoning = clean_reasoning[:trunc_point+1] + ".."
                else:
                    clean_reasoning = clean_reasoning[:997] + "..."
            
            embed["fields"].append({
                "name": "**Analysis**",
                "value": clean_reasoning,
                "inline": False
            })

        # Validate and clean embed
        def clean_embed(embed_data):
            cleaned = embed_data.copy()
            
            # Ensure all field values are strings and not empty
            if 'fields' in cleaned:
                valid_fields = []
                for field in cleaned['fields']:
                    if 'value' in field and 'name' in field:
                        field['value'] = str(field['value'])
                        field['name'] = str(field['name'])
                        if field['value'].strip() and field['name'].strip():
                            valid_fields.append(field)
                cleaned['fields'] = valid_fields
            
            # Ensure title is safe
            if 'title' in cleaned:
                cleaned['title'] = str(cleaned['title'])[:256]
                
            # Ensure description is safe
            if 'description' in cleaned:
                cleaned['description'] = str(cleaned['description'])[:2048]
                
            return cleaned

        cleaned_embed = clean_embed(embed)
        
        # Create the payload
        payload = {
            "embeds": [cleaned_embed],
            "username": "Trading Agent",
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png"
        }

        # Debug log
        print(f"📤 Sending Discord payload for {ticker}: {direction} with {confidence} confidence")

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 204:
            print(f"✅ Sent to Discord: {ticker} {strategy} {direction} ({confidence})")
            return True
        else:
            print(f"❌ Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

# For backward compatibility
if __name__ == "__main__":
    # Test that the function signature matches
    print("Discord sender module loaded successfully")

