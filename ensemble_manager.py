# Version: 3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnsembleManager:
    """
    Enhanced ensemble manager with direction learning integration
    """
    
    def __init__(self, config_path: Optional[str] = None, direction_learner=None):
        self.strategies = {}
        self.weights = {}
        self.performance_history = {}
        self.config_path = config_path
        self.direction_learner = direction_learner
        self.load_config()
        
    def load_config(self):
        """Load ensemble configuration"""
        default_config = {
            'weights': {
                'momentum': 0.4,
                'mean_reversion': 0.3,
                'breakout': 0.3
            },
            'rebalance_frequency': 'weekly',
            'risk_adjustment': True,
            'use_direction_learning': True
        }
        
        self.config = default_config
        self.weights = default_config['weights']
        
    def add_strategy(self, name: str, strategy_data: Dict):
        """Add a trading strategy to the ensemble"""
        self.strategies[name] = strategy_data
        logger.info(f"Added strategy: {name}")
        
    def update_weights(self, new_weights: Dict):
        """Update strategy weights"""
        # Validate weights sum to 1
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1, got {total_weight}")
            
        self.weights.update(new_weights)
        logger.info(f"Updated weights: {self.weights}")
        
    def calculate_ensemble_signal(self, current_data: Dict) -> Dict:
        """
        Calculate combined signal from all strategies with direction learning
        Returns: Dict with final signal and component signals
        """
        signals = {}
        strengths = {}
        direction_insights = {}
        
        # Collect signals from all strategies
        for strategy_name, weight in self.weights.items():
            if strategy_name in self.strategies:
                try:
                    signal_data = self._get_strategy_signal(strategy_name, current_data)
                    signals[strategy_name] = signal_data['signal']
                    strengths[strategy_name] = signal_data.get('strength', 0)
                    
                    # Add direction learning insights if available
                    if self.direction_learner and self.config.get('use_direction_learning', True):
                        direction_insight = self._get_direction_learning_insight(strategy_name, current_data, signal_data)
                        if direction_insight:
                            direction_insights[strategy_name] = direction_insight
                            
                except Exception as e:
                    logger.warning(f"Error getting signal from {strategy_name}: {e}")
                    signals[strategy_name] = 0
                    strengths[strategy_name] = 0
        
        if not signals:
            return {'final_signal': 0, 'component_signals': {}, 'confidence': 0}
        
        # Apply direction learning adjustments to weights
        adjusted_weights = self._adjust_weights_with_learning(signals, current_data)
        
        # Calculate weighted signal with adjusted weights
        weighted_signal = 0
        total_strength = 0
        
        for strategy_name, signal in signals.items():
            weight = adjusted_weights.get(strategy_name, self.weights.get(strategy_name, 0))
            strength = strengths.get(strategy_name, 0)
            
            weighted_signal += signal * weight
            total_strength += strength * weight
        
        # Normalize signal to [-1, 1] range
        final_signal = max(-1, min(1, weighted_signal))
        
        result = {
            'final_signal': final_signal,
            'component_signals': signals,
            'confidence': total_strength,
            'weights_used': adjusted_weights,
            'original_weights': self.weights.copy()
        }
        
        # Add direction learning insights if available
        if direction_insights:
            result['direction_insights'] = direction_insights
            
        return result
    
    def _get_direction_learning_insight(self, strategy_name: str, current_data: Dict, signal_data: Dict) -> Optional[Dict]:
        """Get direction learning insight for a strategy"""
        if not self.direction_learner:
            return None
            
        try:
            # Extract signals from current data
            signals = self._extract_signals_from_data(current_data, strategy_name)
            signal_value = signal_data['signal']
            
            # Determine proposed direction
            if signal_value > 0.1:  # Bullish signal
                proposed_direction = 'BULLISH'
            elif signal_value < -0.1:  # Bearish signal
                proposed_direction = 'BEARISH'
            else:
                return None  # Neutral signal, no insight
                
            # Get historical confidence
            confidence = self.direction_learner.get_direction_confidence(signals, proposed_direction)
            
            return {
                'strategy': strategy_name,
                'proposed_direction': proposed_direction,
                'historical_confidence': confidence,
                'signals_detected': [sig for sig, active in signals.items() if active]
            }
            
        except Exception as e:
            logger.warning(f"Error getting direction learning insight for {strategy_name}: {e}")
            return None
    
    def _extract_signals_from_data(self, current_data: Dict, strategy_name: str) -> Dict:
        """Extract signals for direction learning from current data"""
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False,
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        # Extract from strategy-specific data
        strategy = current_data.get('strategy', '').lower()
        pattern = current_data.get('pattern', '').lower()
        
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
    
    def _adjust_weights_with_learning(self, signals: Dict, current_data: Dict) -> Dict:
        """Adjust strategy weights based on direction learning insights"""
        if not self.direction_learner or not self.config.get('use_direction_learning', True):
            return self.weights.copy()
            
        try:
            adjusted_weights = self.weights.copy()
            
            for strategy_name, signal in signals.items():
                if abs(signal) < 0.1:  # Skip weak signals
                    continue
                    
                # Extract signals for this strategy
                strategy_signals = self._extract_signals_from_data(current_data, strategy_name)
                proposed_direction = 'BULLISH' if signal > 0 else 'BEARISH'
                
                # Get historical confidence
                confidence = self.direction_learner.get_direction_confidence(strategy_signals, proposed_direction)
                
                # Adjust weight based on historical performance
                if confidence > 0.65:  # Strong historical performance
                    adjustment_factor = 1.2
                    logger.info(f"📈 Boosting {strategy_name} weight due to strong historical accuracy ({confidence:.1%})")
                elif confidence < 0.45:  # Poor historical performance
                    adjustment_factor = 0.8
                    logger.info(f"📉 Reducing {strategy_name} weight due to poor historical accuracy ({confidence:.1%})")
                else:  # Neutral performance
                    adjustment_factor = 1.0
                    
                adjusted_weights[strategy_name] *= adjustment_factor
            
            # Normalize weights to sum to 1
            total_weight = sum(adjusted_weights.values())
            if total_weight > 0:
                adjusted_weights = {k: v/total_weight for k, v in adjusted_weights.items()}
                
            return adjusted_weights
            
        except Exception as e:
            logger.warning(f"Error adjusting weights with direction learning: {e}")
            return self.weights.copy()
    
    def _get_strategy_signal(self, strategy_name: str, current_data: Dict) -> Dict:
        """Get signal from individual strategy (simplified)"""
        strategy = self.strategies.get(strategy_name, {})
        
        # Simplified signal generation based on strategy type
        if 'momentum' in strategy_name.lower():
            return self._momentum_signal(current_data)
        elif 'mean_reversion' in strategy_name.lower():
            return self._mean_reversion_signal(current_data)
        elif 'breakout' in strategy_name.lower():
            return self._breakout_signal(current_data)
        else:
            # Default random signal for demonstration
            return {'signal': np.random.uniform(-1, 1), 'strength': 0.5}
    
    def _momentum_signal(self, data: Dict) -> Dict:
        """Generate momentum-based signal"""
        price = data.get('price', 0)
        volume = data.get('volume', 1)
        
        # Simplified momentum calculation
        momentum = np.random.uniform(-1, 1)  # Placeholder
        strength = min(1.0, abs(momentum) * 2)
        
        return {'signal': momentum, 'strength': strength}
    
    def _mean_reversion_signal(self, data: Dict) -> Dict:
        """Generate mean reversion signal"""
        # Simplified mean reversion logic
        reversion_signal = np.random.uniform(-0.8, 0.8)  # Placeholder
        strength = 0.6  # Constant strength for demo
        
        return {'signal': reversion_signal, 'strength': strength}
    
    def _breakout_signal(self, data: Dict) -> Dict:
        """Generate breakout signal"""
        # Simplified breakout logic
        breakout_signal = np.random.uniform(-1, 1)  # Placeholder
        strength = 0.7  # Constant strength for demo
        
        return {'signal': breakout_signal, 'strength': strength}
    
    def rebalance_weights(self, performance_data: Dict):
        """Rebalance weights based on recent performance"""
        if not performance_data:
            return
            
        logger.info("Rebalancing ensemble weights...")
        
        # Simple rebalancing logic: increase weights for better performers
        total_performance = sum(performance_data.values())
        if total_performance == 0:
            return
            
        new_weights = {}
        for strategy, perf in performance_data.items():
            if strategy in self.weights:
                # Adjust weight based on relative performance
                performance_ratio = perf / total_performance if total_performance != 0 else 1/len(performance_data)
                current_weight = self.weights[strategy]
                new_weights[strategy] = current_weight * 0.7 + performance_ratio * 0.3
        
        # Normalize weights to sum to 1
        weight_sum = sum(new_weights.values())
        if weight_sum > 0:
            new_weights = {k: v/weight_sum for k, v in new_weights.items()}
            self.update_weights(new_weights)
    
    def update_with_trade_outcome(self, strategy_name: str, was_successful: bool, signals_used: Dict):
        """Update ensemble based on trade outcome for direction learning"""
        if self.direction_learner:
            try:
                # This would be called from your main trading system when a trade outcome is known
                # The actual recording happens in the direction learner itself
                logger.info(f"Recording trade outcome for {strategy_name}: {'WIN' if was_successful else 'LOSS'}")
            except Exception as e:
                logger.warning(f"Error updating ensemble with trade outcome: {e}")
    
    def get_ensemble_status(self) -> Dict:
        """Get current status of the ensemble"""
        status = {
            'active_strategies': list(self.strategies.keys()),
            'current_weights': self.weights.copy(),
            'total_strategies': len(self.strategies),
            'last_updated': datetime.now().isoformat(),
            'direction_learning_enabled': self.direction_learner is not None
        }
        
        # Add direction learning stats if available
        if self.direction_learner:
            try:
                learning_report = self.direction_learner.get_performance_report()
                status['direction_learning'] = {
                    'total_predictions': learning_report.get('total_predictions', 0),
                    'overall_accuracy': learning_report.get('overall_accuracy', 0.0),
                    'best_combinations': learning_report.get('best_combinations', [])[:3]  # Top 3
                }
            except Exception as e:
                logger.warning(f"Error getting direction learning status: {e}")
                
        return status
    
    def save_state(self, filepath: str):
        """Save ensemble state to file"""
        state = {
            'strategies': self.strategies,
            'weights': self.weights,
            'config': self.config,
            'saved_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Ensemble state saved to {filepath}")
    
    def load_state(self, filepath: str):
        """Load ensemble state from file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                state = json.load(f)
            
            self.strategies = state.get('strategies', {})
            self.weights = state.get('weights', {})
            self.config = state.get('config', {})
            
            logger.info(f"Ensemble state loaded from {filepath}")
