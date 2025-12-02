# Version: 20
import requests
import json
import os
from datetime import datetime
from helpers import _to_float
from config import DISCORD_WEBHOOK_URL


def get_best_reasoning(ensemble_decision, model_details):
    """Get the best reasoning from available models - prioritize detailed analysis"""

    if model_details:
        # Prefer Claude
        for model in model_details:
            if "claude" in model.get("model", "").lower():
                reasoning = model.get("reasoning", "")
                if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                    return reasoning

        # Then GPT-4o
        for model in model_details:
            if "gpt-4o" in model.get("model", "").lower():
                reasoning = model.get("reasoning", "")
                if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                    return reasoning

        # Any other detailed model reasoning
        for model in model_details:
            reasoning = model.get("reasoning", "")
            if reasoning and len(reasoning) > 100 and "ENSEMBLE CONSENSUS" not in reasoning:
                return reasoning

    # Fallback to consensus reasoning if no detailed reasoning found
    consensus_reasoning = ensemble_decision.get("reasoning", "")
    if "ENSEMBLE CONSENSUS" in consensus_reasoning:
        direction = ensemble_decision.get("direction", "UNKNOWN")
        confidence = ensemble_decision.get("confidence", "LOW")
        breakdown = ensemble_decision.get("consensus_breakdown", {})

        if direction == "LONG":
            return (
                f"Bullish consensus with {breakdown.get('LONG', 0)}/3 models recommending LONG. "
                f"Technical indicators suggest upward momentum with {confidence.lower()} confidence."
            )
        elif direction == "SHORT":
            return (
                f"Bearish consensus with {breakdown.get('SHORT', 0)}/3 models recommending SHORT. "
                f"Technical indicators suggest downward pressure with {confidence.lower()} confidence."
            )
        else:
            return (
                f"Mixed signals with {breakdown}. "
                f"Awaiting clearer market direction with {confidence.lower()} confidence."
            )

    return consensus_reasoning or "No analysis available"


