import time

from config import CHECK_INTERVAL

from services.gmail import gmail
from services.parser import parser
from services.chart import chart_service


def main():

    gmail.connect()

    print()

    print("=" * 60)
    print("BOT V2 STARTED")
    print("=" * 60)

    while True:

        try:

            emails = gmail.get_unread()

            print(f"[Gmail] {len(emails)} new emails")

            for email in emails:

                scanner, tickers = parser.parse(
                    email["subject"]
                )

                print(scanner)

                print(tickers)

                for ticker in tickers:

                    page = chart_service.open(
                        ticker
                    )

                    print(
                        f"{ticker} page opened"
                    )

                    page.close()

            time.sleep(CHECK_INTERVAL)

        except Exception as e:

            print(e)

            time.sleep(10)


if __name__ == "__main__":

    main()
