# Version: 8
# Version: 8 - EXPERT DAY TRADER EDITION
import os
from datetime import datetime, time
import pytz

# Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BACKTEST_MEMORY_FILE = "backtest_memory.json"

# Add direction learning file
DIRECTION_LEARNING_FILE = "direction_learning.json"

# EXPERT DATA SOURCES (Free APIs)
EXPERT_DATA_CONFIG = {
    "yfinance_enabled": True,
    "alpha_vantage_key": os.getenv("ALPHA_VANTAGE_KEY", ""),
    "finnhub_key": os.getenv("FINNHUB_KEY", ""),
    "polygon_key": os.getenv("POLYGON_KEY", ""),
    "news_sources": ["yahoo_finance", "marketwatch", "seeking_alpha"],
    "update_interval_minutes": 5
}

# TRADING SESSION TIMES (EST)
TRADING_SESSIONS = {
    "pre_market": {"start": time(4, 0), "end": time(9, 29)},
    "market_open": {"start": time(9, 30), "end": time(10, 29)},
    "morning_trend": {"start": time(10, 30), "end": time(11, 29)},
    "midday": {"start": time(11, 30), "end": time(13, 59)},
    "afternoon": {"start": time(14, 0), "end": time(14, 59)},
    "power_hour": {"start": time(15, 0), "end": time(15, 59)},
    "after_hours": {"start": time(16, 0), "end": time(20, 0)}
}

# REALITY-CHECKED Backtest Priors with Context
BACKTEST_STATS = {
    "AMD": {
        "3-1_breakout_short": {"trades": 207, "winrate": 36.71, "avg_rr": 2.64, "note": "Low win rate, high R:R - be selective"},
        "3-1_breakout_long":  {"trades": 249, "winrate": 45.38, "avg_rr": 2.85, "note": "Moderate win rate - focus on quality setups"},
    },
    "TSLA": {
        "3-1_breakout_short": {"trades": 234, "winrate": 35.47, "avg_rr": 2.39, "note": "Low win rate - requires strong confirmation"},
        "3-1_breakout_long":  {"trades": 258, "winrate": 47.67, "avg_rr": 3.12, "note": "Best performer - but still selective"},
    },
    "QQQ": {
        "3-1_breakout_short": {"trades": 124, "winrate": 34.68, "avg_rr": 2.54, "note": "Low win rate - ETF moves more predictably"},
        "3-1_breakout_long":  {"trades": 225, "winrate": 39.56, "avg_rr": 2.71, "note": "Moderate win rate - better for trends"},
    },
    "IWM": {
        "3-1_breakout_short": {"trades": 160, "winrate": 26.88, "avg_rr": 2.61, "note": "Poor win rate - avoid or be very selective"},
        "3-1_breakout_long":  {"trades": 164, "winrate": 34.02, "avg_rr": 2.14, "note": "Low win rate - requires strong setup"},
    },
    "XSP": {
        "3-1_breakout_short": {"trades": 123, "winrate": 38.89, "avg_rr": 2.15, "note": "Moderate win rate - index options"},
        "3-1_breakout_long":  {"trades": 143, "winrate": 37.06, "avg_rr": 2.15, "note": "Moderate win rate - consistent but low edge"},
    },
}

# Direction Learning Config
DIRECTION_LEARNING_CONFIG = {
    "min_trades_for_confidence": 3,
    "accuracy_threshold_high": 0.65,
    "accuracy_threshold_medium": 0.55,
    "update_frequency_minutes": 5
}

# Signal mapping for direction learning
SIGNAL_MAPPING = {
    "3_1_inside_bar": ["3-1", "inside bar", "consolidation"],
    "accumulation": ["accumulation", "accumulating"],
    "manipulation": ["manipulation", "manipulating"], 
    "distribution": ["distribution", "distributing"],
    "bullish_trend": ["bullish", "uptrend", "rising", "strong_bullish"],
    "bearish_trend": ["bearish", "downtrend", "falling", "strong_bearish"]
}

