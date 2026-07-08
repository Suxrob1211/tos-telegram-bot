from telethon.sync import TelegramClient

api_id = 30196983
api_hash = "SIZNING_API_HASH"

client = TelegramClient("tracker_session", api_id, api_hash)

client.start()

print("Login muvaffaqiyatli!")

client.disconnect()
