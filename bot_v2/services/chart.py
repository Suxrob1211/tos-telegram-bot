import tempfile
from pathlib import Path

from playwright.sync_api import TimeoutError

from services.browser import browser_manager


FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d"


class ChartDownloader:

    def __init__(self):
        browser_manager.start()

    def get_chart(self, ticker: str):

        page = browser_manager.new_page()

        try:

            print(f"[Chart] Opening {ticker}")

            page.goto(
                FINVIZ_URL.format(ticker=ticker.upper()),
                wait_until="networkidle",
                timeout=60000,
            )

            page.wait_for_timeout(3000)

            print("[Chart] Selecting 6 Months...")

            page.get_by_role("button", name="Range").click()

            page.get_by_text("6 Months", exact=True).click()

            page.wait_for_timeout(2000)

            print("[Chart] Opening Share...")

            page.get_by_role("button", name="Share").click()

            with page.expect_download() as download_info:

                page.locator("a[download]").click()

            download = download_info.value

            tmp = tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=False,
            )

            tmp.close()

            download.save_as(tmp.name)

            img = Path(tmp.name).read_bytes()

            Path(tmp.name).unlink(missing_ok=True)

            print("[Chart] Download OK")

            return img

        except TimeoutError as e:

            print(e)

            return None

        finally:

            try:
                page.context.close()
            except:
                pass
