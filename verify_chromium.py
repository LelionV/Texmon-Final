
import os
from playwright.sync_api import sync_playwright

print("HOME:", os.environ.get("HOME"))

with sync_playwright() as p:
    browser_path = p.chromium.executable_path

    print("BROWSER:", browser_path)
    print("EXISTS:", os.path.exists(browser_path))

    cache = "/tmp/.cache/ms-playwright"
    print(
        "CACHE CONTENTS:",
        os.listdir(cache) if os.path.exists(cache) else "NOT FOUND"
    )

    try:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        print("CHROMIUM LAUNCHED SUCCESSFULLY")
        browser.close()
    except Exception as error:
        print("CHROMIUM ERROR:", repr(error))
