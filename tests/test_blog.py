
import os
import pytest
from playwright.sync_api import Page, expect

def test_add_blog_post_with_image(page: Page, tmp_path):
    # Go to the admin login page
    page.goto("http://127.0.0.1:5000/admin/login")

    # Log in
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", "admin123")
    page.click("button[type=submit]")
    expect(page).to_have_url("http://127.0.0.1:5000/admin")

    # Go to the manage blog page
    page.goto("http://127.0.0.1:5000/admin/manage-blog")

    # Add a new blog post with an image
    import time
    unique_title = f"My Test Post {time.time()}"
    page.fill("input[name=title]", unique_title)
    page.fill("textarea[name=content]", "This is a test post.")

    # Create a dummy image file
    image_path = tmp_path / "test_image.png"
    with open(image_path, "w") as f:
        f.write("test")

    page.set_input_files("input[name=image]", image_path)
    page.click("button[type=submit]")

    # Check that the post was created
    expect(page.locator(f"text={unique_title}")).to_be_visible()
