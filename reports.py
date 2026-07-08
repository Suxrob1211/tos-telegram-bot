from datetime import datetime

import requests

from config import (
    BOT_TOKEN,
    RESULTS_CHAT_ID
)

from database import (
    get_all_signals
)


# --------------------------------------------------------
# Telegram
# --------------------------------------------------------

def send_message(text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:

        requests.post(
            url,
            json={
                "chat_id": RESULTS_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=20
        )

    except Exception as e:

        print(e)


# --------------------------------------------------------
# Kunlik hisobot
# --------------------------------------------------------

def send_daily_report():

    signals = get_all_signals()

    today = datetime.now().strftime("%Y-%m-%d")

    today_closed = []

    for signal in signals:

        if signal["exit_date"] == today:

            today_closed.append(signal)

    if not today_closed:

        print("Bugun yopilgan signal yo'q.")

        return

    lines = []

    lines.append(
        f"📅 <b>Kunlik hisobot</b>\n"
    )

    lines.append(
        datetime.now().strftime("%d-%b-%Y")
    )

    lines.append("")

    for signal in today_closed:

        status = signal["status"]

        if status == "profit":
            emoji = "✅"

        elif status == "loss":
            emoji = "❌"

        else:
            emoji = "⏳"

        lines.append(
            f"{emoji} "
            f"<code>{signal['ticker']}</code> "
            f"{signal['pct_change']:+.2f}%"
        )

    send_message("\n".join(lines))

    print("Kunlik hisobot yuborildi.")


# --------------------------------------------------------
# Oylik hisobot
# --------------------------------------------------------

def send_monthly_report():

    signals = get_all_signals()

    month = datetime.now().strftime("%Y-%m")

    month_signals = []

    for signal in signals:

        if signal["entry_date"].startswith(month):

            month_signals.append(signal)

    if not month_signals:

        return

    total = len(month_signals)

    profit = 0
    loss = 0
    expired = 0
    open_count = 0

    for signal in month_signals:

        if signal["status"] == "profit":
            profit += 1

        elif signal["status"] == "loss":
            loss += 1

        elif signal["status"] == "expired":
            expired += 1

        else:
            open_count += 1

    closed = [
        s
        for s in month_signals
        if s["pct_change"] is not None
    ]

    if closed:

        avg = (
            sum(
                s["pct_change"]
                for s in closed
            )
            / len(closed)
        )

    else:

        avg = 0

    text = f"""
📈 <b>Oylik hisobot</b>

Jami signal: <b>{total}</b>

✅ Profit: <b>{profit}</b>

❌ Loss: <b>{loss}</b>

⏳ Expired: <b>{expired}</b>

📊 Ochiq: <b>{open_count}</b>

💰 O'rtacha natija:
<b>{avg:+.2f}%</b>
"""

    send_message(text)

    print("Oylik hisobot yuborildi.")
