import re
from playwright.sync_api import Page, expect

def test_logout_and_back_button(page: Page):
    # Go to the admin login page
    page.goto("http://127.0.0.1:5000/admin/login")

    # Fill in the login form
    page.get_by_label("Username").fill("admin")
    page.get_by_placeholder("Enter your password").fill("admin123")
    page.get_by_role("button", name="Login").click()

    # Expect to be on the admin dashboard
    expect(page).to_have_url(re.compile(r"/admin"))

    # Go to the logout page
    page.goto("http://127.0.0.1:5000/admin/logout")

    # Expect to be on the home page
    expect(page).to_have_url("http://127.0.0.1:5000/")

    # Go back in the browser history
    page.go_back()

    # Expect to be redirected to the login page
    expect(page).to_have_url(re.compile(r"/admin/login"))
