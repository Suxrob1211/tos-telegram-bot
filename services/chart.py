from playwright.sync_api import sync_playwright
import tempfile
import os


def get_chart(ticker: str):

    ticker = ticker.upper()

    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = browser.new_page(
            viewport={"width": 1700, "height": 1000},
        )

        print(f"[Chart] Opening {ticker}")

        page.goto(url, wait_until="domcontentloaded")

        print("[Chart] Page loaded")

        page.wait_for_timeout(3000)

        print("[Chart] Clicking Share")

        page.get_by_role("button", name="Share").click(timeout=10000)

        print("[Chart] Share clicked")

        page.wait_for_timeout(1000)
