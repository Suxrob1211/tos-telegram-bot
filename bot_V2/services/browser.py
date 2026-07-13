from playwright.sync_api import Error, TimeoutError
from services.browser import browser_manager

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d&r=m6"

BLOCKED_DOMAINS = [
    "doubleclick.net", "googlesyndication", "google-analytics",
    "googletagmanager", "adsystem", "facebook.net", "amazon-adsystem",
    "criteo", "taboola", "outbrain", "adnxs.com", "adservice.google",
]

LIGHT_THEME_JS = """
    () => {
        try {
            localStorage.setItem('theme', 'light');
            localStorage.setItem('darkMode', 'false');
            localStorage.setItem('colorScheme', 'light');
            localStorage.setItem('tv-chart-theme', 'light');
            localStorage.setItem('chart-theme', 'light');
            document.cookie = 'theme=light; path=/';
            document.documentElement.classList.remove('dark');
            document.documentElement.classList.add('light');
            document.documentElement.setAttribute('data-theme', 'light');
            document.body.classList.remove('dark');
        } catch (e) {}
    }
"""

IS_DARK_JS = """
    () => document.documentElement.classList.contains('dark')
          || document.body.classList.contains('dark')
          || getComputedStyle(document.body).backgroundColor.includes('rgb(0')
          || getComputedStyle(document.body).backgroundColor.includes('19, 23, 34')
"""

# Toggle selektorlar - eng aniqrog'i (Finviz brightness toggle) birinchi o'rinda
TOGGLE_SELECTORS = [
    'div.rounded-full.w-10.h-5:has(svg use[href*="brightness"])',
    'button[aria-label*="theme" i]',
    'button[title*="theme" i]',
    'button[data-name*="theme" i]',
    '[class*="theme-toggle"]',
    '[class*="dark-mode"]',
    'button:has(svg[class*="moon" i])',
    'button:has(svg[class*="sun" i])',
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

    def _force_light_all_frames(self, page):
        """
        Asosiy sahifa + barcha iframe'larda light temani majburlaydi.
        Agar hali ham 'dark' deb aniqlansa, mos toggle tugmasini bosadi.
        """
        for frame in page.frames:
            try:
                frame.evaluate(LIGHT_THEME_JS)
            except Exception:
                continue

            try:
                is_dark = frame.evaluate(IS_DARK_JS)
            except Exception:
                is_dark = False

            if not is_dark:
                continue

            for sel in TOGGLE_SELECTORS:
                try:
                    toggle = frame.locator(sel).first
                    if toggle.count() > 0:
                        toggle.click(timeout=1500, force=True)
                        print(f"[Chart] Frame theme toggle bosildi: {sel} (url={frame.url})")
                        frame.wait_for_timeout(500)
                        break
                except Exception:
                    continue

    def _safe_click(self, page, locator, label: str):
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
                {"name": "theme", "value": "light", "domain": ".finviz.com", "path": "/"},
                {"name": "darkMode", "value": "false", "domain": ".finviz.com", "path": "/"},
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
            page.evaluate(LIGHT_THEME_JS)
        except Exception:
            pass

        # 1-urinish: reload'dan oldin, sahifa navigatsiya toggle'ni bosib ko'ramiz
        self._force_light_all_frames(page)

        try:
            page.reload(wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # 2-urinish: reload'dan keyin
        page.wait_for_timeout(1000)
        self._force_light_all_frames(page)

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

        # 3-urinish: canvas to'liq yuklangandan keyin
        self._force_light_all_frames(page)

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

        download_selectors = [
            'button:has-text("Dow
