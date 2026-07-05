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
        url = FINVIZ_URL.format(ticker=ticker.upper())

        print(f"[Chart] Opening {ticker}")
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )
        print("[Chart] Goto finished")
        page.wait_for_timeout(3000)
        print("[Chart] Page ready")
        return page

    def _download_chart(self, page):
        print("[Chart] Enter download_chart")
        
        print("========== BEFORE SHARE ==========")
        for a in page.locator("a").all():
            try:
                print(a.inner_text())
            except:
                pass
            print("==================================")
            
        print("[Chart] Clicking Share")
        page.locator("text=Share").first.click(timeout=10000)
        
        page.wait_for_timeout(1000)

        print("========== AFTER SHARE ==========")
        for a in page.locator("a").all():
            try:
                print(a.inner_text())
            except:
                pass
                print("=================================")

        print("[Chart] Waiting download...")
        with page.expect_download(timeout=15000) as d:
            page.locator("a[download]").click()

        download = d.value
        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",
        )
        download.save_as(tmp.name)
        path = Path(tmp.name)
        img = path.read_bytes()
        path.unlink(missing_ok=True)
        print(f"[Chart] Download OK ({len(img)//1024} KB)")
        return img


def get_chart(ticker: str):
    downloader = ChartDownloader()
    page = None
    try:
        page = downloader._open_page(ticker)
        img = downloader._download_chart(page)
        return img
    except TimeoutError as e:
        print(f"[Chart] Timeout: {e}")
    except Error as e:
        print(f"[Chart] Playwright: {e}")
    except Exception as e:
        print(f"[Chart] Error: {e}")
    finally:
        try:
            if page:
                page.close()
        except Exception:
            pass
        try:
            browser_manager.stop()
        except Exception:
            pass
    return None
