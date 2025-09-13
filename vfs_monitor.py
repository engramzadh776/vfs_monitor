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
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '10'))

# VFS কনফিগারেশন
APPLICATION_CENTRE = 'Portugal Visa Application Center, Singapore'
CATEGORY = 'DP Job Seeker'
SUB_CATEGORY = 'T1 Job Seeker Visa'

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def login_to_vfs():
    """VFS Global এ লগইন করার ফাংশন"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        logger.info("Loading login page...")
        response = session.get(VFS_LOGIN_URL, timeout=30)
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
        
        # লগইন request
        logger.info("Sending login request...")
        login_response = session.post(VFS_LOGIN_URL, data=login_data, timeout=30)
        
        if login_response.status_code == 200:
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
        logger.info("Checking appointment slots...")
        response = session.get(VFS_APPOINTMENT_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ফর্ম ডেটা
        form_data = {
            'applicationCentre': APPLICATION_CENTRE,
            'category': CATEGORY,
            'subCategory': SUB_CATEGORY
        }
        
        # ফর্ম submit
        appointment_response = session.post(VFS_APPOINTMENT_URL, data=form_data, timeout=30)
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