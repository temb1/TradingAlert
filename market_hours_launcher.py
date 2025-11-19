#!/usr/bin/env python3
import pytz
from datetime import datetime, time, timedelta
import holidays
import os
import time
import subprocess
import sys
import requests
import json
import threading

def send_discord_message(message, webhook_url=None):
    """Send message to Discord"""
    try:
        if webhook_url is None:
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
            
        if not webhook_url:
            print("❌ No Discord webhook URL configured")
            return False

        embed = {
            "title": "📈 Market Hours Bot",
            "description": message,
            "color": 3066993 if "open" in message.lower() else 15158332 if "close" in message.lower() else 10181046,
            "timestamp": datetime.now().isoformat()
        }

        payload = {
            "embeds": [embed],
            "username": "Market Hours Manager",
            "avatar_url": "https://img.icons8.com/color/96/000000/stock-share.png"
        }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 204:
            print(f"✅ Discord notification sent: {message}")
            return True
        else:
            print(f"❌ Discord error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Discord send error: {e}")
        return False

def is_market_open():
    """Check if US stock market is currently open"""
    try:
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        # Check if weekend
        if now_et.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        
        # Check if holiday
        us_holidays = holidays.US(years=now_et.year)
        if now_et.date() in us_holidays:
            return False
        
        # Check market hours (9:00 AM - 4:00 PM ET)
        # Create time objects for comparison
        market_open_time = time(8, 45)  # 8:45 AM ET
        market_close_time = time(16, 5)  # 4:05 PM ET
        current_time = now_et.time()
        
        return market_open_time <= current_time <= market_close_time
        
    except Exception as e:
        print(f"⚠️ Error checking market hours: {e}")
        import traceback
        print(f"⚠️ Full traceback: {traceback.format_exc()}")
        return True  # Default to open if we can't determine

def get_market_schedule():
    """Get today's market schedule"""
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    
    us_holidays = holidays.US(years=now_et.year)
    
    if now_et.weekday() >= 5:
        return "WEEKEND"
    elif now_et.date() in us_holidays:
        return "HOLIDAY"
    elif now_et.time() < time(9, 25):
        return "PRE_MARKET"
    elif now_et.time() > time(16, 5):
        return "AFTER_HOURS"
    else:
        return "MARKET_OPEN"

def get_next_market_open():
    """Calculate when the market next opens"""
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    
    # Start with tomorrow
    next_day = now_et + timedelta(days=1)
    next_day = next_day.replace(hour=9, minute=25, second=0, microsecond=0)
    
    # Keep moving forward until we find a market day
    us_holidays = holidays.US(years=now_et.year)
    while True:
        if next_day.weekday() < 5 and next_day.date() not in us_holidays:
            return next_day
        next_day += timedelta(days=1)

def wait_until_market_open():
    """Wait until market opens, checking every minute"""
    eastern = pytz.timezone('US/Eastern')
    schedule = get_market_schedule()
    
    if schedule == "WEEKEND":
        message = "📅 Market closed for the weekend. Bot is sleeping."
    elif schedule == "HOLIDAY":
        message = "🎄 Market closed for holiday. Bot is sleeping."
    else:
        message = "🌙 Market closed for the day. Bot is sleeping."
    
    print(f"💤 {message}")
    send_discord_message(message)
    
    last_status_hour = -1
    
    while True:
        if is_market_open():
            market_open_message = "🚀 **MARKET OPENED** - Trading bot is now active and ready for alerts!"
            print("✅ Market is open! Starting app...")
            send_discord_message(market_open_message)
            return True
            
        # Sleep for 1 minute and check again
        time.sleep(60)
        
        # Print status every hour
        now_et = datetime.now(eastern)
        if now_et.hour != last_status_hour:
            last_status_hour = now_et.hour
            
            next_open = get_next_market_open()
            hours_until_open = (next_open - now_et).total_seconds() / 3600
            
            if hours_until_open < 24:
                status_message = f"⏰ Next market open: {next_open.strftime('%I:%M %p %Z')} ({hours_until_open:.1f} hours)"
            else:
                days_until_open = hours_until_open / 24
                status_message = f"⏰ Next market open: {next_open.strftime('%A %I:%M %p %Z')} ({days_until_open:.1f} days)"
            
            print(status_message)

