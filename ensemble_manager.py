# Version: 2
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
    Simplified ensemble manager for trading strategy combination
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.strategies = {}
        self.weights = {}
        self.performance_history = {}
        self.config_path = config_path
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
            'risk_adjustment': True
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
        Calculate combined signal from all strategies
        Returns: Dict with final signal and component signals
        """
        signals = {}
        strengths = {}
        
        # Collect signals from all strategies
        for strategy_name, weight in self.weights.items():
            if strategy_name in self.strategies:
                try:
                    signal_data = self._get_strategy_signal(strategy_name, current_data)
                    signals[strategy_name] = signal_data['signal']
                    strengths[strategy_name] = signal_data.get('strength', 0)
                except Exception as e:
                    logger.warning(f"Error getting signal from {strategy_name}: {e}")
                    signals[strategy_name] = 0
                    strengths[strategy_name] = 0
        
        if not signals:
            return {'final_signal': 0, 'component_signals': {}, 'confidence': 0}
        
        # Calculate weighted signal
        weighted_signal = 0
        total_strength = 0
        
        for strategy_name, signal in signals.items():
            weight = self.weights.get(strategy_name, 0)
            strength = strengths.get(strategy_name, 0)
            
            weighted_signal += signal * weight
            total_strength += strength * weight
        
        # Normalize signal to [-1, 1] range
        final_signal = max(-1, min(1, weighted_signal))
        
        return {
            'final_signal': final_signal,
            'component_signals': signals,
            'confidence': total_strength,
            'weights_used': self.weights.copy()
        }
    
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
    
    def get_ensemble_status(self) -> Dict:
        """Get current status of the ensemble"""
        return {
            'active_strategies': list(self.strategies.keys()),
            'current_weights': self.weights.copy(),
            'total_strategies': len(self.strategies),
            'last_updated': datetime.now().isoformat()
        }
    
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
