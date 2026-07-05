import tempfile
from pathlib import Path

from playwright.sync_api import (
    Error,
    TimeoutError,
)

from services.browser import browser_manager


FINVIZ_URL = (
    "https://finviz.com/quote.ashx?"
    "t={ticker}&p=d"
)


class ChartDownloader:

    def __init__(self):
        browser_manager.start()

    def _open_page(self, ticker: str):

        page = browser_manager.new_page()

        url = FINVIZ_URL.format(
            ticker=ticker.upper()
        )

        print(f"[Chart] Opening {ticker}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_load_state("networkidle")

        page.wait_for_timeout(3000)

        print("[Chart] Page ready")

        return page
