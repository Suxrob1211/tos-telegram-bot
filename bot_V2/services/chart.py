import tempfile
from pathlib import Path

from playwright.sync_api import Error, TimeoutError

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
            timeout=60000,
        )

        page.set_viewport_size(
            {
                "width": 1600,
                "height": 1200,
            }
        )

        page.wait_for_timeout(5000)

        print("[Chart] URL   :", page.url)
        print("[Chart] Title :", page.title())

        print("[Chart] Page ready")

        return page

    def _download_chart(self, page):

        print("[Chart] Opening Share menu...")

        share_btn = page.get_by_role("button", name="Share")

        if share_btn.count() == 0:
            raise Exception("Share button not found")

        share_btn.first.wait_for(timeout=10000)
        share_btn.first.click()

        download_btn = page.locator("a[download]").first

        if download_btn.count() == 0:
            raise Exception("Download button not found")

        download_btn.wait_for(timeout=10000)

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

        img = Path(tmp.name).read_bytes()

        try:
            Path(tmp.name).unlink()
        except Exception:
            pass

        print(f"[Chart] Download OK ({len(img)//1024} KB)")

        return img

    def _page_screenshot(self, page):

        print("[Chart] Screenshot fallback...")

        try:

            img = page.screenshot(
                full_page=True,
                type="png",
            )

            print(f"[Chart] Screenshot OK ({len(img)//1024} KB)")

            return img

        except Exception as e:

            print("[Chart] Screenshot failed:", e)

            return None


def get_chart(ticker: str):

    downloader = ChartDownloader()

    page = None

    try:

        page = downloader._open_page(ticker)

        try:

            return downloader._download_chart(page)

        except Exception as e:

            print(f"[Chart] Download failed: {e}")

            return downloader._page_screenshot(page)

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
