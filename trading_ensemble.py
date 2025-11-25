#Version: 23
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from ensemble_manager import EnsembleManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingEnsemble:
    """
    Enhanced trading ensemble with direction learning integration
    """
    
    def __init__(self, initial_balance: float = 10000.0, direction_learner=None):
        self.ensemble_manager = EnsembleManager(direction_learner=direction_learner)
        self.direction_learner = direction_learner
        self.portfolio = {
            'cash': initial_balance,
            'positions': {},
            'initial_balance': initial_balance,
            'current_balance': initial_balance
        }
        self.trade_history = []
        self.market_data = {}
        self.risk_limits = {
            'max_position_size': 0.1,  # 10% of portfolio per position
            'max_drawdown': 0.2,       # 20% max drawdown
            'daily_loss_limit': 0.05   # 5% daily loss limit
        }
        
    def initialize_strategies(self):
        """Initialize trading strategies"""
        strategies = {
            'momentum': {
                'type': 'momentum',
                'lookback_period': 20,
                'threshold': 0.02
            },
            'mean_reversion': {
                'type': 'mean_reversion', 
                'lookback_period': 10,
                'threshold': 1.5
            },
            'breakout': {
                'type': 'breakout',
                'lookback_period': 15,
                'threshold': 0.015
            }
        }
        
        for name, config in strategies.items():
            self.ensemble_manager.add_strategy(name, config)
            
        logger.info("Trading strategies initialized")
        
        # Log direction learning status
        if self.direction_learner:
            logger.info("✅ Direction learning system integrated")
    
    def update_market_data(self, symbol: str, data: Dict):
        """Update market data for a symbol"""
        self.market_data[symbol] = {
            **data,
            'timestamp': datetime.now().isoformat()
        }
        
    def generate_trading_signals(self, symbol: str) -> Optional[Dict]:
        """Generate trading signals for a symbol with direction learning insights"""
        if symbol not in self.market_data:
            logger.warning(f"No market data for {symbol}")
            return None
            
        current_data = self.market_data[symbol]
        ensemble_signal = self.ensemble_manager.calculate_ensemble_signal(current_data)
        
        # Add direction learning insights if available
        if self.direction_learner and 'direction_insights' in ensemble_signal:
            logger.info(f"🎯 Direction learning insights available for {symbol}")
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            **ensemble_signal
        }
    
    def execute_trading_decision(self, signal_data: Dict, symbol: str) -> Optional[Dict]:
        """Execute trading decision based on ensemble signal with direction learning"""
        if not signal_data:
            return None
            
        final_signal = signal_data['final_signal']
        confidence = signal_data['confidence']
        
        # Apply direction learning confidence adjustment
        adjusted_confidence = self._apply_direction_learning_adjustment(
            symbol, final_signal, confidence, signal_data
        )
        
        # Determine position size based on adjusted confidence
        position_size = self._calculate_position_size(final_signal, adjusted_confidence)
        
        if abs(final_signal) < 0.1:  # Noise threshold
            logger.debug(f"Signal too weak for {symbol}: {final_signal:.3f}")
            return None
        
        # Generate trade order
        current_price = self.market_data[symbol].get('price', 0)
        if current_price <= 0:
            logger.warning(f"Invalid price for {symbol}: {current_price}")
            return None
            
        order = self._create_order(symbol, final_signal, position_size, current_price, adjusted_confidence)
        
        if order and self._validate_order(order):
            trade = self._execute_order(order)
            
            # Record trade for direction learning if applicable
            if trade and self.direction_learner:
                self._record_trade_for_learning(trade, signal_data)
                
            return trade
        
        return None
    
    def _apply_direction_learning_adjustment(self, symbol: str, signal: float, 
                                           confidence: float, signal_data: Dict) -> float:
        """Apply direction learning adjustments to confidence"""
        if not self.direction_learner:
            return confidence
            
        try:
            # Extract current market data for signal detection
            current_data = self.market_data.get(symbol, {})
            
            # Determine proposed direction
            proposed_direction = 'BULLISH' if signal > 0 else 'BEARISH'
            
            # Get direction learning confidence
            direction_confidence = self._get_direction_learning_confidence(
                current_data, proposed_direction
            )
            
            # Adjust confidence based on direction learning
            if direction_confidence > 0.65:
                # Boost confidence for historically accurate signals
                adjusted_confidence = min(1.0, confidence * 1.2)
                logger.info(f"📈 Direction learning boost: {confidence:.2f} -> {adjusted_confidence:.2f}")
            elif direction_confidence < 0.45:
                # Reduce confidence for historically poor signals
                adjusted_confidence = max(0.1, confidence * 0.8)
                logger.info(f"📉 Direction learning reduction: {confidence:.2f} -> {adjusted_confidence:.2f}")
            else:
                adjusted_confidence = confidence
                
            return adjusted_confidence
            
        except Exception as e:
            logger.warning(f"Error applying direction learning adjustment: {e}")
            return confidence
    
    def _get_direction_learning_confidence(self, current_data: Dict, proposed_direction: str) -> float:
        """Get direction learning confidence for current market conditions"""
        if not self.direction_learner:
            return 0.5  # Neutral confidence
            
        try:
            # Extract signals from current data
            signals = self._extract_signals_from_data(current_data)
            
            # Get confidence from direction learner
            confidence = self.direction_learner.get_direction_confidence(signals, proposed_direction)
            
            return confidence
            
        except Exception as e:
            logger.warning(f"Error getting direction learning confidence: {e}")
            return 0.5
    
    def _extract_signals_from_data(self, current_data: Dict) -> Dict:
        """Extract signals for direction learning from current data"""
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False,
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        # Extract from strategy and pattern data
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
    
    def _record_trade_for_learning(self, trade: Dict, signal_data: Dict):
        """Record trade for direction learning system"""
        try:
            symbol = trade['symbol']
            current_data = self.market_data.get(symbol, {})
            
            # Extract signals
            signals = self._extract_signals_from_data(current_data)
            
            # Determine direction
            direction = 'BULLISH' if trade['action'] == 'BUY' else 'BEARISH'
            
            logger.info(f"📝 Recording trade for direction learning: {symbol} {direction}")
            
        except Exception as e:
            logger.warning(f"Error recording trade for learning: {e}")
    
    def _calculate_position_size(self, signal: float, confidence: float) -> float:
        """Calculate position size based on signal and risk limits"""
        base_size = abs(signal) * confidence
        max_size = self.risk_limits['max_position_size']
        
        # Apply risk limits
        position_size = min(base_size, max_size)
        
        # Reduce size during high drawdown
        current_drawdown = self._calculate_current_drawdown()
        if current_drawdown > self.risk_limits['max_drawdown'] * 0.5:
            position_size *= 0.5  # Reduce position size by 50%
            
        return position_size
    
    def _calculate_current_drawdown(self) -> float:
        """Calculate current portfolio drawdown"""
        peak_value = self.portfolio.get('peak_balance', self.portfolio['initial_balance'])
        current_value = self.portfolio['current_balance']
        
        if peak_value > 0:
            drawdown = (peak_value - current_value) / peak_value
            # Update peak balance
            if current_value > peak_value:
                self.portfolio['peak_balance'] = current_value
            return max(0, drawdown)
        return 0.0
    
    def _create_order(self, symbol: str, signal: float, position_size: float, 
                     price: float, confidence: float) -> Dict:
        """Create trading order"""
        order_value = self.portfolio['current_balance'] * position_size
        quantity = order_value / price
        
        action = 'BUY' if signal > 0 else 'SELL'
        
        return {
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'order_value': order_value,
            'timestamp': datetime.now().isoformat(),
            'signal_strength': abs(signal),
            'confidence': confidence,
            'original_confidence': position_size / self.risk_limits['max_position_size']
        }
    
    def _validate_order(self, order: Dict) -> bool:
        """Validate order against risk limits"""
        # Check if we have enough cash for buy orders
        if order['action'] == 'BUY' and order['order_value'] > self.portfolio['cash']:
            logger.warning(f"Insufficient cash for buy order. Need: {order['order_value']:.2f}, Have: {self.portfolio['cash']:.2f}")
            return False
            
        # Check position size limit
        if order['order_value'] > self.portfolio['current_balance'] * self.risk_limits['max_position_size']:
            logger.warning(f"Order exceeds position size limit")
            return False
            
        return True
    
    def _execute_order(self, order: Dict) -> Dict:
        """Execute the trading order"""
        symbol = order['symbol']
        action = order['action']
        quantity = order['quantity']
        price = order['price']
        order_value = order['order_value']
        
        # Update portfolio
        if action == 'BUY':
            self.portfolio['cash'] -= order_value
            if symbol in self.portfolio['positions']:
                self.portfolio['positions'][symbol] += quantity
            else:
                self.portfolio['positions'][symbol] = quantity
        else:  # SELL
            self.portfolio['cash'] += order_value
            if symbol in self.portfolio['positions']:
                self.portfolio['positions'][symbol] -= quantity
                if self.portfolio['positions'][symbol] <= 0:
                    del self.portfolio['positions'][symbol]
        
        # Record trade
        trade = {
            'trade_id': len(self.trade_history) + 1,
            **order,
            'executed_at': datetime.now().isoformat(),
            'portfolio_value_after': self.calculate_portfolio_value()
        }
        
        self.trade_history.append(trade)
        self.portfolio['current_balance'] = self.calculate_portfolio_value()
        
        logger.info(f"Executed {action} order for {symbol}: {quantity:.2f} shares at ${price:.2f}")
        
        return trade
    
    def calculate_portfolio_value(self) -> float:
        """Calculate total portfolio value"""
        cash = self.portfolio['cash']
        positions_value = 0
        
        for symbol, quantity in self.portfolio['positions'].items():
            if symbol in self.market_data:
                price = self.market_data[symbol].get('price', 0)
                positions_value += quantity * price
        
        return cash + positions_value
    
    def run_trading_cycle(self, symbol: str, market_data: Dict):
        """Run complete trading cycle for a symbol with direction learning"""
        try:
            # Update market data
            self.update_market_data(symbol, market_data)
            
            # Generate signals
            signal_data = self.generate_trading_signals(symbol)
            if not signal_data:
                return None
                
            # Execute trading decision
            trade = self.execute_trading_decision(signal_data, symbol)
            
            # Log cycle completion
            if trade:
                logger.info(f"Trading cycle completed for {symbol}. Action: {trade['action']}")
            else:
                logger.debug(f"Trading cycle completed for {symbol}. No action taken.")
                
            return trade
            
        except Exception as e:
            logger.error(f"Error in trading cycle for {symbol}: {e}")
            return None
    
    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary"""
        current_value = self.calculate_portfolio_value()
        initial_balance = self.portfolio['initial_balance']
        total_return = (current_value - initial_balance) / initial_balance
        
        return {
            'current_value': current_value,
            'initial_balance': initial_balance,
            'total_return': total_return,
            'cash': self.portfolio['cash'],
            'positions': self.portfolio['positions'].copy(),
            'number_of_trades': len(self.trade_history),
            'current_drawdown': self._calculate_current_drawdown(),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_performance_report(self) -> Dict:
        """Generate performance report with direction learning insights"""
        portfolio_summary = self.get_portfolio_summary()
        
        # Calculate additional metrics
        trades = self.trade_history
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        
        report = {
            **portfolio_summary,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'win_rate': len(winning_trades) / len(trades) if trades else 0,
            'avg_trade_value': np.mean([t['order_value'] for t in trades]) if trades else 0,
            'ensemble_status': self.ensemble_manager.get_ensemble_status()
        }
        
        # Add direction learning insights if available
        if self.direction_learner:
            try:
                learning_report = self.direction_learner.get_performance_report()
                report['direction_learning'] = {
                    'total_predictions': learning_report.get('total_predictions', 0),
                    'overall_accuracy': learning_report.get('overall_accuracy', 0.0),
                    'best_combinations': learning_report.get('best_combinations', [])[:3]
                }
            except Exception as e:
                logger.warning(f"Error getting direction learning report: {e}")
        
        return report


# Enhanced example usage with direction learning
def demo_trading_ensemble_with_learning():
    """Demonstrate the trading ensemble with direction learning"""
    # Initialize with direction learner
    from direction_learner import DirectionPredictionLearner
    
    direction_learner = DirectionPredictionLearner()
    ensemble = TradingEnsemble(initial_balance=10000, direction_learner=direction_learner)
    ensemble.initialize_strategies()
    
    # Simulate market data updates and trading
    symbols = ['AAPL', 'GOOGL', 'MSFT']
    
    for i in range(10):  # Run 10 trading cycles
        for symbol in symbols:
            # Simulate market data with strategy patterns
            market_data = {
                'price': 150 + np.random.normal(0, 5),
                'volume': 1000000 + np.random.normal(0, 100000),
                'strategy': random.choice(['3-1_breakout', 'bullish_trend', 'accumulation']),
                'pattern': random.choice(['inside_bar', 'breakout', 'consolidation']),
                'timestamp': datetime.now().isoformat()
            }
            
            # Run trading cycle
            trade = ensemble.run_trading_cycle(symbol, market_data)
            
            if trade:
                print(f"Trade executed: {trade['action']} {trade['symbol']}")
        
        # Print portfolio summary every 5 cycles
        if i % 5 == 0:
            summary = ensemble.get_portfolio_summary()
            performance = ensemble.get_performance_report()
            print(f"Cycle {i}: Portfolio Value: ${summary['current_value']:.2f}")
            
            # Show direction learning insights
            if 'direction_learning' in performance:
                dl = performance['direction_learning']
                print(f"🎯 Direction Learning: {dl['overall_accuracy']:.1%} accuracy")

if __name__ == "__main__":
    demo_trading_ensemble_with_learning()
