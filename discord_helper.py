# Version: 11
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
        "value": f"**Direction:** {direction.upper()}\n**Confidence:** {conf_emoji} {confidence.upper()}\n**Entry:** {fmt(agent.get('entry'))}\n**Stop:** {fmt(agent.get('stop'))}\n**TP1:** {fmt(agent.get('tp1'))}\n**TP2:** {fmt(agent.get('tp2'))}\n**Single Option:** {agent.get('single_option')}\n**Vertical Spread:** {agent.get('vertical_spread')}",
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
    """Send trading alert to Discord with clean formatting - UPDATED FOR BETTER REASONING"""
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
        
        # ✅ UPDATED: Use best reasoning instead of generic consensus
        model_details = response_data.get("model_details", [])
        reasoning = get_best_reasoning(response_data, model_details)
        
        # Extract trade levels
        entry = response_data.get("entry")
        stop = response_data.get("stop") 
        tp1 = response_data.get("tp1")
        tp2 = response_data.get("tp2")
        
        # Get consensus breakdown
        consensus_breakdown = response_data.get("consensus_breakdown", {})

        # Color coding based on CONFIDENCE levels
        if confidence == "HIGH":
            color = 3066993  # Green - High confidence
            emoji = "🎯"
        elif confidence == "MEDIUM":
            color = 16753920  # Orange - Medium confidence
            emoji = "⚠️"
        else:  # LOW or UNKNOWN
            color = 15158332  # Red - Low confidence or ignore
            emoji = "❌"

        # Title based on direction
        if direction in ["LONG", "SHORT"]:
            title = f"🎯 TRADE SIGNAL: {ticker}"
        else:
            title = f"⏸️ IGNORE: {ticker}"

        # Create simple embed without complex fields that might cause issues
        embed = {
            "title": title,
            "color": color,
            "fields": [
                {
                    "name": "Strategy",
                    "value": f"`{strategy}`",
                    "inline": True
                },
                {
                    "name": "Direction",
                    "value": f"`{direction}`",
                    "inline": True
                },
                {
                    "name": "Confidence", 
                    "value": f"{emoji} `{confidence}`",
                    "inline": True
                }
            ],
            "timestamp": alert_data.get("timestamp", "")
        }

        # Current Price field
        current_price = alert_data.get('price', alert_data.get('close', 'N/A'))
        embed["fields"].append({
            "name": "Current Price",
            "value": f"`${current_price}`",
            "inline": True
        })

        # TRADE LEVELS SECTION
        if direction in ["LONG", "SHORT"] and any([entry, stop, tp1, tp2]):
            trade_levels = []
            
            if entry:
                trade_levels.append(f"**Entry:** `${entry:.2f}`" if isinstance(entry, (int, float)) else f"**Entry:** `{entry}`")
            if stop:
                trade_levels.append(f"**Stop:** `${stop:.2f}`" if isinstance(stop, (int, float)) else f"**Stop:** `{stop}`")
            if tp1:
                trade_levels.append(f"**TP1:** `${tp1:.2f}`" if isinstance(tp1, (int, float)) else f"**TP1:** `{tp1}`")
            if tp2:
                trade_levels.append(f"**TP2:** `${tp2:.2f}`" if isinstance(tp2, (int, float)) else f"**TP2:** `{tp2}`")
            
            option_strategies = []
            if single_option and single_option != "None":
                option_strategies.append(f"**Single:** {single_option}")
            if vertical_spread and vertical_spread != "None":
                option_strategies.append(f"**Spread:** {vertical_spread}")
            
            if trade_levels:
                embed["fields"].append({
                    "name": "💰 Trade Levels",
                    "value": " | ".join(trade_levels),
                    "inline": False
                })
            
            if option_strategies:
                embed["fields"].append({
                    "name": "📊 Option Strategies", 
                    "value": " | ".join(option_strategies),
                    "inline": False
                })
                
                # Risk/Reward Calculation
                if entry and stop and tp1:
                    try:
                        risk = abs(float(entry) - float(stop))
                        reward = abs(float(tp1) - float(entry))
                        if risk > 0:
                            rr_ratio = round(reward / risk, 2)
                            embed["fields"].append({
                                "name": "📊 Risk/Reward",
                                "value": f"`{rr_ratio}:1` (Risk: ${risk:.2f} | Reward: ${reward:.2f})",
                                "inline": True
                            })
                    except (ValueError, TypeError):
                        pass  # Skip if calculation fails

        # Ensemble consensus info
        if consensus_breakdown:
            consensus_text = ", ".join([f"{k}: {v}" for k, v in consensus_breakdown.items()])
            embed["fields"].append({
                "name": "Consensus",
                "value": f"`{consensus_text}`",
                "inline": True
            })

        # Include trend-specific data if available
        additional_data = alert_data.get('additional_data', {})
        if additional_data:
            trend_info = []
            
            # Add RSI if available
            rsi = additional_data.get('rsi')
            if rsi:
                try:
                    rsi_rounded = round(float(rsi), 2)
                    trend_info.append(f"RSI: `{rsi_rounded}`")
                except (ValueError, TypeError):
                    trend_info.append(f"RSI: `{rsi}`")  # Fallback if rounding fails
            
            # Add volume ratio if available
            volume_ratio = additional_data.get('volume_ratio')
            if volume_ratio:
                trend_info.append(f"Volume: `{volume_ratio:.1f}x`")
            
            # Add trend strength if available
            trend_strength = additional_data.get('trend_strength')
            if trend_strength:
                trend_info.append(f"Strength: `{trend_strength}`")
            
            # Add ETF mode if available
            etf_mode = additional_data.get('etf_mode')
            if etf_mode is not None:
                trend_info.append(f"ETF: `{'✅' if etf_mode else '❌'}`")
            
            if trend_info:
                embed["fields"].append({
                    "name": "Trend Data",
                    "value": " | ".join(trend_info),
                    "inline": False
                })

        # Add model breakdown for ensemble
        if model_details and len(model_details) > 0:
            model_texts = []
            for model in model_details[:3]:  # Limit to 3 models
                model_name = model.get('model', 'Unknown').replace('claude-sonnet-4-20250514', 'Claude').replace('gpt-4', 'GPT-4')
                model_dir = model.get('direction', 'UNKNOWN')
                model_conf = model.get('confidence', 'UNKNOWN')
                model_texts.append(f"• **{model_name}**: `{model_dir}` (`{model_conf}`)")
            
            if model_texts:
                embed["fields"].append({
                    "name": "Model Breakdown",
                    "value": "\n".join(model_texts),
                    "inline": False
                })

        # ✅ UPDATED: Add the best reasoning/analysis
        if reasoning and reasoning.strip() and reasoning != "No analysis available":
            # Truncate long reasoning but keep it meaningful
            if len(reasoning) > 1000:
                # Try to find a good truncation point
                if len(reasoning) > 1000:
                    # Find the last sentence end before 997 characters
                    trunc_point = reasoning[:997].rfind('.')
                    if trunc_point > 500:  # Ensure we keep substantial content
                        reasoning = reasoning[:trunc_point+1] + ".."
                    else:
                        reasoning = reasoning[:997] + "..."
            
            embed["fields"].append({
                "name": "Analysis",
                "value": reasoning,
                "inline": False
            })

        # Validate embed structure before sending
        def clean_embed(embed_data):
            """Ensure embed data is safe for Discord API"""
            cleaned = embed_data.copy()
            
            # Ensure all field values are strings and not empty
            if 'fields' in cleaned:
                for field in cleaned['fields']:
                    if 'value' in field:
                        field['value'] = str(field['value'])
                        if not field['value'].strip():
                            field['value'] = "—"
                    if 'name' in field:
                        field['name'] = str(field['name'])
                        if not field['name'].strip():
                            field['name'] = "—"
            
            # Ensure title is safe
            if 'title' in cleaned:
                cleaned['title'] = str(cleaned['title'])[:256]
                
            return cleaned

        cleaned_embed = clean_embed(embed)
        
        payload = {
            "embeds": [cleaned_embed],
            "username": "Trading Agent",
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png"
        }

        # Debug log
        print(f"📤 Sending Discord payload: {json.dumps(payload, indent=2)[:500]}...")

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 204:
            print(f"✅ Sent to Discord: {ticker} {strategy} {direction}")
            return True
        else:
            print(f"❌ Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

