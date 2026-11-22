import os
import pytest
from playwright.sync_api import sync_playwright
from utils.self_healing import smart_fill, smart_click

def test_self_healing_ecommerce_login():
    """
    Tests a live e-commerce login flow using intentionally broken locators
    to demonstrate real-time AI DOM healing.
    """
    # Automatically run headless in CI/CD pipelines, and headed locally
    is_ci = os.environ.get("CI") == "true"

    with sync_playwright() as p:
        # Launch Chromium in visible mode (headless=False) so you can watch the browser work!
        browser = p.chromium.launch(headless=is_ci, slow_mo=0 if is_ci else 500)
        page = browser.new_page()

        print("\n🌐 Navigating to live SauceDemo web application...")
        page.goto("https://saucedemo.com")

        # 1. INTENTIONALLY BROKEN SELECTOR (Real ID on site is #user-name)
        smart_fill(
            page=page,
            selector="#broken-username-field-999",
            text_value="standard_user",
            description="Username input field"
        )

        # 2. INTENTIONALLY BROKEN SELECTOR (Real ID on site is #password)
        smart_fill(
            page=page,
            selector="input[name='wrong-password-attr']",
            text_value="secret_sauce",
            description="Password input field"
        )

        # 3. INTENTIONALLY BROKEN SELECTOR (Real ID on site is #login-button)
        smart_click(
            page=page,
            selector="button.non-existent-submit-btn",
            description="Login submit button"
        )

        # 4. Verify that the self-healing worked and we successfully logged into the inventory page
        page.wait_for_url("**/inventory.html", timeout=5000)
        assert "inventory.html" in page.url, "Login failed even after self-healing attempts!"
        print("🎉 SUCCESS! AI healed all 3 broken locators and completed the live login flow!")

        browser.close()