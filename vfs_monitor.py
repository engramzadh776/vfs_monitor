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
import random
import cloudscraper
from urllib.parse import urljoin

# লগিং কনফিগারেশন
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
VFS_USERNAME = os.getenv('VFS_USERNAME')
VFS_PASSWORD = os.getenv('VFS_PASSWORD')
VFS_BASE_URL = os.getenv('VFS_BASE_URL', 'https://visa.vfsglobal.com/sgp/en/prt/')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '45'))  # 45 minutes to avoid blocking

# VFS কনফিগারেশন
APPLICATION_CENTRE = 'Portugal Visa Application Center, Singapore'
CATEGORY = 'DP Job Seeker'
SUB_CATEGORY = 'T1 Job Seeker Visa'

# URLs
VFS_LOGIN_URL = urljoin(VFS_BASE_URL, 'login')
VFS_APPOINTMENT_URL = urljoin(VFS_BASE_URL, 'book-appointment')
VFS_DASHBOARD_URL = urljoin(VFS_BASE_URL, 'dashboard')

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def create_scraper():
    """Cloudflare bypass সহ scraper তৈরি করুন"""
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        return scraper
    except Exception as e:
        logger.warning(f"Cloudscraper init failed, using requests: {e}")
        return requests.Session()

def get_realistic_headers():
    """Realistic browser headers তৈরি করুন"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': VFS_BASE_URL
    }

def simulate_human_behavior():
    """Human-like random delays"""
    time.sleep(random.uniform(3, 8))
    time.sleep(random.uniform(1, 3))

def login_to_vfs():
    """VFS Global এ লগইন করার ফাংশন"""
    try:
        # Cloudflare bypass সহ scraper ব্যবহার করুন
        session = create_scraper()
        headers = get_realistic_headers()
        
        # First, visit homepage to get cookies
        logger.info("Visiting homepage for cookies...")
        simulate_human_behavior()
        
        home_response = session.get(VFS_BASE_URL, headers=headers, timeout=30)
        if home_response.status_code != 200:
            logger.error(f"Homepage access failed: {home_response.status_code}")
            return None
        
        # Now visit login page
        logger.info("Loading login page...")
        simulate_human_behavior()
        
        headers['Referer'] = VFS_BASE_URL
        response = session.get(VFS_LOGIN_URL, headers=headers, timeout=30)
        
        if response.status_code == 403:
            logger.error("403 Forbidden - VFS is blocking automated requests")
            return None
            
        if response.status_code != 200:
            logger.error(f"Login page failed: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all possible CSRF tokens
        csrf_tokens = {}
        for input_tag in soup.find_all('input'):
            if input_tag.get('name') and ('csrf' in input_tag.get('name').lower() or '_token' in input_tag.get('name')):
                csrf_tokens[input_tag.get('name')] = input_tag.get('value', '')
        
        # Prepare login data
        login_data = {
            'email': VFS_USERNAME,
            'password': VFS_PASSWORD
        }
        
        # Add all found CSRF tokens
        login_data.update(csrf_tokens)
        
        # Login request
        logger.info("Sending login request...")
        simulate_human_behavior()
        
        headers['Referer'] = VFS_LOGIN_URL
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        login_response = session.post(VFS_LOGIN_URL, data=login_data, headers=headers, timeout=30)
        
        # Check if login successful
        if login_response.status_code == 200:
            if "dashboard" in login_response.url or "myaccount" in login_response.url:
                logger.info("Login successful")
                return session
            else:
                logger.error("Login failed - redirect not to dashboard")
                return None
        else:
            logger.error(f"Login failed with status: {login_response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None

def check_appointment_slots(session):
    """এপয়েন্টমেন্ট স্লট চেক করার ফাংশন"""
    try:
        if not session:
            return False
            
        logger.info("Checking appointment slots...")
        simulate_human_behavior()
        
        headers = get_realistic_headers()
        headers['Referer'] = VFS_LOGIN_URL
        
        # First visit appointment page
        response = session.get(VFS_APPOINTMENT_URL, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Appointment page failed: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all form inputs
        form_data = {}
        for input_tag in soup.find_all('input'):
            if input_tag.get('name') and input_tag.get('value'):
                form_data[input_tag.get('name')] = input_tag.get('value')
        
        # Add our selections
        form_data.update({
            'applicationCentre': APPLICATION_CENTRE,
            'category': CATEGORY,
            'subCategory': SUB_CATEGORY
        })
        
        # Submit form
        simulate_human_behavior()
        
        headers['Referer'] = VFS_APPOINTMENT_URL
        appointment_response = session.post(VFS_APPOINTMENT_URL, data=form_data, headers=headers, timeout=30)
        
        if appointment_response.status_code != 200:
            logger.error(f"Appointment form failed: {appointment_response.status_code}")
            return False
        
        appointment_soup = BeautifulSoup(appointment_response.content, 'html.parser')
        
        # Check for slots
        page_text = appointment_soup.get_text().lower()
        
        if "no appointment slots are currently available" in page_text:
            logger.info("No slots available")
            return False
        elif "select time" in page_text or "available dates" in page_text:
            logger.info("SLOTS AVAILABLE!")
            return True
        else:
            logger.warning("Cannot determine slot status from page content")
            return False
            
    except Exception as e:
        logger.error(f"Slot check error: {str(e)}")
        return False

def send_telegram_notification(message):
    """টেলিগ্রাম নোটিফিকেশন পাঠানোর ফাংশন"""
    try:
        if bot and TELEGRAM_CHAT_ID:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logger.info("Telegram notification sent")
        else:
            logger.warning("Telegram not configured properly")
    except TelegramError as e:
        logger.error(f"Telegram error: {str(e)}")

def job():
    """মূল job ফাংশন"""
    logger.info("Starting VFS slot check...")
    
    session = login_to_vfs()
    
    if session:
        slots_available = check_appointment_slots(session)
        
        if slots_available:
            message = "🎉 URGENT: VFS SLOTS AVAILABLE!\n\n"
            message += f"Center: {APPLICATION_CENTRE}\n"
            message += f"Category: {CATEGORY}\n"
            message += f"Sub-Category: {SUB_CATEGORY}\n"
            message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += f"Login quickly: {VFS_LOGIN_URL}"
            
            send_telegram_notification(message)
        else:
            logger.info("No slots found, will check again later")
    else:
        logger.error("Login failed - skipping slot check")

def main():
    """মেইন ফাংশন"""
    logger.info("VFS Slot Monitor Service Started")
    logger.info(f"Check interval: {CHECK_INTERVAL} minutes")
    
    # Immediate first check
    job()
    
    # Schedule regular checks
    schedule.every(CHECK_INTERVAL).minutes.do(job)
    
    # Main loop
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            logger.error(f"Main loop error: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()
