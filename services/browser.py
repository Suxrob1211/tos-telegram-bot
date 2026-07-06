import os
import threading

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

    def start(self):

        if self.browser:
            return

        self.playwright = sync_playwright().start()

        is_railway = os.getenv("RAILWAY_ENVIRONMENT") is not None

        if is_railway:

            print("[Browser] Railway mode")

            self.browser = self.playwright.chromium.launch(
                headless=True,
                channel=None,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

        else:

            print("[Browser] Windows mode")

            self.browser = self.playwright.chromium.launch(
                channel="chrome",
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

        self.context = self.browser.new_context(
            viewport={"width": 1700, "height": 1000},
            locale="en-US",
            timezone_id="America/New_York",
            accept_downloads=True,
        )

        self.context.set_default_timeout(30000)

    def new_page(self):

        if not self.browser:
            self.start()

        return self.context.new_page()

    def close(self):

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


browser_manager = BrowserManager()
