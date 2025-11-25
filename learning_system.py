# Version: 3
import asyncio
import random
import json
import os
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

class AutomatedLearningSystem:
    """Enhanced learning system with direction learning integration"""
    
    def __init__(self, supabase_client=None, direction_learner=None):
        self.supabase = supabase_client
        self.direction_learner = direction_learner
        self.active_monitors = {}
        
        # Initialize performance tracking in memory
        self.model_performance = {
            "gpt-4o": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0},
            "gpt-4-turbo": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0},
            "claude-sonnet-4-20250514": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_percent": 0.0, "win_rate": 0.5, "confidence_score": 1.0}
        }
        
        self.pattern_performance = {}
        self.direction_accuracy = {}
        
    async def monitor_trade_outcome(self, recommendation: Dict, alert_data: Dict = None):
        """Start monitoring a trade recommendation with direction learning"""
        symbol = recommendation.get('symbol', 'UNKNOWN')
        direction = recommendation.get('direction', 'IGNORE')
        
        if direction == 'IGNORE':
            print(f"⏭️ Skipping monitoring for IGNORE recommendation: {symbol}")
            return
            
        if symbol in self.active_monitors:
            print(f"⚠️ Already monitoring {symbol}, skipping duplicate")
            return
            
        print(f"🔍 Starting automated monitoring for {symbol} {direction}")
        
        # Extract signals for direction learning
        signals = self._extract_signals_for_direction_learning(recommendation, alert_data)
        
        # Store the recommendation for monitoring
        self.active_monitors[symbol] = {
            'recommendation': recommendation,
            'alert_data': alert_data,
            'signals': signals,
            'start_time': datetime.now(),
            'status': 'MONITORING',
            'predicted_direction': 'BULLISH' if direction == 'LONG' else 'BEARISH'
        }
        
        # Start monitoring task
        asyncio.create_task(self._monitor_trade_execution(symbol))
    
    def _extract_signals_for_direction_learning(self, recommendation: Dict, alert_data: Dict) -> Dict:
        """Extract the 3 key signals for direction learning"""
        signals = {
            "inside_bar_3_1": False,
            "accumulation": False,
            "manipulation": False,
            "distribution": False,
            "bullish_trend": False,
            "bearish_trend": False
        }
        
        # Extract from recommendation and alert data
        strategy = recommendation.get('strategy', '').lower()
        reasoning = recommendation.get('reasoning', '').lower()
        
        if alert_data:
            strategy = strategy or alert_data.get('strategy', '').lower()
            pattern = alert_data.get('pattern', '').lower()
        else:
            pattern = ''
        
        # Detect 3-1 Inside Bar
        if any(term in strategy for term in ['3-1', 'inside_bar', 'inside bar']) or \
           any(term in pattern for term in ['3-1', 'inside bar']) or \
           any(term in reasoning for term in ['3-1', 'inside bar', 'consolidation']):
            signals["inside_bar_3_1"] = True
            
        # Detect A/M/D Phases
        if 'accumulation' in strategy or 'accumulation' in reasoning:
            signals["accumulation"] = True
        if 'manipulation' in strategy or 'manipulation' in reasoning:
            signals["manipulation"] = True
        if 'distribution' in strategy or 'distribution' in reasoning:
            signals["distribution"] = True
            
        # Detect Trends
        if any(term in strategy for term in ['bullish', 'uptrend', 'rising', 'strong_bullish']) or \
           any(term in reasoning for term in ['bullish', 'uptrend', 'rising']):
            signals["bullish_trend"] = True
        if any(term in strategy for term in ['bearish', 'downtrend', 'falling', 'strong_bearish']) or \
           any(term in reasoning for term in ['bearish', 'downtrend', 'falling']):
            signals["bearish_trend"] = True
            
        print(f"🎯 Direction learning signals detected: {[k for k, v in signals.items() if v]}")
        return signals
    
    async def _monitor_trade_execution(self, symbol: str):
        """Monitor trade execution with direction learning integration"""
        try:
            monitor_data = self.active_monitors.get(symbol)
            if not monitor_data:
                return
                
            recommendation = monitor_data['recommendation']
            alert_data = monitor_data.get('alert_data', {})
            signals = monitor_data['signals']
            predicted_direction = monitor_data['predicted_direction']
            
            entry_price = self._get_entry_price(recommendation)
            direction = recommendation['direction']
            
            if not entry_price:
                print(f"❌ No valid entry price for {symbol}, stopping monitoring")
                return
            
            # Simulate price movement (Phase 1 - will replace with real data in Phase 2)
            exit_price, exit_reason, duration_hours, actual_direction = self._simulate_price_movement(
                symbol, entry_price, direction, recommendation, signals
            )
            
            # Record the outcome with direction learning
            await self._record_trade_outcome(
                recommendation, entry_price, exit_price, 
                monitor_data['start_time'], exit_reason,
                signals, predicted_direction, actual_direction
            )
            
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
        
        virtual_entry = recommendation.get('virtual_entry')
        if virtual_entry and virtual_entry > 0:
            return float(virtual_entry)
            
        current_price = recommendation.get('current_price')
        if current_price and current_price > 0:
            return float(current_price)
            
        return 100.0  # Default fallback
    
    def _simulate_price_movement(self, symbol: str, entry_price: float, direction: str, 
                               recommendation: Dict, signals: Dict) -> tuple:
        """Simulate realistic price movement with direction learning influence"""
        confidence = recommendation.get('confidence', 'LOW')
        strategy = recommendation.get('strategy', 'unknown')
        
        # Base success probabilities based on confidence
        success_probabilities = {
            'HIGH': 0.7,  # 70% chance of success
            'MEDIUM': 0.6, # 60% chance of success  
            'LOW': 0.4     # 40% chance of success
        }
        
        base_success_prob = success_probabilities.get(confidence, 0.5)
        
        # Adjust based on strategy
        strategy_modifiers = {
            'strong_bullish_trend': 0.1,
            'moderate_bullish_trend': 0.05,
            '3-1_breakout': 0.08,
            'pullback': -0.05,
            'unknown': 0.0
        }
        
        success_prob = base_success_prob + strategy_modifiers.get(strategy, 0.0)
        
        # ✅ NEW: Apply direction learning adjustment
        if self.direction_learner:
            predicted_direction = 'BULLISH' if direction == 'LONG' else 'BEARISH'
            direction_confidence = self.direction_learner.get_direction_confidence(signals, predicted_direction)
            
            # Boost probability if direction learning has high confidence
            if direction_confidence > 0.65:
                success_prob += 0.1
                print(f"📈 Direction learning boost: +10% (confidence: {direction_confidence:.1%})")
            elif direction_confidence < 0.45:
                success_prob -= 0.1
                print(f"📉 Direction learning reduction: -10% (confidence: {direction_confidence:.1%})")
        
        success_prob = max(0.2, min(0.9, success_prob))
        
        # Determine if trade is successful
        is_successful = random.random() < success_prob
        
        # Calculate exit price and reason
        if is_successful:
            if direction == 'LONG':
                exit_price = entry_price * (1 + random.uniform(0.005, 0.03))
                actual_direction = 'BULLISH'
            else:  # SHORT
                exit_price = entry_price * (1 - random.uniform(0.005, 0.03))
                actual_direction = 'BEARISH'
            exit_reason = 'TAKE_PROFIT'
        else:
            if direction == 'LONG':
                exit_price = entry_price * (1 - random.uniform(0.005, 0.02))
                actual_direction = 'BEARISH'
            else:  # SHORT
                exit_price = entry_price * (1 + random.uniform(0.005, 0.02))
                actual_direction = 'BULLISH'
            exit_reason = 'STOP_LOSS'
        
        duration_hours = random.uniform(0.5, 4.0)
        
        print(f"📊 {symbol} simulation: {direction} at ${entry_price:.2f} -> "
              f"${exit_price:.2f} ({'WIN' if is_successful else 'LOSS'}) - {exit_reason}")
              
        return exit_price, exit_reason, duration_hours, actual_direction
    
    async def _record_trade_outcome(self, recommendation: Dict, entry_price: float, 
                                  exit_price: float, start_time: datetime, exit_reason: str,
                                  signals: Dict, predicted_direction: str, actual_direction: str):
        """Record trade outcome and update performance metrics with direction learning"""
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
            if abs(pnl_percent) < 0.1:
                outcome = 'BREAKEVEN'
            elif pnl_percent > 0:
                outcome = 'WIN'
            else:
                outcome = 'LOSS'
            
            duration_minutes = (datetime.now() - start_time).total_seconds() / 60
            
            # ✅ NEW: Update direction learning system
            if self.direction_learner:
                await self._update_direction_learning(
                    recommendation, signals, predicted_direction, actual_direction, pnl_percent
                )
            
            # Update model performance
            await self._update_model_performance(recommendation, outcome, pnl_percent)
            
            # Update pattern performance
            await self._update_pattern_performance(recommendation, outcome, pnl_percent)
            
            print(f"✅ Recorded outcome: {symbol} {direction} -> {outcome} "
                  f"({pnl_percent:+.2f}%) - {exit_reason}")
                  
        except Exception as e:
            print(f"❌ Error recording trade outcome: {e}")
    
    async def _update_direction_learning(self, recommendation: Dict, signals: Dict, 
                                       predicted_direction: str, actual_direction: str, pnl_percent: float):
        """Update direction learning system with trade outcome"""
        try:
            if not self.direction_learner:
                return
                
            # Create price data for direction learner
            price_data = {
                'current_price': recommendation.get('entry') or recommendation.get('current_price', 100),
                'entry_price': recommendation.get('entry'),
                'exit_price': recommendation.get('entry', 100) * (1 + pnl_percent/100)  # Simulated exit
            }
            
            # Record the prediction outcome
            await self.direction_learner.record_prediction_outcome(recommendation, price_data)
            
            # Calculate direction accuracy
            direction_correct = predicted_direction == actual_direction
            
            # Update direction accuracy tracking
            signal_key = "_".join([k for k, v in signals.items() if v])
            if not signal_key:
                signal_key = "no_signals"
                
            if signal_key not in self.direction_accuracy:
                self.direction_accuracy[signal_key] = {
                    'correct': 0,
                    'total': 0,
                    'accuracy': 0.0,
                    'signals': signals
                }
            
            stats = self.direction_accuracy[signal_key]
            stats['total'] += 1
            if direction_correct:
                stats['correct'] += 1
            stats['accuracy'] = stats['correct'] / stats['total']
            
            print(f"🎯 Direction learning: {signal_key} -> {'✅' if direction_correct else '❌'} "
                  f"(Accuracy: {stats['accuracy']:.1%})")
                  
        except Exception as e:
            print(f"❌ Error updating direction learning: {e}")
    
    async def _update_model_performance(self, recommendation: Dict, outcome: str, pnl_percent: float):
        """Update model performance metrics"""
        try:
            model_details = recommendation.get('model_details', [])
            
            for model_result in model_details:
                model_name = model_result.get('model')
                if model_name not in self.model_performance:
                    continue
                    
                perf = self.model_performance[model_name]
                perf['total_trades'] += 1
                
                if outcome == 'WIN':
                    perf['wins'] += 1
                elif outcome == 'LOSS':
                    perf['losses'] += 1
                    
                perf['total_pnl_percent'] += pnl_percent
                
                if perf['total_trades'] > 0:
                    perf['win_rate'] = perf['wins'] / perf['total_trades']
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
                    'total_trades': 0, 'wins': 0, 'losses': 0, 'total_pnl_percent': 0.0,
                    'win_rate': 0.0, 'avg_pnl_percent': 0.0, 'success_score': 0.0
                }
            
            perf = self.pattern_performance[pattern_name]
            perf['total_trades'] += 1
            
            if outcome == 'WIN':
                perf['wins'] += 1
            elif outcome == 'LOSS':
                perf['losses'] += 1
                
            perf['total_pnl_percent'] += pnl_percent
            
            if perf['total_trades'] > 0:
                perf['win_rate'] = perf['wins'] / perf['total_trades']
                perf['avg_pnl_percent'] = perf['total_pnl_percent'] / perf['total_trades']
                perf['success_score'] = perf['win_rate'] * perf['avg_pnl_percent']
            
            print(f"📊 Pattern {pattern_name}: {perf['wins']}W/{perf['losses']}L "
                  f"(Success: {perf['success_score']:.2f})")
                  
        except Exception as e:
            print(f"❌ Error updating pattern performance: {e}")
    
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
            return {model: 1.0/len(self.model_performance) for model in self.model_performance}
    
    def get_direction_learning_insights(self) -> Dict:
        """Get insights from direction learning system"""
        if not self.direction_learner:
            return {"error": "Direction learner not configured"}
            
        try:
            report = self.direction_learner.get_performance_report()
            
            # Add our internal direction accuracy tracking
            report['signal_combination_accuracy'] = {
                k: v for k, v in sorted(
                    self.direction_accuracy.items(), 
                    key=lambda x: x[1]['accuracy'], 
                    reverse=True
                )[:5]  # Top 5 combinations
            }
            
            return report
            
        except Exception as e:
            return {"error": f"Failed to get direction learning insights: {e}"}
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report with direction learning"""
        report = {
            'model_performance': self.model_performance,
            'pattern_performance': self.pattern_performance,
            'active_monitors': len(self.active_monitors),
            'report_time': datetime.now().isoformat()
        }
        
        # Add direction learning insights
        direction_insights = self.get_direction_learning_insights()
        if 'error' not in direction_insights:
            report['direction_learning'] = direction_insights
        
        return report

    def get_best_signal_combinations(self) -> List[Dict]:
        """Get the best performing signal combinations for direction prediction"""
        if not self.direction_accuracy:
            return []
            
        # Sort by accuracy and return top performers
        sorted_combinations = sorted(
            self.direction_accuracy.items(),
            key=lambda x: x[1]['accuracy'],
            reverse=True
        )
        
        return [
            {
                'signal_combination': combo[0],
                'accuracy': combo[1]['accuracy'],
                'total_trades': combo[1]['total'],
                'signals': combo[1]['signals']
            }
            for combo in sorted_combinations[:5]  # Top 5
        ]
