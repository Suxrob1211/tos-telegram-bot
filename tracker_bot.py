import asyncio
from datetime import datetime

from telegram_listener import start_listener
from tracking import check_signals
from reports import (
    send_daily_report,
    send_monthly_report,
)

from config import CHECK_INTERVAL


last_daily = ""
last_month = ""


async def tracking_loop():

    while True:

        try:

            check_signals()

        except Exception as e:

            print(f"[Tracking] {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def report_loop():

    global last_daily
    global last_month

    while True:

        now = datetime.now()

        today = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")

        try:

            if now.hour == 22 and last_daily != today:

                print("📅 Kunlik hisobot")

                send_daily_report()

                last_daily = today

            if (
                now.day == 1
                and now.hour == 0
                and last_month != month
            ):

                print("📈 Oylik hisobot")

                send_monthly_report()

                last_month = month

        except Exception as e:

            print(f"[Report] {e}")

        await asyncio.sleep(60)
        async def main():

    print("=" * 70)
    print("🚀 TOS SIGNAL TRACKER")
    print("=" * 70)

    try:

        await start_listener()

    except Exception as e:

        print(f"❌ Listener xatosi: {e}")

        return

    print("✅ Listener tayyor.")

    tracking_task = asyncio.create_task(
        tracking_loop()
    )

    report_task = asyncio.create_task(
        report_loop()
    )

    print("✅ Tracking Engine ishga tushdi.")
    print("✅ Report Engine ishga tushdi.")

    try:

        await asyncio.gather(

            tracking_task,
            report_task,

        )

    except KeyboardInterrupt:

        print("Dastur to'xtatildi.")

    except Exception as e:

        print(f"Asosiy xato: {e}")


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print("Bot to'xtadi.")
