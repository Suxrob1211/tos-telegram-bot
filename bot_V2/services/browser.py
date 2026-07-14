import os
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserManager:

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):

        with cls._lock:

            if cls._instance is None:

                cls._instance = super().__new__(cls)

                cls._instance.playwright = None
                cls._instance.browser = None
                cls._instance.context = None

        return cls._instance

    def _is_server_env(self) -> bool:
        """
        Server (headless) muhitini aniqlaydi:
        - Railway, Oracle Cloud, yoki har qanday Linux VPS/VM
        - Yoki DISPLAY o'zgaruvchisi yo'q bo'lsa (GUI mavjud emas)
        - Yoki FORCE_HEADLESS=1 qo'lda o'rnatilgan bo'lsa
        Faqat Windows'da GUI (lokal test) rejimida ishlaydi.
        """
        if os.getenv("FORCE_HEADLESS") == "1":
            return True

        if os.getenv("FORCE_DESKTOP") == "1":
            return False

        if sys.platform.startswith("win"):
            return False

        # Linux/Mac server (Railway, Oracle Cloud, VPS va h.k.)
        return True

    def start(self):

        if self.context:
            return

        self.playwright = sync_playwright().start()

        server_mode = self._is_server_env()

        if server_mode:

            print("[Browser] Server (headless) mode")
            print("[Browser] Chromium ishga tushirilmoqda...")

            try:
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    chromium_sandbox=False,
                    timeout=45000,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-background-networking",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--disable-extensions",
                        "--mute-audio",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )
            except Exception as e:
                print(
                    f"[Browser] ❌ Chromium ishga tushmadi: {e}\n"
                    "   Ehtimoliy sabablar:\n"
                    "   1) Xotira yetmayapti -> 'free -m' bilan tekshiring\n"
                    "   2) Kutubxonalar o'rnatilmagan -> "
                    "'python3 -m playwright install --with-deps chromium'\n"
                    "   3) ARM protsessor muvofiqligi muammosi -> 'uname -m'\n"
                    "   4) Osilib qolgan eski jarayon -> 'pkill -9 -f chrome'"
                )
                try:
                    self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
                raise

            print("[Browser] Chromium ishga tushdi ✅")

            self.context = self.browser.new_context(

                viewport={
                    "width": 1200,
                    "height": 900,
                },

                accept_downloads=True,

                locale="en-US",

                timezone_id="UTC",

                color_scheme="light",

                device_scale_factor=1,

                user_agent=(

                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.7204.169 Safari/537.36"

                ),

            )

            self.context.set_extra_http_headers({

                "Accept-Language": "en-US,en;q=0.9"

            })

        else:

            print("[Browser] Windows (desktop) mode")

            profile = str(Path.home() / "playwright_profile")

            self.context = self.playwright.chromium.launch_persistent_context(

                user_data_dir=profile,

                channel="chrome",

                headless=False,

                no_viewport=True,

                accept_downloads=True,

                color_scheme="light",

                args=[

                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",

                ],

            )

        self.context.set_default_timeout(60000)
        self.context.set_default_navigation_timeout(60000)

    def new_page(self):

        if self.context is None:

            self.start()

        try:
            page = self.context.new_page()
        except Exception as e:
            print(f"[Browser] new_page xato, qayta ishga tushirilmoqda: {e}")
            self.restart()
            page = self.context.new_page()

        page.set_viewport_size({

            "width": 1600,
            "height": 1200,

        })

        page.set_extra_http_headers({

            "Accept-Language": "en-US,en;q=0.9"

        })

        return page

    def close(self):

        # Avval ochiq sahifalarni yopamiz — aks holda close() abadiy
        # kutib qolishi (hang) mumkin, ayniqsa server muhitida
        try:
            if self.context:
                for pg in list(self.context.pages):
                    try:
                        pg.close()
                    except Exception:
                        pass
        except Exception:
            pass

        try:

            if self.context:
                self.context.close()

            if self.browser:
                self.browser.close()

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

        self.context = None
        self.browser = None
        self.playwright = None

    def restart(self):
        """Brauzerni to'liq qayta ishga tushiradi (crash/hang bo'lganda)."""
        print("[Browser] Restarting...")
        self.close()
        import time
        time.sleep(1)
        self.start()
        print("[Browser] Restarted")


browser_manager = BrowserManager()
