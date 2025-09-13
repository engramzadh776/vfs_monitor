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
import re

# লগিং কনফিগারেশন
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
VFS_USERNAME = os.getenv('VFS_USERNAME')
VFS_PASSWORD = os.getenv('VFS_PASSWORD')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))  # 60 minutes

# VFS Base URLs (multiple possible endpoints)
VFS_BASE_URLS = [
    'https://visa.vfsglobal.com/sgp/en/prt/',
    'https://www.vfsglobal.com/portugal/singapore/',
    'https://portugal.vfsglobal.com/sgp/'
]

# টেলিগ্রাম বট ইনিশিয়ালাইজ
if TELEGRAM_BOT_TOKEN:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None
    logger.warning("Telegram bot token not set")

def discover_vfs_urls():
    """Automatically discover correct VFS URLs"""
    logger.info("Discovering correct VFS URLs...")
    
    for base_url in VFS_BASE_URLS:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(base_url, headers=headers, timeout=30, allow_redirects=True)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find login links
                login_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href'].lower()
                    if any(x in href for x in ['login', 'signin', 'account', 'auth']):
                        if href.startswith('http'):
                            login_links.append(href)
                        else:
                            login_links.append(base_url.rstrip('/') + '/' + href.lstrip('/'))
                
                # Find appointment links
                appointment_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href'].lower()
                    if any(x in href for x in ['appointment', 'booking', 'schedule', 'book-now']):
                        if href.startswith('http'):
                            appointment_links.append(href)
                        else:
                            appointment_links.append(base_url.rstrip('/') + '/' + href.lstrip('/'))
                
                if login_links or appointment_links:
                    logger.info(f"Found working base URL: {base_url}")
                    return base_url, login_links[0] if login_links else None, appointment_links[0] if appointment_links else None
                    
        except Exception as e:
            logger.warning(f"URL {base_url} failed: {str(e)}")
            continue
    
    return None, None, None

def get_authenticated_session():
    """Get authenticated session with correct URLs"""
    base_url, login_url, appointment_url = discover_vfs_urls()
    
    if not base_url:
        logger.error("Could not discover any working VFS URLs")
        return None, None, None
    
    # Use discovered URLs or fallback to constructed URLs
    login_url = login_url or f"{base_url.rstrip('/')}/login"
    appointment_url = appointment_url or f"{base_url.rstrip('/')}/book-appointment"
    
    logger.info(f"Using Login URL: {login_url}")
    logger.info(f"Using Appointment URL: {appointment_url}")
    
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # First get the login page to collect cookies and CSRF token
        logger.info("Fetching login page...")
        response = session.get(login_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Login page returned status: {response.status_code}")
            return None, None, None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find CSRF token
        csrf_token = None
        for input_name in ['_csrf', 'csrf_token', 'csrf', 'authenticity_token', 'token']:
            input_field = soup.find('input', {'name': input_name})
            if input_field:
                csrf_token = input_field.get('value')
                break
        
        # Prepare login data
        login_data = {
            'email': VFS_USERNAME,
            'password': VFS_PASSWORD
        }
        
        if csrf_token:
            login_data['_csrf'] = csrf_token
        
        # Add other possible hidden fields
        for hidden_field in soup.find_all('input', {'type': 'hidden'}):
            if hidden_field.get('name') and hidden_field.get('value'):
                login_data[hidden_field.get('name')] = hidden_field.get('value')
        
        # Submit login form
        logger.info("Submitting login form...")
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = login_url
        
        login_response = session.post(login_url, data=login_data, headers=headers, timeout=30)
        
        if login_response.status_code == 200:
            # Check if login was successful by looking for dashboard elements
            if any(x in login_response.text.lower() for x in ['dashboard', 'welcome', 'my account', 'logout']):
                logger.info("Login successful!")
                return session, login_url, appointment_url
            else:
                logger.error("Login failed - redirect not to dashboard")
                return None, None, None
        else:
            logger.error(f"Login failed with status: {login_response.status_code}")
            return None, None, None
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None, None, None

def check_appointment_slots(session, appointment_url):
    """এপয়েন্টমেন্ট স্লট চেক করার ফাংশন"""
    if not session or not appointment_url:
        return False
        
    try:
        logger.info("Checking appointment slots...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': appointment_url
        }
        
        # Visit appointment page
        response = session.get(appointment_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Appointment page failed: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for Portugal-specific options
        portugal_centers = []
        for option in soup.find_all('option'):
            if 'portugal' in option.get_text().lower() or 'singapore' in option.get_text().lower():
                portugal_centers.append(option.get('value'))
        
        if not portugal_centers:
            logger.error("Could not find Portugal visa center options")
            return False
        
        # Prepare form data
        form_data = {
            'applicationCentre': portugal_centers[0],
            'category': 'DP Job Seeker',
            'subCategory': 'T1 Job Seeker Visa'
        }
        
        # Submit form
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        response = session.post(appointment_url, data=form_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            page_text = response.text.lower()
            
            if "no appointment slots are currently available" in page_text:
                logger.info("No slots available")
                return False
            elif "select time" in page_text or "available dates" in page_text or "choose date" in page_text:
                logger.info("SLOTS AVAILABLE!")
                return True
            else:
                logger.warning("Cannot determine slot status")
                return False
        else:
            logger.error(f"Appointment form failed: {response.status_code}")
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
    
    session, login_url, appointment_url = get_authenticated_session()
    
    if session and appointment_url:
        slots_available = check_appointment_slots(session, appointment_url)
        
        if slots_available:
            message = "🎉 URGENT: VFS SLOTS AVAILABLE!\n\n"
            message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += f"Login quickly: {login_url}"
            
            send_telegram_notification(message)
        else:
            logger.info("No slots found, will check again later")
    else:
        logger.error("Login failed - skipping slot check")
        
        # Send error notification once per day to avoid spam
        current_hour = datetime.now().hour
        if current_hour == 12:  # Only send at 12 PM
            message = "⚠️ VFS Monitor Error\n\n"
            message += "The automated system cannot login to VFS.\n"
            message += "Please check if URLs have changed or website is down.\n\n"
            message += "Next check in 60 minutes."
            
            send_telegram_notification(message)

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
