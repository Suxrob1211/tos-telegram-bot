import requests

from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)


class TelegramService:

    def send_text(self, text: str):

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        requests.post(

            url,

            data={

                "chat_id": TELEGRAM_CHAT_ID,

                "text": text,

                "parse_mode": "HTML",

            },

            timeout=30,

        )

    def send_photo(

        self,

        photo: bytes,

        caption: str,

    ):

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"

        requests.post(

            url,

            data={

                "chat_id": TELEGRAM_CHAT_ID,

                "caption": caption,

                "parse_mode": "HTML",

            },

            files={

                "photo": photo,

            },

            timeout=60,

        )


telegram = TelegramService()
