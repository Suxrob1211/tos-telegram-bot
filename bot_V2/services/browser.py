import os
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
                cls._instance.context = None

        return cls._instance

    def start(self):

        if self.context:
            return

        self.playwright = sync_playwright().start()

        railway = os.getenv("RAILWAY_ENVIRONMENT") is not None

        if railway:

            print("[Browser] Railway mode")

            browser = self.playwright.chromium.launch(

                headless=True,

                chromium_sandbox=False,

                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1920,1080",

                ],

            )

            self.context = browser.new_context(

                accept_downloads=True,

                viewport={

                    "width": 1920,
                    "height": 1080,
                },

                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0 Safari/537.36"

                ),

                locale="en-US",
                color_scheme="light",
                
            )    

        else:

            print("[Browser] Windows mode")

            profile = str(Path.home() / "playwright_profile")

            self.context = self.playwright.chromium.launch_persistent_context(

                user_data_dir=profile,

                channel="chrome",

                headless=False,

                no_viewport=True,

                accept_downloads=True,

                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

        self.context.set_default_timeout(30000)

    def new_page(self):

        if not self.context:
            self.start()

        return self.context.new_page()

    def close(self):

        try:

            if self.context:
                self.context.close()

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

        self.context = None
        self.playwright = None


browser_manager = BrowserManager()
