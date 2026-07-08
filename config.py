import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SIGNAL_CHAT_ID = int(os.getenv("SIGNAL_CHAT_ID"))
RESULTS_CHAT_ID = int(os.getenv("RESULTS_CHAT_ID"))

# Telethon
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

SESSION_NAME = "tracker_session"

# Tracking
TARGET_PCT = 10.0
STOP_LOSS_PCT = -5.0
MAX_HOLD_DAYS = 30

CHECK_INTERVAL = 60

# Files
SIGNALS_DB = "signals_db.json"
LAST_MONTHLY_REPORT_FILE = "last_monthly_report.txt"
