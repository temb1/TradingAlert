# Version: 21
import os
import json
import requests
from datetime import datetime

from helpers import _to_float
from config import DISCORD_WEBHOOK_URL


def get_best_reasoning(ensemble_decision, model_details):
    """
    Get the best reasoning from available models - prioritize detailed analysis.
    ensemble_decision: dict with at least direction / confidence / consensus_breakdown / reasoning (optional)
    model_details: list of model result dicts, each may have 'model', 'reasoning', 'direction', 'confidence'
    """

    # Prefer detailed, non-consensus model reasoning
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

    # Fallback to ensemble decision reasoning
    consensus_reasoning = (ensemble_decision or {}).get("reasoning", "") or ""
    direction = (ensemble_decision or {}).get("direction", "UNKNOWN")
    confidence = (ensemble_decision or {}).get("confidence", "LOW")
    breakdown = (ensemble_decision or {}).get("consensus_breakdown", {}) or {}

    if "ENSEMBLE CONSENSUS" in consensus_reasoning:
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
    """
    Send trading alert to Discord using a card-style embed.

    alert_data: dict with at least 'ticker', 'strategy'/'pattern', 'price'/'close',
                and optionally 'additional_data', 'model_details', 'consensus_breakdown'
    ai_response: dict or JSON string with ensemble decision from models
    """
    try:
        # Webhook
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or DISCORD_WEBHOOK_URL

        if not webhook_url:
            print("❌ No Discord webhook URL configured")
            return False

        # --- Parse ai_response safely ---
        if isinstance(ai_response, str):
            ai_response = ai_response.strip()
            if ai_response:
                try:
                    response_data = json.loads(ai_response)
                except Exception:
                    # Not JSON – treat as plain reasoning text
                    response_data = {
                        "direction": "UNKNOWN",
                        "confidence": "LOW",
                        "reasoning": ai_response,
                    }
            else:
                response_data = {}
        elif isinstance(ai_response, dict):
            response_data = ai_response
        else:
            response_data = {}

        alert_data = alert_data or {}

        # --- Core values ---
        ticker = (alert_data.get("ticker", "UNKNOWN") or "UNKNOWN").upper()
        strategy = alert_data.get("strategy", alert_data.get("pattern", "unknown")) or "unknown"

        direction = (response_data.get("direction") or "IGNORE").upper()
        confidence = (response_data.get("confidence") or "LOW").upper()

        # Main price
        current_price = alert_data.get("price", alert_data.get("close", "N/A"))
        try:
            current_price_val = _to_float(current_price)
            current_price_str = f"${current_price_val:.2f}"
        except Exception:
            current_price_str = f"${current_price}"

        # Trade levels (from AI response)
        entry = response_data.get("entry")
        stop = response_data.get("stop")
        tp1 = response_data.get("tp1")
        tp2 = response_data.get("tp2")

        # --- Model details & consensus breakdown ---
        model_details = response_data.get("model_details")
        consensus_breakdown = response_data.get("consensus_breakdown")

        # Fallback to alert_data if DeepSeek / ensemble didn’t return these
        if not model_details:
            model_details = alert_data.get("model_details", []) or []
        if not consensus_breakdown:
            consensus_breakdown = alert_data.get("consensus_breakdown", {}) or {}

        # Combined ensemble_decision for reasoning function
        ensemble_decision = {
            "direction": direction,
            "confidence": confidence,
            "consensus_breakdown": consensus_breakdown,
            "reasoning": response_data.get("reasoning") or alert_data.get("reasoning", ""),
        }

        reasoning = get_best_reasoning(ensemble_decision, model_details)

        # --- Consensus text ---
        if consensus_breakdown:
            consensus_parts = [f"{k}: {v}" for k, v in consensus_breakdown.items()]
            consensus_text = ", ".join(consensus_parts)
        else:
            consensus_text = "N/A"

        # --- Trend data from alert_data.additional_data ---
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
            trend_parts.append(f"ETF: {'✅' if etf_mode else '❌'}")

        trend_text = "\n".join(trend_parts) if trend_parts else "N/A"

        # --- Model breakdown text ---
        model_lines = []
        for model in model_details[:3]:
            model_name = model.get("model", "Unknown")
            lower = model_name.lower()
            if "claude" in lower:
                display = "Claude"
            elif "gpt-4o" in lower:
                display = "GPT-4o"
            elif "gpt-4-turbo" in lower:
                display = "GPT-4-turbo"
            else:
                display = model_name

            m_dir = (model.get("direction", "UNKNOWN") or "UNKNOWN").upper()
            m_conf = (model.get("confidence", "UNKNOWN") or "UNKNOWN").upper()
            model_lines.append(f"{display}: {m_dir} ({m_conf})")

        model_breakdown_text = "\n".join(model_lines) if model_lines else "N/A"

        # --- Trade levels text & R/R ---
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

            # Risk / Reward if we have entry, stop, tp1
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

        # --- Confidence → color ---
        if confidence == "HIGH":
            color = 0x2ECC71  # green
        elif confidence == "MEDIUM":
            color = 0xF1C40F  # amber
        else:
            color = 0xE74C3C  # red / ignore

        # --- Analysis text, kept within Discord field limit (1024 chars) ---
        analysis_text = (reasoning or "No analysis available").strip()
        if len(analysis_text) > 1024:
            trimmed = analysis_text[:1020]
            # Try not to cut mid-sentence
            last_dot = trimmed.rfind(".")
            if last_dot > 200:
                trimmed = trimmed[: last_dot + 1]
            analysis_text = trimmed + " ..."

        # --- Build embed fields to mimic your card layout ---
        fields = []

        # Row 1: Strategy / Direction / Confidence
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

        # Row 2: Current Price / Consensus
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

        # Trade Levels (only if present)
        if trade_text:
            fields.append(
                {
                    "name": "Trade Levels",
                    "value": trade_text,
                    "inline": False,
                }
            )

        # Model Breakdown
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

        # --- Build embed ---
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
            # Replace this avatar URL with your own if you like
            "avatar_url": "https://img.icons8.com/color/96/000000/robot-2.png",
        }

        print(f"📤 Sending Discord embed for {ticker}: {direction} ({confidence})")
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
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

        print("❌ Full traceback:", traceback.format_exc())
        return False


# Backwards compatibility wrapper
def make_discord_embed(alert_data, agent_reply):
    """
    Legacy function – kept so existing calls still work.
    Simply forwards to send_to_discord.
    """
    return send_to_discord(alert_data, agent_reply)
