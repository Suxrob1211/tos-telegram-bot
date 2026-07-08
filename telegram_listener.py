import os
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("tracker_session", API_ID, API_HASH)

@client.on(events.NewMessage)
async def handler(event):
    chat = await event.get_chat()

    print("=" * 60)
    print("YANGI XABAR KELDI")
    print("CHAT ID:", event.chat_id)
    print("TEXT:")
    print(event.raw_text)
    print("=" * 60)

client.start()
print("Telethon ishga tushdi...")
client.run_until_disconnected()
