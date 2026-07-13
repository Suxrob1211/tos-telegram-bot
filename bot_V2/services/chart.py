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

        # Sahifa ochilishidan OLDIN light-theme cookie'sini o'rnatamiz,
        # aks holda Finviz dark rejimda render qilib ulguradi
        try:
            page.context.add_cookies([
                {"name": "theme", "value": "light", "url": "https://finviz.com"},
                {"name": "darkMode", "value": "false", "url": "https://finviz.com"},
            ])
        except Exception as e:
            print(f"[Chart] Cookie sozlashda xato: {e}")

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
        # (localStorage sahifa yuklangandan keyin ham qo'shimcha himoya sifatida)
        try:
            page.evaluate("""
                () => {
                    try {
                        localStorage.setItem('theme', 'light');
                        localStorage.setItem('darkMode', 'false');
                        localStorage.setItem('colorScheme', 'light');
                        document.cookie = 'theme=light; path=/';
                        document.documentElement.classList.remove('dark');
                        document.documentElement.classList.add('light');
                        document.documentElement.setAttribute('data-theme', 'light');
                        document.body.classList.remove('dark');
                    } catch (e) {}
                }
            """)
        except Exception:
            pass

        # Agar theme almashtirish tugmasi bo'lsa va hali dark bo'lsa,
        # uni bosib ko'ramiz (Finviz UI'da toggle mavjud bo'lishi mumkin)
        try:
            is_dark = page.evaluate("""
                () => document.documentElement.classList.contains('dark')
                      || document.body.classList.contains('dark')
                      || getComputedStyle(document.body).backgroundColor.includes('rgb(0')
            """)
            if is_dark:
                toggle = page.locator(
                    '[class*="theme-toggle"], [class*="dark-mode"], button[aria-label*="theme" i]'
                ).first
                if toggle.count() > 0:
                    toggle.click(timeout=1000)
                    print("[Chart] Theme toggle bosildi")
        except Exception:
            pass

        # Sahifani qayta yuklab, cookie/localStorage kuchga kirishini ta'minlaymiz
        try:
            page.reload(wait_until="domcontentloaded", timeout=20000)
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

    def _capture_via_share_download(self, page):
        """
        Finviz'ning o'z 'Share Chart' -> 'Download' funksiyasi orqali
        toza, rasmiy PNG grafikni yuklab oladi.
        """
        # Klikni to'sib turadigan yashirin overlay/dim elementlarni olib tashlaymiz
        try:
            page.evaluate("""
                () => {
                    document.querySelectorAll(
                        '[class*="ic_dimm"], [class*="ic_under"], [class*="ic_fade"], [class*="overlay"]'
                    ).forEach(el => {
                        el.style.pointerEvents = 'none';
                        el.style.display = 'none';
                    });
                }
            """)
        except Exception:
            pass

        # "Share" tugmasini topamiz
        share_btn = page.locator(
            'button:has-text("Share"), a:has-text("Share"), [class*="share"]:has-text("Share")'
        ).first

        share_btn.wait_for(state="visible", timeout=8000)
        share_btn.scroll_into_view_if_needed(timeout=3000)

        # Force click — overlay bo'lsa ham, elementning o'ziga majburan bosadi
        try:
            share_btn.click(timeout=5000, force=True)
        except Exception:
            # Force ham ishlamasa, JS orqali to'g'ridan-to'g'ri klik hodisasini chaqiramiz
            share_btn.evaluate("el => el.click()")

        print("[Chart] Share tugmasi bosildi")

        # "Share Chart" oynasi to'liq render bo'lishini kutamiz
        try:
            page.wait_for_selector(
                'text="Share Chart"', timeout=5000
            )
            print("[Chart] 'Share Chart' modal topildi")
        except Exception:
            print("[Chart] 'Share Chart' matni topilmadi, davom etamiz")

        page.wait_for_timeout(1500)

        # Yana bir bor overlaylarni tozalaymiz (modal ochilgach yangi overlay chiqishi mumkin)
        try:
            page.evaluate("""
                () => {
                    document.querySelectorAll(
                        '[class*="ic_dimm"], [class*="ic_under"], [class*="ic_fade"]'
                    ).forEach(el => {
                        el.style.pointerEvents = 'none';
                    });
                }
            """)
        except Exception:
            pass

        # Diagnostika: modal ichidagi barcha tugmalar matnini chiqaramiz
        try:
            btn_texts = page.eval_on_selector_all(
                "button, a",
                "els => els.map(e => e.textContent.trim()).filter(t => t.length > 0 && t.length < 40)"
            )
            print(f"[Chart] Sahifadagi tugmalar: {btn_texts[:30]}")
        except Exception as e:
            print(f"[Chart] Diagnostika xato: {e}")

        # "Download" tugmasini bir nechta usulda qidiramiz
        download_selectors = [
            'button:has-text("Download")',
            'a:has-text("Download")',
            '[class*="download"]',
            'button[title*="Download" i]',
            'a[download]',
        ]

        download_btn = None
        for sel in download_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.wait_for(state="visible", timeout=3000)
                    download_btn = loc
                    print(f"[Chart] Download tugma topildi: {sel}")
                    break
            except Exception:
                continue

        if download_btn is None:
            raise Exception("Download tugmasi hech qanday selector bilan topilmadi")

        download_btn.scroll_into_view_if_needed(timeout=3000)

        with page.expect_download(timeout=15000) as download_info:
            try:
                download_btn.click(timeout=8000, force=True)
            except Exception:
                download_btn.evaluate("el => el.click()")
            print("[Chart] Download tugmasi bosildi")

        download = download_info.value

        # Yuklab olingan faylni vaqtinchalik joyga saqlab, o'qib olamiz
        import tempfile
        import os as _os

        tmp_path = _os.path.join(tempfile.gettempdir(), download.suggested_filename)
        download.save_as(tmp_path)

        with open(tmp_path, "rb") as f:
            img_bytes = f.read()

        try:
            _os.remove(tmp_path)
        except Exception:
            pass

        print(f"[Chart] Share->Download orqali olindi ({len(img_bytes)//1024} KB)")

        # Rasmni matplotlib grafik nisbatiga (12:7 ≈ 1.714:1) moslashtiramiz.
        # Finviz HD rasmi juda keng va past (ingichka) chiqadi, shuning uchun
        # yon tomonlarini kesib, kerakli nisbatga keltiramiz.
        try:
            img_bytes = self._resize_to_target_ratio(img_bytes, target_ratio=12 / 7)
        except Exception as e:
            print(f"[Chart] Qayta o'lchamlashda xato (asl rasm ishlatiladi): {e}")

        # Oynani yopamiz (keyingi ticker uchun tozalik)
        try:
            close_btn = page.locator(
                'button:has-text("Close"), [class*="modal"] button[class*="close"]'
            ).first
            if close_btn.count() > 0:
                close_btn.click(timeout=1000)
        except Exception:
            pass

        return img_bytes

    def _resize_to_target_ratio(self, img_bytes: bytes, target_ratio: float) -> bytes:
        """
        Rasmni berilgan en:bo'y nisbatiga moslaydi. Finviz rasmi juda keng
        (2560x1200 atrofida) chiqadi — kenglikni markazdan kesib (crop),
        grafik mazmuni ramkani to'liq to'ldiradigan qilamiz (padding emas,
        aks holda grafik kichkina bo'lib qolib, atrofi bo'sh ko'rinadi).
        """
        from PIL import Image
        import io as _io

        img = Image.open(_io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            # Rasm juda keng — kenglikni markazdan kesib qisqartiramiz
            new_w = int(h * target_ratio)
            x_offset = (w - new_w) // 2
            img = img.crop((x_offset, 0, x_offset + new_w, h))
        elif current_ratio < target_ratio:
            # Rasm juda tor/baland — balandlikni markazdan kesib qisqartiramiz
            new_h = int(w / target_ratio)
            y_offset = (h - new_h) // 2
            img = img.crop((0, y_offset, w, y_offset + new_h))

        out = _io.BytesIO()
        img.save(out, format="PNG")
        result = out.getvalue()
        print(f"[Chart] Qayta o'lchamlandi: {w}x{h} -> {img.size[0]}x{img.size[1]}")
        return result

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

        # 1-usul: Finviz'ning o'z Share -> Download funksiyasi orqali
        # (eng toza, rasmiy grafik)
        try:
            img = self._capture_via_share_download(page)
            if img:
                return img
        except Exception as e:
            print(f"[Chart] Share->Download muvaffaqiyatsiz: {e}")

        # 2-usul (zaxira): to'g'ridan-to'g'ri screenshot
        print("[Chart] Zaxira usul: screenshot")

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

        try:
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

        except Exception as e:
            print(f"[Chart] Page screenshot ham muvaffaqiyatsiz: {e}")
            return None


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

    # Birinchi urinish muvaffaqiyatsiz bo'lsa, toza sahifa bilan bitta
    # qo'shimcha urinish qilamiz (crash bo'lgan sahifa holatidan qutilish uchun)
    page = None
    try:

        print(f"[Chart] Qayta urinish : {ticker}")

        downloader = ChartDownloader()

        page = downloader._open_page(ticker)

        img = downloader._capture_chart(page)

        if img:

            print(f"[Chart] Qayta urinishda OK : {ticker}")

        return img

    except Exception as e:

        print(f"[Chart] Qayta urinish ham muvaffaqiyatsiz : {e}")

    finally:

        try:

            if page:

                page.close()

        except Exception:

            pass

    return None
