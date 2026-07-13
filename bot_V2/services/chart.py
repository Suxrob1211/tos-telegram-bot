import time

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
        print(f"[Chart] URL: {url}")

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

        page.wait_for_timeout(3000)

        print(f"[Chart] Title: {page.title()}")

        return page

    def _capture_chart(self, page):

        print("[Chart] Searching chart...")

        selectors = [

            "canvas.second",
            "canvas",

            "div[id^='chart'] canvas",

            "div[class*='chart'] canvas",

        ]

        chart = None

        for selector in selectors:

            try:

                locator = page.locator(selector)

                if locator.count() > 0:

                    chart = locator.first

                    chart.wait_for(
                        state="visible",
                        timeout=5000,
                    )

                    print(f"[Chart] Found: {selector}")

                    break

            except Exception:
                pass

        if chart is not None:

            try:

                box = chart.bounding_box()

                if box:

                    print(
                        f"[Chart] Size: {int(box['width'])}x{int(box['height'])}"
                    )

                img = chart.screenshot(
                    type="png"
                )

                print(
                    f"[Chart] Chart screenshot OK ({len(img)//1024} KB)"
                )

                return img

            except Exception as e:

                print(f"[Chart] Canvas screenshot failed: {e}")

        print("[Chart] Canvas not found -> Full page screenshot")

        img = page.screenshot(
            full_page=False,
            type="png",
        )

        print(
            f"[Chart] Page screenshot OK ({len(img)//1024} KB)"
        )

        return img


def get_chart(ticker: str):

    page = None

    try:

        downloader = ChartDownloader()

        page = downloader._open_page(ticker)

        return downloader._capture_chart(page)

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
