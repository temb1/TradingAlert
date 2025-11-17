import requests
import datetime
import json
import os
from helpers import _to_float
from config import DISCORD_WEBHOOK_URL

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
    """Send trading alert to Discord with clean formatting"""
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
                response_data = {"direction": "unknown", "confidence": "unknown", "notes": ai_response}
        else:
            response_data = ai_response

        # Extract data
        ticker = alert_data.get("ticker", "UNKNOWN").upper()
        pattern = alert_data.get("pattern", "unknown")
        direction = response_data.get("direction", "ignore").upper()
        confidence = response_data.get("confidence", "low").upper()
        
        # Create simple embed without complex fields that might cause issues
        embed = {
            "title": f"🔔 {ticker} {pattern}",
            "color": 3066993 if direction == "LONG" else 15158332 if direction == "SHORT" else 10181046,
            "fields": [
                {
                    "name": "Direction",
                    "value": direction,
                    "inline": True
                },
                {
                    "name": "Confidence", 
                    "value": confidence,
                    "inline": True
                },
                {
                    "name": "Current Price",
                    "value": f"${alert_data.get('close', 'N/A')}",
                    "inline": True
                }
            ],
            "timestamp": alert_data.get("timestamp", "")
        }

        # Add notes if available
        notes = response_data.get("notes", "")
        if notes and len(notes) > 0:
            # Truncate long notes
            truncated_notes = notes[:500] + "..." if len(notes) > 500 else notes
            embed["fields"].append({
                "name": "Analysis",
                "value": truncated_notes,
                "inline": False
            })

        payload = {
            "embeds": [embed],
            "username": "TradingView Agent",
            "avatar_url": "https://img.icons8.com/color/96/000000/stock-share.png"
        }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 204:
            print(f"✅ Sent to Discord: {ticker} {direction}")
            return True
        else:
            print(f"❌ Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        return False
