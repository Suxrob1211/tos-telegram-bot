import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SIGNAL_CHAT_ID = int(os.getenv("SIGNAL_CHAT_ID"))
RESULTS_CHAT_ID = int(os.getenv("RESULTS_CHAT_ID"))

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_NAME = os.path.join(DATA_DIR, "tracker_session")

TARGET_PCT = 10.0
STOP_LOSS_PCT = -5.0
MAX_HOLD_DAYS = 30

CHECK_INTERVAL = 60

SIGNALS_DB = os.path.join(DATA_DIR, "signals_db.json")

LAST_MONTHLY_REPORT_FILE = os.path.join(
    DATA_DIR,
    "last_monthly_report.txt"
)
