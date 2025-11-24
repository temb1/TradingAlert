import requests
import datetime
import json
import os
from helpers import _to_float
from config import DISCORD_WEBHOOK_URL
from datetime import datetime

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
    
    # Notes section
    fields.append({"name": "📝 Notes", "value": agent.get("notes", "n/a"), "inline": False})

    embed = {
        "title": f"{emoji} {ticker} {pattern}",
        "color": color,
        "fields": fields,
        "footer": {"text": "TradingView AI Agent"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    return {"embeds": [embed]}

def send_to_discord(alert_data, ai_response, webhook_url=None):
    """Send trading alert to Discord with clean formatting - UPDATED FOR ENSEMBLE"""
    try:
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
            
        if not webhook_url:
            print("❌ No Discord webhook URL configured")
            return False

        # Parse AI response - UPDATED FOR ENSEMBLE FORMAT
        if isinstance(ai_response, str):
            try:
                response_data = json.loads(ai_response)
            except:
                # If it's not JSON, check if it's an ensemble dict string
                if 'direction' in ai_response and 'confidence' in ai_response:
                    # Try to extract basic fields from string
                    response_data = {
                        "direction": "unknown", 
                        "confidence": "unknown", 
                        "reasoning": ai_response
                    }
                else:
                    response_data = {"direction": "unknown", "confidence": "unknown", "reasoning": ai_response}
        else:
            response_data = ai_response

        # Extract data - UPDATED FOR ENSEMBLE
        ticker = alert_data.get("ticker", "UNKNOWN").upper()
        strategy = alert_data.get("strategy", alert_data.get("pattern", "unknown"))
        
        # ✅ UPDATED: Handle ensemble response structure
        direction = response_data.get("direction", "ignore").upper()
        confidence = response_data.get("confidence", "low").upper()
        reasoning = response_data.get("reasoning", response_data.get("notes", ""))
        
        # ✅ ADDED: Get model breakdown for ensemble
        model_details = response_data.get("model_details", [])
        consensus_breakdown = response_data.get("consensus_breakdown", {})
        
        # ✅ ADDED: Different formatting for trend alerts vs breakout alerts
        if any(x in strategy for x in ['bullish_trend', 'bearish_trend']):
            title = f"📈 TREND ALERT: {ticker}"
            # Green for bullish, Red for bearish, Yellow for ignore
            if 'bullish' in strategy:
                color = 3066993  # Green
                emoji = "🟢"
            elif 'bearish' in strategy: 
                color = 15158332  # Red
                emoji = "🔴"
            else:
                color = 10181046  # Gray
                emoji = "⚫"
        else:
            title = f"🔔 BREAKOUT ALERT: {ticker}"
            # Use existing color scheme for breakouts
            color = 3066993 if direction == "LONG" else 15158332 if direction == "SHORT" else 10181046
            emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚫"

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
                    "value": f"{emoji} `{direction}`",
                    "inline": True
                },
                {
                    "name": "Confidence", 
                    "value": f"`{confidence}`",
                    "inline": True
                }
            ],
            "timestamp": alert_data.get("timestamp", "")
        }

        # ✅ ADDED: Current Price field
        current_price = alert_data.get('price', alert_data.get('close', 'N/A'))
        embed["fields"].append({
            "name": "Current Price",
            "value": f"`${current_price}`",
            "inline": True
        })

        # ✅ ADDED: Ensemble consensus info
        if consensus_breakdown:
            consensus_text = ", ".join([f"{k}: {v}" for k, v in consensus_breakdown.items()])
            embed["fields"].append({
                "name": "Consensus",
                "value": f"`{consensus_text}`",
                "inline": True
            })

        # ✅ ADDED: Include trend-specific data if available
        additional_data = alert_data.get('additional_data', {})
        if additional_data:
            trend_info = []
            
            # Add RSI if available
            rsi = additional_data.get('rsi')
            if rsi:
                trend_info.append(f"RSI: `{rsi}`")
            
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

        # ✅ UPDATED: Add model breakdown for ensemble
        if model_details and len(model_details) > 0:
            model_texts = []
            for model in model_details[:3]:  # Limit to 3 models
                model_name = model.get('model', 'Unknown').replace('claude-3-5-sonnet-20241022', 'Claude').replace('gpt-4', 'GPT-4')
                model_dir = model.get('direction', 'UNKNOWN')
                model_conf = model.get('confidence', 'UNKNOWN')
                model_texts.append(f"• **{model_name}**: `{model_dir}` (`{model_conf}`)")
            
            if model_texts:
                embed["fields"].append({
                    "name": "Model Breakdown",
                    "value": "\n".join(model_texts),
                    "inline": False
                })

        # ✅ UPDATED: Add reasoning/analysis
        if reasoning and reasoning != "No reasoning provided" and reasoning.strip():
            # Truncate long reasoning
            if len(reasoning) > 1000:
                reasoning = reasoning[:997] + "..."
            embed["fields"].append({
                "name": "Analysis",
                "value": reasoning,
                "inline": False
            })

        # ✅ ADDED: Validate embed structure before sending
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
            "username": "Trading Ensemble",
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
            # Log the problematic payload for debugging
            print(f"❌ Problematic payload: {json.dumps(payload, indent=2)}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False
