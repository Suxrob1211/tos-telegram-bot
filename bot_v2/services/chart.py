from config import FINVIZ_URL
from services.browser import browser


class ChartService:

    def __init__(self):
        browser.start()

    def open(self, ticker: str):

        page = browser.new_page()

        url = FINVIZ_URL.format(
            ticker=ticker.upper()
        )

        print(f"[Chart] Opening {ticker}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_load_state("networkidle")

        page.wait_for_timeout(3000)

        return page


chart_service = ChartService()
