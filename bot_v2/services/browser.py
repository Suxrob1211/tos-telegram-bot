import os

from playwright.sync_api import sync_playwright


class BrowserManager:

    def __init__(self):

        self.playwright = None
        self.browser = None

    def start(self):

        if self.browser:
            return

        print("[Browser] Starting Chrome...")

        self.playwright = sync_playwright().start()

        headless = os.getenv("HEADLESS", "true").lower() == "true"

        self.browser = self.playwright.chromium.launch(

            channel="chrome",

            headless=headless,

            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
            ],
        )

        print("[Browser] Chrome started")

    def new_page(self):

        if not self.browser:
            self.start()

        context = self.browser.new_context(

            viewport={
                "width": 1920,
                "height": 1080,
            },

            device_scale_factor=1,

            accept_downloads=True,

            locale="en-US",

            timezone_id="America/New_York",
        )

        page = context.new_page()

        page.set_default_timeout(30000)

        return page

    def close(self):

        try:

            if self.browser:
                self.browser.close()

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

        self.browser = None
        self.playwright = None


browser_manager = BrowserManager()
