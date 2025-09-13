# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import time
from telegram import Bot
from telegram.error import TelegramError
import os
import logging
from datetime import datetime
import schedule
import re

# লগিং কনফিগারেশন
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
VFS_EMAIL = os.getenv('VFS_EMAIL')
VFS_PASSWORD = os.getenv('VFS_PASSWORD')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))

# VFS URLs
BASE_URL = "https://visa.vfsglobal.com"
LOGIN_URL = f"{BASE_URL}/sgp/en/prt/login"
DASHBOARD_URL = f"{BASE_URL}/sgp/en/prt/dashboard"
APPOINTMENT_URL = f"{BASE_URL}/sgp/en/prt/book-appointment"

# VFS Configuration
APPLICATION_CENTRE = "Portugal Visa Application Center, Singapore"
CATEGORY = "DP Job Seeker"
SUB_CATEGORY = "T1 Job Seeker Visa"

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def get_session():
    """Create a requests session with proper headers"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Origin': BASE_URL,
        'Referer': LOGIN_URL,
    })
    return session

def get_csrf_token(session, url):
    """Extract CSRF token from a page"""
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find CSRF token in meta tags
        csrf_meta = soup.find('meta', {'name': '_csrf'})
        if csrf_meta:
            return csrf_meta.get('content'), soup
        
        # Find CSRF token in input fields
        csrf_input = soup.find('input', {'name': '_csrf'})
        if csrf_input:
            return csrf_input.get('value'), soup
        
        # Try to find any CSRF token
        for meta_tag in soup.find_all('meta'):
            if 'csrf' in meta_tag.get('name', '').lower():
                return meta_tag.get('content'), soup
        
        logger.warning("CSRF token not found, trying to continue without it")
        return None, soup
        
    except Exception as e:
        logger.error(f"Error getting CSRF token: {str(e)}")
        return None, None

def login_to_vfs(session):
    """Login to VFS Global account"""
    try:
        logger.info("Step 1: Getting login page and CSRF token")
        
        # Get CSRF token from login page
        csrf_token, soup = get_csrf_token(session, LOGIN_URL)
        if not soup:
            return False
        
        # Prepare login data
        login_data = {
            'email': VFS_EMAIL,
            'password': VFS_PASSWORD,
        }
        
        # Add CSRF token if found
        if csrf_token:
            login_data['_csrf'] = csrf_token
        
        # Add other hidden fields
        for hidden_field in soup.find_all('input', {'type': 'hidden'}):
            name = hidden_field.get('name')
            value = hidden_field.get('value', '')
            if name and name not in login_data:
                login_data[name] = value
        
        logger.info("Step 2: Submitting login form")
        
        # Submit login form
        response = session.post(LOGIN_URL, data=login_data, timeout=30)
        
        # Check if login was successful
        if response.status_code == 200:
            if "dashboard" in response.url.lower() or "myaccount" in response.text.lower():
                logger.info("✅ Login successful! Redirected to dashboard.")
                return True
            elif "sign in" not in response.text.lower():
                logger.info("✅ Login might be successful (no sign-in page detected)")
                return True
            else:
                logger.error("❌ Login failed - still on login page")
                return False
        else:
            logger.error(f"❌ Login failed with status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return False

def navigate_to_appointment(session):
    """Navigate to appointment booking page"""
    try:
        logger.info("Step 3: Navigating to appointment page")
        
        # First try to go to dashboard
        response = session.get(DASHBOARD_URL, timeout=30)
        if response.status_code != 200:
            logger.warning("Dashboard not accessible, trying direct appointment URL")
        
        # Now go to appointment page
        response = session.get(APPOINTMENT_URL, timeout=30)
        response.raise_for_status()
        
        logger.info("✅ Successfully accessed appointment page")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error navigating to appointment page: {str(e)}")
        return False

def check_slot_availability(session):
    """Check for available appointment slots"""
    try:
        logger.info("Step 4: Checking slot availability")
        
        # Get CSRF token for appointment page
        csrf_token, soup = get_csrf_token(session, APPOINTMENT_URL)
        if not soup:
            return False, "CSRF token not found"
        
        # Prepare appointment data based on your screenshots
        appointment_data = {
            'applicationCentre': APPLICATION_CENTRE,
            'category': CATEGORY,
            'subCategory': SUB_CATEGORY,
        }
        
        # Add CSRF token if found
        if csrf_token:
            appointment_data['_csrf'] = csrf_token
        
        # Add other hidden fields
        for hidden_field in soup.find_all('input', {'type': 'hidden'}):
            name = hidden_field.get('name')
            value = hidden_field.get('value', '')
            if name and name not in appointment_data:
                appointment_data[name] = value
        
        logger.info("Step 5: Submitting appointment form")
        
        # Submit appointment form
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': APPOINTMENT_URL,
            'Origin': BASE_URL
        }
        
        response = session.post(APPOINTMENT_URL, data=appointment_data, headers=headers, timeout=30)
        
        # Check response for slot availability
        if response.status_code == 200:
            response_text = response.text.lower()
            
            # Check for available slots
            if "earliest available slot" in response_text:
                # Extract the date using regex
                date_match = re.search(r'(\d{2}-\d{2}-\d{4})', response.text)
                if date_match:
                    slot_date = date_match.group(1)
                    logger.info(f"✅ Slots available! Earliest slot: {slot_date}")
                    return True, f"Earliest available slot: {slot_date}"
                else:
                    logger.info("✅ Slots available! (date not extracted)")
                    return True, "Slots available (check website for dates)"
            
            # Check for no slots message
            elif "no appointment slots" in response_text or "not available" in response_text:
                logger.info("❌ No slots available")
                return False, "No appointment slots available"
            
            # Check for other messages
            elif "select time" in response_text or "choose date" in response_text:
                logger.info("✅ Slots available - date selection page")
                return True, "Slots available - date selection page shown"
            
            else:
                logger.warning("⚠️ Cannot determine slot status from page content")
                return False, "Unable to determine slot status"
        else:
            logger.error(f"❌ Appointment form failed with status: {response.status_code}")
            return False, f"HTTP Error: {response.status_code}"
            
    except Exception as e:
        logger.error(f"❌ Slot check error: {str(e)}")
        return False, f"Error: {str(e)}"

def send_telegram_notification(message):
    """টেলিগ্রাম নোটিফিকেশন পাঠানোর ফাংশন"""
    try:
        if bot and TELEGRAM_CHAT_ID:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logger.info("✅ Telegram notification sent")
            return True
        else:
            logger.warning("⚠️ Telegram not configured properly")
            return False
    except TelegramError as e:
        logger.error(f"❌ Telegram error: {str(e)}")
        return False

def job():
    """মূল job ফাংশন"""
    logger.info("🚀 Starting VFS slot check...")
    
    try:
        # Create session
        session = get_session()
        
        # Login to VFS
        if not login_to_vfs(session):
            logger.error("❌ Login failed, skipping slot check")
            return
        
        # Navigate to appointment page
        if not navigate_to_appointment(session):
            logger.error("❌ Cannot access appointment page")
            return
        
        # Check slot availability
        slots_available, message = check_slot_availability(session)
        
        if slots_available:
            # Send notification if slots are available
            notification_msg = f"🎉 VFS SLOTS AVAILABLE!\n\n"
            notification_msg += f"📍 Center: {APPLICATION_CENTRE}\n"
            notification_msg += f"📋 Category: {CATEGORY}\n"
            notification_msg += f"🔍 Sub-Category: {SUB_CATEGORY}\n"
            notification_msg += f"📅 {message}\n\n"
            notification_msg += f"⏰ Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            notification_msg += f"🔗 Login quickly: {LOGIN_URL}"
            
            send_telegram_notification(notification_msg)
        else:
            logger.info(f"No slots available: {message}")
            
    except Exception as e:
        logger.error(f"❌ Job execution error: {str(e)}")
        
        # Send error notification for critical errors
        error_msg = f"⚠️ VFS Check Error\n\nError: {str(e)}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_notification(error_msg)

def main():
    """মেইন ফাংশন"""
    logger.info("✅ VFS Slot Monitor Service Started")
    logger.info(f"⏰ Check interval: {CHECK_INTERVAL} minutes")
    logger.info(f"📧 VFS Email: {VFS_EMAIL}")
    logger.info(f"🌐 Login URL: {LOGIN_URL}")
    
    # Immediate first check
    job()
    
    # Schedule regular checks
    schedule.every(CHECK_INTERVAL).minutes.do(job)
    
    logger.info("🔄 Service is running. Press Ctrl+C to stop.")
    
    # Main loop
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("⏹️ Service stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Main loop error: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()
