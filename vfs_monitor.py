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

# লগিং কনফিগারেশন
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
VFS_USERNAME = os.getenv('VFS_USERNAME')
VFS_PASSWORD = os.getenv('VFS_PASSWORD')
VFS_LOGIN_URL = os.getenv('VFS_LOGIN_URL', 'https://visa.vfsglobal.com/sgp/en/prt/login')
VFS_APPOINTMENT_URL = os.getenv('VFS_APPOINTMENT_URL', 'https://visa.vfsglobal.com/sgp/en/prt/book-appointment')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # Increased to 30 minutes

# VFS কনফিগারেশন
APPLICATION_CENTRE = 'Portugal Visa Application Center, Singapore'
CATEGORY = 'DP Job Seeker'
SUB_CATEGORY = 'T1 Job Seeker Visa'

# User-Agent list for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def get_random_headers():
    """Random headers তৈরি করার ফাংশন"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

def login_to_vfs():
    """VFS Global এ লগইন করার ফাংশন"""
    try:
        session = requests.Session()
        session.headers.update(get_random_headers())
        
        # Random delay add করুন
        time.sleep(random.uniform(2, 5))
        
        logger.info("Loading login page...")
        response = session.get(VFS_LOGIN_URL, timeout=30)
        
        # 403 error check করুন
        if response.status_code == 403:
            logger.error("403 Forbidden Error - VFS is blocking our requests")
            return None
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # CSRF টোকেন খুঁজুন
        csrf_token = None
        for input_name in ['_csrf', 'csrf_token', 'csrf']:
            csrf_input = soup.find('input', {'name': input_name})
            if csrf_input:
                csrf_token = csrf_input.get('value')
                break
        
        # লগইন ডেটা
        login_data = {
            'email': VFS_USERNAME,
            'password': VFS_PASSWORD
        }
        
        if csrf_token:
            login_data['_csrf'] = csrf_token
        
        # Additional headers for POST request
        post_headers = get_random_headers()
        post_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        post_headers['Referer'] = VFS_LOGIN_URL
        
        # লগইন request
        logger.info("Sending login request...")
        time.sleep(random.uniform(3, 6))  # Random delay
        
        login_response = session.post(VFS_LOGIN_URL, data=login_data, headers=post_headers, timeout=30)
        
        if login_response.status_code == 403:
            logger.error("403 Forbidden Error during login")
            return None
            
        if login_response.status_code == 200 and (VFS_USERNAME in login_response.text or "dashboard" in login_response.url):
            logger.info("Login successful")
            return session
        else:
            logger.error(f"Login failed: {login_response.status_code}")
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
        time.sleep(random.uniform(2, 4))
        
        response = session.get(VFS_APPOINTMENT_URL, timeout=30)
        
        if response.status_code == 403:
            logger.error("403 Forbidden Error - Cannot access appointment page")
            return False
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ফর্ম ডেটা
        form_data = {
            'applicationCentre': APPLICATION_CENTRE,
            'category': CATEGORY,
            'subCategory': SUB_CATEGORY
        }
        
        # Additional headers for POST request
        post_headers = get_random_headers()
        post_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        post_headers['Referer'] = VFS_APPOINTMENT_URL
        
        # ফর্ম submit
        time.sleep(random.uniform(3, 5))
        appointment_response = session.post(VFS_APPOINTMENT_URL, data=form_data, headers=post_headers, timeout=30)
        
        if appointment_response.status_code == 403:
            logger.error("403 Forbidden Error - Cannot submit appointment form")
            return False
            
        appointment_response.raise_for_status()
        
        appointment_soup = BeautifulSoup(appointment_response.content, 'html.parser')
        
        # স্লট availability check
        no_slots_text = appointment_soup.find(string=lambda text: text and "no appointment slots are currently available" in text.lower())
        
        if no_slots_text:
            logger.info("No slots available")
            return False
        else:
            logger.info("SLOTS AVAILABLE!")
            return True
            
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
