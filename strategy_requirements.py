"""
Strategy Requirements Module
Defines data requirements and processing logic for each trading strategy type.
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """Classification of strategy types"""
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend"
    MEAN_REVERSION = "reversion"
    ARBITRAGE = "arbitrage"
    ML_BASED = "ml"
    UNKNOWN = "unknown"

class DataField(Enum):
    """Standardized data fields"""
    # Price data
    CLOSE = "close"
    HIGH = "high"
    LOW = "low"
    OPEN = "open"
    VOLUME = "volume"
    
    # Technical indicators
    RSI = "rsi"
    MACD = "macd"
    MACD_SIGNAL = "macd_signal"
    EMA_FAST = "ema_fast"
    EMA_SLOW = "ema_slow"
    BB_UPPER = "bollinger_upper"
    BB_LOWER = "bollinger_lower"
    BB_MIDDLE = "bollinger_middle"
    STOCHASTIC = "stochastic"
    ATR = "atr"
    
    # Pattern-specific
    IB_HIGH = "ib_high"
    IB_LOW = "ib_low"
    BOX_HIGH = "box_high"
    BOX_LOW = "box_low"
    SUPPORT = "support"
    RESISTANCE = "resistance"
    
    # Market context
    TREND_STRENGTH = "trend_strength"
    VOLUME_RATIO = "volume_ratio"
    MARKET_CAP = "market_cap"
    VOLATILITY = "volatility"
    
    # Time/sequence
    TIMEFRAME = "timeframe"
    TIMESTAMP = "timestamp"
    PATTERN_NAME = "pattern"
    
    # Sentiment/Fundamental
    SENTIMENT = "sentiment"
    NEWS_SCORE = "news_score"
    SOCIAL_VOLUME = "social_volume"

@dataclass
class StrategyRequirements:
    """Defines what data a strategy needs"""
    name: str
    strategy_type: StrategyType
    required_fields: List[DataField]
    recommended_fields: List[DataField]
    optional_fields: List[DataField]
    not_needed_fields: List[DataField]
    description: str
    confidence_threshold: float = 0.6
    min_data_points: int = 20
    
    def validate_alert_data(self, alert_data: Dict) -> Tuple[bool, List[str]]:
        """Validate if alert has required data for this strategy"""
        missing = []
        
        for field in self.required_fields:
            field_name = field.value
            if field_name not in alert_data or alert_data[field_name] is None:
                missing.append(field_name)
        
        return len(missing) == 0, missing
    
    def get_validation_score(self, alert_data: Dict) -> float:
        """Calculate a score (0-1) of how complete the data is for this strategy"""
        total_weight = 0
        score = 0
        
        # Required fields: weight 3
        for field in self.required_fields:
            total_weight += 3
            if field.value in alert_data and alert_data[field.value] is not None:
                score += 3
        
        # Recommended fields: weight 2
        for field in self.recommended_fields:
            total_weight += 2
            if field.value in alert_data and alert_data[field.value] is not None:
                score += 2
        
        # Optional fields: weight 1
        for field in self.optional_fields:
            total_weight += 1
            if field.value in alert_data and alert_data[field.value] is not None:
                score += 1
        
        return score / total_weight if total_weight > 0 else 0.0

# ============================================================================
# BREAKOUT STRATEGIES
# ============================================================================

BREAKOUT_STRATEGIES = {
    "3-1_breakout_long": StrategyRequirements(
        name="3-1_breakout_long",
        strategy_type=StrategyType.BREAKOUT,
        required_fields=[
            DataField.CLOSE,
            DataField.IB_HIGH,
            DataField.IB_LOW,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.VOLUME,
            DataField.VOLUME_RATIO,
            DataField.TIMEFRAME
        ],
        optional_fields=[
            DataField.VOLATILITY,
            DataField.ATR
        ],
        not_needed_fields=[
            DataField.RSI,
            DataField.MACD,
            DataField.TREND_STRENGTH,
            DataField.EMA_FAST,
            DataField.EMA_SLOW
        ],
        description="Breakout above Initial Balance high (3-1 pattern)",
        confidence_threshold=0.65
    ),
    
    "3-1_breakout_short": StrategyRequirements(
        name="3-1_breakout_short",
        strategy_type=StrategyType.BREAKOUT,
        required_fields=[
            DataField.CLOSE,
            DataField.IB_HIGH,
            DataField.IB_LOW,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.VOLUME,
            DataField.VOLUME_RATIO
        ],
        optional_fields=[
            DataField.VOLATILITY,
            DataField.ATR
        ],
        not_needed_fields=[
            DataField.RSI,
            DataField.MACD,
            DataField.TREND_STRENGTH
        ],
        description="Breakout below Initial Balance low (3-1 pattern)",
        confidence_threshold=0.65
    ),
    
    "box_breakout_long": StrategyRequirements(
        name="box_breakout_long",
        strategy_type=StrategyType.BREAKOUT,
        required_fields=[
            DataField.CLOSE,
            DataField.BOX_HIGH,
            DataField.BOX_LOW,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.VOLUME,
            DataField.VOLUME_RATIO,
            DataField.TIMEFRAME
        ],
        optional_fields=[
            DataField.VOLATILITY,
            DataField.ATR
        ],
        not_needed_fields=[
            DataField.RSI,
            DataField.MACD,
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="Breakout above box consolidation pattern",
        confidence_threshold=0.7
    ),
}

# ============================================================================
# TREND FOLLOWING STRATEGIES
# ============================================================================

TREND_STRATEGIES = {
    "strong_bullish_tr": StrategyRequirements(
        name="strong_bullish_tr",
        strategy_type=StrategyType.TREND_FOLLOWING,
        required_fields=[
            DataField.CLOSE,
            DataField.RSI,
            DataField.TREND_STRENGTH,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.EMA_FAST,
            DataField.EMA_SLOW,
            DataField.MACD,
            DataField.VOLUME,
            DataField.VOLUME_RATIO
        ],
        optional_fields=[
            DataField.ATR,
            DataField.VOLATILITY
        ],
        not_needed_fields=[
            DataField.IB_HIGH,
            DataField.IB_LOW,
            DataField.BOX_HIGH,
            DataField.BOX_LOW
        ],
        description="Strong bullish trend following with RSI confirmation",
        confidence_threshold=0.75
    ),
    
    "strong_bearish_tr": StrategyRequirements(
        name="strong_bearish_tr",
        strategy_type=StrategyType.TREND_FOLLOWING,
        required_fields=[
            DataField.CLOSE,
            DataField.RSI,
            DataField.TREND_STRENGTH,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.EMA_FAST,
            DataField.EMA_SLOW,
            DataField.MACD,
            DataField.VOLUME
        ],
        optional_fields=[
            DataField.ATR,
            DataField.VOLATILITY
        ],
        not_needed_fields=[
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="Strong bearish trend following with RSI confirmation",
        confidence_threshold=0.75
    ),
    
    "ema_crossover_bullish": StrategyRequirements(
        name="ema_crossover_bullish",
        strategy_type=StrategyType.TREND_FOLLOWING,
        required_fields=[
            DataField.CLOSE,
            DataField.EMA_FAST,
            DataField.EMA_SLOW,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.RSI,
            DataField.MACD,
            DataField.VOLUME
        ],
        optional_fields=[
            DataField.TREND_STRENGTH,
            DataField.VOLUME_RATIO
        ],
        not_needed_fields=[
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="EMA crossover (fast above slow) bullish signal",
        confidence_threshold=0.7
    ),
}

# ============================================================================
# MEAN REVERSION STRATEGIES
# ============================================================================

REVERSION_STRATEGIES = {
    "oversold_bounce": StrategyRequirements(
        name="oversold_bounce",
        strategy_type=StrategyType.MEAN_REVERSION,
        required_fields=[
            DataField.CLOSE,
            DataField.RSI,
            DataField.BB_LOWER,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.STOCHASTIC,
            DataField.VOLUME,
            DataField.VOLUME_RATIO
        ],
        optional_fields=[
            DataField.SUPPORT,
            DataField.ATR
        ],
        not_needed_fields=[
            DataField.TREND_STRENGTH,
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="Oversold bounce from lower Bollinger Band",
        confidence_threshold=0.68
    ),
    
    "overbought_rejection": StrategyRequirements(
        name="overbought_rejection",
        strategy_type=StrategyType.MEAN_REVERSION,
        required_fields=[
            DataField.CLOSE,
            DataField.RSI,
            DataField.BB_UPPER,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.STOCHASTIC,
            DataField.VOLUME,
            DataField.RESISTANCE
        ],
        optional_fields=[
            DataField.VOLUME_RATIO,
            DataField.ATR
        ],
        not_needed_fields=[
            DataField.TREND_STRENGTH,
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="Overbought rejection from upper Bollinger Band",
        confidence_threshold=0.68
    ),
    
    "bollinger_squeeze": StrategyRequirements(
        name="bollinger_squeeze",
        strategy_type=StrategyType.MEAN_REVERSION,
        required_fields=[
            DataField.CLOSE,
            DataField.BB_UPPER,
            DataField.BB_LOWER,
            DataField.BB_MIDDLE,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.VOLATILITY,
            DataField.ATR,
            DataField.VOLUME
        ],
        optional_fields=[
            DataField.RSI,
            DataField.MACD
        ],
        not_needed_fields=[
            DataField.TREND_STRENGTH,
            DataField.IB_HIGH
        ],
        description="Bollinger Band squeeze expecting volatility expansion",
        confidence_threshold=0.6
    ),
}

# ============================================================================
# ML/ENSEMBLE STRATEGIES
# ============================================================================

ML_STRATEGIES = {
    "ml_momentum": StrategyRequirements(
        name="ml_momentum",
        strategy_type=StrategyType.ML_BASED,
        required_fields=[
            DataField.CLOSE,
            DataField.VOLUME,
            DataField.RSI,
            DataField.MACD,
            DataField.PATTERN_NAME
        ],
        recommended_fields=[
            DataField.EMA_FAST,
            DataField.EMA_SLOW,
            DataField.VOLUME_RATIO,
            DataField.ATR
        ],
        optional_fields=[
            DataField.SENTIMENT,
            DataField.NEWS_SCORE
        ],
        not_needed_fields=[
            DataField.IB_HIGH,
            DataField.IB_LOW
        ],
        description="Machine learning based momentum prediction",
        confidence_threshold=0.8,
        min_data_points=100
    ),
}

# ============================================================================
# COMPREHENSIVE STRATEGY REGISTRY
# ============================================================================

STRATEGY_REGISTRY = {
    **BREAKOUT_STRATEGIES,
    **TREND_STRATEGIES,
    **REVERSION_STRATEGIES,
    **ML_STRATEGIES
}

# ============================================================================
# STRATEGY PROCESSING LOGIC
# ============================================================================

class StrategyProcessor:
    """Processes alerts based on strategy-specific requirements"""
    
    def __init__(self):
        self.registry = STRATEGY_REGISTRY
        
    def get_strategy_requirements(self, pattern_name: str) -> StrategyRequirements:
        """Get requirements for a specific pattern"""
        pattern_key = pattern_name.lower()
        
        # Try exact match first
        if pattern_key in self.registry:
            return self.registry[pattern_key]
        
        # Try partial match
        for key, requirements in self.registry.items():
            if key in pattern_key or pattern_key in key:
                return requirements
        
        # Default to generic requirements
        return StrategyRequirements(
            name=pattern_name,
            strategy_type=StrategyType.UNKNOWN,
            required_fields=[DataField.CLOSE, DataField.PATTERN_NAME],
            recommended_fields=[],
            optional_fields=[],
            not_needed_fields=[],
            description="Unknown strategy pattern",
            confidence_threshold=0.5
        )
    
    def classify_strategy_type(self, pattern_name: str) -> StrategyType:
        """Classify strategy type based on pattern name"""
        pattern_lower = pattern_name.lower()
        
        # Breakout patterns
        if any(word in pattern_lower for word in ['breakout', 'break', 'ib_', 'box_']):
            return StrategyType.BREAKOUT
        
        # Trend patterns
        if any(word in pattern_lower for word in ['trend', 'tr', 'bullish', 'bearish', 'ema', 'macd']):
            return StrategyType.TREND_FOLLOWING
        
        # Reversion patterns
        if any(word in pattern_lower for word in ['reversion', 'oversold', 'overbought', 'bounce', 'bollinger', 'bb_']):
            return StrategyType.MEAN_REVERSION
        
        # ML patterns
        if any(word in pattern_lower for word in ['ml_', 'ai_', 'model_', 'ensemble']):
            return StrategyType.ML_BASED
        
        return StrategyType.UNKNOWN
    
    def validate_alert_for_strategy(self, alert_data: Dict) -> Dict:
        """Validate alert data against strategy requirements"""
        pattern_name = alert_data.get('pattern', 'unknown')
        requirements = self.get_strategy_requirements(pattern_name)
        
        # Check if we have required data
        is_valid, missing_fields = requirements.validate_alert_data(alert_data)
        validation_score = requirements.get_validation_score(alert_data)
        
        # Determine if missing fields are critical
        critical_missing = [
            field for field in missing_fields 
            if DataField(field) in requirements.required_fields
        ]
        
        # Check for unnecessary fields (warnings)
        unnecessary_fields = []
        for field in requirements.not_needed_fields:
            if field.value in alert_data:
                unnecessary_fields.append(field.value)
        
        return {
            'pattern': pattern_name,
            'strategy_type': requirements.strategy_type.value,
            'is_valid': is_valid,
            'validation_score': validation_score,
            'missing_required': missing_fields,
            'critical_missing': critical_missing,
            'unnecessary_fields': unnecessary_fields,
            'confidence_threshold': requirements.confidence_threshold,
            'description': requirements.description
        }
    
    def suggest_missing_data(self, alert_data: Dict) -> List[str]:
        """Suggest what data is missing for optimal processing"""
        pattern_name = alert_data.get('pattern', 'unknown')
        requirements = self.get_strategy_requirements(pattern_name)
        
        suggestions = []
        
        # Check required fields
        for field in requirements.required_fields:
            if field.value not in alert_data:
                suggestions.append(f"REQUIRED: {field.value} - {self._get_field_description(field)}")
        
        # Check recommended fields
        for field in requirements.recommended_fields:
            if field.value not in alert_data:
                suggestions.append(f"RECOMMENDED: {field.value} - {self._get_field_description(field)}")
        
        return suggestions
    
    def _get_field_description(self, field: DataField) -> str:
        """Get human-readable description of data field"""
        descriptions = {
            DataField.CLOSE: "Closing price",
            DataField.IB_HIGH: "Initial Balance high",
            DataField.IB_LOW: "Initial Balance low",
            DataField.BOX_HIGH: "Box pattern high",
            DataField.BOX_LOW: "Box pattern low",
            DataField.RSI: "Relative Strength Index (0-100)",
            DataField.TREND_STRENGTH: "Trend strength (weak/medium/strong)",
            DataField.VOLUME: "Trading volume",
            DataField.VOLUME_RATIO: "Volume relative to average",
            DataField.EMA_FAST: "Fast Exponential Moving Average",
            DataField.EMA_SLOW: "Slow Exponential Moving Average",
            DataField.MACD: "MACD value",
            DataField.MACD_SIGNAL: "MACD signal line",
            DataField.BB_UPPER: "Upper Bollinger Band",
            DataField.BB_LOWER: "Lower Bollinger Band",
            DataField.STOCHASTIC: "Stochastic oscillator",
            DataField.ATR: "Average True Range",
            DataField.VOLATILITY: "Price volatility",
            DataField.TIMEFRAME: "Chart timeframe",
            DataField.PATTERN_NAME: "Strategy pattern name",
        }
        
        return descriptions.get(field, field.value)
    
    def get_processing_instructions(self, pattern_name: str) -> Dict:
        """Get instructions for how to process this strategy"""
        requirements = self.get_strategy_requirements(pattern_name)
        
        instructions = {
            'strategy_type': requirements.strategy_type.value,
            'description': requirements.description,
            'data_needed': {
                'required': [f.value for f in requirements.required_fields],
                'recommended': [f.value for f in requirements.recommended_fields],
                'optional': [f.value for f in requirements.optional_fields],
                'not_needed': [f.value for f in requirements.not_needed_fields]
            },
            'confidence_threshold': requirements.confidence_threshold,
            'processing_hint': self._get_processing_hint(requirements.strategy_type)
        }
        
        return instructions
    
    def _get_processing_hint(self, strategy_type: StrategyType) -> str:
        """Get hint for how to process this strategy type"""
        hints = {
            StrategyType.BREAKOUT: "Focus on price relative to IB/Box levels. Volume confirmation increases confidence.",
            StrategyType.TREND_FOLLOWING: "Focus on trend strength and momentum indicators. RSI extremes may indicate exhaustion.",
            StrategyType.MEAN_REVERSION: "Focus on extreme readings in oscillators and distance from moving averages.",
            StrategyType.ML_BASED: "Use model predictions with caution. Consider as one input among many.",
            StrategyType.UNKNOWN: "Process with conservative defaults. Validate all inputs carefully."
        }
        
        return hints.get(strategy_type, "Process with caution.")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def list_all_strategies() -> List[str]:
    """List all registered strategies"""
    return list(STRATEGY_REGISTRY.keys())

def list_strategies_by_type(strategy_type: StrategyType) -> List[str]:
    """List strategies filtered by type"""
    return [
        name for name, req in STRATEGY_REGISTRY.items()
        if req.strategy_type == strategy_type
    ]

def get_strategy_summary() -> Dict:
    """Get summary of all strategies"""
    summary = {
        'total_strategies': len(STRATEGY_REGISTRY),
        'by_type': {},
        'breakout_strategies': list(BREAKOUT_STRATEGIES.keys()),
        'trend_strategies': list(TREND_STRATEGIES.keys()),
        'reversion_strategies': list(REVERSION_STRATEGIES.keys()),
        'ml_strategies': list(ML_STRATEGIES.keys())
    }
    
    for strategy in STRATEGY_REGISTRY.values():
        strategy_type = strategy.strategy_type.value
        if strategy_type not in summary['by_type']:
            summary['by_type'][strategy_type] = 0
        summary['by_type'][strategy_type] += 1
    
    return summary

# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_strategy_processor() -> StrategyProcessor:
    """Initialize and return a strategy processor"""
    processor = StrategyProcessor()
    
    logger.info(f"Strategy processor initialized with {len(STRATEGY_REGISTRY)} strategies")
    summary = get_strategy_summary()
    
    for strategy_type, count in summary['by_type'].items():
        logger.info(f"  {strategy_type}: {count} strategies")
    
    return processor

# Singleton instance
_strategy_processor = None

def get_strategy_processor() -> StrategyProcessor:
    """Get or create singleton strategy processor"""
    global _strategy_processor
    if _strategy_processor is None:
        _strategy_processor = initialize_strategy_processor()
    return _strategy_processor

# ============================================================================
# MAIN EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    processor = initialize_strategy_processor()
    
    # Test with your AMD alert
    amd_alert = {
        'ticker': 'AMD',
        'interval': '5m',
        'pattern': '3-1_breakout_long',
        'close': 217.51,
        'ib_high': 217.67,
        'ib_low': 216.73,
        'message': '3-1 long breakout on AMD',
        # Note: No RSI, no trend_strength - which is FINE for breakout!
    }
    
    validation_result = processor.validate_alert_for_strategy(amd_alert)
    
    print("\n=== STRATEGY VALIDATION RESULT ===")
    print(f"Pattern: {validation_result['pattern']}")
    print(f"Strategy Type: {validation_result['strategy_type']}")
    print(f"Valid: {validation_result['is_valid']}")
    print(f"Validation Score: {validation_result['validation_score']:.2%}")
    print(f"Missing Required: {validation_result['missing_required']}")
    print(f"Critical Missing: {validation_result['critical_missing']}")
    print(f"Unnecessary Fields: {validation_result['unnecessary_fields']}")
    print(f"Description: {validation_result['description']}")
    
    print("\n=== SUGGESTIONS ===")
    suggestions = processor.suggest_missing_data(amd_alert)
    if suggestions:
        for suggestion in suggestions:
            print(f"  - {suggestion}")
    else:
        print("  All required data present!")
    
    print("\n=== PROCESSING INSTRUCTIONS ===")
    instructions = processor.get_processing_instructions('3-1_breakout_long')
    print(f"Strategy Type: {instructions['strategy_type']}")
    print(f"Confidence Threshold: {instructions['confidence_threshold']}")
    print(f"Processing Hint: {instructions['processing_hint']}")
    print("\nRequired Data:")
    for field in instructions['data_needed']['required']:
        print(f"  - {field}")
    
    # Show that RSI is NOT needed for breakout
    print("\nData NOT needed for this strategy:")
    for field in instructions['data_needed']['not_needed']:
        print(f"  - {field}")
