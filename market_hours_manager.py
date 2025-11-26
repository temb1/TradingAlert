# Version: 9
import datetime
import pytz

class MarketHoursManager:
    def __init__(self):
        self.bot_started_today = False
        self.market_open_time = datetime.time(9, 0, 0)   # 9:00 AM ET
        self.market_close_time = datetime.time(16, 0, 0)  # 4:00 PM ET
        self.daily_reset_time = datetime.time(17, 0, 0)  # 5:00 PM ET for reset
        self.et_timezone = pytz.timezone('US/Eastern')
        self.last_reset_date = None
    
    def check_market_hours(self, current_time_str=None):
        """
        Main function to check market hours and manage bot startup messages
        """
        # Parse current time
        if current_time_str:
            current_time = datetime.datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S')
            current_time = self.et_timezone.localize(current_time)
        else:
            current_time = datetime.datetime.now(self.et_timezone)
        
        # Reset daily flag if needed
        self._reset_daily_flag_if_needed(current_time)
        
        # Check if within market hours
        if self._is_within_market_hours(current_time):
            if not self.bot_started_today:
                self.bot_started_today = True
                return self._format_startup_message(current_time)
            else:
                return self._format_ongoing_message(current_time)
        else:
            return self._format_closed_message(current_time)
    
    def _is_within_market_hours(self, current_time):
        """Check if current time is within market hours (9:00 AM - 4:00 PM ET)"""
        current_time_et = current_time.astimezone(self.et_timezone)
        current_time_only = current_time_et.time()
        
        # Check if it's a weekday (Monday=0, Friday=4)
        if current_time_et.weekday() > 4:  # Saturday or Sunday
            return False
            
        return (self.market_open_time <= current_time_only <= self.market_close_time)
    
    def _reset_daily_flag_if_needed(self, current_time):
        """Reset the daily flag for new trading days"""
        current_time_et = current_time.astimezone(self.et_timezone)
        current_date = current_time_et.date()
        current_time_only = current_time_et.time()
        
        # Reset if it's a new day
        if self.last_reset_date != current_date:
            self.bot_started_today = False
            self.last_reset_date = current_date
        # Also reset if we're after the reset time but still same day
        elif current_time_only >= self.daily_reset_time:
            self.bot_started_today = False
    
    def _format_startup_message(self, current_time):
        """Format the initial startup message"""
        return {
            "status": "TRADING_BOT_STARTED",
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S EST'),
            "market_hours": "9:00 AM - 4:00 PM ET",
            "message": "Bot only processes trades during market hours.",
            "display_format": f"""## Market Hours Bot
- **TRADING BOT STARTED**  
  Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S EST')}  
  Market hours: 9:00 AM - 4:00 PM ET  
  Bot only processes trades during market hours."""
        }
    
    def _format_ongoing_message(self, current_time):
        """Format the ongoing market hours message"""
        return {
            "status": "WITHIN_MARKET_HOURS",
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S EST'),
            "message": "Proceeding with trade analysis...",
            "display_format": f"""## Market Hours Bot
- **WITHIN MARKET HOURS**  
  Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S EST')}  
  Proceeding with trade analysis..."""
        }
    
    def _format_closed_message(self, current_time):
        """Format message for when markets are closed"""
        return {
            "status": "OUTSIDE_MARKET_HOURS",
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S EST'),
            "message": "Bot only processes trades during market hours.",
            "display_format": f"""## Market Hours Bot
- **MARKETS CLOSED**  
  Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S EST')}  
  Market hours: 9:00 AM - 4:00 PM ET  
  Bot only processes trades during market hours."""
        }

    def force_reset(self):
        """Force reset the daily flag"""
        self.bot_started_today = False
        self.last_reset_date = None
        return "Daily flag reset successfully"

def is_etf(symbol):
    """Check if a symbol is an ETF based on common patterns"""
    symbol = str(symbol).upper().strip()
    
    print(f"🔍 is_etf() called with: '{symbol}'")  # DEBUG
    
    # Common ETF suffixes and patterns
    etf_indicators = [
        # ETF suffixes
        'ETF', 'FUND', 'TRUST', 'INDEX', 'SERIES',
        # Common ETF ticker patterns
        'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'IVV', 'VTI', 'AGG',
        'GLD', 'SLV', 'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLP',
        'XLY', 'XLU', 'XLB', 'XBI', 'SOXX', 'ARKK', 'ARKQ', 'ARKW',
        'TLT', 'HYG', 'LQD', 'MBB', 'IEF', 'SHY', 'BND', 'EMB',
        'VWO', 'VEU', 'VEA', 'VXUS', 'ACWI', 'EEM', 'IEMG', 'SCHE',
        'VGK', 'EWJ', 'FEZ', 'EPP', 'VPL', 'DBO', 'USO', 'UNG',
        'GDX', 'GDXJ', 'XOP', 'OIH', 'KRE', 'XRT', 'ITB', 'XHB'
    ]
    
    # Check if symbol matches any ETF indicators
    for indicator in etf_indicators:
        if indicator in symbol:
            print(f"✅ ETF detected: '{symbol}' contains '{indicator}'")
            return True
    
    # Common single-stock patterns (definitely NOT ETFs)
    stock_indicators = [
        'NVDA', 'AMD', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN',
        'NFLX', 'GOOG', 'BRK.B', 'JPM', 'JNJ', 'V', 'PG', 'UNH', 'HD',
        'DIS', 'PYPL', 'ADBE', 'CRM', 'INTC', 'CSCO', 'PFE', 'ABT',
        'TMO', 'COST', 'TXN', 'LLY', 'AVGO', 'WMT', 'XOM', 'CVX'
    ]
    
    # If it's a known stock, definitely not an ETF
    if symbol in stock_indicators:
        print(f"❌ NOT ETF: '{symbol}' is in known stocks")
        return False
    
    # For unknown symbols, use additional checks
    # ETFs often have 3+ letters, stocks often have 1-4 letters
    if len(symbol) <= 4 and symbol.isalpha():
        print(f"❌ NOT ETF: '{symbol}' is short and alphabetic (likely stock)")
        return False
    
    print(f"❓ Unknown symbol '{symbol}' - defaulting to NOT ETF")
    return False  # Default to not ETF when uncertain

def get_trend_data(alert_data, symbol):
    """Generate trend data with correct ETF detection"""
    # Your existing trend data calculation...
    rsi = alert_data.get('rsi', 0)
    volume = alert_data.get('volume_ratio', 1.0)
    strength = alert_data.get('strength', 'unknown')
    
    # ✅ FIXED: Use proper ETF detection
    is_etf_symbol = is_etf(symbol)
    
    return {
        "rsi": rsi,
        "volume": volume,
        "strength": strength,
        "etf": is_etf_symbol
    }

def check_market_status():
    """Standalone function to check market status"""
    manager = MarketHoursManager()
    return manager.check_market_hours()

# ✅ SIMPLIFIED EXPORTS
__all__ = ['MarketHoursManager', 'check_market_status', 'is_etf']
