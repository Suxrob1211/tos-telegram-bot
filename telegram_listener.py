from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import (
    API_ID,
    API_HASH,
    STRING_SESSION,
    SIGNAL_CHAT_ID
)

from parser import parse_signal_message
from database import add_signal


client = TelegramClient(
    StringSession(STRING_SESSION),
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

    await client.connect()
    
    if not await client.is_user_authorized():
        raise RuntimeError("Telethon avtorizatsiya qilinmagan.")
    
    print("✅ Telethon ulandi.")