def send_to_discord(alert_data, ai_response, webhook_url=None):
    """Send trading alert to Discord using a card-style embed similar to the screenshot."""
    try:
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or DISCORD_WEBHOOK_URL

        if not webhook_url:
            print("No Discord webhook URL configured")
            return False

        # Parse AI response
        if isinstance(ai_response, str):
            try:
                response_data = json.loads(ai_response)
            except Exception:
                # If it's not JSON, wrap it
                if "direction" in ai_response and "confidence" in ai_response:
                    response_data = {
                        "direction": "unknown",
                        "confidence": "unknown",
                        "reasoning": ai_response,
                    }
                else:
                    response_data = {
                        "direction": "unknown",
                        "confidence": "unknown",
                        "reasoning": ai_response,
                    }
        else:
            response_data = ai_response or {}

        # Core data
        ticker = alert_data.get("ticker", "UNKNOWN").upper()
        strategy = alert_data.get("strategy", alert_data.get("pattern", "unknown"))
        direction = response_data.get("direction", "ignore").upper()
        confidence = response_data.get("confidence", "low").upper()
        model_details = response_data.get("model_details", [])
        reasoning = get_best_reasoning(response_data, model_details)

        # Price
        current_price = alert_data.get("price", alert_data.get("close", "N/A"))
        try:
            current_price_val = _to_float(current_price)
            current_price_str = f"${current_price_val:.2f}"
        except Exception:
            current_price_str = f"${current_price}"

        # Trade levels (for LONG / SHORT only)
        entry = response_data.get("entry")
        stop = response_data.get("stop")
        tp1 = response_data.get("tp1")
        tp2 = response_data.get("tp2")

        # Consensus breakdown
        consensus_breakdown = response_data.get("consensus_breakdown", {})
        consensus_parts = [f"{k}: {v}" for k, v in consensus_breakdown.items()]
        consensus_text = ", ".join(consensus_parts) if consensus_parts else "N/A"

        # Trend data
        additional_data = alert_data.get("additional_data", {}) or {}
        trend_parts = []

        rsi = additional_data.get("rsi")
        if rsi is not None:
            try:
                trend_parts.append(f"RSI: {float(rsi):.2f}")
            except Exception:
                trend_parts.append(f"RSI: {rsi}")

        volume_ratio = additional_data.get("volume_ratio")
        if volume_ratio is not None:
            try:
                trend_parts.append(f"Volume: {float(volume_ratio):.1f}x")
            except Exception:
                trend_parts.append(f"Volume: {volume_ratio}")

        trend_strength = additional_data.get("trend_strength")
        if trend_strength:
            trend_parts.append(f"Strength: {trend_strength}")

        etf_mode = additional_data.get("etf_mode")
        if etf_mode is not None:
            trend_parts.append(f"ETF: {'Yes' if etf_mode else 'No'}")

        trend_text = "\n".join(trend_parts) if trend_parts else "N/A"

        # Model breakdown text
        model_lines = []
        for model in model_details[:3]:
            model_name = model.get("model", "Unknown")
            name_lower = model_name.lower()
            if "claude" in name_lower:
                display = "Claude"
            elif "gpt-4o" in name_lower:
                display = "GPT-4o"
            elif "gpt-4-turbo" in name_lower:
                display = "GPT-4-turbo"
            else:
                display = model_name

            m_dir = model.get("direction", "UNKNOWN").upper()
            m_conf = model.get("confidence", "UNKNOWN").upper()
            model_lines.append(f"{display}: {m_dir} ({m_conf})")

        model_breakdown_text = "\n".join(model_lines) if model_lines else "N/A"

        # Trade level field text
        trade_lines = []
        if direction in ["LONG", "SHORT"]:
            if entry is not None:
                try:
                    trade_lines.append(f"Entry: ${float(entry):.2f}")
                except Exception:
                    trade_lines.append(f"Entry: ${entry}")
            if stop is not None:
                try:
                    trade_lines.append(f"Stop: ${float(stop):.2f}")
                except Exception:
                    trade_lines.append(f"Stop: ${stop}")
            if tp1 is not None:
                try:
                    trade_lines.append(f"TP1: ${float(tp1):.2f}")
                except Exception:
                    trade_lines.append(f"TP1: ${tp1}")
            if tp2 is not None:
                try:
                    trade_lines.append(f"TP2: ${float(tp2):.2f}")
                except Exception:
                    trade_lines.append(f"TP2: ${tp2}")

            # Risk / Reward
            if entry is not None and stop is not None and tp1 is not None:
                try:
                    risk = abs(float(entry) - float(stop))
                    reward = abs(float(tp1) - float(entry))
                    if risk > 0:
                        rr = round(reward / risk, 2)
                        trade_lines.append("")
                        trade_lines.append(f"Risk/Reward: {rr}:1")
                        trade_lines.append(f"Risk: ${risk:.2f} | Reward: ${reward:.2f}")
                except Exception:
                    pass

        trade_text = "\n".join(trade_lines) if trade_lines else None

        # Confidence -> color
        if confidence == "HIGH":
            color = 0x2ECC71  # green
        elif confidence == "MEDIUM":
            color = 0xF1C40F  # amber
        else:
            color = 0xE74C3C  # red / ignore

        # Analysis text (kept in one field, truncated to 1024 chars)
        analysis_text = reasoning.strip() if reasoning else "No analysis available"
        if len(analysis_text) > 1024:
            analysis_text = analysis_text[:1020].rsplit(".", 1)[0]
            if len(analysis_text) < 20:
                analysis_text = reasoning[:1020]
            analysis_text += " ..."

        # Build embed fields to resemble the screenshot layout
        fields = []

        # Top row: strategy / direction / confidence
        fields.append(
            {
                "name": "Strategy",
                "value": f"`{strategy}`",
                "inline": True,
            }
        )
        fields.append(
            {
                "name": "Direction",
                "value": direction,
                "inline": True,
            }
        )
        fields.append(
            {
                "name": "Confidence",
                "value": confidence,
                "inline": True,
            }
        )

        # Second row: current price / consensus
        fields.append(
            {
                "name": "Current Price",
                "value": current_price_str,
                "inline": True,
            }
        )
        fields.append(
            {
                "name": "Consensus",
                "value": consensus_text,
                "inline": True,
            }
        )

        # Trend Data
        fields.append(
            {
                "name": "Trend Data",
                "value": trend_text,
                "inline": False,
            }
        )

        # Trade Levels (only if we have them)
        if trade_text:
            fields.append(
                {
                    "name": "Trade Levels",
                    "value": trade_text,
                    "inline": False,
                }
            )

        # Model breakdown
        fields.append(
            {
                "name": "Model Breakdown",
                "value": model_breakdown_text,
                "inline": False,
            }
        )

        # Analysis
        fields.append(
            {
                "name": "Analysis",
                "value": analysis_text,
                "inline": False,
            }
        )

        # Build embed
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
            # You can swap this for your own avatar if you want
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png",
        }

        print(f"Sending Discord embed for {ticker}: {direction} ({confidence})")
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 204:
            print(f"Sent to Discord: {ticker} {strategy} {direction} ({confidence})")
            return True
        else:
            print(f"Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"Discord send error: {e}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        return False


# Keep for backward compatibility
def make_discord_embed(alert_data, agent_reply):
    """Legacy function - kept for compatibility"""
    return send_to_discord(alert_data, agent_reply)
