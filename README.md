# VFS Global Slot Monitor

এই Python script টি স্বয়ংক্রিয়ভাবে VFS Global ওয়েবসাইটে Portugal Job Seeker Visa এর জন্য available appointment slots check করে এবং Telegram-এ notification পাঠায়।

## Features

- ✅ Automatic login to VFS Global
- ✅ Appointment slot availability check
- ✅ Telegram notifications
- ✅ Railway deployment support
- ✅ Error handling and logging

## Setup

### 1. Railway Environment Variables

নিচের environment variables গুলি Railway dashboard এ set করুন:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
VFS_EMAIL=your_vfs_email@example.com
VFS_PASSWORD=your_vfs_password_here
CHECK_INTERVAL=30
