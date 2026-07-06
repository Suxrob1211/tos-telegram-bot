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

        if self.browser is not None:
            return

        print("[Browser] Starting Chrome...")

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-infobars",
                "--disable-extensions",
            ],
        )

        self.context = self.browser.new_context(
            viewport={"width": 1700, "height": 1000},
            locale="en-US",
            timezone_id="America/New_York",
            accept_downloads=True,
        )

        self.context.set_default_timeout(30000)

        print("[Browser] Ready")

    def new_page(self):

        if self.browser is None:
            self.start()

        page = self.context.new_page()

        page.set_default_timeout(30000)

        return page

    def restart(self):

        print("[Browser] Restarting...")

        self.close()

        self.start()

    def close(self):

        try:
            if self.context:
                self.context.close()
        except Exception:
            pass

        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass

        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

        self.context = None
        self.browser = None
        self.playwright = None

        print("[Browser] Closed")


browser_manager = BrowserManager()
