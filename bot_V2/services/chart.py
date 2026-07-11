import tempfile
from pathlib import Path

from playwright.sync_api import (
    Error,
    TimeoutError,
)

from services.browser import browser_manager

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d&r=m6"


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

        page.set_viewport_size({
            "width": 1600,
            "height": 1200,
        })    

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
                                   
        print("[Chart] Page ready")

        return page

    def _download_chart(self, page):

        print("[Chart] Opening Share menu...")

        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        share_btn = page.get_by_role("button", name="Share")

        share_btn.wait_for(timeout=30000)

        share_btn.click()

        download_btn = page.locator("a[download]").first

        download_btn.wait_for(timeout=30000)
        
        print("[Chart] Waiting download...")
        
        with page.expect_download(timeout=30000) as download_info:

            download_btn.click()
            
        download = download_info.value
        
        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",

        )
        
        tmp.close()
        
        download.save_as(tmp.name)

        src = Path(tmp.name)

        img = src.read_bytes()

        try:
            src.unlink()
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
