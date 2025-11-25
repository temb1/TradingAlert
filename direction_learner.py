# Version: 1
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import json

class DirectionPredictionLearner:
    """
    Focuses purely on predicting stock direction accurately
    Integrates with your existing agent structure
    """
    
    def __init__(self):
        # Track direction accuracy for each signal
        self.signal_accuracy = {
            # 3-1 Inside Bar
            "inside_bar_3_1": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            },
            # A/M/D Phases
            "accumulation": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            },
            "manipulation": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            },
            "distribution": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            },
            # Trends
            "bullish_trend": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            },
            "bearish_trend": {
                "bullish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0},
                "bearish_predictions": {"correct": 0, "total": 0, "accuracy": 0.0}
            }
        }
        
        # Track combination performance
        self.combination_accuracy = {}
        self.prediction_history = []
        
    def extract_signals_from_agent(self, agent_recommendation: Dict) -> Dict:
        """
        Extract your 3 key signals from agent recommendations
        This matches how your agent already thinks
        """
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False, 
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        # Extract from agent's reasoning (adjust based on your actual agent output)
        reasoning = agent_recommendation.get('reasoning', '').lower()
        strategy = agent_recommendation.get('strategy', '').lower()
        
        # Detect 3-1 Inside Bar
        if any(term in reasoning for term in ['3-1', 'three one', 'inside bar', 'consolidation']):
            signals["inside_bar_3_1"] = True
            
        # Detect A/M/D Phases
        if 'accumulation' in reasoning:
            signals["accumulation"] = True
        if 'manipulation' in reasoning:
            signals["manipulation"] = True  
        if 'distribution' in reasoning:
            signals["distribution"] = True
            
        # Detect Trends
        if any(term in reasoning for term in ['bullish', 'uptrend', 'rising']):
            signals["bullish_trend"] = True
        if any(term in reasoning for term in ['bearish', 'downtrend', 'falling']):
            signals["bearish_trend"] = True
            
        return signals
    
    def get_predicted_direction(self, agent_recommendation: Dict) -> str:
        """
        Extract direction from agent's recommendation
        Matches your existing agent output
        """
        direction = agent_recommendation.get('direction', '').upper()
        if direction in ['LONG', 'BULLISH', 'CALL']:
            return 'BULLISH'
        elif direction in ['SHORT', 'BEARISH', 'PUT']:
            return 'BEARISH'
        else:
            # Fallback: infer from strategy
            strategy = agent_recommendation.get('strategy', '').lower()
            if 'call' in strategy:
                return 'BULLISH'
            elif 'put' in strategy:
                return 'BEARISH'
            return 'UNKNOWN'
    
    async def record_prediction_outcome(self, agent_recommendation: Dict, actual_price_data: Dict):
        """
        Record whether the agent's direction prediction was correct
        Integrates with your existing monitoring system
        """
        try:
            symbol = agent_recommendation.get('symbol', 'UNKNOWN')
            predicted_direction = self.get_predicted_direction(agent_recommendation)
            signals = self.extract_signals_from_agent(agent_recommendation)
            
            # Calculate actual direction (simplified - you can enhance this)
            actual_direction = self._calculate_actual_direction(agent_recommendation, actual_price_data)
            correct = predicted_direction == actual_direction
            
            # Update signal accuracy
            self._update_signal_accuracy(signals, predicted_direction, correct)
            
            # Update combination accuracy
            self._update_combination_accuracy(signals, predicted_direction, correct)
            
            # Store prediction history
            self.prediction_history.append({
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'predicted_direction': predicted_direction,
                'actual_direction': actual_direction,
                'correct': correct,
                'signals': signals,
                'agent_confidence': agent_recommendation.get('confidence', 0.5)
            })
            
            print(f"🎯 Direction Prediction: {symbol} | Predicted: {predicted_direction} | "
                  f"Actual: {actual_direction} | Correct: {correct}")
                  
        except Exception as e:
            print(f"❌ Error recording prediction outcome: {e}")
    
    def _calculate_actual_direction(self, recommendation: Dict, price_data: Dict) -> str:
        """Calculate actual price movement direction"""
        entry_price = recommendation.get('entry_price') or recommendation.get('current_price')
        if not entry_price or 'current_price' not in price_data:
            return 'UNKNOWN'
            
        current_price = price_data['current_price']
        price_change = (current_price - entry_price) / entry_price
        
        # Consider it bullish if up > 0.5%, bearish if down > 0.5%
        if price_change > 0.005:
            return 'BULLISH'
        elif price_change < -0.005:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _update_signal_accuracy(self, signals: Dict, predicted_direction: str, correct: bool):
        """Update accuracy for individual signals"""
        for signal_name, is_present in signals.items():
            if is_present and signal_name in self.signal_accuracy:
                direction_key = f"{predicted_direction.lower()}_predictions"
                
                if direction_key in self.signal_accuracy[signal_name]:
                    stats = self.signal_accuracy[signal_name][direction_key]
                    stats['total'] += 1
                    if correct:
                        stats['correct'] += 1
                    stats['accuracy'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0
    
    def _update_combination_accuracy(self, signals: Dict, predicted_direction: str, correct: bool):
        """Update accuracy for signal combinations"""
        active_signals = [sig for sig, present in signals.items() if present]
        if len(active_signals) < 2:
            return
            
        combination_key = f"{predicted_direction}_{'_'.join(sorted(active_signals))}"
        
        if combination_key not in self.combination_accuracy:
            self.combination_accuracy[combination_key] = {
                'correct': 0, 'total': 0, 'accuracy': 0.0,
                'signals': active_signals, 'direction': predicted_direction
            }
        
        stats = self.combination_accuracy[combination_key]
        stats['total'] += 1
        if correct:
            stats['correct'] += 1
        stats['accuracy'] = stats['correct'] / stats['total']
    
    def get_direction_confidence(self, signals: Dict, proposed_direction: str) -> float:
        """
        Get confidence score for a direction prediction based on historical accuracy
        Your agent can use this to adjust its confidence
        """
        confidence_scores = []
        
        for signal_name, is_present in signals.items():
            if is_present and signal_name in self.signal_accuracy:
                direction_key = f"{proposed_direction.lower()}_predictions"
                if direction_key in self.signal_accuracy[signal_name]:
                    accuracy = self.signal_accuracy[signal_name][direction_key]['accuracy']
                    if accuracy > 0:  # Only consider signals with historical data
                        confidence_scores.append(accuracy)
        
        # Also check combinations
        active_signals = [sig for sig, present in signals.items() if present]
        if len(active_signals) >= 2:
            combination_key = f"{proposed_direction}_{'_'.join(sorted(active_signals))}"
            if combination_key in self.combination_accuracy:
                combo_accuracy = self.combination_accuracy[combination_key]['accuracy']
                confidence_scores.append(combo_accuracy)
        
        # Return average confidence, or 0.5 (neutral) if no data
        return sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive direction prediction performance report"""
        report = {
            'signal_accuracy': {},
            'best_combinations': [],
            'overall_accuracy': 0.0,
            'total_predictions': len(self.prediction_history),
            'report_time': datetime.now().isoformat()
        }
        
        # Calculate overall accuracy
        correct_predictions = sum(1 for pred in self.prediction_history if pred['correct'])
        report['overall_accuracy'] = correct_predictions / len(self.prediction_history) if self.prediction_history else 0.0
        
        # Get best performing combinations
        combo_list = [{'key': k, **v} for k, v in self.combination_accuracy.items() if v['total'] >= 3]
        combo_list.sort(key=lambda x: x['accuracy'], reverse=True)
        report['best_combinations'] = combo_list[:5]  # Top 5
        
        return report

# Integration with your existing system
class EnhancedAutomatedLearningSystem:
    """
    Wrapper that integrates direction learning with your existing system
    """
    
    def __init__(self, supabase_client=None):
        self.direction_learner = DirectionPredictionLearner()
        # Your existing initialization...
        
    async def monitor_with_direction_focus(self, agent_recommendation: Dict):
        """Enhanced monitoring that focuses on direction prediction"""
        # Your existing monitoring logic...
        
        # Add direction learning
        await self.direction_learner.record_prediction_outcome(
            agent_recommendation, 
            actual_price_data=self.get_current_price_data(agent_recommendation['symbol'])
        )
