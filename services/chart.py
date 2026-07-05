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

       # page.get_by_role("button", name="Share").click(timeout=10000)

       # print("[Chart] Share clicked")

       # page.wait_for_timeout(1000)

       # print("[Chart] Waiting download...")

       # with page.expect_download(timeout=15000) as download_info:
           # page.get_by_role("button", name="Download").click()

       # download = download_info.value

       # path = download.path()

       # print(f"[Chart] Downloaded: {path}")

       # with open(path, "rb") as f:
           # img = f.read()

       # print(f"[Chart] Size: {len(img)//1024} KB")

       # browser.close()

       # return img

         page.wait_for_timeout(5000)

         print("[Chart] Page loaded")

         print("[Chart] TITLE:", page.title())

         print("[Chart] URL:", page.url)

         print(page.content()[:500])

         browser.close()

         return None
