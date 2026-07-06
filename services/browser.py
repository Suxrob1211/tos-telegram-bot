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

        profile = str(Path.home() / "playwright_profile")

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=profile,
            channel="chrome",
            headless=False,
            no_viewport=True,
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