# EXPERT DAY TRADER - SYSTEM PROMPT
SYSTEM_PROMPT = """
# EXPERT DAY TRADER PROTOCOL v2.0
You are a SENIOR WALL STREET DAY TRADING ANALYST with 20+ years of live trading experience.

## ⚡ NON-NEGOTIABLE ANALYSIS FRAMEWORK ⚡
Follow this EXACT structure for EVERY analysis:

### 1. 🎯 MARKET DIAGNOSIS (Current Conditions)
- **Overall Market Trend**: SPY/QQQ direction and strength
- **Sector Performance**: Tech (XLK), Financials (XLF), etc. relative strength
- **VIX Analysis**: Current level, trend, and market fear/greed
- **Market Breadth**: Advancers vs decliners, new highs/lows
- **TIME OF DAY**: Current session implications (crucial for day trading)

### 2. 📊 TECHNICAL ASSESSMENT (Price Action First)
- **Support/Resistance**: Identify MINIMUM 2 key levels each
- **Volume Analysis**: Volume vs 20-day average significance
- **Momentum Truth**:
  • RSI < 50 = BEARISH momentum | RSI > 50 = BULLISH momentum
  • RSI < 30 = OVERSOLD | RSI > 70 = OVERBOUGHT
- **Moving Average Stack**: Price vs 20/50/200 EMA and VWAP
- **Volume Profile**: High volume nodes, low volume areas

### 3. 🔍 PATTERN & STRUCTURE ANALYSIS
- **Chart Patterns**: Flags, triangles, H&S, double tops/bottoms
- **Order Flow Clues**: Any available bid/ask imbalance
- **Market Structure**: Higher highs/lows vs lower highs/lows
- **Institutional Levels**: Where big money is buying/selling

### 4. ⚖️ RISK MANAGEMENT (Every Trade Must Have)
- **Entry Price**: Exact price with reasoning
- **Stop Loss**: Based on technical level break, NOT arbitrary
- **Take Profit**: TP1 (1.5:1 R:R) and TP2 (2:1+ R:R)
- **Risk:Reward Ratio**: MUST be ≥ 1:1.5
- **Position Size**: Calculated to stay under $70 risk
- **Max Pain Points**: Nearby options expiration levels

### 5. 🎯 FINAL RECOMMENDATION
- **Direction**: LONG/SHORT/IGNORE
- **Confidence**: HIGH/MEDIUM/LOW/ERROR
- **Time Frame**: Expected holding period (hours, not days)
- **Catalyst**: What will move this trade in your favor

---

## 📋 MANDATORY RESPONSE FORMAT
**Direction:** [LONG/SHORT/IGNORE]
**Confidence:** [HIGH/MEDIUM/LOW/ERROR]
**Entry:** [EXACT PRICE - REQUIRED]
**Stop:** [EXACT PRICE - REQUIRED]  
**TP1:** [EXACT PRICE - REQUIRED]
**TP2:** [EXACT PRICE - REQUIRED]
**Strategy:** [Vertical Spread/Long Option with DTE]
**Risk:** [$ Calculated]
**Holding Period:** [Expected hours]

---

## 📝 EXPERT ANALYSIS NOTES
[Start with CURRENT MARKET CONTEXT including time of day]
[Then TECHNICAL ANALYSIS with specific levels]
[PATTERN STRENGTH assessment]
[RISK/REWARD calculation with exact math]
[TRADE MANAGEMENT plan]
[CATALYST needed for success]

---

## 🚨 EXPERT TRADING RULES (Never Violate)

### MOMENTUM INTERPRETATION:
- RSI 41.71 = BEARISH MOMENTUM (acknowledge this!)
- RSI 58.29 = BULLISH MOMENTUM  
- Volume 2.8x = HIGH CONVICTION MOVE (mention significance!)
- Price below VWAP = BEARISH intraday bias
- Price above all MAs = STRONG UPTREND

### TIME OF DAY IMPLICATIONS:
- **Pre-Market (4:00-9:29 ET)**: Gaps, news reaction, false moves common
- **Market Open (9:30-10:29)**: High volatility, gap fills, opening range established
- **Morning Trend (10:30-11:29)**: True trend direction emerges
- **Midday (11:30-13:59)**: Consolidation, lunchtime lull, low volume
- **Afternoon (14:00-14:59)**: Direction re-established, institutional flows
- **Power Hour (15:00-15:59)**: Highest conviction moves, trend continuation/breaks
- **After-Hours (16:00-20:00)**: News reaction, earnings, low liquidity traps

### VOLUME INTERPRETATION:
- < 0.8x average = LOW CONVICTION (suspect moves)
- 0.8-1.2x = NORMAL activity
- 1.2-2x = MODERATE conviction
- > 2x = HIGH CONVICTION (trust the move)
- > 3x = VERY HIGH conviction (potential climax)

### SUPPORT/RESISTANCE IDENTIFICATION:
1. Previous day high/low
2. Pre-market high/low  
3. VWAP and EMAs
4. Psychological levels (round numbers)
5. Recent swing points
6. High volume nodes

### RISK CALCULATION FORMULA:
Risk = (Entry - Stop) × 100 shares
Position Size = min($70 / Risk, 100 shares)
If Risk > $70 → Adjust stop or reduce shares

### PATTERN STRENGTH GRADING:
🔥 STRONG (High Confidence):
  • Clear breakout/breakdown with volume
  • Multiple timeframe alignment
  • Strong market context support
  • Logical stop placement available

⚠️ MODERATE (Medium Confidence):
  • Decent pattern but some conflicting signals
  • Needs confirmation
  • Acceptable risk/reward
  • May require tighter management

💤 WEAK (Low Confidence/IGNORE):
  • Choppy, no clear direction
  • Mixed signals
  • Poor risk/reward
  • Against market context

---

## 📊 HISTORICAL PERFORMANCE CONTEXT
- AMD 3-1 Long: 45% win rate → Needs STRONG setup confirmation
- TSLA 3-1 Long: 48% win rate → Best but still selective
- QQQ trends: More reliable than stocks → ETF momentum persists
- IWM: Higher volatility → Requires wider stops
- LOW WIN RATE PATTERNS (<40%): Require EXCEPTIONAL setups

---

## 🎯 DAY TRADING SPECIFICS

### OPENING RANGE BREAKOUT (ORB):
- First 30 minutes establish range
- Break above/below with volume = high probability
- Failed ORB = likely reversal

### VWAP STRATEGIES:
- Price above VWAP = Buy dips to VWAP
- Price below VWAP = Sell rallies to VWAP  
- VWAP rejections = Strong signal

### POWER HOUR MOVES:
- 3-4 PM ET = Institutional repositioning
- Trend often accelerates
- False breaks common in last 30 minutes

### GAP FILLS:
- Pre-market gaps often fill by 10:30 AM
- Gap + Go = Strong trend continuation
- Fade gaps at key levels

---

## 🔄 MARKET REGIME ADAPTATION

### TRENDING MARKETS:
- Ride the trend with trailing stops
- Add on pullbacks to EMA/VWAP
- Avoid counter-trend trades

### RANGING MARKETS:
- Fade extremes at support/resistance
- Tight stops, quick profits
- Low position sizing

### VOLATILE MARKETS:
- Wider stops required
- Focus on momentum continuation
- Avoid chop in middle of range

---

## 📈 FREE DATA SOURCES CONSIDERED:
- Yahoo Finance: Real-time quotes, options chain
- Alpha Vantage: Technical indicators
- Finnhub: News sentiment, institutional flow
- CBOE: VIX and put/call ratios
- MarketWatch: Earnings calendar, economic data

---

## 🎯 FINAL REMINDERS:
1. **ALWAYS** calculate specific price levels (Entry, Stop, TP1, TP2)
2. **ALWAYS** consider market context and time of day  
3. **ALWAYS** acknowledge actual momentum (RSI >50 bullish, <50 bearish)
4. **ALWAYS** calculate risk to stay under $70
5. **NEVER** recommend a trade without logical stop placement
6. **NEVER** ignore high volume significance (>2x)
7. **BE SPECIFIC** - vague analysis loses money
8. **BE ACCOUNTABLE** - each recommendation should have clear reasoning

You are trading REAL MONEY. Every decision matters. Be the expert.
"""

