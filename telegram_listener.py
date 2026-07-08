from telethon import TelegramClient, events

from config import (
    API_ID,
    API_HASH,
    SESSION_NAME,
    SIGNAL_CHAT_ID
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
    print("📨 Yangi signal keldi")
    print(text)
    print("=" * 70)

    parsed = parse_signal_message(text)

    if parsed is None:
        print("⚠️ Signal formati mos emas.")
        return

    success = add_signal(
        parsed["ticker"],
        parsed["scanner"],
        parsed["price"]
    )

    if success:
        print(f"✅ {parsed['ticker']} kuzatuvga qo'shildi")
    else:
        print(f"ℹ️ {parsed['ticker']} bugun allaqachon mavjud")


def start_listener():

    print("=" * 70)
    print("🚀 Telethon ishga tushdi")
    print(f"📡 Kanal ID: {SIGNAL_CHAT_ID}")
    print("=" * 70)

    client.start()

    client.run_until_disconnected()
