from datetime import datetime
import requests

from config import (
    BOT_TOKEN,
    RESULTS_CHAT_ID,
)

from database import get_all_signals


# --------------------------------------------------------
# Telegram
# --------------------------------------------------------

def send_message(text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:

        response = requests.post(
            url,
            json={
                "chat_id": RESULTS_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=20,
        )

        if not response.ok:
            print("[Telegram Error]")
            print(response.text)

    except Exception as e:
        print(f"[Telegram] {e}")


# --------------------------------------------------------
# Kunlik hisobot
# --------------------------------------------------------

def send_daily_report():

    signals = get_all_signals()

    today = datetime.now().strftime("%Y-%m-%d")

    today_closed = [
        s for s in signals
        if s.get("exit_date") == today
    ]

    if not today_closed:
        print("Bugun yopilgan signal yo'q.")
        return

    text = (
        "📅 <b>Kunlik hisobot</b>\n"
        f"{datetime.now().strftime('%d-%b-%Y')}\n\n"
    )

    for signal in today_closed:

        status = signal["status"]

        if status == "profit":
            emoji = "✅"
        elif status == "loss":
            emoji = "❌"
        else:
            emoji = "⏳"

        text += (
            f"{emoji} "
            f"<code>{signal['ticker']}</code> "
            f"{signal['pct_change']:+.2f}%\n"
        )

    send_message(text)

    print("✅ Kunlik hisobot yuborildi.")


# --------------------------------------------------------
# Oylik hisobot
# --------------------------------------------------------

def send_monthly_report():

    signals = get_all_signals()

    month = datetime.now().strftime("%Y-%m")

    month_signals = [
        s for s in signals
        if s["entry_date"].startswith(month)
    ]

    if not month_signals:
        return

    total = len(month_signals)

    profit = sum(
        1 for s in month_signals
        if s["status"] == "profit"
    )

    loss = sum(
        1 for s in month_signals
        if s["status"] == "loss"
    )

    expired = sum(
        1 for s in month_signals
        if s["status"] == "expired"
    )

    open_count = sum(
        1 for s in month_signals
        if s["status"] == "open"
    )

    closed = [
        s for s in month_signals
        if s["pct_change"] is not None
    ]

    if closed:
        avg = sum(
            s["pct_change"] for s in closed
        ) / len(closed)
    else:
        avg = 0

    text = f"""
📈 <b>Oylik hisobot</b>

📊 Jami signal: <b>{total}</b>

✅ Profit: <b>{profit}</b>

❌ Loss: <b>{loss}</b>

⏳ Expired: <b>{expired}</b>

📌 Ochiq: <b>{open_count}</b>

💰 O'rtacha natija:
<b>{avg:+.2f}%</b>
"""

    send_message(text)

    print("✅ Oylik hisobot yuborildi.")
