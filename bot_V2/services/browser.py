"""
services/browser.py
Singleton Playwright browser manager (server/headless mode)
"""

import time
import threading

from playwright.sync_api import sync_playwright, Page

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


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
                cls._instance.last_used = 0
        return cls._instance

    def start(self):
        if self.browser:
            return

        print("[Browser] Server (headless) mode")

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=True,
            chromium_sandbox=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=site-per-process",
                "--single-process",
                "--no-zygote",
                "--window-size=1600,900",
            ],
        )

        self.context = self.browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent=USER_AGENT,
        )

        self.context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)

        self.context.set_default_timeout(30000)
        self.last_used = time.time()
        print("[Browser] Chromium started")

    def stop(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"[Browser] Stop xato: {e}")

        self.context = None
        self.browser = None
        self.playwright = None
        print("[Browser] Closed")

    def restart(self):
        """Brauzerni to'liq qayta ishga tushiradi."""
        print("[Browser] Restarting...")
        self.stop()
        self.start()
        print("[Browser] Restarted")

    def new_page(self) -> Page:
        if not self.browser:
            self.start()

        # Agar browser/context ulanishi uzilgan bo'lsa, qayta tiklaymiz
        try:
            self.last_used = time.time()
            return self.context.new_page()
        except Exception as e:
            print(f"[Browser] new_page xato, restart qilinmoqda: {e}")
            self.restart()
            return self.context.new_page()


browser_manager = BrowserManager()
