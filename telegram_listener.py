from telethon import TelegramClient, events

from config import (
    API_ID,
    API_HASH,
    SESSION_NAME,
    SIGNAL_CHAT_ID,
)

from parser import parse_signal_message
from database import add_signal


client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)


@client.on(events.NewMessage(chats=SIGNAL_CHAT_ID))
async def new_signal(event):

    text = event.raw_text

    print("=" * 70)
    print("📨 YANGI SIGNAL")
    print(text)
    print("=" * 70)

    parsed = parse_signal_message(text)

    if parsed is None:
        print("⚠️ Parse bo'lmadi.")
        return

    if add_signal(
        parsed["ticker"],
        parsed["scanner"],
        parsed["price"]
    ):
        print(f"✅ {parsed['ticker']} qo'shildi")
    else:
        print(f"ℹ️ {parsed['ticker']} mavjud")


async def start_listener():

    print("=" * 70)
    print("🚀 Telethon ishga tushdi")
    print(f"📡 Kanal: {SIGNAL_CHAT_ID}")
    print("=" * 70)

    await client.start()

    await client.run_until_disconnected()
