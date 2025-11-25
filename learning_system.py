# Version: 1
import asyncio
import random
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

class AutomatedLearningSystem:
    """Automated system to track trade outcomes and model performance"""
    
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.active_monitors = {}
        
        # Initialize performance tracking in memory
        self.model_performance = {
            "gpt-4o": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0},
            "gpt-4-turbo": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0},
            "claude-sonnet-4-20250514": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0}
        }
        
        self.pattern_performance = {}
        
    async def monitor_trade_outcome(self, recommendation: Dict):
        """Start monitoring a trade recommendation for automatic outcome tracking"""
        symbol = recommendation.get('symbol', 'UNKNOWN')
        direction = recommendation.get('direction', 'IGNORE')
        
        if direction == 'IGNORE':
            print(f"⏭️ Skipping monitoring for IGNORE recommendation: {symbol}")
            return
            
        if symbol in self.active_monitors:
            print(f"⚠️ Already monitoring {symbol}, skipping duplicate")
            return
            
        print(f"🔍 Starting automated monitoring for {symbol} {direction}")
        
        # Store the recommendation for monitoring
        self.active_monitors[symbol] = {
            'recommendation': recommendation,
            'start_time': datetime.now(),
            'status': 'MONITORING'
        }
        
        # Start monitoring task
        asyncio.create_task(self._monitor_trade_execution(symbol))
    
    async def _monitor_trade_execution(self, symbol: str):
        """Monitor trade execution with simulated price data (Phase 1)"""
        try:
            monitor_data = self.active_monitors.get(symbol)
            if not monitor_data:
                return
                
            recommendation = monitor_data['recommendation']
            entry_price = self._get_entry_price(recommendation)
            direction = recommendation['direction']
            
            if not entry_price:
                print(f"❌ No valid entry price for {symbol}, stopping monitoring")
                return
            
            # Simulate price movement (Phase 1 - will replace with real data in Phase 2)
            exit_price, exit_reason, duration_hours = self._simulate_price_movement(
                symbol, entry_price, direction, recommendation
            )
            
            # Record the outcome
            await self._record_trade_outcome(recommendation, entry_price, exit_price, 
                                           monitor_data['start_time'], exit_reason)
            
            # Clean up
            if symbol in self.active_monitors:
                del self.active_monitors[symbol]
                
        except Exception as e:
            print(f"❌ Error monitoring {symbol}: {e}")
            if symbol in self.active_monitors:
                del self.active_monitors[symbol]
    
    def _get_entry_price(self, recommendation: Dict) -> float:
        """Extract entry price from recommendation"""
        entry_price = recommendation.get('entry')
        if entry_price and entry_price > 0:
            return float(entry_price)
        
        # Fallback to virtual entry or current price
        virtual_entry = recommendation.get('virtual_entry')
        if virtual_entry and virtual_entry > 0:
            return float(virtual_entry)
            
        current_price = recommendation.get('current_price')
        if current_price and current_price > 0:
            return float(current_price)
            
        return 100.0  # Default fallback
    
    def _simulate_price_movement(self, symbol: str, entry_price: float, direction: str, 
                               recommendation: Dict) -> tuple:
        """Simulate realistic price movement based on strategy and confidence"""
        confidence = recommendation.get('confidence', 'LOW')
        strategy = recommendation.get('strategy', 'unknown')
        
        # Base success probabilities based on confidence
        success_probabilities = {
            'HIGH': 0.7,  # 70% chance of success
            'MEDIUM': 0.6, # 60% chance of success  
            'LOW': 0.4     # 40% chance of success
        }
        
        base_success_prob = success_probabilities.get(confidence, 0.5)
        
        # Adjust based on strategy (you can customize these)
        strategy_modifiers = {
            'strong_bullish_trend': 0.1,
            'moderate_bullish_trend': 0.05,
            '3-1_breakout': 0.08,
            'pullback': -0.05,
            'unknown': 0.0
        }
        
        success_prob = base_success_prob + strategy_modifiers.get(strategy, 0.0)
        success_prob = max(0.2, min(0.9, success_prob))  # Keep within reasonable bounds
        
        # Determine if trade is successful
        is_successful = random.random() < success_prob
        
        # Calculate exit price and reason
        if is_successful:
            # Successful trade - hit take profit
            if direction == 'LONG':
                exit_price = entry_price * (1 + random.uniform(0.005, 0.03))  # 0.5% to 3% gain
            else:  # SHORT
                exit_price = entry_price * (1 - random.uniform(0.005, 0.03))  # 0.5% to 3% gain
            exit_reason = 'TAKE_PROFIT'
        else:
            # Failed trade - hit stop loss
            if direction == 'LONG':
                exit_price = entry_price * (1 - random.uniform(0.005, 0.02))  # 0.5% to 2% loss
            else:  # SHORT
                exit_price = entry_price * (1 + random.uniform(0.005, 0.02))  # 0.5% to 2% loss
            exit_reason = 'STOP_LOSS'
        
        # Random duration between 30 minutes and 4 hours
        duration_hours = random.uniform(0.5, 4.0)
        
        print(f"📊 {symbol} simulation: {direction} at ${entry_price:.2f} -> "
              f"${exit_price:.2f} ({'WIN' if is_successful else 'LOSS'}) - {exit_reason}")
              
        return exit_price, exit_reason, duration_hours
    
    async def _record_trade_outcome(self, recommendation: Dict, entry_price: float, 
                                  exit_price: float, start_time: datetime, exit_reason: str):
        """Record trade outcome and update performance metrics"""
        try:
            symbol = recommendation.get('symbol', 'UNKNOWN')
            direction = recommendation.get('direction', 'LONG')
            
            # Calculate PnL
            if direction == 'LONG':
                pnl_percent = (exit_price - entry_price) / entry_price * 100
            else:  # SHORT
                pnl_percent = (entry_price - exit_price) / entry_price * 100
                
            pnl_dollars = (pnl_percent / 100) * entry_price
            
            # Determine outcome
            if abs(pnl_percent) < 0.1:  # Within 0.1%
                outcome = 'BREAKEVEN'
            elif pnl_percent > 0:
                outcome = 'WIN'
            else:
                outcome = 'LOSS'
            
            duration_minutes = (datetime.now() - start_time).total_seconds() / 60
            
            # Create outcome record
            outcome_data = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': float(entry_price),
                'exit_price': float(exit_price),
                'pnl_percent': float(pnl_percent),
                'pnl_dollars': float(pnl_dollars),
                'outcome': outcome,
                'exit_reason': exit_reason,
                'duration_minutes': int(duration_minutes),
                'strategy': recommendation.get('strategy', 'unknown'),
                'confidence': recommendation.get('confidence', 'LOW'),
                'monitored_at': datetime.now().isoformat()
            }
            
            # Update model performance
            await self._update_model_performance(recommendation, outcome, pnl_percent)
            
            # Update pattern performance
            await self._update_pattern_performance(recommendation, outcome, pnl_percent)
            
            # Save to database if available
            if self.supabase:
                await self._save_outcome_to_db(outcome_data, recommendation)
            
            print(f"✅ Recorded outcome: {symbol} {direction} -> {outcome} "
                  f"({pnl_percent:+.2f}%) - {exit_reason}")
                  
        except Exception as e:
            print(f"❌ Error recording trade outcome: {e}")
    
    async def _update_model_performance(self, recommendation: Dict, outcome: str, pnl_percent: float):
        """Update model performance metrics"""
        try:
            model_details = recommendation.get('model_details', [])
            
            for model_result in model_details:
                model_name = model_result.get('model')
                if model_name not in self.model_performance:
                    continue
                    
                # Update performance stats
                perf = self.model_performance[model_name]
                perf['total_trades'] += 1
                
                if outcome == 'WIN':
                    perf['wins'] += 1
                elif outcome == 'LOSS':
                    perf['losses'] += 1
                    
                perf['total_pnl_percent'] += pnl_percent
                
                # Calculate win rate
                if perf['total_trades'] > 0:
                    perf['win_rate'] = perf['wins'] / perf['total_trades']
                    
                    # Calculate confidence score (win rate weighted by avg PnL)
                    avg_pnl = perf['total_pnl_percent'] / perf['total_trades']
                    perf['confidence_score'] = perf['win_rate'] * (1 + avg_pnl / 100)
                
                print(f"📈 Updated {model_name}: {perf['wins']}W/{perf['losses']}L "
                      f"(Win Rate: {perf['win_rate']:.1%})")
                      
        except Exception as e:
            print(f"❌ Error updating model performance: {e}")
    
    async def _update_pattern_performance(self, recommendation: Dict, outcome: str, pnl_percent: float):
        """Update pattern performance metrics"""
        try:
            pattern_name = recommendation.get('strategy', 'unknown')
            
            if pattern_name not in self.pattern_performance:
                self.pattern_performance[pattern_name] = {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pnl_percent': 0.0,
                    'win_rate': 0.0,
                    'avg_pnl_percent': 0.0,
                    'success_score': 0.0
                }
            
            perf = self.pattern_performance[pattern_name]
            perf['total_trades'] += 1
            
            if outcome == 'WIN':
                perf['wins'] += 1
            elif outcome == 'LOSS':
                perf['losses'] += 1
                
            perf['total_pnl_percent'] += pnl_percent
            
            # Calculate metrics
            if perf['total_trades'] > 0:
                perf['win_rate'] = perf['wins'] / perf['total_trades']
                perf['avg_pnl_percent'] = perf['total_pnl_percent'] / perf['total_trades']
                perf['success_score'] = perf['win_rate'] * perf['avg_pnl_percent']
            
            print(f"📊 Pattern {pattern_name}: {perf['wins']}W/{perf['losses']}L "
                  f"(Success: {perf['success_score']:.2f})")
                  
        except Exception as e:
            print(f"❌ Error updating pattern performance: {e}")
    
    async def _save_outcome_to_db(self, outcome_data: Dict, recommendation: Dict):
        """Save outcome to database (will be implemented when DB is ready)"""
        # This will be implemented after we create the new database
        pass
    
    def get_adaptive_weights(self) -> Dict[str, float]:
        """Get dynamically adjusted model weights based on performance"""
        try:
            total_confidence = sum(perf['confidence_score'] for perf in self.model_performance.values())
            
            adaptive_weights = {}
            for model_name, perf in self.model_performance.items():
                if total_confidence > 0:
                    adaptive_weights[model_name] = perf['confidence_score'] / total_confidence
                else:
                    adaptive_weights[model_name] = 1.0 / len(self.model_performance)
            
            print(f"🎯 Adaptive weights: {adaptive_weights}")
            return adaptive_weights
            
        except Exception as e:
            print(f"❌ Error calculating adaptive weights: {e}")
            # Return equal weights as fallback
            return {model: 1.0/len(self.model_performance) for model in self.model_performance}
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        return {
            'model_performance': self.model_performance,
            'pattern_performance': self.pattern_performance,
            'active_monitors': len(self.active_monitors),
            'report_time': datetime.now().isoformat()
        }
