from playwright.sync_api import Error, TimeoutError
from services.browser import browser_manager

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d&r=m6"

# Layout siljishi (reflow) va xotira sarfini keltirib chiqaradigan
# reklama/tracker domenlari - bularni bloklaymiz
BLOCKED_DOMAINS = [
    "doubleclick.net", "googlesyndication", "google-analytics",
    "googletagmanager", "adsystem", "facebook.net", "amazon-adsystem",
    "criteo", "taboola", "outbrain", "adnxs.com", "adservice.google",
]


class ChartDownloader:

    def __init__(self):
        browser_manager.start()

    def _block_ads(self, page):
        def _route_handler(route):
            req = route.request
            try:
                if any(b in req.url for b in BLOCKED_DOMAINS) or req.resource_type == "media":
                    route.abort()
                else:
                    route.continue_()
            except Exception:
                try:
                    route.continue_()
                except Exception:
                    pass

        try:
            page.route("**/*", _route_handler)
        except Exception as e:
            print(f"[Chart] Route bloklashda xato: {e}")

    def _safe_click(self, page, locator, label: str):
        """
        scroll_into_view_if_needed / click dagi 'stability' timeout muammosidan
        qochish uchun bosqichma-bosqich zaxira usullar bilan bosadi:
        1) scroll_into_view_if_needed (qisqa timeout, xato bo'lsa e'tiborsiz)
        2) oddiy click(force=True)
        3) bounding_box() orqali mouse koordinatasiga bosish
        4) JS orqali .click()
        """
        try:
            locator.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            print(f"[Chart] {label}: scroll_into_view timeout, davom etamiz")

        try:
            locator.click(timeout=4000, force=True)
            print(f"[Chart] {label} bosildi (click)")
            return
        except Exception as e:
            print(f"[Chart] {label} click xato: {e}")

        try:
            box = locator.bounding_box()
            if box:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
                page.mouse.move(x, y)
                page.mouse.click(x, y)
                print(f"[Chart] {label} bosildi (mouse coord)")
                return
        except Exception as e:
            print(f"[Chart] {label} mouse click xato: {e}")

        try:
            locator.evaluate("el => el.click()")
            print(f"[Chart] {label} bosildi (JS click)")
        except Exception as e:
            print(f"[Chart] {label} JS click ham xato: {e}")
            raise

    def _open_page(self, ticker: str):
        page = browser_manager.new_page()
        self._block_ads(page)

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
            print(f"[Chart] Cookie sozlashda xato: {e}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except TimeoutError:
            print("[Chart] First timeout -> retry")
            page.goto(url, wait_until="commit", timeout=30000)

        page.set_viewport_size({"width": 1600, "height": 1200})

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

        try:
            page.reload(wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        try:
            page.evaluate("""
                () => {
                    const selectors = [
                        '[class*="cookie"]', '[class*="consent"]',
                        '[class*="tooltip"]', '[class*="popup"]',
                        '[class*="banner"]', '[id*="cookie"]',
                        '[class*="new-compare"]', '[class*="promo"]',
                        '.chart-tooltip', '.overlay-tooltip',
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            el.style.display = 'none';
                            el.remove();
                        });
                    });
                    document.querySelectorAll('div, span, section').forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (text.length > 0 && text.length < 300 &&
                            (text.includes('New Compare') ||
                             text.includes('multi-timeframe') ||
                             text.includes('sector ranking'))) {
                            el.style.display = 'none';
                            el.remove();
                        }
                    });
                }
            """)
        except Exception:
            pass

        page.locator("canvas").first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(1200)

        try:
            page.evaluate("""
                () => {
                    document.querySelectorAll(
                        '[class*="tooltip"], [class*="popup"], [class*="new-compare"], [class*="banner"]'
                    ).forEach(el => { el.style.display = 'none'; el.remove(); });
                    document.querySelectorAll('div, span, section').forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (text.length > 0 && text.length < 300 &&
                            (text.includes('New Compare') ||
                             text.includes('multi-timeframe') ||
                             text.includes('sector ranking'))) {
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
            raise Exception(f"Unexpected Finviz page : {title}")

        return page

    def _scale_image(self, img_bytes: bytes, target_width: int = 1400) -> bytes:
        """
        Rasmni proporsional ravishda kattalashtiradi.
        Hech narsa kesilmaydi, hech narsa qo'shilmaydi —
        faqat o'lcham oshiriladi.
        """
        try:
            from PIL import Image
            import io as _io

            img = Image.open(_io.BytesIO(img_bytes))
            w, h = img.size

            if w >= target_width:
                print(f"[Chart] Rasm allaqachon yetarli katta: {w}x{h}")
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
            print(f"[Chart] Resize xato (asl rasm ishlatiladi): {e}")
            return img_bytes

    def _capture_via_share_download(self, page):
        """
        Finviz Share Chart -> Download orqali asl PNG grafikni yuklab oladi.
        So'ng proporsional ravishda kattalashtiradi.
        """
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

        share_btn = page.locator(
            'button:has-text("Share"), a:has-text("Share"), [class*="share"]:has-text("Share")'
        ).first

        share_btn.wait_for(state="visible", timeout=8000)
        self._safe_click(page, share_btn, "Share tugmasi")

        try:
            page.wait_for_selector('text="Share Chart"', timeout=5000)
            print("[Chart] 'Share Chart' modal topildi")
        except Exception:
            print("[Chart] 'Share Chart' matni topilmadi, davom etamiz")

        page.wait_for_timeout(1500)

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

        try:
            btn_texts = page.eval_on_selector_all(
                "button, a",
                "els => els.map(e => e.textContent.trim()).filter(t => t.length > 0 && t.length < 40)"
            )
            print(f"[Chart] Sahifadagi tugmalar: {btn_texts[:30]}")
        except Exception as e:
            print(f"[Chart] Diagnostika xato: {e}")

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
            raise Exception("Download tugmasi topilmadi")

        with page.expect_download(timeout=15000) as download_info:
            self._safe_click(page, download_btn, "Download tugmasi")

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

        print(f"[Chart] Share->Download OK ({len(img_bytes)//1024} KB)")

        img_bytes = self._scale_image(img_bytes, target_width=1400)

        try:
            close_btn = page.locator(
                'button:has-text("Close"), [class*="modal"] button[class*="close"]'
            ).first
            if close_btn.count() > 0:
                close_btn.click(timeout=1000)
        except Exception:
            pass

        return img_bytes

    def _find_chart(self, page):
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
                    print(f"[Chart] Found container: {selector}")
                    return locator
            except Exception:
                pass

        selectors = [
            "canvas.second",
            "canvas",
            "div[id^='chart'] canvas",
            "div[class*='chart'] canvas",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=2000)
                print(f"[Chart] Found : {selector}")
                return locator
            except Exception:
                pass

        return None

    def _capture_chart(self, page):
        # 1-usul: Share -> Download
        try:
            img = self._capture_via_share_download(page)
            if img:
                return img
        except Exception as e:
            print(f"[Chart] Share->Download muvaffaqiyatsiz: {e}")

        # 2-usul (zaxira): screenshot
        print("[Chart] Zaxira usul: screenshot")
        chart = self._find_chart(page)

        if chart:
            try:
                box = chart.bounding_box()
                if box:
                    print(f"[Chart] Size : {int(box['width'])}x{int(box['height'])}")
                    if box["width"] < 400 or box["height"] < 200:
                        print("[Chart] Element too small, page screenshot ga o'tamiz")
                        raise ValueError("Element too small")

                img = chart.screenshot(type="png")
                print(f"[Chart] Chart screenshot OK ({len(img)//1024} KB)")
                return img
            except Exception as e:
                print(f"[Chart] Canvas screenshot failed : {e}")

        print("[Chart] Canvas topilmadi -> Page screenshot")
        try:
            img = page.screenshot(
                clip={"x": 0, "y": 140, "width": 1600, "height": 850},
                type="png",
            )
            print(f"[Chart] Page screenshot OK ({len(img)//1024} KB)")
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
            print(f"[Chart] Finviz OK : {ticker}")
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

    # Qayta urinish
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
