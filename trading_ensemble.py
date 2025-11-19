import asyncio
import os
from typing import List, Dict
import re
from openai import OpenAI
from anthropic import Anthropic

class TradingEnsemble:
    def __init__(self):
        # Initialize API clients
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Model configurations with weights
        self.models = {
            "gpt-4o": {"weight": 1.0, "client": "openai"},
            "gpt-4-turbo": {"weight": 0.9, "client": "openai"}, 
            "claude-3-5-sonnet-20241022": {"weight": 0.95, "client": "anthropic"}
        }
        
        self.system_prompt = """You are a professional trading analyst. Analyze the trading setup and provide:
1. Direction: LONG, SHORT, or IGNORE
2. Confidence: LOW, MEDIUM, or HIGH  
3. Brief reasoning

Format your response exactly as:
DIRECTION: [LONG/SHORT/IGNORE]
CONFIDENCE: [LOW/MEDIUM/HIGH]
REASONING: [Your analysis here]"""

    async def get_ensemble_decision(self, alert_data):
        """Get decisions from all 3 models and return consensus"""
        context = self._build_context(alert_data)
        
        # Get decisions from all models in parallel
        tasks = []
        for model_name in self.models:
            task = self._get_single_model_decision(model_name, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze consensus
        final_decision = self._analyze_consensus(results)
        return final_decision

    async def _get_single_model_decision(self, model: str, context: str):
        """Get decision from a single model"""
        try:
            if self.models[model]["client"] == "openai":
                return await self._get_openai_decision(model, context)
            else:
                return await self._get_anthropic_decision(model, context)
        except Exception as e:
            return {
                "model": model,
                "direction": "IGNORE", 
                "confidence": "LOW",
                "reasoning": f"Error: {str(e)}",
                "error": True
            }

    async def _get_openai_decision(self, model: str, context: str):
        """Get decision from OpenAI model"""
        resp = self.openai_client.chat.completions.create(
            model=model,
            max_tokens=500,
            temperature=0.1,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context}
            ]
        )
        return self._parse_decision(resp.choices[0].message.content, model)

    async def _get_anthropic_decision(self, model: str, context: str):
        """Get decision from Anthropic model"""
        message = self.anthropic_client.messages.create(
            model=model,
            max_tokens=500,
            temperature=0.1,
            system=self.system_prompt,
            messages=[{"role": "user", "content": context}]
        )
        return self._parse_decision(message.content[0].text, model)

    def _build_context(self, alert_data):
        """Build context from alert data"""
        return f"""
Trading Alert Data:
- Ticker: {alert_data.get('ticker', 'N/A')}
- Strategy: {alert_data.get('strategy', 'N/A')} 
- Current Price: {alert_data.get('price', 'N/A')}
- Setup: {alert_data.get('setup', 'N/A')}
- Additional Data: {alert_data.get('additional_data', {})}

Please analyze this trading setup and provide your decision.
"""

    def _parse_decision(self, response: str, model: str) -> Dict:
    """Parse model response into structured decision with better error handling"""
    try:
        # Clean the response
        response = response.strip()
        
        # Extract direction with multiple patterns
        direction = "IGNORE"
        for pattern in [r'DIRECTION:\s*(LONG|SHORT|IGNORE)', r'Decision:\s*(LONG|SHORT|IGNORE)']:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                direction = match.group(1).upper()
                break
        
        # Extract confidence with multiple patterns  
        confidence = "LOW"
        for pattern in [r'CONFIDENCE:\s*(LOW|MEDIUM|HIGH)', r'Confidence:\s*(LOW|MEDIUM|HIGH)']:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                confidence = match.group(1).upper()
                break
        
        # Extract reasoning - take everything after REASONING: or use the whole response
        reasoning = "No reasoning provided"
        reasoning_match = re.search(r'REASONING:\s*(.+)', response, re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            # If no REASONING tag, take everything except the first 2 lines
            lines = response.split('\n')
            if len(lines) > 2:
                # Skip direction and confidence lines
                reasoning_lines = []
                for line in lines:
                    if not re.match(r'(DIRECTION|CONFIDENCE|Decision|Confidence):', line, re.IGNORECASE):
                        reasoning_lines.append(line)
                reasoning = ' '.join(reasoning_lines).strip()
        
        # Clean up reasoning - remove extra whitespace, limit length
        reasoning = re.sub(r'\s+', ' ', reasoning).strip()
        if len(reasoning) > 500:  # Increased limit for full analysis
            reasoning = reasoning[:497] + "..."
            
        return {
            "model": model,
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "raw_response": response,
            "error": False
        }
    except Exception as e:
        return {
            "model": model,
            "direction": "IGNORE",
            "confidence": "LOW", 
            "reasoning": f"Parse error: {str(e)}",
            "raw_response": response,
            "error": True
        }

    def _analyze_consensus(self, results: List[Dict]) -> Dict:
        """Analyze multiple model decisions and return consensus"""
        valid_results = [r for r in results if isinstance(r, dict) and not r.get('error', False)]
        
        if not valid_results:
            return {
                "direction": "IGNORE", 
                "confidence": "LOW", 
                "reasoning": "All models failed or had errors",
                "model_details": [],
                "consensus_breakdown": {}
            }
        
        # Count directions and calculate weighted scores
        direction_counts = {}
        confidence_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        total_weighted_confidence = 0
        total_weights = 0
        
        for result in valid_results:
            direction = result["direction"]
            confidence = result["confidence"]
            weight = self.models[result["model"]]["weight"]
            
            direction_counts[direction] = direction_counts.get(direction, 0) + 1
            total_weighted_confidence += confidence_scores.get(confidence, 0) * weight
            total_weights += weight
        
        # Determine consensus direction (majority rule)
        consensus_direction = max(direction_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate weighted average confidence
        avg_confidence_score = total_weighted_confidence / total_weights if total_weights > 0 else 0
        
        if avg_confidence_score >= 2.5:
            consensus_confidence = "HIGH"
        elif avg_confidence_score >= 1.5:
            consensus_confidence = "MEDIUM" 
        else:
            consensus_confidence = "LOW"
        
        # Build consensus reasoning
        reasoning = f"ENSEMBLE CONSENSUS: {len(valid_results)}/3 models analyzed. "
        reasoning += f"Direction: {consensus_direction} ("
        reasoning += ", ".join([f"{dir}: {count}" for dir, count in direction_counts.items()])
        reasoning += f"). Confidence: {consensus_confidence}"
        
        return {
            "direction": consensus_direction,
            "confidence": consensus_confidence,
            "reasoning": reasoning,
            "model_details": valid_results,
            "consensus_breakdown": direction_counts
        }
