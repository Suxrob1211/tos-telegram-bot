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
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-gpu",
                "--window-size=1600,1200",
            ],
        )

        self.context = self.browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="dark",
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
        )

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
            "#chart0",
            "img[src*='chart.ashx']",
            "img[src*='charts.finviz']",
            "#charts",
        ]

        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=8000)
                return selector
            except Exception:
                pass

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

                page.wait_for_timeout(4000)
                self._hide_popups(page)
                selector = self._wait_chart(page)
                time.sleep(1.5)

                chart = page.locator(selector).first
                screenshot = chart.screenshot(type="png")

                if screenshot and len(screenshot) > 10000:
                    print(
                        f"[Finviz] {ticker} screenshot OK "
                        f"({len(screenshot)//1024} KB)"
                    )
                    page.close()
                    return screenshot

            except Exception as e:
                print(f"[Finviz] Attempt {attempt+1}/3 failed: {e}")

                if page:
                    try:
                        page.close()
                    except Exception:
                        pass

                time.sleep(2)

                if attempt == 2:
                    browser_manager.restart()

        return None


engine = FinvizScreenshot()


def get_chart(ticker: str) -> Optional[bytes]:
    return engine.capture(ticker)


def shutdown():
    browser_manager.stop()