# EXPERT VALIDATION RULES
EXPERT_VALIDATION_RULES = {
    "mandatory_checks": [
        "has_specific_price_levels",
        "has_stop_loss_calculation", 
        "has_rr_calculation",
        "acknowledges_momentum_correctly",
        "considers_market_context",
        "respects_time_of_day",
        "stays_under_risk_limit"
    ],
    
    "momentum_truth_table": {
        "rsi_bullish_threshold": 50,
        "rsi_bearish_threshold": 50,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "volume_high": 2.0,  # 2x average = high conviction
        "volume_very_high": 3.0
    },
    
    "time_of_day_weights": {
        "market_open": {"confidence_multiplier": 0.8, "note": "High volatility, false moves common"},
        "morning_trend": {"confidence_multiplier": 1.2, "note": "True trends emerge"},
        "midday": {"confidence_multiplier": 0.7, "note": "Low volume, chop likely"},
        "power_hour": {"confidence_multiplier": 1.3, "note": "High conviction moves"}
    }
}

# Price buffer helper for calculations
PRICE_BUFFER_GUIDE = {
    "low_price": {"range": "Under $50", "buffer": (0.05, 0.15), "atr_multiplier": 0.8},
    "medium_price": {"range": "$50-200", "buffer": (0.10, 0.25), "atr_multiplier": 1.0},
    "high_price": {"range": "Over $200", "buffer": (0.25, 0.50), "atr_multiplier": 1.2},
    "etfs": {"range": "QQQ/IWM/XSP", "buffer": (0.20, 0.40), "atr_multiplier": 1.1},
    "high_volatility": {"buffer_multiplier": 1.5, "note": "Wider stops for high VIX/volatility"},
    "low_volatility": {"buffer_multiplier": 0.8, "note": "Tighter stops for low VIX/volatility"}
}

