import tempfile
import shutil
import time
from pathlib import Path

from playwright.sync_api import (
    Error,
    TimeoutError,
)

from services.browser import browser_manager

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d"


class ChartDownloader:

    def __init__(self):
        browser_manager.start()

    def _open_page(self, ticker: str):

        page = browser_manager.new_page()

        url = FINVIZ_URL.format(ticker=ticker.upper())

        print(f"[Chart] Opening {ticker}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(3000)

        print("[Chart] Page ready")
        print("========== PAGE TITLE ==========")
        print(page.title())

        print("========== CURRENT URL ==========")
        print(page.url)

        print("========== PAGE BODY ==========")
        try:
            print(page.locator("body").inner_text(timeout=5000)[:3000])
        except Exception as e:
            print(e)

        page.screenshot(path="page.png", full_page=True)
        print("[Chart] Screenshot saved")

        return page

    def _download_chart(self, page):

        print("[Chart] Opening Share menu...")

        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        share_btn = page.locator("button:has-text('Share')")

        if share_btn.count() == 0:
            share_btn = page.locator("[title='Share']")

        if share_btn.count() == 0:
            share_btn = page.locator("button").filter(has_text="Share")

        print("Share buttons found:", share_btn.count())
        
        share_btn.first.wait_for(state="visible", timeout=10000)
        share_btn.first.click(timeout=10000)

        link = page.locator("a[download]").first

        print("========== DOWNLOAD INFO ==========")
        print("HREF :", link.get_attribute("href"))
        print("NAME :", link.get_attribute("download"))
        print("==================================")

        print("[Chart] Waiting download...")

        with page.expect_download(timeout=15000) as download_info:
            link.click()

        download = download_info.value

        # Download tugashini kutadi
        download.path()

        src = Path(download.path())

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",
        )

        tmp.close()

        dst = Path(tmp.name)

        # Chrome faylni bo'shatishini kutamiz
        copied = False

        for _ in range(20):

            try:
                shutil.copy2(src, dst)
                copied = True
                break

            except PermissionError:
                time.sleep(0.25)

        if not copied:
            raise Exception("Downloaded file is still locked.")

        img = dst.read_bytes()

        try:
            dst.unlink()
        except Exception:
            pass

        print(f"[Chart] Download OK ({len(img)//1024} KB)")

        return img


def get_chart(ticker: str):

    downloader = ChartDownloader()

    page = None

    try:

        page = downloader._open_page(ticker)

        return downloader._download_chart(page)

    except TimeoutError as e:
        print(f"[Chart] Timeout: {e}")

    except Error as e:
        print(f"[Chart] Playwright Error: {e}")

    except Exception as e:
        print(f"[Chart] Error: {e}")

    finally:

        try:
            if page:
                page.close()
        except Exception:
            pass

    return None
