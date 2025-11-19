#!/usr/bin/env python3
"""
Market Hours Launcher
Main application file that uses the MarketHoursManager
"""

import datetime
import time
from market_hours_manager import MarketHoursManager

class MarketHoursLauncher:
    def __init__(self):
        self.market_hours_manager = MarketHoursManager()
        self.check_interval = 60  # seconds between checks
    
    def format_output(self, result, app_name="Market Hours Manager APP"):
        """Format the output to match your existing display style"""
        current_time_display = datetime.datetime.now().strftime("%H:%M")
        
        output = f"# {app_name} {current_time_display}\n\n"
        output += result['display_format']
        return output
    
    def run_single_check(self):
        """Perform a single market hours check"""
        result = self.market_hours_manager.check_market_hours()
        output = self.format_output(result)
        print(output)
        print("\n" + "="*50 + "\n")
        return result
    
    def run_continuous_checks(self, duration_minutes=480):
        """Run continuous checks throughout the trading day (for testing)"""
        print("Starting Market Hours Launcher - Continuous Mode")
        print("=" * 60)
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        
        while datetime.datetime.now() < end_time:
            self.run_single_check()
            time.sleep(self.check_interval)
    
    def simulate_trading_day(self):
        """Simulate a full trading day for testing purposes"""
        test_times = [
            "2025-11-19 08:00:00",  # Before open - MARKETS CLOSED
            "2025-11-19 09:05:36",  # First check after open - TRADING BOT STARTED
            "2025-11-19 10:08:13",  # Second check - WITHIN MARKET HOURS
            "2025-11-19 14:55:00",  # Third check - WITHIN MARKET HOURS
            "2025-11-19 15:08:00",  # Fourth check - WITHIN MARKET HOURS
            "2025-11-19 16:30:00",  # After close - MARKETS CLOSED
            "2025-11-20 09:05:00",  # Next day - TRADING BOT STARTED again
        ]
        
        print("Simulating Trading Day")
        print("=" * 60)
        
        for time_str in test_times:
            print(f"Simulated time: {time_str}")
            result = self.market_hours_manager.check_market_hours(time_str)
            output = self.format_output(result)
            print(output)
            print("-" * 50)

def main():
    launcher = MarketHoursLauncher()
    
    print("Market Hours Launcher")
    print("1. Run single check")
    print("2. Run continuous checks (8 hours)")
    print("3. Simulate trading day")
    print("4. Force reset daily flag")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == "1":
        launcher.run_single_check()
    elif choice == "2":
        launcher.run_continuous_checks()
    elif choice == "3":
        launcher.simulate_trading_day()
    elif choice == "4":
        result = launcher.market_hours_manager.force_reset()
        print(result)
    else:
        print("Invalid option")

if __name__ == "__main__":
    main()