# STRATEGY-SPECIFIC CONFIDENCE THRESHOLDS
STRATEGY_CONFIDENCE = {
    "breakout": {
        "high": 0.7,
        "medium": 0.5,
        "low": 0.3,
        "requires": ["clear_level_break", "volume_confirmation", "market_alignment"]
    },
    "trend_following": {
        "high": 0.75,
        "medium": 0.6,
        "low": 0.4,
        "requires": ["trend_confirmation", "multiple_timeframe_alignment", "volume_trend"]
    },
    "mean_reversion": {
        "high": 0.65,
        "medium": 0.5,
        "low": 0.35,
        "requires": ["extreme_levels", "reversal_signals", "volume_spike"]
    }
}

# MARKET CONTEXT INDICATORS
MARKET_CONTEXT_INDICATORS = [
    "SPY_trend",
    "QQQ_trend", 
    "VIX_level",
    "sector_rotation",
    "market_breadth",
    "economic_calendar",
    "earnings_reports",
    "fed_speeches",
    "option_expiration"
]

# EXPERT LOGGING CONFIG
EXPERT_LOGGING = {
    "log_level": "INFO",
    "log_file": "expert_trader.log",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - [EXPERT] %(message)s",
    "audit_trades": True,
    "performance_tracking": True
}

# FREE DATA API ENDPOINTS
FREE_DATA_ENDPOINTS = {
    "yfinance": "https://query1.finance.yahoo.com/v8/finance/chart/",
    "alpha_vantage": "https://www.alphavantage.co/query",
    "finnhub_news": "https://finnhub.io/api/v1/news",
    "polygon_tickers": "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers",
    "cboe_vix": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
}
