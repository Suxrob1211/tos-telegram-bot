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

        # Finviz'ni majburan kunduzgi (light) rejimga o'tkazamiz
        try:
            page.evaluate("""
                () => {
                    try {
                        localStorage.setItem('theme', 'light');
                        localStorage.setItem('darkMode', 'false');
                        document.cookie = 'theme=light; path=/';
                        document.documentElement.classList.remove('dark');
                        document.documentElement.setAttribute('data-theme', 'light');
                    } catch (e) {}
                }
            """)
        except Exception:
            pass

        # Reklama / cookie / tooltip bannerlarini yopamiz
        try:
            page.evaluate("""
                () => {
                    const selectors = [
                        '[class*="cookie"]',
                        '[class*="consent"]',
                        '[class*="tooltip"]',
                        '[class*="popup"]',
                        '[class*="banner"]',
                        '[id*="cookie"]',
                        '[class*="new-compare"]',
                        '[class*="promo"]',
                        '.chart-tooltip',
                        '.overlay-tooltip',
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            el.style.display = 'none';
                            el.remove();
                        });
                    });

                    // Matn ichida "Compare" yoki "fundamentals" so'zi bo'lgan
                    // kichik overlay/tooltip elementlarni ham topib o'chiramiz
                    document.querySelectorAll('div, span, section').forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (
                            text.length > 0 && text.length < 300 &&
                            (text.includes('New Compare') ||
                             text.includes('multi-timeframe') ||
                             text.includes('sector ranking'))
                        ) {
                            el.style.display = 'none';
                            el.remove();
                        }
                    });
                }
            """)
        except Exception:
            pass

        # Grafik chiqishini kutamiz
        page.locator("canvas").first.wait_for(
            state="visible",
            timeout=15000,
        )

        # Sahifa qayta chizilishi uchun kichik kutish
        page.wait_for_timeout(1200)

        # Yana bir marta banner tozalash (kech chiqadigan tooltiplar uchun)
        try:
            page.evaluate("""
                () => {
                    document.querySelectorAll('[class*="tooltip"], [class*="popup"], [class*="new-compare"], [class*="banner"]')
                        .forEach(el => { el.style.display = 'none'; el.remove(); });

                    document.querySelectorAll('div, span, section').forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (
                            text.length > 0 && text.length < 300 &&
                            (text.includes('New Compare') ||
                             text.includes('multi-timeframe') ||
                             text.includes('sector ranking'))
                        ) {
                            el.style.display = 'none';
                            el.remove();
                        }
                    });
                }
            """)
        except Exception:
            pass

        page.wait_for_timeout(300)

        title = page.title()

        print(f"[Chart] Title : {title}")

        if ticker.upper() not in title.upper():
            raise Exception(
                f"Unexpected Finviz page : {title}"
            )

        return page

    def _find_chart(self, page):

        # Avval to'liq grafik konteynerini qidiramiz (canvas emas —
        # canvas ko'pincha juda ingichka/uzun bo'lib chiqadi)
        container_selectors = [

            "#chart-container",
            "div[class*='chart-wrap']",
            "div[id^='chart']",
            "div[class*='chart']:has(canvas)",

        ]

        for selector in container_selectors:

            try:

                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=2000)

                box = locator.bounding_box()
                # Konteyner yetarlicha katta bo'lsa (haqiqiy grafik hudud)
                if box and box["width"] > 400 and box["height"] > 250:
                    print(f"[Chart] Found container: {selector}")
                    return locator

            except Exception:
                pass

        # Konteyner topilmasa, canvas'ga tushamiz
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

                    # Agar topilgan element juda ingichka/tor bo'lsa (masalan
                    # faqat canvas, konteyner emas) — page screenshot'ga o'tamiz
                    if box["width"] < 400 or box["height"] < 200:
                        print("[Chart] Element too small, falling back to page screenshot")
                        raise ValueError("Element too small")

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
                "height": 850,
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
