from playwright.sync_api import sync_playwright

from config import HEADLESS


class Browser:

    def __init__(self):

        self.playwright = None
        self.browser = None

    def start(self):

        if self.browser:
            return

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(

            headless=HEADLESS,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        print("Browser Started")

    def new_page(self):

        self.start()

        page = self.browser.new_page(

            viewport={
                "width": 1280,
                "height": 900,
            }

        )

        return page

    def close(self):

        try:

            self.browser.close()

            self.playwright.stop()

        except Exception:
            pass


browser = Browser()
