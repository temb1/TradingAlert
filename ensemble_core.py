# Version: 1
import re
import json
from typing import List, Dict, Optional
from datetime import datetime

class EnsembleCore:
    """Core analysis methods for TradingEnsemble"""
    
    def __init__(self, system_prompt: str, models_config: Dict):
        self.system_prompt = system_prompt
        self.models = models_config
    
    def _build_context(self, alert_data):
        """Build richer context that captures momentum and multiple signals"""
        rsi = alert_data.get('rsi', 0)
        volume_status = alert_data.get('volume', 'NORMAL')
        bullish_signals = sum(1 for key in alert_data.keys() if 'BULL' in str(key).upper())
        bearish_signals = sum(1 for key in alert_data.keys() if 'BEAR' in str(key).upper())
        current_price = alert_data.get('price') or alert_data.get('close') or alert_data.get('current_price') or 'N/A'
        
        momentum_patterns = self._detect_momentum_patterns(alert_data)
        
        context = f"""
TRADING ALERT WITH MOMENTUM ANALYSIS:

TICKER: {alert_data.get('ticker', alert_data.get('symbol', 'UNKNOWN'))}
STRATEGY: {alert_data.get('strategy', alert_data.get('pattern', 'UNKNOWN'))} 
CURRENT PRICE: ${current_price}

🚨 MOMENTUM SIGNALS:
- RSI: {rsi} ({'OVERSOLD' if rsi < 30 else 'OVERBOUGHT' if rsi > 70 else 'NEUTRAL'})
- Volume: {volume_status}
- Bullish Indicators: {bullish_signals} active
- Bearish Indicators: {bearish_signals} active
- Trend: {alert_data.get('trend', 'UNKNOWN')}
- Momentum Patterns: {', '.join(momentum_patterns) if momentum_patterns else 'None detected'}

PRICE LEVELS:
- IB High: {alert_data.get('ib_high', 'N/A')}
- IB Low: {alert_data.get('ib_low', 'N/A')}

TRADING APPROACH:
- Strong momentum (RSI >70/<30) suggests trend continuation
- Multiple confirmations increase confidence
- Consider momentum over perfect patterns in strong environments

ADDITIONAL DATA:
{json.dumps(alert_data.get('additional_data', {}), indent=2) if alert_data.get('additional_data') else 'No additional data'}
"""
        return context

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

    def _parse_decision(self, response: str, model: str) -> Dict:
        """Parse model response into structured decision"""
        try:
            response = response.strip()
            print(f"📝 {model} raw response length: {len(response)} chars")
            
            direction = "IGNORE"
            for pattern in [r'\*\*Direction:\*\*\s*(LONG|SHORT|IGNORE)', 
                           r'Direction:\s*(LONG|SHORT|IGNORE)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    direction = match.group(1).upper()
                    print(f"🎯 {model} direction: {direction}")
                    break
            
            confidence = "LOW"
            for pattern in [r'\*\*Confidence:\*\*\s*(LOW|MEDIUM|HIGH)',
                           r'Confidence:\s*(LOW|MEDIUM|HIGH)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    confidence = match.group(1).upper()
                    print(f"📊 {model} confidence: {confidence}")
                    break
            
            entry = self._extract_price_level(response, 'Entry')
            stop = self._extract_price_level(response, 'Stop')
            tp1 = self._extract_price_level(response, 'TP1')
            tp2 = self._extract_price_level(response, 'TP2')
            single_option = self._extract_text_field(response, 'Single Option')
            vertical_spread = self._extract_text_field(response, 'Vertical Spread')
            
            print(f"💰 {model} levels - Entry: {entry}, Stop: {stop}, TP1: {tp1}, TP2: {tp2}")
    
            reasoning = "No reasoning provided"
            notes_match = re.search(r'### Notes\s*(.+)', response, re.DOTALL)
            if notes_match:
                reasoning = notes_match.group(1).strip()
            else:
                separator_match = re.search(r'---\s*\n\s*(.+)', response, re.DOTALL)
                if separator_match:
                    reasoning = separator_match.group(1).strip()
            
            reasoning = re.sub(r'\s+', ' ', reasoning).strip()
            if len(reasoning) > 400:
                reasoning = reasoning[:397] + "..."
                
            print(f"💭 {model} reasoning extracted: {len(reasoning)} chars")
                
            return {
                "model": model,
                "direction": direction,
                "confidence": confidence,
                "entry": entry,
                "stop": stop,
                "tp1": tp1,
                "tp2": tp2,
                "single_option": single_option,
                "vertical_spread": vertical_spread,
                "reasoning": reasoning,
                "raw_response": response,
                "error": False
            }
        except Exception as e:
            print(f"❌ {model} parse error: {e}")
            return {
                "model": model,
                "direction": "IGNORE",
                "confidence": "LOW", 
                "entry": None,
                "stop": None,
                "tp1": None,
                "tp2": None,
                "single_option": "None",
                "vertical_spread": "None",
                "reasoning": f"Parse error: {str(e)}",
                "raw_response": response,
                "error": True
            }

    def _extract_price_level(self, response: str, field: str):
        """Extract price level from response text"""
        try:
            pattern = rf'\*\*{field}:\*\*\s*\$?([0-9]+\.?[0-9]*)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                value = match.group(1)
                if value.lower() not in ['n/a', 'none', 'null']:
                    return float(value)
            
            pattern2 = rf'{field}:\s*\$?([0-9]+\.?[0-9]*)'
            match2 = re.search(pattern2, response, re.IGNORECASE)
            if match2:
                value = match2.group(1)
                if value.lower() not in ['n/a', 'none', 'null']:
                    return float(value)
                
            return None
        except (ValueError, TypeError):
            return None

    def _extract_text_field(self, response: str, field: str) -> str:
        """Extract text field from response"""
        try:
            pattern = rf'\*\*{field}:\*\*\s*(.+)'
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value.lower() not in ['n/a', 'none', 'null']:
                    return value
            
            pattern2 = rf'{field}:\s*(.+)'
            match2 = re.search(pattern2, response, re.IGNORECASE)
            if match2:
                value = match2.group(1).strip()
                if value.lower() not in ['n/a', 'none', 'null']:
                    return value
                
            return "None"
        except:
            return "None"

    def _analyze_consensus(self, results: List[Dict], alert_data: Dict) -> Dict:
        """Analyze multiple model decisions and return consensus"""
        def round_to_2_decimals(value):
            return round(value, 2) if value is not None else None
        
        try:
            print("\n" + "="*50)
            print("🤖 ENSEMBLE CONSENSUS ANALYSIS")
            print("="*50)
            
            print(f"📊 Raw results received: {len(results)}")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Model {i} raised exception: {result}")
                elif isinstance(result, dict):
                    status = "✅" if not result.get('error', False) else "⚠️"
                    print(f"{status} {result.get('model', 'Unknown')}: {result.get('direction', 'ERROR')} (Confidence: {result.get('confidence', 'UNKNOWN')})")
                else:
                    print(f"⚠️ Model {i} returned unexpected type: {type(result)}")
            
            valid_results = [r for r in results if isinstance(r, dict) and not r.get('error', False)]
            print(f"\n🎯 Valid results: {len(valid_results)}/3 models")
            
            if not valid_results:
                print("❌ CRITICAL: All models failed!")
                return {
                    "direction": "IGNORE", 
                    "confidence": "LOW", 
                    "reasoning": "All models failed or had errors",
                    "model_details": [],
                    "consensus_breakdown": {},
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
            
            print("\n📈 Model Breakdown:")
            for result in valid_results:
                direction = result["direction"]
                confidence = result["confidence"]
                weight = self.models[result["model"]]["weight"]
                
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
                
                print(f"   - {result['model']}: {direction} (Confidence: {confidence}, Weight: {weight})")
            
            consensus_direction = max(direction_counts.items(), key=lambda x: x[1])[0]
            avg_confidence_score = total_weighted_confidence / total_weights if total_weights > 0 else 0
            
            if avg_confidence_score >= 2.5:
                consensus_confidence = "HIGH"
            elif avg_confidence_score >= 1.5:
                consensus_confidence = "MEDIUM" 
            else:
                consensus_confidence = "LOW"
            
            avg_entry = round_to_2_decimals(sum(entry_levels) / len(entry_levels)) if entry_levels else None
            avg_stop = round_to_2_decimals(sum(stop_levels) / len(stop_levels)) if stop_levels else None
            avg_tp1 = round_to_2_decimals(sum(tp1_levels) / len(tp1_levels)) if tp1_levels else None
            avg_tp2 = round_to_2_decimals(sum(tp2_levels) / len(tp2_levels)) if tp2_levels else None
            rsi = round_to_2_decimals(alert_data.get('rsi')) if alert_data.get('rsi') else None
            
            print(f"💰 Average levels - Entry: {avg_entry}, Stop: {avg_stop}, TP1: {avg_tp1}, TP2: {avg_tp2}")
            print(f"📊 RSI: {rsi}")
            
            reasoning = f"ENSEMBLE CONSENSUS: {len(valid_results)}/3 models analyzed. Direction: {consensus_direction} ("
            reasoning += ", ".join([f"{dir}: {count}" for dir, count in direction_counts.items()])
            reasoning += f"). Confidence: {consensus_confidence}"
            
            print(f"\n🏁 FINAL CONSENSUS: {consensus_direction} (Confidence: {consensus_confidence})")
            print(f"   Breakdown: {direction_counts}")
            
            final_decision = {
                "direction": consensus_direction,
                "confidence": consensus_confidence,
                "entry": avg_entry,
                "stop": avg_stop,
                "tp1": avg_tp1,
                "tp2": avg_tp2,
                "rsi": rsi,
                "single_option": "None",
                "vertical_spread": "None",
                "reasoning": reasoning,
                "model_details": valid_results,
                "consensus_breakdown": direction_counts,
                "success": True
            }
            
            return final_decision
            
        except Exception as e:
            print(f"❌ Error in _analyze_consensus: {e}")
            return {
                "direction": "IGNORE",
                "confidence": "LOW", 
                "reasoning": f"Consensus analysis error: {str(e)}",
                "model_details": [],
                "consensus_breakdown": {},
                "success": False
            }
