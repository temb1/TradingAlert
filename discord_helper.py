import requests
import datetime
import json
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

def send_to_discord(alert_data, agent_reply):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook set.")
        return

    try:
        payload = make_discord_embed(alert_data, agent_reply)
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=8)
        if res.status_code < 300:
            print("✅ Sent alert to Discord.")
        else:
            print("⚠️ Discord error:", res.status_code, res.text)
    except Exception as e:
        print("❌ Discord exception:", e)
