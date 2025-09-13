# VFS Global Slot Monitor

This Python script automatically checks for available appointment slots on VFS Global website and sends Telegram notifications when slots are available.

## Features

- Automatically checks VFS Global every 10 minutes
- Sends instant Telegram notifications when slots are available
- Runs 24/7 on Railway

## Setup

1. **Fork this repository** on GitHub
2. **Create a Railway account** at [railway.app](https://railway.app)
3. **Connect your GitHub repository** to Railway
4. **Set environment variables** in Railway dashboard:

## Environment Variables

Set these in Railway dashboard:

- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token from @BotFather
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID (use @userinfobot to get it)
- `VFS_USERNAME` - Your VFS Global account email
- `VFS_PASSWORD` - Your VFS Global account password
- `VFS_LOGIN_URL` - VFS login URL (default: https://visa.vfsglobal.com/sgp/en/prt/login)
- `VFS_APPOINTMENT_URL` - VFS appointment URL (default: https://visa.vfsglobal.com/sgp/en/prt/book-appointment)
- `CHECK_INTERVAL` - Check interval in minutes (default: 10)

## Telegram Bot Setup

1. Message @BotFather on Telegram
2. Create a new bot with `/newbot` command
3. Copy the bot token
4. Add the bot to a chat and get chat ID using @userinfobot

## Configuration

The script is configured for:
- Application Centre: Portugal Visa Application Center, Singapore
- Category: DP Job Seeker  
- Sub-Category: T1 Job Seeker Visa

## Notes

- The script runs continuously on Railway
- Check interval can be adjusted with CHECK_INTERVAL variable
- Notifications are sent only when slots become available