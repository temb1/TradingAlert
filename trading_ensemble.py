import asyncio
import os
import time
from typing import List, Dict
import re
import json
from openai import OpenAI
from anthropic import Anthropic

class TradingEnsemble:
    def __init__(self):
        # Initialize API clients with validation
        self.openai_client = None
        self.anthropic_client = None
        
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key:
                print("❌ OPENAI_API_KEY environment variable is not set")
            else:
                self.openai_client = OpenAI(api_key=openai_key)
                print("✅ OpenAI client initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI client: {e}")
            
        try:
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key:
                print("❌ ANTHROPIC_API_KEY environment variable is not set")
            else:
                self.anthropic_client = Anthropic(api_key=anthropic_key)
                print("✅ Anthropic client initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Anthropic client: {e}")
        
        # Model configurations with weights
        self.models = {
            "gpt-4o": {"weight": 1.0, "client": "openai"},
            "gpt-4-turbo": {"weight": 0.9, "client": "openai"}, 
            "claude-3-5-sonnet-20241022": {"weight": 0.95, "client": "anthropic"}
        }
        
        # ✅ USE YOUR EXISTING SYSTEM PROMPT FROM CONFIG
        try:
            from config import SYSTEM_PROMPT
            self.system_prompt = SYSTEM_PROMPT
            print("✅ System prompt loaded successfully")
        except ImportError:
            print("❌ Failed to import SYSTEM_PROMPT from config")
            self.system_prompt = "You are a trading analyst. Analyze the trading alert and provide your decision."
        except Exception as e:
            print(f"❌ Error loading system prompt: {e}")
            self.system_prompt = "You are a trading analyst. Analyze the trading alert and provide your decision."

    async def get_ensemble_decision(self, alert_data):
        """Get decisions from all 3 models and return consensus"""
        print("🚀 Starting ensemble decision process with 3 models...")
        
        context = self._build_context(alert_data)
        
        # Get decisions from all models in parallel
        tasks = []
        for model_name in self.models:
            task = self._get_single_model_decision(model_name, context)
            tasks.append(task)
        
        print("🔄 Waiting for all 3 models to respond...")
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        print(f"⏱️ All models completed in {end_time - start_time:.2f} seconds")
        
        # Analyze consensus with detailed debugging
        final_decision = self._analyze_consensus(results)
        return final_decision

    async def _get_single_model_decision(self, model: str, context: str):
        """Get decision from a single model"""
        print(f"🔍 Querying {model}...")
        
        try:
            # Check if client is available
            if self.models[model]["client"] == "openai":
                if not self.openai_client:
                    raise Exception("OpenAI client not initialized")
                return await self._get_openai_decision(model, context)
            else:
                if not self.anthropic_client:
                    raise Exception("Anthropic client not initialized")
                return await self._get_anthropic_decision(model, context)
                
        except Exception as e:
            print(f"❌ {model} error: {str(e)}")
            return {
                "model": model,
                "direction": "IGNORE", 
                "confidence": "LOW",
                "reasoning": f"Error: {str(e)}",
                "error": True,
                "raw_response": ""
            }

    async def _get_openai_decision(self, model: str, context: str):
        """Get decision from OpenAI model"""
        try:
            resp = self.openai_client.chat.completions.create(
                model=model,
                max_tokens=1000,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context}
                ]
            )
            response_text = resp.choices[0].message.content
            print(f"✅ {model} responded successfully")
            return self._parse_decision(response_text, model)
        except Exception as e:
            print(f"❌ {model} API error: {e}")
            raise

    async def _get_anthropic_decision(self, model: str, context: str):
        """Get decision from Anthropic model"""
        try:
            message = self.anthropic_client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=0.1,
                system=self.system_prompt,
                messages=[{"role": "user", "content": context}]
            )
            response_text = message.content[0].text
            print(f"✅ {model} responded successfully")
            return self._parse_decision(response_text, model)
        except Exception as e:
            print(f"❌ {model} API error: {e}")
            raise

    def _build_context(self, alert_data):
        """Build context from alert data - optimized for your system prompt"""
        # Extract key fields with fallbacks
        ticker = alert_data.get('ticker') or alert_data.get('symbol') or 'UNKNOWN'
        strategy = alert_data.get('strategy') or alert_data.get('pattern') or 'UNKNOWN'
        price = alert_data.get('price') or alert_data.get('close') or alert_data.get('current_price') or 'N/A'
        
        # Additional data that might be useful
        additional_data = alert_data.get('additional_data', {})
        
        # Build context that works with your existing system prompt
        context = f"""
TRADING ALERT RECEIVED:

TICKER: {ticker}
STRATEGY: {strategy} 
CURRENT PRICE: ${price}

ADDITIONAL DATA:
{json.dumps(additional_data, indent=2) if additional_data else 'No additional data'}

Please analyze this trading alert using your established criteria and provide your decision in the required format.
"""
        return context

    def _parse_decision(self, response: str, model: str) -> Dict:
        """Parse model response into structured decision - updated for your format"""
        try:
            # Clean the response
            response = response.strip()
            print(f"📝 {model} raw response length: {len(response)} chars")
            
            # Extract direction with multiple patterns for your format
            direction = "IGNORE"
            for pattern in [r'\*\*Direction:\*\*\s*(LONG|SHORT|IGNORE)', 
                           r'Direction:\s*(LONG|SHORT|IGNORE)',
                           r'DIRECTION:\s*(LONG|SHORT|IGNORE)',
                           r'Decision:\s*(LONG|SHORT|IGNORE)',
                           r'\*\*Decision:\*\*\s*(LONG|SHORT|IGNORE)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    direction = match.group(1).upper()
                    print(f"🎯 {model} direction: {direction}")
                    break
            
            # Extract confidence with multiple patterns for your format
            confidence = "LOW"
            for pattern in [r'\*\*Confidence:\*\*\s*(LOW|MEDIUM|HIGH)',
                           r'Confidence:\s*(LOW|MEDIUM|HIGH)',
                           r'CONFIDENCE:\s*(LOW|MEDIUM|HIGH)']:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    confidence = match.group(1).upper()
                    print(f"📊 {model} confidence: {confidence}")
                    break
            
            # Extract reasoning - look for Notes section or everything after the main format
            reasoning = "No reasoning provided"
            
            # Try to extract from Notes section first (your format)
            notes_match = re.search(r'### Notes\s*(.+)', response, re.DOTALL)
            if notes_match:
                reasoning = notes_match.group(1).strip()
            else:
                # Try to extract from --- separator (your format)
                separator_match = re.search(r'---\s*\n\s*(.+)', response, re.DOTALL)
                if separator_match:
                    reasoning = separator_match.group(1).strip()
                else:
                    # Fallback: take everything after the main decision blocks
                    lines = response.split('\n')
                    reasoning_lines = []
                    capture = False
                    for line in lines:
                        if re.match(r'.*(Notes|Reasoning|Analysis|###):', line, re.IGNORECASE):
                            capture = True
                            continue
                        if capture and line.strip():
                            reasoning_lines.append(line)
                    
                    if reasoning_lines:
                        reasoning = ' '.join(reasoning_lines).strip()
            
            # Clean up reasoning
            reasoning = re.sub(r'\s+', ' ', reasoning).strip()
            if len(reasoning) > 400:
                reasoning = reasoning[:397] + "..."
                
            print(f"💭 {model} reasoning extracted: {len(reasoning)} chars")
                
            return {
                "model": model,
                "direction": direction,
                "confidence": confidence,
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
                "reasoning": f"Parse error: {str(e)}",
                "raw_response": response,
                "error": True
            }

    def _analyze_consensus(self, results: List[Dict]) -> Dict:
        """Analyze multiple model decisions and return consensus"""
        print("\n" + "="*50)
        print("🤖 ENSEMBLE CONSENSUS ANALYSIS")
        print("="*50)
        
        # DEBUG: Check what models actually returned
        print(f"📊 Raw results received: {len(results)}")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Model {i} raised exception: {result}")
            elif isinstance(result, dict):
                status = "✅" if not result.get('error', False) else "⚠️"
                print(f"{status} {result.get('model', 'Unknown')}: {result.get('direction', 'ERROR')} (Confidence: {result.get('confidence', 'UNKNOWN')})")
                if result.get('error', False):
                    print(f"   Error details: {result.get('reasoning', 'No details')}")
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
        
        # Count directions and calculate weighted scores
        direction_counts = {}
        confidence_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        total_weighted_confidence = 0
        total_weights = 0
        
        print("\n📈 Model Breakdown:")
        for result in valid_results:
            direction = result["direction"]
            confidence = result["confidence"]
            weight = self.models[result["model"]]["weight"]
            
            direction_counts[direction] = direction_counts.get(direction, 0) + 1
            total_weighted_confidence += confidence_scores.get(confidence, 0) * weight
            total_weights += weight
            
            print(f"   - {result['model']}: {direction} (Confidence: {confidence}, Weight: {weight})")
        
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
        reasoning = f"ENSEMBLE CONSENSUS: {len(valid_results)}/3 models analyzed. Direction: {consensus_direction} ("
        reasoning += ", ".join([f"{dir}: {count}" for dir, count in direction_counts.items()])
        reasoning += f"). Confidence: {consensus_confidence}"
        
        print(f"\n🏁 FINAL CONSENSUS: {consensus_direction} (Confidence: {consensus_confidence})")
        print(f"   Breakdown: {direction_counts}")
        
        return {
            "direction": consensus_direction,
            "confidence": consensus_confidence,
            "reasoning": reasoning,
            "model_details": valid_results,
            "consensus_breakdown": direction_counts,
            "success": True
        }


# Singleton instance for easy import
ensemble = TradingEnsemble()

async def get_ensemble_decision(alert_data):
    """Convenience function to get ensemble decision"""
    return await ensemble.get_ensemble_decision(alert_data)
