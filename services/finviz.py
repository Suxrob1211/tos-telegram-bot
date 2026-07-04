"""
services/finviz.py
Professional Finviz Screenshot Engine
"""

from __future__ import annotations

import time
import threading
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
)

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}&p=d"

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
        except Exception:
            pass

        self.context = None
        self.browser = None
        self.playwright = None
        print("[Browser] Closed")

    def restart(self):
        self.stop()
        self.start()

    def new_page(self) -> Page:
        if not self.browser:
            self.start()
        self.last_used = time.time()
        return self.context.new_page()


browser_manager = BrowserManager()


class FinvizScreenshot:

    def __init__(self):
        browser_manager.start()

    def _hide_popups(self, page: Page):
        js = """
        (() => {
            const ids = [
                '#cookieConsent',
                '#consent',
                '#overlay',
                '.popup',
                '.modal',
                '.ads',
                '.advertisement',
            ];
            ids.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    el.remove();
                });
            });
        })();
        """
        try:
            page.evaluate(js)
        except Exception:
            pass

    def _wait_chart(self, page: Page):
        selectors = [
            "img[src*='chart.ashx']",
            "img[src*='quote.ashx']",
            "img[src*='finviz.com/chart']",
            "img.chart-image",
            "img",
            "canvas",
        ]

       # page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        
        print("Network wait finished")

        for _ in range(15):
            for selector in selectors:
                try:
                    print(f"Searching: {selector}")
                    element = page.query_selector(selector)
                    if element:
                        box = element.bounding_box()
                        if box and box["width"] > 300 and box["height"] > 200:
                            return selector
                except Exception:
                    pass

            page.wait_for_timeout(1000)

        raise RuntimeError("Chart not found")

    def capture(self, ticker: str) -> Optional[bytes]:
        url = FINVIZ_URL.format(ticker=ticker.upper())

        for attempt in range(3):
            page = None
            try:
                page = browser_manager.new_page()

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=15000,
                )

                print("1. goto OK")

                page.wait_for_timeout(4000)
                
                print("2. timeout OK")
                
                self._hide_popups(page)
                
                print("3. hide OK")

                selector = self._wait_chart(page)

                print(f"4. selector = {selector}")
                
                time.sleep(1.5)

                chart = page.locator(selector).first

                print("5. locator OK")

                screenshot = chart.screenshot(type="png")

                print("6. screenshot OK")

                if screenshot and len(screenshot) > 10000:
                    print(
                        f"[Finviz] {ticker} screenshot OK "
                        f"({len(screenshot)//1024} KB)"
                    )
                    return screenshot

            except Exception as e:
                print(f"[Finviz] Attempt {attempt+1}/3 failed: {e}")
                time.sleep(2)
                if attempt == 2:
                    browser_manager.restart()

            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass

        return None


engine = FinvizScreenshot()


def get_chart(ticker: str) -> Optional[bytes]:
    return engine.capture(ticker)


def shutdown():
    browser_manager.stop()
