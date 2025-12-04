# Version 1
"""
ENFORCES expert trading knowledge before AI can respond.
Catches rookie mistakes and forces corrections.
"""

import re
import logging
from typing import Dict, List, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class ExpertEnforcer:
    """Ensures AI doesn't make rookie trading mistakes"""
    
    def __init__(self):
        self.est = pytz.timezone('US/Eastern')
        
        # CRITICAL: Common rookie mistakes to catch
        self.rookie_mistakes = {
            "rsi_neutral_wrong": [
                (r"RSI.*neutral", "RSI below 50 is BEARISH, above 50 is BULLISH"),
                (r"RSI.*is neutral", "RSI 41.71 = BEARISH momentum (below 50)"),
            ],
            "volume_ignored": [
                (r"(?!.*volume.*significant|.*high volume|.*conviction).*volume.*", 
                 "Volume 2.8x = HIGH CONVICTION - MUST mention significance"),
            ],
            "no_market_context": [
                (r"(?!.*market.*context|.*SPY|.*QQQ|.*sector|.*VIX).*", 
                 "MUST include market context (SPY/QQQ trend, sector performance)"),
            ],
            "no_time_of_day": [
                (r"(?!.*time.*day|.*session|.*morning|.*afternoon|.*power hour).*",
                 "MUST consider time of day implications for day trading"),
            ],
            "vague_levels": [
                (r"Entry:.*\nStop:.*\nTP1:.*\nTP2:.*", 
                 "MUST calculate SPECIFIC price levels for Entry, Stop, TP1, TP2"),
            ]
        }
    
    def enforce_expert_analysis(self, ai_response: str, alert_data: Dict) -> Tuple[str, List[str]]:
        """
        Enforce expert trading knowledge on AI response
        Returns: (corrected_response, warnings)
        """
        warnings = []
        corrected = ai_response
        
        # 1. CHECK RSI INTERPRETATION
        rsi = alert_data.get('rsi')
        if rsi:
            corrected, rsi_warnings = self._enforce_rsi_truth(corrected, rsi)
            warnings.extend(rsi_warnings)
        
        # 2. CHECK VOLUME SIGNIFICANCE
        volume_ratio = alert_data.get('volume_ratio')
        if volume_ratio:
            corrected, volume_warnings = self._enforce_volume_significance(corrected, volume_ratio)
            warnings.extend(volume_warnings)
        
        # 3. ENFORCE MARKET CONTEXT
        corrected, context_warnings = self._enforce_market_context(corrected)
        warnings.extend(context_warnings)
        
        # 4. ENFORCE TIME OF DAY
        corrected, time_warnings = self._enforce_time_of_day(corrected)
        warnings.extend(time_warnings)
        
        # 5. ENFORCE SPECIFIC LEVELS
        corrected, level_warnings = self._enforce_specific_levels(corrected, alert_data)
        warnings.extend(level_warnings)
        
        return corrected, warnings
    
    def _enforce_rsi_truth(self, response: str, rsi: float) -> Tuple[str, List[str]]:
        """Force correct RSI interpretation"""
        warnings = []
        
        # RSI TRUTH TABLE
        if rsi < 30:
            expected = "OVERSOLD"
        elif rsi < 50:
            expected = "BEARISH momentum"
        elif rsi < 70:
            expected = "BULLISH momentum"
        else:
            expected = "OVERBOUGHT"
        
        # Check if AI got it wrong
        if rsi < 50 and "bearish" not in response.lower():
            warnings.append(f"❌ RSI {rsi} is BEARISH (<50), but AI didn't mention bearish")
            # Force correction
            if "RSI" in response:
                response = re.sub(
                    r"(RSI.*?:.*?)(neutral|not clear|unclear)",
                    r"\1" + expected,
                    response,
                    flags=re.IGNORECASE
                )
        
        elif rsi > 50 and "bullish" not in response.lower():
            warnings.append(f"❌ RSI {rsi} is BULLISH (>50), but AI didn't mention bullish")
        
        return response, warnings
    
    def _enforce_volume_significance(self, response: str, volume_ratio: float) -> Tuple[str, List[str]]:
        """Force acknowledgment of volume significance"""
        warnings = []
        
        # VOLUME SIGNIFICANCE TRUTH
        if volume_ratio > 2.0:
            significance = "HIGH CONVICTION"
        elif volume_ratio > 1.2:
            significance = "MODERATE CONVICTION"
        elif volume_ratio < 0.8:
            significance = "LOW CONVICTION"
        else:
            significance = "NORMAL"
        
        # Check if AI ignored volume
        volume_mentioned = any(word in response.lower() for word in ['volume', 'conviction', 'participation'])
        
        if not volume_mentioned and volume_ratio > 1.5:
            warnings.append(f"⚠️ Volume {volume_ratio}x = {significance}, but AI didn't mention it")
            # Add volume note if there's an analysis section
            if "Analysis" in response or "Notes" in response:
                volume_note = f"\n📊 VOLUME: {volume_ratio}x average = {significance} move"
                response = self._insert_after_section(response, volume_note, ["Analysis", "Notes"])
        
        return response, warnings
    
    def _enforce_market_context(self, response: str) -> Tuple[str, List[str]]:
        """Force inclusion of market context"""
        warnings = []
        
        market_context_indicators = ['SPY', 'QQQ', 'sector', 'VIX', 'market', 'breadth']
        has_context = any(indicator in response for indicator in market_context_indicators)
        
        if not has_context:
            warnings.append("⚠️ Missing market context (SPY/QQQ trend, sector performance)")
            
            # Add market context section if missing
            current_time = datetime.now(self.est).strftime("%H:%M ET")
            market_context = f"""
📈 MARKET CONTEXT (REQUIRED):
- Time: {current_time} ({self._get_trading_session(current_time)})
- SPY: [Check trend - bullish/bearish/sideways]
- QQQ: [Relative performance to SPY]
- VIX: [Level and trend - fear/greed gauge]
- Sector Rotation: [Tech/Financials/Healthcare performance]
"""
            response = self._insert_after_section(response, market_context, ["TICKER:", "SYMBOL:", "\n"])
        
        return response, warnings
    
    def _enforce_time_of_day(self, response: str) -> Tuple[str, List[str]]:
        """Force time of day consideration"""
        warnings = []
        
        time_indicators = ['morning', 'afternoon', 'power hour', 'session', 'open', 'close', 'time.*day']
        has_time = any(re.search(pattern, response, re.IGNORECASE) for pattern in time_indicators)
        
        if not has_time:
            warnings.append("⚠️ Missing time of day analysis (crucial for day trading)")
            
            current_hour = datetime.now(self.est).hour
            session = self._get_trading_session_by_hour(current_hour)
            time_analysis = f"""
⏰ TIME OF DAY ANALYSIS:
- Current Session: {session['name']}
- Implications: {session['implications']}
- Common Strategies: {session['strategies']}
"""
            response = self._insert_after_section(response, time_analysis, ["MARKET CONTEXT", "TICKER:", "\n"])
        
        return response, warnings
    
    def _enforce_specific_levels(self, response: str, alert_data: Dict) -> Tuple[str, List[str]]:
        """Force specific price level calculations"""
        warnings = []
        
        # Check if specific levels are provided
        has_entry = "Entry:" in response and not "Entry: ["
        has_stop = "Stop:" in response and not "Stop: ["
        has_tp1 = "TP1:" in response and not "TP1: ["
        
        if not (has_entry and has_stop and has_tp1):
            warnings.append("❌ Missing specific price level calculations")
            
            # Calculate example levels if we have IB data
            close = alert_data.get('close')
            ib_high = alert_data.get('ib_high')
            ib_low = alert_data.get('ib_low')
            
            if close and ib_high and ib_low:
                levels = self._calculate_breakout_levels(close, ib_high, ib_low)
                
                if "**Direction:**" in response and "LONG" in response:
                    level_template = f"""
🎯 PRICE LEVELS CALCULATED:
Entry: {levels['long_entry']}
Stop: {levels['long_stop']}
TP1: {levels['long_tp1']}
TP2: {levels['long_tp2']}
Risk: ${levels['long_risk']}
R:R: {levels['long_rr']}
"""
                    response = self._insert_after_section(response, level_template, ["**Direction:**"])
        
        return response, warnings
    
    def _calculate_breakout_levels(self, close: float, ib_high: float, ib_low: float) -> Dict:
        """Calculate breakout levels based on price buffer"""
        buffer = 0.25 if close > 200 else 0.15 if close > 50 else 0.10
        
        return {
            'long_entry': round(ib_high + buffer, 2),
            'long_stop': round(ib_low - buffer, 2),
            'long_tp1': round(ib_high + buffer + (ib_high - ib_low) * 1.5, 2),
            'long_tp2': round(ib_high + buffer + (ib_high - ib_low) * 2.0, 2),
            'long_risk': round((ib_high + buffer - (ib_low - buffer)) * 100, 2),
            'long_rr': "1:1.5"
        }
    
    def _get_trading_session(self, time_str: str) -> str:
        """Get current trading session"""
        try:
            hour = int(time_str.split(':')[0])
            return self._get_trading_session_by_hour(hour)['name']
        except:
            return "Unknown session"
    
    def _get_trading_session_by_hour(self, hour: int) -> Dict:
        """Get trading session details by hour (EST)"""
        sessions = {
            "pre_market": {"name": "Pre-Market", "hour_range": (4, 9), 
                          "implications": "Gaps, news reaction, false moves common",
                          "strategies": "Fade extreme gaps, wait for open"},
            "market_open": {"name": "Market Open", "hour_range": (9, 10),
                           "implications": "High volatility, gap fills, opening range established",
                           "strategies": "ORB (Opening Range Breakout), gap fills"},
            "morning_trend": {"name": "Morning Trend", "hour_range": (10, 11),
                             "implications": "True trend direction emerges",
                             "strategies": "Trend following, add to positions"},
            "midday": {"name": "Midday", "hour_range": (11, 14),
                      "implications": "Consolidation, lunchtime lull, low volume",
                      "strategies": "Range trading, small position sizing"},
            "afternoon": {"name": "Afternoon", "hour_range": (14, 15),
                         "implications": "Direction re-established, institutional flows",
                         "strategies": "Momentum continuation, VWAP strategies"},
            "power_hour": {"name": "Power Hour", "hour_range": (15, 16),
                          "implications": "Highest conviction moves, trend continuation/breaks",
                          "strategies": "Trend riding, trailing stops, prepare for close"}
        }
        
        for session, info in sessions.items():
            start, end = info['hour_range']
            if start <= hour < end:
                return info
        
        return {"name": "After-Hours", "implications": "News reaction, low liquidity", 
                "strategies": "Avoid or very small size"}
    
    def _insert_after_section(self, text: str, insert_text: str, sections: List[str]) -> str:
        """Insert text after a specific section"""
        for section in sections:
            if section in text:
                # Find the position after the section
                idx = text.find(section)
                if idx != -1:
                    # Find the next newline after this section
                    newline_idx = text.find('\n', idx)
                    if newline_idx != -1:
                        return text[:newline_idx] + insert_text + text[newline_idx:]
        
        # If section not found, insert at beginning
        return insert_text + "\n\n" + text
    
    def validate_ai_response(self, ai_response: str, alert_data: Dict) -> Dict:
        """
        Comprehensive validation of AI response
        Returns validation report
        """
        # First enforce expert rules
        corrected_response, warnings = self.enforce_expert_analysis(ai_response, alert_data)
        
        # Score the response
        score = self._calculate_expert_score(ai_response, alert_data)
        
        return {
            'original_response': ai_response,
            'corrected_response': corrected_response,
            'warnings': warnings,
            'expert_score': score,
            'needs_correction': len(warnings) > 0,
            'passed_validation': score > 0.7  # 70% threshold
        }
    
    def _calculate_expert_score(self, response: str, alert_data: Dict) -> float:
        """Calculate how expert the response is (0-1)"""
        score = 0
        max_score = 0
        
        # 1. RSI interpretation (20 points)
        max_score += 20
        rsi = alert_data.get('rsi')
        if rsi:
            if rsi < 50 and "bearish" in response.lower():
                score += 20
            elif rsi > 50 and "bullish" in response.lower():
                score += 20
        
        # 2. Volume acknowledgment (20 points)
        max_score += 20
        volume_ratio = alert_data.get('volume_ratio')
        if volume_ratio:
            volume_mentioned = any(word in response.lower() for word in ['volume', 'conviction'])
            if volume_mentioned:
                score += 20
        
        # 3. Market context (20 points)
        max_score += 20
        has_market_context = any(indicator in response for indicator in ['SPY', 'QQQ', 'sector', 'VIX'])
        if has_market_context:
            score += 20
        
        # 4. Time of day (20 points)
        max_score += 20
        has_time = any(word in response.lower() for word in ['morning', 'afternoon', 'session', 'time'])
        if has_time:
            score += 20
        
        # 5. Specific levels (20 points)
        max_score += 20
        has_specific_levels = all(marker in response for marker in ['Entry:', 'Stop:', 'TP1:'])
        if has_specific_levels:
            score += 20
        
        return score / max_score if max_score > 0 else 0
