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

        try:
            page.context.add_cookies([
                {"name": "theme", "value": "light", "url": "https://finviz.com"},
                {"name": "darkMode", "value": "false", "url": "https://finviz.com"},
            ])
        except Exception as e:
            print(f"[Chart] Cookie xato: {e}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except TimeoutError:
            print("[Chart] First timeout -> retry")
            page.goto(url, wait_until="commit", timeout=45000)

        page.set_viewport_size({"width": 1600, "height": 1200})

        # Tarmoq so'rovlari (grafik ma'lumotlari) tugashini kutamiz
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            print("[Chart] networkidle kutish vaqti tugadi, davom etamiz")

        try:
            page.evaluate("""
                () => {
                    try {
                        localStorage.setItem('theme', 'light');
                        localStorage.setItem('darkMode', 'false');
                        document.cookie = 'theme=light; path=/';
                        document.documentElement.classList.remove('dark');
                        document.body.classList.remove('dark');
                    } catch (e) {}
                }
            """)
        except Exception:
            pass

        try:
            page.reload(wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        self._dismiss_consent(page)
        self._hide_popups(page)

        try:
            page.locator("canvas").first.wait_for(state="visible", timeout=25000)
        except TimeoutError:
            print("[Chart] Canvas 25s da chiqmadi, sahifani qayta yuklab ko'ramiz")
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.locator("canvas").first.wait_for(state="visible", timeout=20000)

        page.wait_for_timeout(2000)

        self._dismiss_consent(page)
        self._hide_popups(page)

        title = page.title()
        print(f"[Chart] Title : {title}")

        if ticker.upper() not in title.upper():
            raise Exception(f"Unexpected page: {title}")

        return page

    def _dismiss_consent(self, page):
        """
        GDPR / reklama consent oynalarini yopadi yoki rad etadi
        (masalan Google CMP, sp_message, OneTrust va h.k.)
        """
        try:
            page.evaluate("""
                () => {
                    // Umumiy consent tugmalarini qidirib bosamiz
                    const texts = ['accept', 'agree', 'reject', 'i agree', 'consent', 'got it', 'ok'];
                    const btns = Array.from(document.querySelectorAll('button, a'));
                    for (const btn of btns) {
                        const t = (btn.textContent || '').trim().toLowerCase();
                        if (texts.some(x => t === x || t.includes(x))) {
                            try { btn.click(); } catch (e) {}
                        }
                    }

                    // Konteynerlarni to'g'ridan olib tashlaymiz
                    const selectors = [
                        '[id*="sp_message"]', '[class*="sp_message"]',
                        '[id*="consent"]', '[class*="consent"]',
                        '[id*="onetrust"]', '[class*="onetrust"]',
                        '[id*="cmp"]', '[class*="cmp-"]',
                        'iframe[src*="consent"]', 'iframe[title*="consent" i]',
                        '[class*="cookie"]', '[id*="cookie"]',
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            el.style.display = 'none';
                            el.remove();
                        });
                    });
                }
            """)
        except Exception as e:
            print(f"[Chart] Consent tozalashda xato: {e}")

    def _hide_popups(self, page):
        try:
            page.evaluate("""
                () => {
                    ['[class*="tooltip"]','[class*="popup"]','[class*="banner"]',
                     '[class*="promo"]','.chart-tooltip','.overlay-tooltip',
                     '[class*="new-compare"]'].forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            el.style.display = 'none'; el.remove();
                        });
                    });
                }
            """)
        except Exception:
            pass

    def _scale_image(self, img_bytes: bytes, target_width: int = 1400) -> bytes:
        """Proporsional kattalashtirish — hech narsa kesilmaydi."""
        try:
            from PIL import Image
            import io as _io

            img = Image.open(_io.BytesIO(img_bytes))
            w, h = img.size

            if w >= target_width:
                print(f"[Chart] Rasm yetarli katta: {w}x{h}")
                return img_bytes

            scale = target_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)

            img = img.resize((new_w, new_h), Image.LANCZOS)
            out = _io.BytesIO()
            img.save(out, format="PNG")
            result = out.getvalue()
            print(f"[Chart] Resize: {w}x{h} -> {new_w}x{new_h}")
            return result

        except Exception as e:
            print(f"[Chart] Resize xato: {e}")
            return img_bytes

    def _capture_via_share_download(self, page):
        """Share -> Download orqali grafik yuklab oladi."""

        self._hide_popups(page)

        # Share tugmasini JS orqali bosish
        print("[Chart] Share tugmasi bosilmoqda...")
        clicked = page.evaluate("""
            () => {
                let btn = document.querySelector('[data-testid="chart-toolbar-publish"]');
                if (!btn) {
                    const btns = Array.from(document.querySelectorAll('button, a'));
                    btn = btns.find(el => el.textContent.trim().toLowerCase().includes('share'));
                }
                if (btn) { btn.click(); return true; }
                return false;
            }
        """)

        if not clicked:
            raise Exception("Share tugmasi topilmadi")

        print("[Chart] Share bosildi, modal ochilishi kutilmoqda...")

        # Modal ochilishini kutamiz
        try:
            page.wait_for_selector('dialog[data-testid="charts-publish-modal"]', timeout=6000)
            print("[Chart] Share modal topildi")
        except Exception:
            print("[Chart] Modal selector topilmadi, davom etamiz")

        # Ichidagi grafik generatsiya spinnerini kutamiz —
        # spinner yo'qolguncha Download tugmasi hali tayyor emas
        try:
            page.wait_for_selector(
                '[data-testid="charts-publish-chart-spinner"]',
                state="hidden",
                timeout=20000,
            )
            print("[Chart] Spinner tugadi, grafik tayyor")
        except Exception:
            print("[Chart] Spinner kutish vaqti tugadi, baribir davom etamiz")

        page.wait_for_timeout(800)

        # Download tugmasini modal ICHIDA qidiramiz
        with page.expect_download(timeout=15000) as download_info:
            downloaded = page.evaluate("""
                () => {
                    const dialog = document.querySelector('dialog[data-testid="charts-publish-modal"]')
                                   || document.querySelector('[role="dialog"]')
                                   || document;

                    let btn = dialog.querySelector('a[download]');

                    if (!btn) {
                        const all = Array.from(dialog.querySelectorAll('button, a'));
                        btn = all.find(el => {
                            const t = (el.textContent || '').trim().toLowerCase();
                            return t === 'download' || t.includes('download');
                        });
                    }

                    if (!btn) {
                        // ikonka orqali (svg use href="#download")
                        const all = Array.from(dialog.querySelectorAll('button, a'));
                        btn = all.find(el => {
                            const svg = el.querySelector('use');
                            return svg && (svg.getAttribute('href') || '').includes('download');
                        });
                    }

                    if (btn) {
                        btn.click();
                        return btn.textContent.trim() || 'icon-button';
                    }
                    return null;
                }
            """)
            print(f"[Chart] Download bosildi: {downloaded}")

        download = download_info.value

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

        print(f"[Chart] Download OK ({len(img_bytes)//1024} KB)")

        img_bytes = self._scale_image(img_bytes, target_width=1400)

        # Modalni yopamiz
        try:
            page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const close = btns.find(el =>
                        (el.getAttribute('aria-label') || '').toLowerCase() === 'close' ||
                        el.textContent.trim().toLowerCase() === 'close'
                    );
                    if (close) close.click();
                }
            """)
        except Exception:
            pass

        return img_bytes

    def _capture_chart(self, page):
        # 1-usul: Share -> Download
        try:
            img = self._capture_via_share_download(page)
            if img:
                return img
        except Exception as e:
            print(f"[Chart] Share->Download muvaffaqiyatsiz: {e}")

        # 2-usul: faqat grafik konteynerini screenshot qilish
        # (butun sahifa emas — reklama/consent tushmasligi uchun)
        print("[Chart] Zaxira usul: chart container screenshot")

        self._dismiss_consent(page)
        self._hide_popups(page)
        page.wait_for_timeout(500)

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
                if box and box["width"] > 400 and box["height"] > 250:
                    img = locator.screenshot(type="png")
                    print(f"[Chart] Container screenshot OK ({len(img)//1024} KB)")
                    img = self._scale_image(img, target_width=1400)
                    return img
            except Exception:
                pass

        # 3-usul: canvas
        try:
            canvas = page.locator("canvas").first
            canvas.wait_for(state="visible", timeout=3000)
            img = canvas.screenshot(type="png")
            print(f"[Chart] Canvas screenshot OK ({len(img)//1024} KB)")
            img = self._scale_image(img, target_width=1400)
            return img
        except Exception as e:
            print(f"[Chart] Canvas screenshot muvaffaqiyatsiz: {e}")

        return None


def get_chart(ticker: str):
    page = None
    try:
        downloader = ChartDownloader()
        page = downloader._open_page(ticker)
        img = downloader._capture_chart(page)
        if img:
            print(f"[Chart] OK : {ticker}")
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

    # Qayta urinish — browser restart bilan
    page = None
    try:
        print(f"[Chart] Qayta urinish (browser restart): {ticker}")
        browser_manager.restart()
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
