# Version: 17
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

def send_to_discord(alert_data, ai_response, webhook_url=None):
    """Send trading alert to Discord - FIXED COLOR CODING BASED ON CONFIDENCE"""
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

        # ✅✅✅ FIXED: COLOR CODING BASED ON CONFIDENCE, NOT DIRECTION ✅✅✅
        # GREEN for HIGH confidence, ORANGE for MEDIUM, RED for LOW/IGNORE
        if confidence == "HIGH":
            color = 3066993  # Green - High confidence
            title_emoji = "🎯"
        elif confidence == "MEDIUM":
            color = 15105570  # Orange/Yellow - Medium confidence  
            title_emoji = "⚠️"
        else:  # LOW or IGNORE
            color = 15158332  # Red - Low confidence or ignore
            title_emoji = "❌"

        # Title - matching your screenshot format
        if direction in ["LONG", "SHORT"]:
            title = f"# TRADE SIGNAL: {ticker}"
        else:
            title = f"# IGNORE: {ticker}"

        # Start building the embed - MATCHING YOUR SCREENSHOTS
        embed = {
            "title": title,
            "color": color,
            "fields": [],
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add Strategy, Direction, Confidence as inline fields - MATCHING YOUR SCREENSHOT
        embed["fields"].append({
            "name": "Strategy",
            "value": f"```{strategy}```",
            "inline": True
        })
        
        embed["fields"].append({
            "name": "Direction",
            "value": f"```{direction}```",
            "inline": True
        })
        
        embed["fields"].append({
            "name": "Confidence",
            "value": f"```{confidence}```",
            "inline": True
        })

        # Current Price - as its own section
        current_price = alert_data.get('price', alert_data.get('close', 'N/A'))
        embed["fields"].append({
            "name": "Current Price",
            "value": f"**${current_price}**",
            "inline": False
        })

        # Add separator
        embed["fields"].append({
            "name": "\u200b",
            "value": "---",
            "inline": False
        })

        # TRADE LEVELS SECTION (only for LONG/SHORT) - MATCHING YOUR SCREENSHOT
        if direction in ["LONG", "SHORT"] and any([entry, stop, tp1, tp2]):
            trade_levels_text = ""
            
            if entry:
                try:
                    trade_levels_text += f"**Entry:** ${float(entry):.2f}\n"
                except:
                    trade_levels_text += f"**Entry:** ${entry}\n"
            if stop:
                try:
                    trade_levels_text += f"**Stop:** ${float(stop):.2f}\n"
                except:
                    trade_levels_text += f"**Stop:** ${stop}\n"
            if tp1:
                try:
                    trade_levels_text += f"**TP1:** ${float(tp1):.2f}\n"
                except:
                    trade_levels_text += f"**TP1:** ${tp1}\n"
            if tp2:
                try:
                    trade_levels_text += f"**TP2:** ${float(tp2):.2f}\n"
                except:
                    trade_levels_text += f"**TP2:** ${tp2}\n"
            
            if trade_levels_text:
                embed["fields"].append({
                    "name": "Trade Levels",
                    "value": trade_levels_text.strip(),
                    "inline": False
                })
            
            # Risk/Reward Calculation - MATCHING YOUR SCREENSHOT FORMAT
            if entry and stop and tp1:
                try:
                    risk = abs(float(entry) - float(stop))
                    reward = abs(float(tp1) - float(entry))
                    if risk > 0:
                        rr_ratio = round(reward / risk, 2)
                        embed["fields"].append({
                            "name": "Risk/Reward",
                            "value": f"{rr_ratio}:1 (Risk: ${risk:.2f} | Reward: ${reward:.2f})",
                            "inline": True
                        })
                except (ValueError, TypeError):
                    pass

        # Consensus breakdown - MATCHING YOUR SCREENSHOT
        if consensus_breakdown:
            consensus_items = []
            for key, value in consensus_breakdown.items():
                consensus_items.append(f"{key}: {value}")
            consensus_text = ", ".join(consensus_items)
            
            embed["fields"].append({
                "name": "Consensus",
                "value": consensus_text,
                "inline": True
            })

        # Include trend-specific data if available - MATCHING YOUR SCREENSHOT FORMAT
        additional_data = alert_data.get('additional_data', {})
        if additional_data:
            trend_parts = []
            
            # Add RSI if available
            rsi = additional_data.get('rsi')
            if rsi:
                try:
                    rsi_rounded = round(float(rsi), 2)
                    trend_parts.append(f"RSI: {rsi_rounded}")
                except (ValueError, TypeError):
                    trend_parts.append(f"RSI: {rsi}")
            
            # Add volume ratio if available
            volume_ratio = additional_data.get('volume_ratio')
            if volume_ratio:
                try:
                    volume_text = f"{float(volume_ratio):.1f}x"
                    trend_parts.append(f"Volume: {volume_text}")
                except (ValueError, TypeError):
                    trend_parts.append(f"Volume: {volume_ratio}")
            
            # Add trend strength if available
            trend_strength = additional_data.get('trend_strength')
            if trend_strength:
                trend_parts.append(f"Strength: {trend_strength}")
            
            # Add ETF mode if available
            etf_mode = additional_data.get('etf_mode')
            if etf_mode is not None:
                trend_parts.append(f"ETF: {'✅' if etf_mode else '❌'}")
            
            if trend_parts:
                embed["fields"].append({
                    "name": "Trend Data",
                    "value": " | ".join(trend_parts),
                    "inline": False
                })

        # Model breakdown - MATCHING YOUR SCREENSHOT FORMAT
        if model_details and len(model_details) > 0:
            model_texts = []
            for model in model_details[:3]:  # Limit to 3 models
                # Clean model names to match your screenshot
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
                
                model_texts.append(f"• **{model_display}:** {model_dir} ({model_conf})")
            
            if model_texts:
                embed["fields"].append({
                    "name": "Model Breakdown",
                    "value": "\n".join(model_texts),
                    "inline": False
                })

        # Analysis section - MATCHING YOUR SCREENSHOT
        if reasoning and reasoning.strip() and reasoning != "No analysis available":
            # Clean up the reasoning text
            clean_reasoning = reasoning.strip()
            
            # Truncate if too long
            if len(clean_reasoning) > 1000:
                # Try to find a good truncation point
                trunc_point = clean_reasoning[:997].rfind('.')
                if trunc_point > 500:
                    clean_reasoning = clean_reasoning[:trunc_point+1] + ".."
                else:
                    clean_reasoning = clean_reasoning[:997] + "..."
            
            embed["fields"].append({
                "name": "Analysis",
                "value": clean_reasoning,
                "inline": False
            })

        # Create the payload with embeds
        payload = {
            "embeds": [embed],
            "username": "Trading Agent",
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png"
        }

        # Debug log
        print(f"📤 Sending Discord embed for {ticker}: {direction} ({confidence})")
        print(f"🎨 Using color: {'GREEN' if confidence == 'HIGH' else 'ORANGE' if confidence == 'MEDIUM' else 'RED'}")

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

# Keep for backward compatibility
def make_discord_embed(alert_data, agent_reply):
    """Legacy function - kept for compatibility"""
    return send_to_discord(alert_data, agent_reply)
