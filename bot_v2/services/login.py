from playwright.sync_api import sync_playwright


def create_storage():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
        )

        context = browser.new_context()

        page = context.new_page()

        page.goto(
            "https://finviz.com/login.ashx",
            wait_until="networkidle",
        )

        print()
        print("=" * 60)
        print("FINVIZ GA LOGIN QILING")
        print("Login bo'lgach ENTER bosing.")
        print("=" * 60)
        print()

        input()

        context.storage_state(
            path="storage_state.json"
        )

        browser.close()

        print()
        print("storage_state.json yaratildi.")
