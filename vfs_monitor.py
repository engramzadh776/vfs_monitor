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
import json

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
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def debug_response(response, stage_name):
    """Debug response details"""
    logger.debug(f"{stage_name} - Status: {response.status_code}")
    logger.debug(f"{stage_name} - URL: {response.url}")
    logger.debug(f"{stage_name} - Headers: {dict(response.headers)}")
    
    if response.status_code != 200:
        logger.error(f"{stage_name} failed with status {response.status_code}")
        return False
    return True

def get_session_with_cookies():
    """Get session with proper cookies by simulating browser behavior"""
    try:
        session = requests.Session()
        
        # First, visit the main page to get initial cookies
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        logger.info("Step 1: Getting initial cookies from homepage...")
        home_response = session.get('https://visa.vfsglobal.com/', headers=headers, timeout=30)
        if not debug_response(home_response, "Homepage"):
            return None
        
        # Now visit the specific country page
        logger.info("Step 2: Visiting Singapore/Portugal page...")
        country_headers = headers.copy()
        country_headers['Referer'] = 'https://visa.vfsglobal.com/'
        
        country_response = session.get('https://visa.vfsglobal.com/sgp/en/prt/', headers=country_headers, timeout=30)
        if not debug_response(country_response, "Country Page"):
            return None
        
        # Now try to access the login page
        logger.info("Step 3: Accessing login page...")
        login_headers = headers.copy()
        login_headers['Referer'] = 'https://visa.vfsglobal.com/sgp/en/prt/'
        
        login_page_response = session.get(VFS_LOGIN_URL, headers=login_headers, timeout=30)
        if not debug_response(login_page_response, "Login Page"):
            return None
        
        return session
        
    except Exception as e:
        logger.error(f"Session creation error: {str(e)}")
        return None

def extract_login_form_data(html_content):
    """Extract all form data from login page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    form_data = {}
    
    # Find all form inputs
    for input_tag in soup.find_all('input'):
        name = input_tag.get('name')
        value = input_tag.get('value', '')
        
        if name:
            form_data[name] = value
    
    return form_data

def perform_login(session):
    """Perform the login process"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://visa.vfsglobal.com',
            'Referer': VFS_LOGIN_URL,
            'Connection': 'keep-alive',
        }
        
        # First get the login page to extract form data
        logger.info("Step 4: Getting login form data...")
        login_page_response = session.get(VFS_LOGIN_URL, headers=headers, timeout=30)
        if not debug_response(login_page_response, "Login Form"):
            return None
        
        # Extract all form fields
        form_data = extract_login_form_data(login_page_response.content)
        
        # Add login credentials
        form_data['email'] = VFS_USERNAME
        form_data['password'] = VFS_PASSWORD
        
        logger.info(f"Form data extracted: {list(form_data.keys())}")
        
        # Submit login form
        logger.info("Step 5: Submitting login form...")
        login_response = session.post(VFS_LOGIN_URL, data=form_data, headers=headers, timeout=30)
        
        if not debug_response(login_response, "Login Submit"):
            return None
        
        # Check if login was successful
        if 'dashboard' in login_response.url or 'myaccount' in login_response.url:
            logger.info("Login successful! Redirected to dashboard.")
            return session
        else:
            logger.error("Login failed - not redirected to dashboard")
            logger.error(f"Final URL: {login_response.url}")
            return None
            
    except Exception as e:
        logger.error(f"Login process error: {str(e)}")
        return None

def check_slots_directly():
    """Alternative: Check slots without login first"""
    try:
        logger.info("Trying direct slot check without login...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        # Try to access appointment page directly
        response = requests.get(VFS_APPOINTMENT_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text().lower()
            
            if "no appointment slots" in page_text:
                logger.info("Direct check: No slots available")
                return False
            elif "select date" in page_text or "available slots" in page_text:
                logger.info("Direct check: Slots might be available")
                return True
            else:
                logger.warning("Direct check: Cannot determine slot status")
                return False
        else:
            logger.error(f"Direct check failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Direct check error: {str(e)}")
        return False

def job():
    """মূল job ফাংশন"""
    logger.info("Starting VFS slot check...")
    
    # Try direct check first (without login)
    slots_available = check_slots_directly()
    
    if slots_available:
        message = "🎉 URGENT: VFS SLOTS MAY BE AVAILABLE!\n\n"
        message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "The automated system detected possible available slots.\n"
        message += f"Please login manually to check: {VFS_LOGIN_URL}\n\n"
        message += "Note: This is a direct check without login, so please verify manually."
        
        send_telegram_notification(message)
        return
    
    # If direct check didn't find slots, try full login process
    logger.info("Direct check found no slots, trying full login process...")
    
    session = get_session_with_cookies()
    if session:
        session = perform_login(session)
        
        if session:
            # Now try to check appointment slots
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': VFS_LOGIN_URL,
                }
                
                logger.info("Step 6: Checking appointment slots...")
                appointment_response = session.get(VFS_APPOINTMENT_URL, headers=headers, timeout=30)
                
                if appointment_response.status_code == 200:
                    soup = BeautifulSoup(appointment_response.content, 'html.parser')
                    page_text = soup.get_text().lower()
                    
                    if "no appointment slots" in page_text:
                        logger.info("Logged-in check: No slots available")
                    else:
                        logger.info("Logged-in check: Page loaded successfully")
                        # Additional slot checking logic would go here
                else:
                    logger.error(f"Appointment page failed: {appointment_response.status_code}")
                    
            except Exception as e:
                logger.error(f"Appointment check error: {str(e)}")
    else:
        logger.error("Failed to establish session")

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

def main():
    """মেইন ফাংশন"""
    logger.info("VFS Slot Monitor Service Started")
    logger.info(f"Check interval: {CHECK_INTERVAL} minutes")
    logger.info(f"Login URL: {VFS_LOGIN_URL}")
    logger.info(f"Appointment URL: {VFS_APPOINTMENT_URL}")
    
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
