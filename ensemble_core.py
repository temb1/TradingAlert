# Version: 10
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
    """Core analysis methods for TradingEnsemble with direction learning and strategy-aware processing"""
    
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
                "weight": 0.4,
                "provider": "anthropic",
                "model_name": "claude-sonnet-4-20250514"
            }
        }
        
        self.direction_learner = direction_learner
        
        # Load API keys
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        
        # Check if we can make real API calls
        self.use_real_api = bool(self.openai_key and self.anthropic_key)
        
        # Initialize Strategy Processor
        try:
            from strategy_requirements import get_strategy_processor
            self.strategy_processor = get_strategy_processor()
            logger.info("✅ Strategy processor initialized successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import strategy_requirements: {e}")
            self.strategy_processor = None
        
        # Initialize Expert Enforcer - CATCHES ROOKIE MISTAKES
        try:
            from expert_enforcer import ExpertEnforcer
            self.expert_enforcer = ExpertEnforcer()
            logger.info("✅ Expert enforcer initialized - AI will be held accountable")
        except ImportError as e:
            logger.error(f"❌ Failed to import expert_enforcer: {e}")
            self.expert_enforcer = None
        
        # DEBUG: Log API key status
        logger.info("🔑 API Key Status:")
        logger.info(f"  - OpenAI Key: {'✅ SET' if self.openai_key else '❌ MISSING'}")
        logger.info(f"  - Anthropic Key: {'✅ SET' if self.anthropic_key else '❌ MISSING'}")
        logger.info(f"  - Use Real API: {self.use_real_api}")
        
        if not self.use_real_api:
            logger.error("❌ API keys not configured - ALL calls will fail!")
        else:
            logger.info("✅ Real API keys configured for AI ensemble")
    
    def validate_and_classify_alert(self, alert_data: Dict) -> Dict:
        """Validate alert data and classify strategy type"""
        if not self.strategy_processor:
            return {
                'is_valid': True,
                'strategy_type': 'unknown',
                'validation_score': 0.5,
                'missing_data': [],
                'processing_hint': 'Strategy processor not available'
            }
        
        pattern = alert_data.get('pattern', 'unknown')
        
        # Get validation results
        validation = self.strategy_processor.validate_alert_for_strategy(alert_data)
        
        # Log validation results
        logger.info(f"🔍 Strategy Validation for '{pattern}':")
        logger.info(f"   Type: {validation['strategy_type']}")
        logger.info(f"   Valid: {validation['is_valid']}")
        logger.info(f"   Score: {validation['validation_score']:.2%}")
        
        if validation['missing_required']:
            logger.warning(f"   Missing required: {validation['missing_required']}")
        
        if validation['unnecessary_fields']:
            logger.info(f"   Unnecessary fields (ok to ignore): {validation['unnecessary_fields']}")
        
        return validation
    
    def generate_strategy_aware_prompt(self, alert_data: Dict, validation_result: Dict) -> str:
        """Generate a prompt tailored to the specific strategy type"""
        pattern = alert_data.get('pattern', 'unknown')
        strategy_type = validation_result.get('strategy_type', 'unknown')
        
        base_prompt = f"""You are analyzing a {pattern} trading signal for {alert_data.get('ticker', 'unknown')}.
Current price: {alert_data.get('close', 'N/A')}
Timeframe: {alert_data.get('interval', 'N/A')}
"""
        
        # Strategy-specific instructions
        if strategy_type == 'breakout':
            base_prompt += """
This is a BREAKOUT strategy. Focus on:
1. Price position relative to key levels (IB High/Low, Box High/Low)
2. Volume confirmation
3. Breakout strength and validity
4. Risk-reward ratio based on breakout range

DO NOT require RSI or trend strength indicators for evaluation.
"""
            
            # Add breakout-specific data if available
            if 'ib_high' in alert_data:
                base_prompt += f"IB High: {alert_data.get('ib_high')}\n"
            if 'ib_low' in alert_data:
                base_prompt += f"IB Low: {alert_data.get('ib_low')}\n"
            if 'box_high' in alert_data:
                base_prompt += f"Box High: {alert_data.get('box_high')}\n"
            if 'box_low' in alert_data:
                base_prompt += f"Box Low: {alert_data.get('box_low')}\n"
        
        elif strategy_type == 'trend':
            base_prompt += """
This is a TREND-FOLLOWING strategy. Focus on:
1. Trend strength and direction
2. RSI levels and momentum
3. Moving average alignment
4. Volume trend confirmation

REQUIRES RSI and trend strength for proper evaluation.
"""
            # Add trend-specific data if available
            if 'rsi' in alert_data:
                base_prompt += f"RSI: {alert_data.get('rsi')}\n"
            if 'trend_strength' in alert_data:
                base_prompt += f"Trend Strength: {alert_data.get('trend_strength')}\n"
            if 'ema_fast' in alert_data:
                base_prompt += f"EMA Fast: {alert_data.get('ema_fast')}\n"
            if 'ema_slow' in alert_data:
                base_prompt += f"EMA Slow: {alert_data.get('ema_slow')}\n"
        
        elif strategy_type == 'reversion':
            base_prompt += """
This is a MEAN REVERSION strategy. Focus on:
1. Extreme RSI/Stochastic levels
2. Distance from moving averages or Bollinger Bands
3. Oversold/overbought conditions
4. Reversal confirmation signals
"""
            # Add reversion-specific data if available
            if 'rsi' in alert_data:
                base_prompt += f"RSI: {alert_data.get('rsi')}\n"
            if 'bollinger_upper' in alert_data:
                base_prompt += f"Bollinger Upper: {alert_data.get('bollinger_upper')}\n"
            if 'bollinger_lower' in alert_data:
                base_prompt += f"Bollinger Lower: {alert_data.get('bollinger_lower')}\n"
        
        # Add volume data if available
        if 'volume' in alert_data:
            base_prompt += f"Volume: {alert_data.get('volume')}\n"
        if 'volume_ratio' in alert_data:
            base_prompt += f"Volume Ratio: {alert_data.get('volume_ratio')}\n"
        
        # Add additional context
        base_prompt += f"""
Pattern Description: {validation_result.get('description', 'N/A')}
Validation Score: {validation_result.get('validation_score', 0):.2%}

Provide your analysis with:
1. Direction (LONG, SHORT, or IGNORE)
2. Confidence (HIGH, MEDIUM, LOW, or ERROR if data insufficient)
3. Brief reasoning

IMPORTANT: If critical data is missing for this strategy type, respond with ERROR confidence.
"""
        
        return base_prompt
    
    # ============================================================================
    # MAIN METHODS WITH EXPERT VALIDATION
    # ============================================================================
    
    async def get_ensemble_decision(self, ticker: str, alert_data: Dict) -> Dict:
        """
        Main method to get ensemble decision from AI models WITH EXPERT VALIDATION
        Returns formatted data ready for Discord
        """
        logger.info(f"🎯 Getting AI ensemble decision for {ticker}")
        
        # ✅ EXPERT ENFORCER ACTIVE
        if self.expert_enforcer:
            logger.info("🔍 Expert enforcer active - will validate AI responses")
        else:
            logger.warning("⚠️ Expert enforcer not available - proceeding without validation")
        
        # Check if we can make API calls
        if not self.use_real_api:
            error_msg = "API keys not configured. Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables."
            logger.error(f"❌ {error_msg}")
            return self._get_error_decision(ticker, alert_data, error_msg)
        
        # Build context and prompt
        context = self._build_context(alert_data)
        
        # Query all AI models
        model_responses = await self._query_all_models(context)
        
        # Parse responses WITH EXPERT VALIDATION
        parsed_responses = []
        for model_name, response in model_responses:
            if isinstance(response, Exception):
                logger.error(f"❌ Error from {model_name}: {response}")
                parsed_responses.append({
                    "model": model_name,
                    "direction": "ERROR",
                    "confidence": "ERROR",
                    "reasoning": f"API Error: {str(response)}",
                    "error": True
                })
            else:
                # ✅ APPLY EXPERT VALIDATION
                parsed_response = self._parse_response_with_expert_validation(
                    response, model_name, alert_data
                )
                parsed_responses.append(parsed_response)
        
        # Check if any models succeeded
        successful_responses = [r for r in parsed_responses if not r.get('error', False)]
        if not successful_responses:
            error_msg = "All AI models failed to respond"
            logger.error(f"❌ {error_msg}")
            return self._get_error_decision(ticker, alert_data, error_msg)
        
        # ✅ USE EXPERT-WEIGHTED CONSENSUS
        if self.expert_enforcer:
            consensus = self._analyze_consensus_with_expert_weights(parsed_responses, alert_data)
            logger.info("🎯 Using expert-weighted consensus")
        else:
            consensus = self._analyze_consensus(parsed_responses, alert_data)
            logger.info("⚠️ Using regular consensus (no expert weighting)")
        
        # Format for Discord
        result = self._format_for_discord(consensus, parsed_responses, ticker, alert_data)
        
        # ✅ ADD EXPERT VALIDATION SUMMARY
        if self.expert_enforcer:
            expert_summary = self._create_expert_summary(parsed_responses)
            result['expert_validation'] = expert_summary
            logger.info(f"📊 Expert validation summary added to result")
        
        logger.info(f"✅ Ensemble complete: {result['direction']} ({result['confidence']})")
        return result
    
    def _parse_response_with_expert_validation(self, response: str, model_name: str, alert_data: Dict) -> Dict:
        """Parse model response with expert validation"""
        try:
            # First parse the response
            parsed = self._parse_model_response(response, model_name)
            
            if parsed.get('error', False):
                return parsed
            
            # ✅ APPLY EXPERT VALIDATION
            if self.expert_enforcer:
                validation = self.expert_enforcer.validate_ai_response(response, alert_data)
                
                if validation['warnings']:
                    logger.warning(f"⚠️ {model_name} made rookie mistakes:")
                    for warning in validation['warnings']:
                        logger.warning(f"   - {warning}")
                    
                    # Parse corrected response
                    corrected_parsed = self._parse_model_response(
                        validation['corrected_response'], 
                        model_name
                    )
                    
                    if not corrected_parsed.get('error', False):
                        # Use corrected version
                        corrected_parsed['expert_corrected'] = True
                        corrected_parsed['expert_score'] = validation['expert_score']
                        corrected_parsed['expert_warnings'] = validation['warnings']
                        logger.info(f"✅ {model_name} response corrected by expert enforcer")
                        logger.info(f"   Expert Score: {validation['expert_score']:.1%}")
                        return corrected_parsed
                    else:
                        logger.error(f"❌ Failed to parse corrected response for {model_name}")
                
                else:
                    # No mistakes - just add expert score
                    parsed['expert_score'] = validation['expert_score']
                    logger.info(f"✅ {model_name} passed expert validation")
                    logger.info(f"   Expert Score: {validation['expert_score']:.1%}")
            
            return parsed
            
        except Exception as e:
            logger.error(f"❌ Error in expert validation for {model_name}: {e}")
            return self._create_error_response(model_name, f"Validation error: {str(e)}")
    
    def _create_expert_summary(self, parsed_responses: List[Dict]) -> Dict:
        """Create expert validation summary"""
        expert_summary = {
            'expert_scores': {},
            'corrections_made': 0,
            'total_warnings': 0,
            'average_score': 0
        }
        
        scores = []
        for resp in parsed_responses:
            if 'expert_score' in resp:
                expert_summary['expert_scores'][resp['model']] = resp['expert_score']
                scores.append(resp['expert_score'])
            
            if resp.get('expert_corrected', False):
                expert_summary['corrections_made'] += 1
            
            if 'expert_warnings' in resp:
                expert_summary['total_warnings'] += len(resp['expert_warnings'])
        
        if scores:
            expert_summary['average_score'] = sum(scores) / len(scores)
        
        return expert_summary
    
    def _analyze_consensus_with_expert_weights(self, results: List[Dict], alert_data: Dict) -> Dict:
        """Analyze consensus with expert score weighting"""
        try:
            logger.info("\n" + "="*50)
            logger.info("🎓 EXPERT-WEIGHTED CONSENSUS ANALYSIS")
            logger.info("="*50)
            
            valid_results = [r for r in results if not r.get('error', False)]
            
            if not valid_results:
                return self._analyze_consensus(results, alert_data)  # Fallback
            
            direction_weights = {}
            confidence_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "ERROR": 0}
            total_weighted_confidence = 0
            total_expert_weights = 0
            
            entry_levels = []
            stop_levels = []
            tp1_levels = []
            tp2_levels = []
            
            logger.info("\n📊 Expert-Weighted Model Breakdown:")
            for result in valid_results:
                model_name = result["model"]
                direction = result["direction"]
                confidence = result["confidence"]
                
                # Get base model weight
                base_weight = self.models.get(model_name, {}).get("weight", 0.3)
                
                # Adjust weight by expert score (higher score = more influence)
                expert_score = result.get('expert_score', 0.5)  # Default to 0.5 if no score
                weight = base_weight * expert_score
                
                direction_weights[direction] = direction_weights.get(direction, 0) + weight
                total_weighted_confidence += confidence_scores.get(confidence, 0) * weight
                total_expert_weights += weight
                
                if result.get('entry') is not None:
                    entry_levels.append(result['entry'])
                if result.get('stop') is not None:
                    stop_levels.append(result['stop'])
                if result.get('tp1') is not None:
                    tp1_levels.append(result['tp1'])
                if result.get('tp2') is not None:
                    tp2_levels.append(result['tp2'])
                
                logger.info(f"   - {model_name}: {direction} ({confidence})")
                logger.info(f"     Base Weight: {base_weight:.2f}, Expert Score: {expert_score:.1%}")
                logger.info(f"     Effective Weight: {weight:.3f}")
            
            # Determine consensus direction (weighted)
            if direction_weights:
                consensus_direction = max(direction_weights.items(), key=lambda x: x[1])[0]
                weighted_votes = direction_weights[consensus_direction]
                logger.info(f"🎯 Weighted consensus: {consensus_direction} (weight: {weighted_votes:.3f})")
            else:
                consensus_direction = "ERROR"
            
            # Calculate weighted confidence
            avg_confidence_score = total_weighted_confidence / total_expert_weights if total_expert_weights > 0 else 0
            
            if avg_confidence_score >= 2.5:
                consensus_confidence = "HIGH"
            elif avg_confidence_score >= 1.5:
                consensus_confidence = "MEDIUM" 
            elif avg_confidence_score > 0:
                consensus_confidence = "LOW"
            else:
                consensus_confidence = "ERROR"
            
            # Calculate average price levels
            def round_to_2_decimals(value):
                return round(value, 2) if value is not None else None
            
            avg_entry = round_to_2_decimals(sum(entry_levels) / len(entry_levels)) if entry_levels else None
            avg_stop = round_to_2_decimals(sum(stop_levels) / len(stop_levels)) if stop_levels else None
            avg_tp1 = round_to_2_decimals(sum(tp1_levels) / len(tp1_levels)) if tp1_levels else None
            avg_tp2 = round_to_2_decimals(sum(tp2_levels) / len(tp2_levels)) if tp2_levels else None
            
            # Build reasoning with expert context
            reasoning = f"🎓 EXPERT-VALIDATED CONSENSUS: {len(valid_results)}/3 models analyzed. "
            
            # Add direction breakdown
            dir_breakdown = []
            for direction, weight in direction_weights.items():
                dir_breakdown.append(f"{direction}: {weight:.3f}")
            reasoning += f"Direction weights: {', '.join(dir_breakdown)}. "
            
            reasoning += f"Final: {consensus_direction} ({consensus_confidence})"
            
            # Add average expert score
            avg_expert_score = sum(r.get('expert_score', 0.5) for r in valid_results) / len(valid_results)
            reasoning += f". AI Expertise: {avg_expert_score:.1%}"
            
            # Add corrections info
            corrections = sum(1 for r in valid_results if r.get('expert_corrected', False))
            if corrections > 0:
                reasoning += f". {corrections} model(s) corrected"
            
            # Add direction learning if available
            if self.direction_learner and consensus_direction in ["LONG", "SHORT"]:
                signals = self._extract_signals_for_learning(alert_data)
                learning_direction = "BULLISH" if consensus_direction == "LONG" else "BEARISH"
                learning_confidence = self.direction_learner.get_direction_confidence(signals, learning_direction)
                
                if learning_confidence > 0.6:
                    reasoning += f". Historical accuracy: {learning_confidence:.1%}"
            
            logger.info(f"\n🏁 FINAL EXPERT CONSENSUS: {consensus_direction} ({consensus_confidence})")
            logger.info(f"   Avg Expert Score: {avg_expert_score:.1%}")
            logger.info(f"   Corrections made: {corrections}")
            
            return {
                "direction": consensus_direction,
                "confidence": consensus_confidence,
                "entry": avg_entry,
                "stop": avg_stop,
                "tp1": avg_tp1,
                "tp2": avg_tp2,
                "reasoning": reasoning,
                "success": True,
                "expert_weighted": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in expert-weighted consensus: {e}")
            return self._analyze_consensus(results, alert_data)  # Fallback to regular consensus
    
    # ============================================================================
    # EXISTING METHODS (KEEP THESE AS-IS)
    # ============================================================================
    
    def get_ensemble_decision_sync(self, ticker: str, alert_data: Dict) -> Dict:
        """
        Synchronous wrapper for async ensemble decision - IMPROVED
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    logger.warning("🔄 Event loop already running, attempting to run within existing loop")
                    # Try to use nest_asyncio if available
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                        return loop.run_until_complete(self.get_ensemble_decision(ticker, alert_data))
                    except ImportError:
                        logger.error("❌ nest_asyncio not installed. Install: pip install nest_asyncio")
                        return self._get_error_decision(ticker, alert_data, "Event loop running - install nest_asyncio")
            except RuntimeError:
                # No event loop, create one
                pass
            
            # Standard async run
            return asyncio.run(self.get_ensemble_decision(ticker, alert_data))
            
        except Exception as e:
            logger.error(f"❌ Error in sync ensemble decision: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return self._get_error_decision(ticker, alert_data, f"Sync error: {str(e)}")
    
    def _get_error_decision(self, ticker: str, alert_data: Dict, error_msg: str) -> Dict:
        """Return an ERROR decision when AI ensemble fails - NO MOCK DATA"""
        logger.error(f"❌ Ensemble failed: {error_msg}")
        
        additional_data = alert_data.get('additional_data', {})
        
        return {
            "direction": "ERROR",
            "confidence": "ERROR",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "model_details": [
                {
                    "model": "SYSTEM",
                    "direction": "ERROR",
                    "confidence": "ERROR",
                    "reasoning": f"Ensemble system error: {error_msg}"
                }
            ],
            "consensus_breakdown": {"ERROR": 1},
            "reasoning": f"AI ensemble system failed: {error_msg}. Check API keys and network connection.",
            "additional_data": additional_data,
            "ticker": ticker,
            "strategy": alert_data.get("strategy", alert_data.get("pattern", "unknown")),
            "success": False,
            "error": True
        }
    
    def _build_context(self, alert_data):
        """Build richer context that captures momentum and multiple signals - UPGRADED"""
        # Get additional data FIRST - RSI is likely here
        additional_data = alert_data.get('additional_data', {})
        
        # Get RSI from the correct location
        rsi = additional_data.get('rsi') or alert_data.get('rsi', 0)
        
        # Convert to float
        try:
            rsi_value = float(rsi) if rsi is not None else 0
        except (ValueError, TypeError):
            rsi_value = 0
            logger.warning(f"⚠️ Could not parse RSI value: {rsi}")
        
        volume_status = alert_data.get('volume', 'NORMAL')
        current_price = alert_data.get('price') or alert_data.get('close') or alert_data.get('current_price') or 'N/A'
        
        # Get other data from additional_data
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
- RSI: {rsi_value:.2f} ({'OVERSOLD' if rsi_value < 30 else 'OVERBOUGHT' if rsi_value > 70 else 'NEUTRAL'})
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

IMPORTANT: YOU MUST RESPONSE WITH VALID JSON ONLY! Do not include any other text.

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
        
        # DEBUG: Log what we're sending to AI
        logger.info(f"📊 Context sent to AI:")
        logger.info(f"  - RSI: {rsi_value:.2f}")
        logger.info(f"  - Volume Ratio: {volume_ratio}")
        logger.info(f"  - Trend Strength: {trend_strength}")
        logger.info(f"  - ETF Mode: {etf_mode}")
        
        return context

    async def _query_all_models(self, context: str) -> List[tuple]:
        """Query all AI models in parallel with better logging"""
        tasks = []
        
        logger.info(f"🤖 Querying {len(self.models)} AI models with REAL API calls...")
        
        # Add tasks for each model
        for model_display, config in self.models.items():
            logger.info(f"  - Preparing REAL API call for {model_display}")
            if config["provider"] == "openai":
                task = self._query_openai(context, config["model_name"], model_display)
            else:  # anthropic
                task = self._query_anthropic(context, config["model_name"], model_display)
            tasks.append(task)
        
        # Run all queries in parallel
        logger.info("🚀 Running REAL AI model queries in parallel...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success_count = 0
        error_count = 0
        for i, result in enumerate(results):
            model_name = list(self.models.keys())[i]
            if isinstance(result, Exception):
                error_count += 1
                logger.error(f"❌ {model_name} FAILED: {result}")
            elif isinstance(result, tuple) and isinstance(result[1], Exception):
                error_count += 1
                logger.error(f"❌ {model_name} FAILED: {result[1]}")
            else:
                success_count += 1
                logger.info(f"✅ {model_name} SUCCESS: Response received")
        
        logger.info(f"📊 Results: {success_count} succeeded, {error_count} failed out of {len(self.models)} models")
        
        return results
    
    async def _query_openai(self, context: str, model_name: str, display_name: str) -> tuple:
        """Query OpenAI models - REAL API ONLY"""
        try:
            logger.info(f"🌐 Making REAL OpenAI API call to {display_name} ({model_name})")
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are a professional trading analyst. Always respond with valid JSON only."},
                        {"role": "user", "content": context}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "response_format": {"type": "json_object"}
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        error_msg = f"OpenAI API error {response.status}: {error_text[:200]}"
                        logger.error(f"❌ {error_msg}")
                        return (display_name, Exception(error_msg))
                    
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"✅ OpenAI {display_name} response received")
                    return (display_name, content)
                    
        except Exception as e:
            error_msg = f"OpenAI query error: {e}"
            logger.error(f"❌ {error_msg}")
            return (display_name, Exception(error_msg))
    
    async def _query_anthropic(self, context: str, model_name: str, display_name: str) -> tuple:
        """Query Anthropic Claude models - REAL API ONLY"""
        try:
            logger.info(f"🌐 Making REAL Claude API call to {display_name} ({model_name})")
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "max_tokens": 500,
                    "system": "You are a professional trading analyst. Always respond with valid JSON only.",
                    "messages": [
                        {"role": "user", "content": context}
                    ]
                }
                
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        error_msg = f"Claude API error {response.status}: {error_text[:200]}"
                        logger.error(f"❌ {error_msg}")
                        return (display_name, Exception(error_msg))
                    
                    data = await response.json()
                    content = data["content"][0]["text"]
                    logger.info(f"✅ Claude {display_name} response received")
                    return (display_name, content)
                    
        except Exception as e:
            error_msg = f"Claude query error: {e}"
            logger.error(f"❌ {error_msg}")
            return (display_name, Exception(error_msg))
    
    def _parse_model_response(self, response: str, model: str) -> Dict:
        """Parse model response into structured decision - UPGRADED with better JSON handling"""
        try:
            response = response.strip()
            logger.debug(f"📝 Parsing {model} response: {response[:200]}...")
            
            # First, try to find JSON object in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0).strip()
                try:
                    data = json.loads(json_str)
                    logger.info(f"✅ {model}: Successfully parsed JSON")
                    return {
                        "model": model,
                        "direction": str(data.get("direction", "IGNORE")).upper(),
                        "confidence": str(data.get("confidence", "LOW")).upper(),
                        "entry": data.get("entry"),
                        "stop": data.get("stop"),
                        "tp1": data.get("tp1"),
                        "tp2": data.get("tp2"),
                        "reasoning": str(data.get("reasoning", "No reasoning provided")),
                        "error": False
                    }
                except json.JSONDecodeError as e:
                    logger.warning(f"❌ {model}: JSON parse failed: {e}")
                    logger.debug(f"❌ Failed JSON: {json_str}")
            
            # Fallback: regex parsing for non-JSON responses
            direction = "ERROR"
            confidence = "ERROR"
            entry = None
            stop = None
            tp1 = None
            tp2 = None
            
            # Try to extract direction
            direction_patterns = [
                r'"direction"\s*:\s*"([^"]+)"',
                r"'direction'\s*:\s*'([^']+)'",
                r'direction["\s:]+([A-Z]+)',
                r'["\']?direction["\']?\s*:\s*["\']?([A-Z]+)["\']?'
            ]
            
            for pattern in direction_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    direction = match.group(1).upper()
                    break
            
            # Try to extract confidence
            confidence_patterns = [
                r'"confidence"\s*:\s*"([^"]+)"',
                r"'confidence'\s*:\s*'([^']+)'",
                r'confidence["\s:]+([A-Z]+)',
                r'["\']?confidence["\']?\s*:\s*["\']?([A-Z]+)["\']?'
            ]
            
            for pattern in confidence_patterns:
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
            reasoning = "Could not parse response"
            reason_patterns = [
                r'"reasoning"\s*:\s*"([^"]+)"',
                r"'reasoning'\s*:\s*'([^']+)'",
                r'reasoning["\s:]+"([^"]+)"'
            ]
            
            for pattern in reason_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    reasoning = match.group(1)
                    break
            else:
                # Try to find reasoning text after JSON structure
                lines = response.split('\n')
                for i, line in enumerate(lines):
                    if 'reasoning' in line.lower() or 'analysis' in line.lower():
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
            import traceback
            logger.debug(f"❌ Parse error traceback: {traceback.format_exc()}")
            return self._create_error_response(model, f"Parse error: {str(e)}")

    def _create_error_response(self, model_name: str, error_msg: str) -> Dict:
        """Create error response"""
        return {
            "model": model_name,
            "direction": "ERROR",
            "confidence": "ERROR",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "reasoning": f"{error_msg[:100]}",
            "error": True
        }

    def _format_for_discord(self, consensus: Dict, model_details: List[Dict], ticker: str, alert_data: Dict) -> Dict:
        """Format ensemble decision for Discord output - FIXED"""
        # Get trend data
        additional_data = alert_data.get('additional_data', {})
        rsi = additional_data.get('rsi')
        volume_ratio = additional_data.get('volume_ratio', additional_data.get('volume', 'N/A'))
        trend_strength = additional_data.get('trend_strength', 'N/A')
        etf_mode = additional_data.get('etf_mode', False)
        
        # Format model breakdown for Discord
        formatted_model_details = []
        for model in model_details:
            formatted_model_details.append({
                "model": model["model"],
                "direction": model["direction"],
                "confidence": model["confidence"],
                "reasoning": model["reasoning"],
                "error": model.get("error", False),
                "expert_corrected": model.get("expert_corrected", False),
                "expert_score": model.get("expert_score", 0)
            })
        
        # Build consensus breakdown
        consensus_breakdown = {}
        for model in model_details:
            if not model.get("error", False):
                direction = model["direction"]
                consensus_breakdown[direction] = consensus_breakdown.get(direction, 0) + 1
        
        # If no consensus (all models failed), default to IGNORE
        if not consensus_breakdown:
            consensus_breakdown = {"ERROR": len(model_details)}
        
        # Create final result for Discord
        result = {
            "direction": consensus.get("direction", "ERROR"),
            "confidence": consensus.get("confidence", "ERROR"),
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
            "strategy": alert_data.get("strategy", alert_data.get("pattern", "unknown")),
            "success": consensus.get("success", False),
            "error": consensus.get("success", True) == False
        }
        
        # Add expert info if available
        if consensus.get("expert_weighted", False):
            result["expert_weighted"] = True
        
        logger.info(f"📤 Formatted Discord result: {result['direction']} with {len(result['model_details'])} models")
        return result

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
            error_results = [r for r in results if r.get('error', False)]
            
            logger.info(f"📊 Valid results: {len(valid_results)}/3 models")
            if error_results:
                logger.warning(f"⚠️ Errors: {len(error_results)} models failed")
                for err in error_results:
                    logger.warning(f"   - {err['model']}: {err['reasoning'][:100]}")
            
            if not valid_results:
                logger.error("❌ CRITICAL: All models failed!")
                return {
                    "direction": "ERROR", 
                    "confidence": "ERROR", 
                    "reasoning": "All models failed or had errors. Check API keys and network.",
                    "success": False
                }
            
            direction_counts = {}
            confidence_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "ERROR": 0}
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
                # Find the direction with most votes
                consensus_direction = max(direction_counts.items(), key=lambda x: x[1])[0]
                vote_count = direction_counts[consensus_direction]
                
                # If we have ERRORs mixed in, handle specially
                if "ERROR" in direction_counts and consensus_direction != "ERROR":
                    logger.warning(f"⚠️ Mix of valid results and errors. Proceeding with {consensus_direction}")
                
                # If no clear majority (2+ votes for 3 models), default to IGNORE
                if vote_count < 2 and consensus_direction != "ERROR":
                    consensus_direction = "IGNORE"
                    logger.info("🤷‍♂️ No clear majority, defaulting to IGNORE")
            else:
                consensus_direction = "ERROR"
            
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
            elif avg_confidence_score > 0:
                consensus_confidence = "LOW"
            else:
                consensus_confidence = "ERROR"
            
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
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {
                "direction": "ERROR",
                "confidence": "ERROR", 
                "reasoning": f"Consensus analysis error: {str(e)}",
                "success": False
            }


# Test function
def test_ensemble_core():
    """Test the ensemble core system with real API"""
    print("🧪 Testing Ensemble Core System (REAL API ONLY)...")
    
    core = EnsembleCore()
    
    test_alert = {
        "ticker": "AAPL",
        "strategy": "bullish_trend",
        "price": 150.50,
        "rsi": 65.5,
        "additional_data": {
            "rsi": 65.5,
            "volume_ratio": 1.8,
            "trend_strength": "strong",
            "etf_mode": False
        }
    }
    
    print(f"🔑 API Status: OpenAI={bool(core.openai_key)}, Anthropic={bool(core.anthropic_key)}")
    print(f"🔄 Use Real API: {core.use_real_api}")
    print(f"🎓 Expert Enforcer: {'✅ ACTIVE' if core.expert_enforcer else '❌ INACTIVE'}")
    
    if not core.use_real_api:
        print("❌ API keys not configured. Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.")
        return None
    
    print("🔄 Getting ensemble decision...")
    result = core.get_ensemble_decision_sync("AAPL", test_alert)
    
    print(f"\n✅ Result keys: {list(result.keys())}")
    print(f"🎯 Direction: {result.get('direction')}")
    print(f"📊 Confidence: {result.get('confidence')}")
    print(f"🤖 Model details: {len(result.get('model_details', []))} models")
    print(f"📈 Consensus breakdown: {result.get('consensus_breakdown')}")
    print(f"💭 Reasoning: {result.get('reasoning', '')[:100]}...")
    
    if result.get('model_details'):
        for model in result['model_details']:
            print(f"  - {model['model']}: {model['direction']} ({model['confidence']})")
            if model.get('expert_corrected'):
                print(f"    ⚠️ Expert Corrected (Score: {model.get('expert_score', 0):.1%})")
            if model.get('error'):
                print(f"    ❌ ERROR: {model.get('reasoning', 'Unknown error')}")
    
    if result.get('expert_validation'):
        print(f"\n🎓 EXPERT VALIDATION SUMMARY:")
        print(f"  Avg Score: {result['expert_validation'].get('average_score', 0):.1%}")
        print(f"  Corrections: {result['expert_validation'].get('corrections_made', 0)}")
    
    return result

if __name__ == "__main__":
    test_result = test_ensemble_core()
    print("\n" + "="*50)
    if test_result:
        print(f"✅ Test completed! Final Decision: {test_result.get('direction')} with {test_result.get('confidence')} confidence")
    else:
        print("❌ Test failed - check API keys")
