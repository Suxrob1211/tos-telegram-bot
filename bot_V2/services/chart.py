from playwright.sync_api import Error, TimeoutError

from services.browser import browser_manager

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d&r=m6"


class ChartDownloader:

    def __init__(self):
        browser_manager.start()

    def _open_page(self, ticker: str):

        page = browser_manager.new_page()

        print(f"[Chart] Page id: {id(page)}")
        print(f"[Chart] Opening {ticker}")

        url = FINVIZ_URL.format(ticker=ticker.upper())

        print(f"[Chart] URL: {url}")

        # Birinchi urinish
        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

        except TimeoutError:

            print("[Chart] First timeout -> retry")

            page.goto(
                url,
                wait_until="commit",
                timeout=30000,
            )

        page.set_viewport_size(
            {
                "width": 1600,
                "height": 1200,
            }
        )

        # Grafik chiqishini kutamiz
        page.locator("canvas").first.wait_for(
            state="visible",
            timeout=15000,
        )

        title = page.title()

        print(f"[Chart] Title : {title}")

        if ticker.upper() not in title.upper():
            raise Exception(
                f"Unexpected Finviz page : {title}"
            )

        return page

    def _find_chart(self, page):

        selectors = [

            "canvas.second",

            "canvas",

            "div[id^='chart'] canvas",

            "div[class*='chart'] canvas",

        ]

        for selector in selectors:

            try:

                locator = page.locator(selector).first

                locator.wait_for(
                    state="visible",
                    timeout=2000,
                )

                print(f"[Chart] Found : {selector}")

                return locator

            except Exception:

                pass

        return None

    def _capture_chart(self, page):

        print("[Chart] Searching chart...")

        chart = self._find_chart(page)

        if chart:

            try:

                box = chart.bounding_box()

                if box:

                    print(
                        f"[Chart] Size : {int(box['width'])}x{int(box['height'])}"
                    )

                img = chart.screenshot(
                    type="png",
                )

                print(
                    f"[Chart] Chart screenshot OK ({len(img)//1024} KB)"
                )

                return img

            except Exception as e:

                print(f"[Chart] Canvas screenshot failed : {e}")

        print("[Chart] Canvas topilmadi -> Page screenshot")

        img = page.screenshot(

            clip={
                "x": 0,
                "y": 140,
                "width": 1600,
                "height": 700,
            },

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

        img = downloader._capture_chart(page)

        if img:

            print(f"[Chart] Finviz HD OK : {ticker}")

        return img

    except TimeoutError as e:

        print(f"[Chart] Timeout : {e}")

    except Error as e:

        print(f"[Chart] Playwright Error : {e}")

    except Exception as e:

        print(f"[Chart] Error : {e}")

    finally:

        try:

            if page:

                page.close()

        except Exception:

            pass

    return None
