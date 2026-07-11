import imaplib
import email

from config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
)


class GmailService:

    def __init__(self):

        self.mail = None

    def connect(self):

        print("Connecting Gmail...")

        self.mail = imaplib.IMAP4_SSL(
            "imap.gmail.com"
        )

        self.mail.login(
            GMAIL_USER,
            GMAIL_APP_PASSWORD,
        )

        self.mail.select("INBOX")

        print("Gmail Connected")

    def get_unread(self):

        if self.mail is None:
            self.connect()

        status, messages = self.mail.search(
            None,
            '(UNSEEN)'
        )

        ids = messages[0].split()

        emails = []

        for num in ids:

            _, data = self.mail.fetch(
                num,
                "(RFC822)"
            )

            raw = data[0][1]

            msg = email.message_from_bytes(raw)

            subject = email.header.decode_header(
                msg["Subject"]
            )[0][0]

            if isinstance(subject, bytes):
                subject = subject.decode()

            body = ""

            if msg.is_multipart():

                for part in msg.walk():

                    ctype = part.get_content_type()

                    if ctype == "text/plain":

                        body = part.get_payload(
                            decode=True
                        ).decode(
                            errors="ignore"
                        )

                        break

            else:

                body = msg.get_payload(
                    decode=True
                ).decode(
                    errors="ignore"
                )

            emails.append(

                {

                    "subject": subject,

                    "body": body,

                }

            )

        return emails


gmail = GmailService()
