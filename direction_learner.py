# Version: 2
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import json
import os

class DirectionPredictionLearner:
    """
    Focuses purely on predicting stock direction accurately
    Integrates with your existing agent structure
    """
    
    def __init__(self, data_file="direction_learning.json"):
        self.data_file = data_file
        self.load_data()
        
    def load_data(self):
        """Load learning data from file to persist across sessions"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.signal_accuracy = data.get('signal_accuracy', self._get_default_signal_accuracy())
                    self.combination_accuracy = data.get('combination_accuracy', {})
                    self.prediction_history = data.get('prediction_history', [])
            else:
                self.signal_accuracy = self._get_default_signal_accuracy()
                self.combination_accuracy = {}
                self.prediction_history = []
        except Exception as e:
            print(f"❌ Error loading direction learning data: {e}")
            self.signal_accuracy = self._get_default_signal_accuracy()
            self.combination_accuracy = {}
            self.prediction_history = []
    
    def _get_default_signal_accuracy(self):
        """Get default signal accuracy structure"""
        return {
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
    
    def save_data(self):
        """Save learning data to file"""
        try:
            data = {
                'signal_accuracy': self.signal_accuracy,
                'combination_accuracy': self.combination_accuracy,
                'prediction_history': self.prediction_history,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving direction learning data: {e}")
    
    def extract_signals_from_agent(self, agent_recommendation: Dict) -> Dict:
        """
        Extract your 3 key signals from agent recommendations
        UPDATED: Uses strategy field which is more reliable than reasoning
        """
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False, 
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        # Extract from strategy field (more reliable than reasoning)
        strategy = agent_recommendation.get('strategy', '').lower()
        reasoning = agent_recommendation.get('reasoning', '').lower()
        
        # Detect 3-1 Inside Bar
        if any(term in strategy for term in ['3-1', 'inside_bar', 'inside bar']) or \
           any(term in reasoning for term in ['3-1', 'inside bar', 'consolidation']):
            signals["inside_bar_3_1"] = True
            
        # Detect A/M/D Phases - from strategy name
        if 'accumulation' in strategy:
            signals["accumulation"] = True
        if 'manipulation' in strategy:
            signals["manipulation"] = True  
        if 'distribution' in strategy:
            signals["distribution"] = True
            
        # Detect Trends - from strategy name
        if any(term in strategy for term in ['bullish', 'uptrend', 'rising', 'strong_bullish']):
            signals["bullish_trend"] = True
        if any(term in strategy for term in ['bearish', 'downtrend', 'falling', 'strong_bearish']):
            signals["bearish_trend"] = True
            
        return signals
    
    def get_predicted_direction(self, agent_recommendation: Dict) -> str:
        """
        Extract direction from agent's recommendation
        UPDATED: Uses your actual agent output format
        """
        direction = agent_recommendation.get('direction', '').upper()
        
        # Your agent uses LONG/SHORT/IGNORE
        if direction == 'LONG':
            return 'BULLISH'
        elif direction == 'SHORT':
            return 'BEARISH'
        elif direction == 'IGNORE':
            return 'IGNORE'
        else:
            return 'UNKNOWN'
    
    async def record_prediction_outcome(self, agent_recommendation: Dict, actual_price_data: Dict):
        """
        Record whether the agent's direction prediction was correct
        UPDATED: Better price data handling
        """
        try:
            symbol = agent_recommendation.get('symbol', 'UNKNOWN')
            predicted_direction = self.get_predicted_direction(agent_recommendation)
            
            # Skip IGNORE recommendations
            if predicted_direction == 'IGNORE':
                return
                
            signals = self.extract_signals_from_agent(agent_recommendation)
            
            # Calculate actual direction
            actual_direction = self._calculate_actual_direction(agent_recommendation, actual_price_data)
            if actual_direction == 'UNKNOWN':
                return  # Skip if we can't determine actual direction
                
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
                'agent_confidence': agent_recommendation.get('confidence', 'LOW')
            })
            
            # Save data after each update
            self.save_data()
            
            print(f"🎯 Direction Learning: {symbol} | Predicted: {predicted_direction} | "
                  f"Actual: {actual_direction} | Correct: {correct}")
                  
        except Exception as e:
            print(f"❌ Error recording prediction outcome: {e}")
    
    def _calculate_actual_direction(self, recommendation: Dict, price_data: Dict) -> str:
        """Calculate actual price movement direction with better logic"""
        try:
            # Use entry price from recommendation or current price from alert
            entry_price = recommendation.get('entry')
            if not entry_price:
                return 'UNKNOWN'
                
            # Get current price from price_data (this should come from your monitoring system)
            current_price = price_data.get('current_price')
            if not current_price:
                return 'UNKNOWN'
            
            # Convert to float safely
            try:
                entry = float(entry_price)
                current = float(current_price)
            except (ValueError, TypeError):
                return 'UNKNOWN'
            
            price_change = (current - entry) / entry
            
            # More realistic thresholds for options trading
            if price_change > 0.01:  # 1% up = bullish
                return 'BULLISH'
            elif price_change < -0.01:  # 1% down = bearish
                return 'BEARISH'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            print(f"❌ Error calculating actual direction: {e}")
            return 'UNKNOWN'
    
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
                    if accuracy > 0 and self.signal_accuracy[signal_name][direction_key]['total'] >= 3:
                        confidence_scores.append(accuracy)
        
        # Also check combinations (require at least 5 trades for reliability)
        active_signals = [sig for sig, present in signals.items() if present]
        if len(active_signals) >= 2:
            combination_key = f"{proposed_direction}_{'_'.join(sorted(active_signals))}"
            if combination_key in self.combination_accuracy and self.combination_accuracy[combination_key]['total'] >= 5:
                combo_accuracy = self.combination_accuracy[combination_key]['accuracy']
                confidence_scores.append(combo_accuracy)
        
        # Return average confidence, or 0.5 (neutral) if no reliable data
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
        valid_predictions = [p for p in self.prediction_history if p['predicted_direction'] != 'IGNORE']
        correct_predictions = sum(1 for pred in valid_predictions if pred['correct'])
        report['overall_accuracy'] = correct_predictions / len(valid_predictions) if valid_predictions else 0.0
        
        # Get best performing combinations (require minimum trades)
        combo_list = [{'key': k, **v} for k, v in self.combination_accuracy.items() if v['total'] >= 5]
        combo_list.sort(key=lambda x: x['accuracy'], reverse=True)
        report['best_combinations'] = combo_list[:5]  # Top 5
        
        # Add signal accuracy summary
        for signal_name, data in self.signal_accuracy.items():
            bull_stats = data['bullish_predictions']
            bear_stats = data['bearish_predictions']
            total_trades = bull_stats['total'] + bear_stats['total']
            
            if total_trades > 0:
                report['signal_accuracy'][signal_name] = {
                    'total_trades': total_trades,
                    'bullish_accuracy': bull_stats['accuracy'],
                    'bearish_accuracy': bear_stats['accuracy']
                }
        
        return report

# Simple integration - no need for the wrapper class
# Just use: direction_learner = DirectionPredictionLearner()
