import datetime
import pytz

class MarketHoursManager:
    def __init__(self):
        self.bot_started_today = False
        self.market_open_time = datetime.time(9, 00, 0)  # 9:00 AM ET
        self.market_close_time = datetime.time(16, 0, 0)  # 4:00 PM ET
        self.daily_reset_time = datetime.time(17, 0, 0)  # 5:00 PM ET for reset
        self.et_timezone = pytz.timezone('US/Eastern')
    
    def check_market_hours(self, current_time_str=None):
        """
        Main function to check market hours and manage bot startup messages
        
        Args:
            current_time_str: Optional timestamp string in 'YYYY-MM-DD HH:MM:SS' format
                           If None, uses current time
        """
        # Parse current time
        if current_time_str:
            current_time = datetime.datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S')
            current_time = self.et_timezone.localize(current_time)
        else:
            current_time = datetime.datetime.now(self.et_timezone)
        
        # Reset daily flag if needed (after market close)
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
        
        # Also check if it's a weekday (Monday=0, Friday=4)
        if current_time_et.weekday() > 4:  # Saturday or Sunday
            return False
            
        return (self.market_open_time <= current_time_only <= self.market_close_time)
    
    def _reset_daily_flag_if_needed(self, current_time):
        """Reset the daily flag after market close to prepare for next trading day"""
        current_time_et = current_time.astimezone(self.et_timezone)
        current_time_only = current_time_et.time()
        
        # Reset flag after reset time (5:00 PM) or before market open
        if current_time_only >= self.daily_reset_time or current_time_only < self.market_open_time:
            self.bot_started_today = False
    
    def _format_startup_message(self, current_time):
        """Format the initial startup message (shown only once per day)"""
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
        """Format the ongoing market hours message (shown after initial startup)"""
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
        """Force reset the daily flag (useful for testing or manual overrides)"""
        self.bot_started_today = False
        return "Daily flag reset successfully"

# Example usage and integration
def main():
    # Initialize the manager
    market_hours_manager = MarketHoursManager()
    
    # Simulate your app's time checks throughout the day
    test_times = [
        "2025-11-19 09:35:36",  # First check - should show STARTUP
        "2025-11-19 10:08:13",  # Second check - should show ONGOING
        "2025-11-19 14:55:00",  # Third check - should show ONGOING
        "2025-11-19 16:30:00",  # After close - should show CLOSED
        "2025-11-20 09:35:00",  # Next day - should show STARTUP again
    ]
    
    for time_str in test_times:
        result = market_hours_manager.check_market_hours(time_str)
        print(f"Time: {time_str}")
        print(f"Status: {result['status']}")
        print(result['display_format'])
        print("-" * 50)

if __name__ == "__main__":
    main()
