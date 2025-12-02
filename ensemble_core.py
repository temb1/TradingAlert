# Version: 4
import re
import json
import asyncio
import aiohttp
import os
from typing import List, Dict, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnsembleCore:
    """Core analysis methods for TradingEnsemble with direction learning - UPGRADED"""
    
    def __init__(self, system_prompt: str = None, models_config: Dict = None, direction_learner=None):
        self.system_prompt = system_prompt or "You are a professional trading analyst."
        
        # ✅ UPDATED: Correct weights - Claude 40%, GPT-4o 30%, GPT-4-turbo 30%
        self.models = models_config or {
            "GPT-4o": {
                "weight": 0.3,
                "provider": "openai",
                "model_name": "gpt-4o"
            },
            "GPT-4-turbo": {
                "weight": 0.3,
                "provider": "openai", 
                "model_name": "gpt-4-turbo"
            },
            "Claude": {
                "weight": 0.4,  # Fixed: 40% not 30%
                "provider": "anthropic",
                "model_name": "claude-sonnet-4-20250514"  # Updated to current Claude
            }
        }
        
        self.direction_learner = direction_learner
        
        # Load API keys
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        
        # Check if we can make real API calls
        self.use_real_api = bool(self.openai_key and self.anthropic_key)
        
        if not self.use_real_api:
            logger.warning("⚠️ API keys not configured - will return mock data")
        else:
            logger.info("✅ Real API keys configured for AI ensemble")
    
    def _build_context(self, alert_data):
        """Build richer context that captures momentum and multiple signals - UPGRADED"""
        rsi = alert_data.get('rsi', 0)
        volume_status = alert_data.get('volume', 'NORMAL')
        current_price = alert_data.get('price') or alert_data.get('close') or alert_data.get('current_price') or 'N/A'
        
        # Get additional data
        additional_data = alert_data.get('additional_data', {})
        volume_ratio = additional_data.get('volume_ratio', volume_status)
        trend_strength = additional_data.get('trend_strength', 'UNKNOWN')
        etf_mode = additional_data.get('etf_mode', False)
        
        momentum_patterns = self._detect_momentum_patterns(alert_data)
        
        # Add direction learning insights if available
        direction_insights = ""
        if self.direction_learner:
            signals = self._extract_signals_for_learning(alert_data)
            if any(signals.values()):
                direction_insights = self._get_direction_learning_insights(signals, alert_data)
        
        context = f"""
TRADING ALERT ANALYSIS:

TICKER: {alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))}
STRATEGY: {alert_data.get('strategy', alert_data.get('pattern', 'UNKNOWN'))} 
CURRENT PRICE: ${current_price}

TECHNICAL DATA:
- RSI: {rsi} ({'OVERSOLD' if rsi < 30 else 'OVERBOUGHT' if rsi > 70 else 'NEUTRAL'})
- Volume: {volume_ratio}
- Trend Strength: {trend_strength}
- ETF Mode: {'✅ YES' if etf_mode else '❌ NO'}

MOMENTUM SIGNALS:
- Momentum Patterns: {', '.join(momentum_patterns) if momentum_patterns else 'None detected'}
- Bullish Indicators: {sum(1 for key in alert_data.keys() if 'BULL' in str(key).upper())} active
- Bearish Indicators: {sum(1 for key in alert_data.keys() if 'BEAR' in str(key).upper())} active

{direction_insights}

PRICE LEVELS:
- IB High: {alert_data.get('ib_high', 'N/A')}
- IB Low: {alert_data.get('ib_low', 'N/A')}
- Box High: {alert_data.get('box_high', 'N/A')}
- Box Low: {alert_data.get('box_low', 'N/A')}

TRADING REQUIREMENTS:
- Max Risk: $70 per trade
- Minimum Risk/Reward: 1:1.5
- Must provide specific Entry, Stop, TP1, TP2 levels
- Only recommend trades with clear setup

FORMAT YOUR RESPONSE AS JSON:
{{
    "direction": "LONG" or "SHORT" or "IGNORE",
    "confidence": "HIGH" or "MEDIUM" or "LOW",
    "entry": specific_price,
    "stop": specific_price,
    "tp1": specific_price,
    "tp2": specific_price,
    "reasoning": "Detailed analysis here..."
}}
"""
        return context

    async def get_ensemble_decision(self, ticker: str, alert_data: Dict) -> Dict:
        """
        Main method to get ensemble decision from AI models
        Returns formatted data ready for Discord
        """
        logger.info(f"🎯 Getting AI ensemble decision for {ticker}")
        
        # Build context and prompt
        context = self._build_context(alert_data)
        
        # Query all AI models
        model_responses = await self._query_all_models(context)
        
        # Parse responses
        parsed_responses = []
        for model_name, response in model_responses:
            if isinstance(response, Exception):
                logger.error(f"Error from {model_name}: {response}")
                parsed_responses.append({
                    "model": model_name,
                    "direction": "IGNORE",
                    "confidence": "LOW",
                    "reasoning": f"Error: {str(response)}",
                    "error": True
                })
            else:
                parsed = self._parse_model_response(response, model_name)
                parsed_responses.append(parsed)
        
        # Analyze consensus
        consensus = self._analyze_consensus(parsed_responses, alert_data)
        
        # Format for Discord
        result = self._format_for_discord(consensus, parsed_responses, ticker, alert_data)
        
        logger.info(f"✅ Ensemble complete: {result['direction']} ({result['confidence']})")
        return result
    
    async def _query_all_models(self, context: str) -> List[tuple]:
        """Query all AI models in parallel"""
        tasks = []
        
        # Add tasks for each model
        for model_display, config in self.models.items():
            if config["provider"] == "openai":
                task = self._query_openai(context, config["model_name"], model_display)
            else:  # anthropic
                task = self._query_anthropic(context, config["model_name"], model_display)
            tasks.append(task)
        
        # Run all queries in parallel
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _query_openai(self, context: str, model_name: str, display_name: str) -> tuple:
        """Query OpenAI models"""
        if not self.use_real_api:
            # Return mock response
            mock_response = self._get_mock_openai_response(display_name)
            return (display_name, mock_response)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": context}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    data = await response.json()
                    return (display_name, data["choices"][0]["message"]["content"])
                    
        except Exception as e:
            logger.error(f"OpenAI query error ({display_name}): {e}")
            return (display_name, e)
    
    async def _query_anthropic(self, context: str, model_name: str, display_name: str) -> tuple:
        """Query Anthropic Claude models"""
        if not self.use_real_api:
            # Return mock response
            mock_response = self._get_mock_claude_response(display_name)
            return (display_name, mock_response)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "max_tokens": 500,
                    "system": self.system_prompt,
                    "messages": [
                        {"role": "user", "content": context}
                    ]
                }
                
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    data = await response.json()
                    return (display_name, data["content"][0]["text"])
                    
        except Exception as e:
            logger.error(f"Claude query error ({display_name}): {e}")
            return (display_name, e)
    
    def _get_mock_openai_response(self, model_name: str) -> str:
        """Get mock OpenAI response for testing"""
        if "GPT-4o" in model_name:
            return json.dumps({
                "direction": "LONG",
                "confidence": "HIGH",
                "entry": 216.50,
                "stop": 215.50,
                "tp1": 218.00,
                "tp2": 220.00,
                "reasoning": "Mock GPT-4o analysis: Strong bullish trend with RSI confirmation and volume surge."
            })
        else:  # GPT-4-turbo
            return json.dumps({
                "direction": "SHORT",
                "confidence": "MEDIUM",
                "entry": 216.30,
                "stop": 217.30,
                "tp1": 214.50,
                "tp2": 212.00,
                "reasoning": "Mock GPT-4-turbo analysis: Bearish divergence on RSI suggests potential reversal."
            })
    
    def _get_mock_claude_response(self, model_name: str) -> str:
        """Get mock Claude response for testing"""
        return json.dumps({
            "direction": "IGNORE",
            "confidence": "LOW",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "reasoning": "Mock Claude analysis: Mixed signals - RSI neutral and volume not confirming direction."
        })
    
    def _parse_model_response(self, response: str, model: str) -> Dict:
        """Parse model response into structured decision - UPGRADED"""
        try:
            response = response.strip()
            logger.info(f"📝 {model} response length: {len(response)} chars")
            
            # Try to parse as JSON first
            if response.startswith("{") and response.endswith("}"):
                try:
                    data = json.loads(response)
                    return {
                        "model": model,
                        "direction": data.get("direction", "IGNORE").upper(),
                        "confidence": data.get("confidence", "LOW").upper(),
                        "entry": data.get("entry"),
                        "stop": data.get("stop"),
                        "tp1": data.get("tp1"),
                        "tp2": data.get("tp2"),
                        "reasoning": data.get("reasoning", "No reasoning provided"),
                        "error": False
                    }
                except json.JSONDecodeError:
                    pass  # Fall back to regex parsing
            
            # Fallback: regex parsing for non-JSON responses
            direction = "IGNORE"
            for pattern in [r'"direction"\s*:\s*"([^"]+)"', r'direction["\s:]+([A-Z]+)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    direction = match.group(1).upper()
                    break
            
            confidence = "LOW"
            for pattern in [r'"confidence"\s*:\s*"([^"]+)"', r'confidence["\s:]+([A-Z]+)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    confidence = match.group(1).upper()
                    break
            
            # Extract price levels
            entry = self._extract_price_level(response, 'entry')
            stop = self._extract_price_level(response, 'stop')
            tp1 = self._extract_price_level(response, 'tp1')
            tp2 = self._extract_price_level(response, 'tp2')
            
            # Extract reasoning
            reasoning = "No reasoning provided"
            reason_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', response, re.IGNORECASE)
            if reason_match:
                reasoning = reason_match.group(1)
            else:
                # Try to find any text after the JSON structure
                lines = response.split('\n')
                for i, line in enumerate(lines):
                    if 'reasoning' in line.lower():
                        if i + 1 < len(lines):
                            reasoning = lines[i + 1].strip()
                        break
            
            logger.info(f"🎯 {model}: {direction} ({confidence})")
            
            return {
                "model": model,
                "direction": direction,
                "confidence": confidence,
                "entry": entry,
                "stop": stop,
                "tp1": tp1,
                "tp2": tp2,
                "reasoning": reasoning[:500] + "..." if len(reasoning) > 500 else reasoning,
                "error": False
            }
            
        except Exception as e:
            logger.error(f"❌ {model} parse error: {e}")
            return {
                "model": model,
                "direction": "IGNORE",
                "confidence": "LOW",
                "entry": None,
                "stop": None,
                "tp1": None,
                "tp2": None,
                "reasoning": f"Parse error: {str(e)}",
                "error": True
            }

    def _format_for_discord(self, consensus: Dict, model_details: List[Dict], ticker: str, alert_data: Dict) -> Dict:
        """Format ensemble decision for Discord output"""
        # Get trend data
        additional_data = alert_data.get('additional_data', {})
        rsi = additional_data.get('rsi')
        volume_ratio = additional_data.get('volume_ratio', additional_data.get('volume', 'N/A'))
        trend_strength = additional_data.get('trend_strength', 'N/A')
        etf_mode = additional_data.get('etf_mode', False)
        
        # Format model breakdown for Discord
        formatted_model_details = []
        for model in model_details:
            if not model.get("error", False):
                formatted_model_details.append({
                    "model": model["model"],
                    "direction": model["direction"],
                    "confidence": model["confidence"],
                    "reasoning": model["reasoning"]
                })
        
        # Build consensus breakdown string
        consensus_breakdown = {}
        for model in model_details:
            if not model.get("error", False):
                direction = model["direction"]
                consensus_breakdown[direction] = consensus_breakdown.get(direction, 0) + 1
        
        # Create final result for Discord
        result = {
            "direction": consensus.get("direction", "IGNORE"),
            "confidence": consensus.get("confidence", "LOW"),
            "entry": consensus.get("entry"),
            "stop": consensus.get("stop"),
            "tp1": consensus.get("tp1"),
            "tp2": consensus.get("tp2"),
            "model_details": formatted_model_details,
            "consensus_breakdown": consensus_breakdown,
            "reasoning": consensus.get("reasoning", "No analysis available"),
            "additional_data": {
                "rsi": rsi,
                "volume_ratio": volume_ratio,
                "trend_strength": trend_strength,
                "etf_mode": etf_mode
            },
            "ticker": ticker,
            "strategy": alert_data.get("strategy", alert_data.get("pattern", "unknown"))
        }
        
        return result

    # --- Keep existing helper methods ---
    def _extract_signals_for_learning(self, alert_data: Dict) -> Dict:
        """Extract signals for direction learning system"""
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False,
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        strategy = alert_data.get('strategy', '').lower()
        pattern = alert_data.get('pattern', '').lower()
        
        # Detect 3-1 Inside Bar
        if any(term in strategy for term in ['3-1', 'inside_bar', 'inside bar']) or \
           any(term in pattern for term in ['3-1', 'inside bar']):
            signals["inside_bar_3_1"] = True
            
        # Detect A/M/D Phases
        if 'accumulation' in strategy:
            signals["accumulation"] = True
        if 'manipulation' in strategy:
            signals["manipulation"] = True
        if 'distribution' in strategy:
            signals["distribution"] = True
            
        # Detect Trends
        if any(term in strategy for term in ['bullish', 'uptrend', 'rising', 'strong_bullish']):
            signals["bullish_trend"] = True
        if any(term in strategy for term in ['bearish', 'downtrend', 'falling', 'strong_bearish']):
            signals["bearish_trend"] = True
            
        return signals

    def _get_direction_learning_insights(self, signals: Dict, alert_data: Dict) -> str:
        """Get insights from direction learning system"""
        if not self.direction_learner:
            return ""
            
        try:
            insights = []
            
            # Get confidence for both directions
            bull_confidence = self.direction_learner.get_direction_confidence(signals, 'BULLISH')
            bear_confidence = self.direction_learner.get_direction_confidence(signals, 'BEARISH')
            
            # Only show insights if we have meaningful data
            if bull_confidence > 0.55 or bear_confidence > 0.55:
                insights.append("🎯 DIRECTION LEARNING INSIGHTS:")
                
                if bull_confidence > bear_confidence:
                    insights.append(f"- Historical BULLISH confidence: {bull_confidence:.1%}")
                    if bull_confidence > 0.65:
                        insights.append("- ✅ Strong historical bullish bias for these signals")
                    elif bull_confidence > 0.55:
                        insights.append("- ⚠️ Moderate historical bullish bias")
                else:
                    insights.append(f"- Historical BEARISH confidence: {bear_confidence:.1%}")
                    if bear_confidence > 0.65:
                        insights.append("- ✅ Strong historical bearish bias for these signals")
                    elif bear_confidence > 0.55:
                        insights.append("- ⚠️ Moderate historical bearish bias")
                
                # Add specific signal insights
                active_signals = [sig for sig, active in signals.items() if active]
                if active_signals:
                    insights.append(f"- Active signals: {', '.join(active_signals)}")
            
            return "\n".join(insights) if insights else ""
            
        except Exception as e:
            logger.error(f"❌ Error getting direction learning insights: {e}")
            return ""

    def _detect_momentum_patterns(self, alert_data):
        """Detect strong momentum patterns"""
        patterns = []
        rsi = alert_data.get('rsi', 0)
        bullish_count = sum(1 for key in alert_data.keys() if 'BULL' in str(key).upper())
        bearish_count = sum(1 for key in alert_data.keys() if 'BEAR' in str(key).upper())
        current_price = alert_data.get('price', 0) or alert_data.get('close', 0)
        ib_high = alert_data.get('ib_high', 0)
        
        if (rsi > 75 and bullish_count >= 3) or (rsi > 70 and bullish_count >= 4):
            patterns.append("STRONG_BULLISH_MOMENTUM")
        
        if (rsi < 25 and bearish_count >= 3) or (rsi < 30 and bearish_count >= 4):
            patterns.append("STRONG_BEARISH_MOMENTUM")
        
        if (rsi > 70 and current_price > ib_high > 0):
            patterns.append("BREAKOUT_MOMENTUM")
        
        if rsi > 70 or rsi < 30:
            patterns.append("HIGH_MOMENTUM_ENVIRONMENT")
            
        return patterns

    def _extract_price_level(self, response: str, field: str):
        """Extract price level from response text"""
        try:
            pattern = rf'"{field}"\s*:\s*([0-9]+\.?[0-9]*)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                value = match.group(1)
                if value.lower() not in ['n/a', 'none', 'null']:
                    return float(value)
            
            pattern2 = rf'{field}\s*["\s:]*([0-9]+\.?[0-9]*)'
            match2 = re.search(pattern2, response, re.IGNORECASE)
            if match2:
                value = match2.group(1)
                if value.lower() not in ['n/a', 'none', 'null']:
                    return float(value)
                
            return None
        except (ValueError, TypeError):
            return None

    def _analyze_consensus(self, results: List[Dict], alert_data: Dict) -> Dict:
        """Analyze multiple model decisions and return consensus with direction learning"""
        def round_to_2_decimals(value):
            return round(value, 2) if value is not None else None
        
        try:
            logger.info("\n" + "="*50)
            logger.info("🤖 ENSEMBLE CONSENSUS ANALYSIS")
            logger.info("="*50)
            
            # Show model weights
            weights_info = []
            for model_name, config in self.models.items():
                weights_info.append(f"{model_name}: {config['weight']:.1%}")
            logger.info(f"📊 Model Weights: {', '.join(weights_info)}")
            
            valid_results = [r for r in results if not r.get('error', False)]
            logger.info(f"📊 Valid results: {len(valid_results)}/3 models")
            
            if not valid_results:
                logger.error("❌ CRITICAL: All models failed!")
                return {
                    "direction": "IGNORE", 
                    "confidence": "LOW", 
                    "reasoning": "All models failed or had errors",
                    "success": False
                }
            
            direction_counts = {}
            confidence_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
            total_weighted_confidence = 0
            total_weights = 0
            
            entry_levels = []
            stop_levels = []
            tp1_levels = []
            tp2_levels = []
            
            logger.info("\n📈 Model Breakdown:")
            for result in valid_results:
                model_name = result["model"]
                direction = result["direction"]
                confidence = result["confidence"]
                weight = self.models.get(model_name, {}).get("weight", 0.3)
                
                direction_counts[direction] = direction_counts.get(direction, 0) + 1
                total_weighted_confidence += confidence_scores.get(confidence, 0) * weight
                total_weights += weight
                
                if result.get('entry') is not None:
                    entry_levels.append(result['entry'])
                if result.get('stop') is not None:
                    stop_levels.append(result['stop'])
                if result.get('tp1') is not None:
                    tp1_levels.append(result['tp1'])
                if result.get('tp2') is not None:
                    tp2_levels.append(result['tp2'])
                
                logger.info(f"   - {model_name}: {direction} (Confidence: {confidence}, Weight: {weight})")
            
            # Determine consensus direction
            if direction_counts:
                consensus_direction = max(direction_counts.items(), key=lambda x: x[1])[0]
                vote_count = direction_counts[consensus_direction]
                
                # If no clear majority (2+ votes), default to IGNORE
                if vote_count < 2:
                    consensus_direction = "IGNORE"
            else:
                consensus_direction = "IGNORE"
            
            avg_confidence_score = total_weighted_confidence / total_weights if total_weights > 0 else 0
            
            # Apply direction learning confidence adjustment if available
            if self.direction_learner and consensus_direction in ["LONG", "SHORT"]:
                signals = self._extract_signals_for_learning(alert_data)
                learning_direction = "BULLISH" if consensus_direction == "LONG" else "BEARISH"
                learning_confidence = self.direction_learner.get_direction_confidence(signals, learning_direction)
                
                logger.info(f"🎯 Direction Learning Confidence: {learning_confidence:.1%}")
                
                # Adjust confidence based on learning system
                if learning_confidence > 0.65:
                    avg_confidence_score = min(3.0, avg_confidence_score + 0.5)
                    logger.info(f"📈 Confidence boosted due to strong historical accuracy")
                elif learning_confidence < 0.45:
                    avg_confidence_score = max(1.0, avg_confidence_score - 0.5)
                    logger.info(f"📉 Confidence reduced due to poor historical accuracy")
            
            # Determine final confidence level
            if avg_confidence_score >= 2.5:
                consensus_confidence = "HIGH"
            elif avg_confidence_score >= 1.5:
                consensus_confidence = "MEDIUM" 
            else:
                consensus_confidence = "LOW"
            
            # Calculate average price levels
            avg_entry = round_to_2_decimals(sum(entry_levels) / len(entry_levels)) if entry_levels else None
            avg_stop = round_to_2_decimals(sum(stop_levels) / len(stop_levels)) if stop_levels else None
            avg_tp1 = round_to_2_decimals(sum(tp1_levels) / len(tp1_levels)) if tp1_levels else None
            avg_tp2 = round_to_2_decimals(sum(tp2_levels) / len(tp2_levels)) if tp2_levels else None
            
            logger.info(f"💰 Average levels - Entry: {avg_entry}, Stop: {avg_stop}, TP1: {avg_tp1}, TP2: {avg_tp2}")
            
            # Build reasoning
            reasoning = f"ENSEMBLE CONSENSUS: {len(valid_results)}/3 models analyzed. "
            reasoning += f"Direction: {consensus_direction} ("
            reasoning += ", ".join([f"{dir}: {count}" for dir, count in direction_counts.items()])
            reasoning += f"). Confidence: {consensus_confidence}"
            
            # Add direction learning insight
            if self.direction_learner and consensus_direction in ["LONG", "SHORT"]:
                signals = self._extract_signals_for_learning(alert_data)
                learning_direction = "BULLISH" if consensus_direction == "LONG" else "BEARISH"
                learning_confidence = self.direction_learner.get_direction_confidence(signals, learning_direction)
                
                if learning_confidence > 0.6:
                    reasoning += f". Historical accuracy for these signals: {learning_confidence:.1%}"
                elif learning_confidence < 0.4:
                    reasoning += f". Caution: Historical accuracy for these signals: {learning_confidence:.1%}"
            
            logger.info(f"\n🏁 FINAL CONSENSUS: {consensus_direction} (Confidence: {consensus_confidence})")
            
            return {
                "direction": consensus_direction,
                "confidence": consensus_confidence,
                "entry": avg_entry,
                "stop": avg_stop,
                "tp1": avg_tp1,
                "tp2": avg_tp2,
                "reasoning": reasoning,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in _analyze_consensus: {e}")
            return {
                "direction": "IGNORE",
                "confidence": "LOW", 
                "reasoning": f"Consensus analysis error: {str(e)}",
                "success": False
            }
