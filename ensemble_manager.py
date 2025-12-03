# Version: 4
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any
import json
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnsembleManager:
    """
    Production-ready ensemble manager with full Supabase integration
    """
    
    def __init__(self, 
                 config_path: Optional[str] = None, 
                 direction_learner=None,
                 ensemble_name: str = "default_ensemble",
                 supabase_client: Optional[Client] = None):
        
        self.strategies = {}
        self.weights = {}
        self.performance_history = {}
        self.config_path = config_path
        self.direction_learner = direction_learner
        self.ensemble_name = ensemble_name
        self.supabase = supabase_client
        self.ensemble_id = None
        self.last_decision_id = None
        
        # Initialize database connection if not provided
        if not self.supabase:
            self._init_supabase_client()
        
        # Load configuration
        self.load_config()
        
        # Load ensemble from database
        self.load_from_database()
        
        logger.info(f"EnsembleManager initialized: {ensemble_name}")
    
    def _init_supabase_client(self):
        """Initialize Supabase client from environment variables"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found in environment")
                return
                
            self.supabase = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
    
    def load_config(self):
        """Load ensemble configuration from file or defaults"""
        default_config = {
            'weights': {
                'momentum': 0.4,
                'mean_reversion': 0.3,
                'breakout': 0.3
            },
            'rebalance_frequency': 'weekly',
            'risk_adjustment': True,
            'use_direction_learning': True,
            'min_confidence': 0.6,
            'max_position_size': 0.1,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.04
        }
        
        self.config = default_config
        self.weights = default_config['weights']
        
        # Load from file if config_path provided
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    self.config.update(file_config)
                    if 'weights' in file_config:
                        self.weights = file_config['weights']
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Error loading config file: {e}")
    
    def load_from_database(self):
        """Load ensemble configuration from Supabase database"""
        if not self.supabase:
            logger.warning("No Supabase client available, using local config only")
            return False
        
        try:
            # Query ensemble configuration
            response = self.supabase.table('ensemble_configurations') \
                .select('*') \
                .eq('name', self.ensemble_name) \
                .eq('is_active', True) \
                .execute()
            
            if response.data:
                ensemble_data = response.data[0]
                self.ensemble_id = ensemble_data['id']
                
                # Update weights from database
                if 'strategy_weights' in ensemble_data and ensemble_data['strategy_weights']:
                    self.weights = ensemble_data['strategy_weights']
                    logger.info(f"Loaded weights from database: {self.weights}")
                
                # Update config from database
                if 'config_settings' in ensemble_data and ensemble_data['config_settings']:
                    self.config.update(ensemble_data['config_settings'])
                
                # Load active strategies
                if 'active_strategies' in ensemble_data and ensemble_data['active_strategies']:
                    # This would initialize actual strategy objects
                    self._initialize_strategies(ensemble_data['active_strategies'])
                
                logger.info(f"Loaded ensemble '{self.ensemble_name}' from database (ID: {self.ensemble_id})")
                return True
            else:
                # Create default ensemble if it doesn't exist
                logger.info(f"Ensemble '{self.ensemble_name}' not found, creating default")
                return self._create_default_ensemble()
                
        except Exception as e:
            logger.error(f"Error loading from database: {e}")
            return False
    
    def _create_default_ensemble(self):
        """Create default ensemble configuration in database"""
        if not self.supabase:
            return False
        
        try:
            default_ensemble = {
                'name': self.ensemble_name,
                'description': 'Default trading ensemble configuration',
                'strategy_weights': self.weights,
                'active_strategies': list(self.weights.keys()),
                'config_settings': self.config,
                'performance_metrics': {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'last_updated': datetime.now().isoformat()
                },
                'direction_learning_enabled': True,
                'is_active': True,
                'version': 1,
                'created_by': 'system'
            }
            
            response = self.supabase.table('ensemble_configurations') \
                .insert(default_ensemble) \
                .execute()
            
            if response.data:
                self.ensemble_id = response.data[0]['id']
                logger.info(f"Created default ensemble with ID: {self.ensemble_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating default ensemble: {e}")
        
        return False
    
    def _initialize_strategies(self, strategy_names: List[str]):
        """Initialize strategy objects (placeholder - connect to actual strategy classes)"""
        for strategy_name in strategy_names:
            self.strategies[strategy_name] = {
                'name': strategy_name,
                'type': strategy_name,
                'parameters': self._get_default_strategy_params(strategy_name),
                'performance': {'wins': 0, 'losses': 0, 'total': 0}
            }
        logger.info(f"Initialized {len(strategy_names)} strategies")
    
    def _get_default_strategy_params(self, strategy_name: str) -> Dict:
        """Get default parameters for strategy type"""
        params = {
            'momentum': {
                'lookback_period': 14,
                'threshold': 0.5,
                'smoothing': 2
            },
            'mean_reversion': {
                'lookback_period': 20,
                'std_dev_multiplier': 2.0,
                'oversold_level': 30,
                'overbought_level': 70
            },
            'breakout': {
                'resistance_lookback': 20,
                'support_lookback': 20,
                'confirmation_bars': 2
            }
        }
        return params.get(strategy_name.lower(), {})
    
    def add_strategy(self, name: str, strategy_data: Dict):
        """Add a trading strategy to the ensemble"""
        self.strategies[name] = strategy_data
        
        # Add to database if connected
        if self.supabase and self.ensemble_id:
            self._update_ensemble_in_database()
        
        logger.info(f"Added strategy: {name}")
        
    def update_weights(self, new_weights: Dict):
        """Update strategy weights"""
        # Validate weights sum to 1
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1, got {total_weight}")
            
        self.weights.update(new_weights)
        logger.info(f"Updated weights: {self.weights}")
        
        # Update in database
        if self.supabase and self.ensemble_id:
            self._update_ensemble_in_database()
    
    def _update_ensemble_in_database(self):
        """Update ensemble configuration in database"""
        if not self.supabase or not self.ensemble_id:
            return
        
        try:
            update_data = {
                'strategy_weights': self.weights,
                'active_strategies': list(self.strategies.keys()),
                'config_settings': self.config,
                'updated_at': datetime.now().isoformat()
            }
            
            self.supabase.table('ensemble_configurations') \
                .update(update_data) \
                .eq('id', self.ensemble_id) \
                .execute()
            
            logger.debug("Updated ensemble in database")
            
        except Exception as e:
            logger.error(f"Error updating ensemble in database: {e}")
    
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
            'original_weights': self.weights.copy(),
            'timestamp': datetime.now().isoformat(),
            'symbol': current_data.get('symbol', 'UNKNOWN')
        }
        
        # Add direction learning insights if available
        if direction_insights:
            result['direction_insights'] = direction_insights
        
        # Log decision to database
        self._log_decision_to_database(result, current_data)
        
        return result
    
    def _log_decision_to_database(self, decision_data: Dict, current_data: Dict):
        """Log ensemble decision to Supabase database"""
        if not self.supabase or not self.ensemble_id:
            return
        
        try:
            # Prepare decision log entry
            decision_log = {
                'ensemble_id': self.ensemble_id,
                'timestamp': decision_data.get('timestamp', datetime.now().isoformat()),
                'symbol': decision_data.get('symbol', current_data.get('symbol', 'UNKNOWN')),
                'market_conditions': {
                    'price': current_data.get('price'),
                    'volume': current_data.get('volume'),
                    'volatility': current_data.get('volatility'),
                    'trend': current_data.get('trend')
                },
                'component_signals': decision_data.get('component_signals', {}),
                'final_signal': decision_data.get('final_signal', 0),
                'confidence': decision_data.get('confidence', 0),
                'weights_used': decision_data.get('weights_used', {}),
                'original_weights': decision_data.get('original_weights', {}),
                'direction_insights': decision_data.get('direction_insights'),
                'trade_executed': False,  # Will be updated when trade is executed
                'processing_time_ms': 0  # Could measure actual processing time
            }
            
            response = self.supabase.table('ensemble_decisions') \
                .insert(decision_log) \
                .execute()
            
            if response.data:
                self.last_decision_id = response.data[0]['id']
                logger.debug(f"Logged ensemble decision with ID: {self.last_decision_id}")
            
        except Exception as e:
            logger.error(f"Error logging decision to database: {e}")
    
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
        """Get signal from individual strategy"""
        strategy = self.strategies.get(strategy_name, {})
        
        # Connect to actual strategy implementations
        strategy_type = strategy.get('type', strategy_name.lower())
        
        if 'momentum' in strategy_type:
            return self._momentum_signal(current_data)
        elif 'mean_reversion' in strategy_type:
            return self._mean_reversion_signal(current_data)
        elif 'breakout' in strategy_type:
            return self._breakout_signal(current_data)
        else:
            # Placeholder for actual strategy integration
            logger.warning(f"Using placeholder signal for {strategy_name}")
            return {'signal': np.random.uniform(-1, 1), 'strength': 0.5}
    
    def _momentum_signal(self, data: Dict) -> Dict:
        """Generate momentum-based signal"""
        # Connect to actual momentum strategy
        # This is a placeholder - should call actual strategy class
        price = data.get('price', 0)
        volume = data.get('volume', 1)
        
        # Simplified momentum calculation
        momentum = np.random.uniform(-1, 1)  # Placeholder
        strength = min(1.0, abs(momentum) * 2)
        
        return {'signal': momentum, 'strength': strength}
    
    def _mean_reversion_signal(self, data: Dict) -> Dict:
        """Generate mean reversion signal"""
        # Connect to actual mean reversion strategy
        # This is a placeholder
        reversion_signal = np.random.uniform(-0.8, 0.8)  # Placeholder
        strength = 0.6  # Constant strength for demo
        
        return {'signal': reversion_signal, 'strength': strength}
    
    def _breakout_signal(self, data: Dict) -> Dict:
        """Generate breakout signal"""
        # Connect to actual breakout strategy
        # This is a placeholder
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
            
        # Log performance to database
        self._log_performance_to_database(performance_data)
    
    def _log_performance_to_database(self, performance_data: Dict):
        """Log performance metrics to database"""
        if not self.supabase or not self.ensemble_id:
            return
        
        try:
            # Calculate performance metrics
            total_decisions = len(performance_data)
            if total_decisions == 0:
                return
            
            # Aggregate performance
            avg_performance = sum(performance_data.values()) / total_decisions
            
            # Log to performance history
            period_end = datetime.now()
            period_start = period_end - timedelta(days=7)  # Weekly periods
            
            performance_log = {
                'ensemble_id': self.ensemble_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_decisions': total_decisions,
                'trades_executed': 0,  # Would be updated with actual trade data
                'wins': 0,
                'losses': 0,
                'win_rate': avg_performance,
                'average_confidence': 0.0,  # Would be calculated
                'total_pnl': 0.0,  # Would be calculated
                'starting_weights': self.weights.copy(),
                'ending_weights': self.weights.copy(),
                'weight_adjustments': {},
                'strategy_performance': performance_data
            }
            
            self.supabase.table('ensemble_performance_history') \
                .insert(performance_log) \
                .execute()
            
            logger.info("Logged performance metrics to database")
            
        except Exception as e:
            logger.error(f"Error logging performance to database: {e}")
    
    def update_with_trade_outcome(self, 
                                 strategy_name: str, 
                                 was_successful: bool, 
                                 signals_used: Dict,
                                 trade_data: Optional[Dict] = None):
        """Update ensemble based on trade outcome for direction learning"""
        
        # Update direction learner if available
        if self.direction_learner:
            try:
                # This would be called from your main trading system when a trade outcome is known
                # The actual recording happens in the direction learner itself
                logger.info(f"Recording trade outcome for {strategy_name}: {'WIN' if was_successful else 'LOSS'}")
                
                # Update the last decision with trade outcome
                if self.last_decision_id and self.supabase:
                    self._update_decision_outcome(
                        self.last_decision_id,
                        was_successful,
                        trade_data
                    )
                    
            except Exception as e:
                logger.warning(f"Error updating ensemble with trade outcome: {e}")
    
    def _update_decision_outcome(self, decision_id: int, was_successful: bool, trade_data: Dict = None):
        """Update decision record with trade outcome"""
        if not self.supabase:
            return
        
        try:
            update_data = {
                'trade_executed': True,
                'trade_outcome': 'WIN' if was_successful else 'LOSS',
                'updated_at': datetime.now().isoformat()
            }
            
            if trade_data:
                update_data['pnl'] = trade_data.get('pnl', 0)
            
            self.supabase.table('ensemble_decisions') \
                .update(update_data) \
                .eq('id', decision_id) \
                .execute()
            
            logger.info(f"Updated decision {decision_id} with trade outcome")
            
        except Exception as e:
            logger.error(f"Error updating decision outcome: {e}")
    
    def get_ensemble_status(self) -> Dict:
        """Get current status of the ensemble"""
        status = {
            'ensemble_name': self.ensemble_name,
            'ensemble_id': self.ensemble_id,
            'active_strategies': list(self.strategies.keys()),
            'current_weights': self.weights.copy(),
            'total_strategies': len(self.strategies),
            'last_updated': datetime.now().isoformat(),
            'direction_learning_enabled': self.direction_learner is not None,
            'database_connected': self.supabase is not None
        }
        
        # Add database stats if connected
        if self.supabase:
            try:
                # Get recent performance from database
                recent_decisions = self._get_recent_decisions(limit=10)
                status['recent_decisions_count'] = len(recent_decisions)
                
                # Get performance summary if ensemble exists in database
                if self.ensemble_id:
                    performance = self._get_performance_summary()
                    status['performance_summary'] = performance
                    
            except Exception as e:
                logger.warning(f"Error getting database stats: {e}")
                status['database_error'] = str(e)
        
        # Add direction learning stats if available
        if self.direction_learner:
            try:
                learning_report = self.direction_learner.get_performance_report()
                status['direction_learning'] = {
                    'total_predictions': learning_report.get('total_predictions', 0),
                    'overall_accuracy': learning_report.get('overall_accuracy', 0.0),
                    'best_combinations': learning_report.get('best_combinations', [])[:3]
                }
            except Exception as e:
                logger.warning(f"Error getting direction learning status: {e}")
                
        return status
    
    def _get_recent_decisions(self, limit: int = 10) -> List[Dict]:
        """Get recent ensemble decisions from database"""
        if not self.supabase or not self.ensemble_id:
            return []
        
        try:
            response = self.supabase.table('ensemble_decisions') \
                .select('*') \
                .eq('ensemble_id', self.ensemble_id) \
                .order('timestamp', desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting recent decisions: {e}")
            return []
    
    def _get_performance_summary(self) -> Dict:
        """Get performance summary from database view"""
        if not self.supabase:
            return {}
        
        try:
            response = self.supabase.table('ensemble_performance_summary') \
                .select('*') \
                .eq('ensemble_name', self.ensemble_name) \
                .execute()
            
            if response.data:
                return response.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def save_state(self, filepath: str):
        """Save ensemble state to file"""
        state = {
            'strategies': self.strategies,
            'weights': self.weights,
            'config': self.config,
            'ensemble_name': self.ensemble_name,
            'ensemble_id': self.ensemble_id,
            'saved_at': datetime.now().isoformat()
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Ensemble state saved to {filepath}")
            
            # Also save to database
            if self.supabase and self.ensemble_id:
                self._update_ensemble_in_database()
                
        except Exception as e:
            logger.error(f"Error saving ensemble state: {e}")
    
    def load_state(self, filepath: str):
        """Load ensemble state from file"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    state = json.load(f)
                
                self.strategies = state.get('strategies', {})
                self.weights = state.get('weights', {})
                self.config = state.get('config', {})
                self.ensemble_name = state.get('ensemble_name', self.ensemble_name)
                self.ensemble_id = state.get('ensemble_id')
                
                logger.info(f"Ensemble state loaded from {filepath}")
                
                # Update database with loaded state
                if self.supabase:
                    self._update_ensemble_in_database()
                    
            else:
                logger.warning(f"State file not found: {filepath}")
                
        except Exception as e:
            logger.error(f"Error loading ensemble state: {e}")
    
    def export_configuration(self) -> Dict:
        """Export complete ensemble configuration"""
        return {
            'ensemble_name': self.ensemble_name,
            'ensemble_id': self.ensemble_id,
            'strategies': self.strategies,
            'weights': self.weights,
            'config': self.config,
            'performance_history': self.performance_history,
            'database_connected': self.supabase is not None,
            'direction_learning_enabled': self.direction_learner is not None,
            'exported_at': datetime.now().isoformat()
        }
    
    async def calculate_signal_async(self, current_data: Dict) -> Dict:
        """Async version of calculate_ensemble_signal"""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.calculate_ensemble_signal, current_data)


# Factory function for easy creation
def create_ensemble_manager(
    ensemble_name: str = "default_ensemble",
    config_path: Optional[str] = None,
    direction_learner = None,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None
) -> EnsembleManager:
    """
    Factory function to create an EnsembleManager with optional Supabase connection
    """
    supabase_client = None
    
    # Initialize Supabase client if credentials provided
    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            supabase_client = create_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
    
    return EnsembleManager(
        config_path=config_path,
        direction_learner=direction_learner,
        ensemble_name=ensemble_name,
        supabase_client=supabase_client
    )
