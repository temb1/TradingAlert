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
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        # Start 5 minutes early and end 5 minutes late for safety
        market_open = time(9, 25)  # 9:25 AM ET
        market_close = time(16, 5)  # 4:05 PM ET
        
        return market_open <= now_et.time() <= market_close
        
    except Exception as e:
        print(f"⚠️ Error checking market hours: {e}")
        return False

def get_market_schedule():
    """Get today's market schedule"""
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    
    us_holidays = holidays.US(years=now_et.year)
    
    if now_et.weekday() >= 5:
        return "WEEKEND"
    elif now_et.date() in us_holidays:
        return "HOLIDAY"
    else:
        return "TRADING_DAY"

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

def main():
    """Main launcher that only runs during market hours"""
    print("🚀 Market Hours Launcher Started")
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    print(f"📅 Current time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Send startup message
    startup_message = f"🤖 **Trading Bot Started**\nCurrent time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}\nMarket hours: 9:30 AM - 4:00 PM ET"
    send_discord_message(startup_message)
    
    while True:
        if is_market_open():
            # Market is open - start the app
            now_et = datetime.now(eastern)
            print(f"🏁 Market open! Starting Flask app at {now_et.strftime('%H:%M %Z')}...")
            
            try:
                # Start your main app - this will block until app exits
                process = subprocess.Popen([sys.executable, "app.py"])
                
                # Monitor the app while market is open
                last_health_check = datetime.now()
                while is_market_open():
                    # Check if app is still running
                    if process.poll() is not None:
                        print("❌ App crashed! Restarting...")
                        send_discord_message("⚠️ **App Crashed** - Restarting trading bot...")
                        break
                    
                    # Send health check every 30 minutes
                    if (datetime.now() - last_health_check).total_seconds() > 1800:  # 30 minutes
                        health_message = f"✅ **Bot Active** - Monitoring trades at {datetime.now(eastern).strftime('%I:%M %p %Z')}"
                        send_discord_message(health_message)
                        last_health_check = datetime.now()
                    
                    time.sleep(30)  # Check every 30 seconds
                
                # Market closed or app crashed - terminate app
                if is_market_open():
                    # App crashed during market hours
                    crash_message = "🔴 **Trading Bot Crashed** during market hours! Attempting restart..."
                    print("🛑 App crashed during market hours!")
                else:
                    # Market closed normally
                    close_message = "🔴 **MARKET CLOSED** - Trading bot is shutting down. See you tomorrow!"
                    print("🛑 Stopping app (market closed)...")
                    send_discord_message(close_message)
                
                # Terminate the app
                process.terminate()
                try:
                    process.wait(timeout=10)  # Wait 10 seconds for clean shutdown
                except subprocess.TimeoutExpired:
                    print("⚠️ App didn't terminate cleanly, killing...")
                    process.kill()
                
            except Exception as e:
                error_message = f"❌ **Critical Error** - Failed to start app: {str(e)}"
                print(f"❌ Failed to start app: {e}")
                send_discord_message(error_message)
                
        else:
            # Market is closed - wait until it opens
            wait_until_market_open()

if __name__ == "__main__":
    main()
