# Version: 1
from trading_ensemble import TradingEnsemble

# Singleton instance
ensemble = TradingEnsemble()

async def get_ensemble_decision(alert_data):
    """Convenience function to get ensemble decision"""
    return await ensemble.get_ensemble_decision(alert_data)

async def get_performance_report():
    """Get learning system performance report"""
    return ensemble.learning_system.get_performance_report()

def get_adaptive_weights():
    """Get current adaptive model weights"""
    return ensemble.learning_system.get_adaptive_weights()