def market_hours_monitor():
    """Background thread to monitor market hours and send notifications"""
    last_market_state = None
    
    while True:
        current_market_state = is_market_open()
        
        # Send notification on state change
        if last_market_state is not None and current_market_state != last_market_state:
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)
            
            if current_market_state:
                message = f"🚀 **MARKET OPENED** at {now_et.strftime('%I:%M %p %Z')} - Trading bot is active!"
            else:
                message = f"🔴 **MARKET CLOSED** at {now_et.strftime('%I:%M %p %Z')} - Bot will ignore trades until tomorrow"
            
            send_discord_message(message)
        
        last_market_state = current_market_state
        time.sleep(60)  # Check every minute

def is_development_mode():
    """Check if development mode is enabled"""
    return os.environ.get("DEVELOPMENT_MODE", "false").lower() == "true"

def should_run_app():
    """Determine if the app should run based on mode and market hours"""
    if is_development_mode():
        return True  # Always run in development mode
    else:
        return is_market_open()  # Only run during market hours in production

def run_flask_app():
    """Start the Flask application"""
    try:
        from app import app
        port = int(os.environ.get('PORT', 10000))
        print(f"🌐 Flask app starting on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
        return True
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
        return False

def development_mode_loop():
    """Run in development mode - app runs 24/7 with restart on crash"""
    print("🔧 DEVELOPMENT MODE: Running 24/7 with auto-restart")
    
    startup_message = "🔧 **DEVELOPMENT MODE ACTIVATED**\nBot running 24/7 for testing and updates"
    send_discord_message(startup_message)
    
    while True:
        print("🏁 Starting Flask app in development mode...")
        success = run_flask_app()
        
        if not success:
            print("🔄 Development mode: App crashed, restarting in 10 seconds...")
            time.sleep(10)
        else:
            # App exited normally (shouldn't happen in production)
            print("⚠️ Development mode: App exited normally, restarting in 5 seconds...")
            time.sleep(5)

def production_mode_loop():
    """Run in production mode - only during market hours"""
    print("🏭 PRODUCTION MODE: Running during market hours only")
    
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    
    startup_message = f"🤖 **TRADING BOT STARTED**\nCurrent time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}\nMarket hours: 9:30 AM - 4:00 PM ET\nBot only processes trades during market hours."
    send_discord_message(startup_message)
    
    # Start market hours monitor in background thread
    monitor_thread = threading.Thread(target=market_hours_monitor, daemon=True)
    monitor_thread.start()
    
    while True:
        if is_market_open():
            print("🏁 Market open - starting Flask app...")
            success = run_flask_app()
            
            if not success:
                print("❌ App crashed during market hours! Attempting restart...")
                crash_message = "🔴 **TRADING BOT CRASHED** during market hours! Attempting restart..."
                send_discord_message(crash_message)
                time.sleep(30)  # Wait 30 seconds before restart attempt
            else:
                # App exited normally (market closed)
                close_message = "🔴 **MARKET CLOSED** - Trading bot is shutting down. See you tomorrow!"
                print("🛑 Market closed - stopping app...")
                send_discord_message(close_message)
        else:
            # Market is closed - wait until it opens
            wait_until_market_open()

def main():
    """Main launcher with development/production mode support"""
    print("🚀 Market Hours Launcher Started")
    
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    print(f"📅 Current time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Determine mode
    if is_development_mode():
        print("🔧 DEVELOPMENT MODE DETECTED")
        print("💡 To switch to production, set DEVELOPMENT_MODE=false in environment variables")
        development_mode_loop()
    else:
        print("🏭 PRODUCTION MODE DETECTED") 
        print("💡 To switch to development, set DEVELOPMENT_MODE=true in environment variables")
        production_mode_loop()

if __name__ == "__main__":
    main()
