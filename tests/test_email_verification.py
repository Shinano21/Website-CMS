import pytest
from playwright.sync_api import Page, expect
import re
import sqlite3

@pytest.fixture(autouse=True)
def mock_send_verification_email(mocker):
    mocker.patch("app.send_verification_email")

@pytest.fixture(autouse=True)
def cleanup_db():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("DELETE FROM admin_user WHERE username IN (?, ?)", ('testuser', 'verifieduser'))
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("DELETE FROM admin_user WHERE username IN (?, ?)", ('testuser', 'verifieduser'))
    conn.commit()
    conn.close()

def test_user_creation_and_verification(page: Page):
    # Log in as admin
    page.goto("http://127.0.0.1:5000/admin/login")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "admin123")
    page.click("button[type='submit']")
    expect(page.locator("text=Login successful!")).to_be_visible()

    # Add a new user
    page.goto("http://127.0.0.1:5000/admin/users")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='email']", "test@example.com")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    page.wait_for_url("**/admin/users")

    # Check that the user is in the list and is not verified
    expect(page.locator("text=User 'testuser' created. A verification email has been sent.")).to_be_visible()
    expect(page.locator("text=testuser")).to_be_visible()
    expect(page.locator("text=test@example.com")).to_be_visible()
    expect(page.locator("text=✖")).to_be_visible()

    # Log out and try to log in as the new user (should fail)
    page.goto("http://127.0.0.1:5000/admin/logout")
    page.goto("http://127.0.0.1:5000/admin/login")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    expect(page.locator("text=Your email is not verified.")).to_be_visible()

def test_verified_user_can_login(page: Page):
    # Manually add a verified user to the database
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash('password123')
    c.execute("INSERT INTO admin_user (username, email, password_hash, email_verified) VALUES (?, ?, ?, ?)",
              ('verifieduser', 'verified@example.com', password_hash, 1))
    conn.commit()
    conn.close()

    # Try to log in as the verified user
    page.goto("http://127.0.0.1:5000/admin/login")
    page.fill("input[name='username']", "verifieduser")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    expect(page.locator("text=Login successful!")).to_be_visible()
