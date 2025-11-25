#Version: 22
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
    Simplified trading ensemble that combines multiple strategies
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        self.ensemble_manager = EnsembleManager()
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
    
    def update_market_data(self, symbol: str, data: Dict):
        """Update market data for a symbol"""
        self.market_data[symbol] = {
            **data,
            'timestamp': datetime.now().isoformat()
        }
        
    def generate_trading_signals(self, symbol: str) -> Optional[Dict]:
        """Generate trading signals for a symbol"""
        if symbol not in self.market_data:
            logger.warning(f"No market data for {symbol}")
            return None
            
        current_data = self.market_data[symbol]
        ensemble_signal = self.ensemble_manager.calculate_ensemble_signal(current_data)
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            **ensemble_signal
        }
    
    def execute_trading_decision(self, signal_data: Dict, symbol: str) -> Optional[Dict]:
        """Execute trading decision based on ensemble signal"""
        if not signal_data:
            return None
            
        final_signal = signal_data['final_signal']
        confidence = signal_data['confidence']
        
        # Determine position size based on signal strength and confidence
        position_size = self._calculate_position_size(final_signal, confidence)
        
        if abs(final_signal) < 0.1:  # Noise threshold
            logger.debug(f"Signal too weak for {symbol}: {final_signal:.3f}")
            return None
        
        # Generate trade order
        current_price = self.market_data[symbol].get('price', 0)
        if current_price <= 0:
            logger.warning(f"Invalid price for {symbol}: {current_price}")
            return None
            
        order = self._create_order(symbol, final_signal, position_size, current_price)
        
        if order and self._validate_order(order):
            return self._execute_order(order)
        
        return None
    
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
    
    def _create_order(self, symbol: str, signal: float, position_size: float, price: float) -> Dict:
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
            'confidence': position_size / self.risk_limits['max_position_size']
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
        """Run complete trading cycle for a symbol"""
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
        """Generate performance report"""
        portfolio_summary = self.get_portfolio_summary()
        
        # Calculate additional metrics
        trades = self.trade_history
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        
        return {
            **portfolio_summary,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'win_rate': len(winning_trades) / len(trades) if trades else 0,
            'avg_trade_value': np.mean([t['order_value'] for t in trades]) if trades else 0,
            'ensemble_status': self.ensemble_manager.get_ensemble_status()
        }


# Example usage
def demo_trading_ensemble():
    """Demonstrate the trading ensemble"""
    ensemble = TradingEnsemble(initial_balance=10000)
    ensemble.initialize_strategies()
    
    # Simulate market data updates and trading
    symbols = ['AAPL', 'GOOGL', 'MSFT']
    
    for i in range(10):  # Run 10 trading cycles
        for symbol in symbols:
            # Simulate market data
            market_data = {
                'price': 150 + np.random.normal(0, 5),
                'volume': 1000000 + np.random.normal(0, 100000),
                'timestamp': datetime.now().isoformat()
            }
            
            # Run trading cycle
            trade = ensemble.run_trading_cycle(symbol, market_data)
            
            if trade:
                print(f"Trade executed: {trade['action']} {trade['symbol']}")
        
        # Print portfolio summary every 5 cycles
        if i % 5 == 0:
            summary = ensemble.get_portfolio_summary()
            print(f"Cycle {i}: Portfolio Value: ${summary['current_value']:.2f}")

if __name__ == "__main__":
    demo_trading_ensemble()

