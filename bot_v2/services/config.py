import os
from dotenv import load_dotenv

load_dotenv()

# Gmail
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Browser
HEADLESS = True

# Check interval
CHECK_INTERVAL = 30

# Finviz
FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d"
