import pytest
import requests
from bs4 import BeautifulSoup

def test_css_integration(build_and_run_container):
    """
    Verify that the Auth pages are inheriting the base template and linking
    to the main /style.css.
    """
    base_url = build_and_run_container
    response = requests.get(f"{base_url}/auth/login")
    assert response.status_code == 200

    soup = BeautifulSoup(response.content, 'html.parser')

    # 1. Check for the CSS link
    # The auth server doesn't  host the CSS, NGINX does.
    # But the HTML must request it from root.
    css_link = soup.find('link', rel='stylesheet', href='/style.css')
    assert css_link is not None, "The page is missing the link to /style.css"

def test_clickable_brand_title(build_and_run_container):
    """
    Verify the title is present, container the correct text, and links back
    to the root (/) homepage.
    """
    base_url = build_and_run_container
    response = requests.get(f"{base_url}/auth/login")
    soup = BeautifulSoup(response.content, 'html.parser')

    # 1. Find the Navbar Brand div
    brand_div = soup.find('div', class_='navbar-brand')
    assert brand_div is not None, "Could not find .navbar-brand div"

    # 2. Find the anchor tag inside
    link = brand_div.find('a')
    assert link is not None, "Title is not wrapped in an anchor tag"

    # 3. Verify the link destination
    assert link['href'] == '/', "Title does not link to the root (/)"

    # 4. Verify the text
    header = link.find('h1')
    assert "Music Translator for and by Deaf" in header.text

def test_custom_form_style(build_and_run_container):
    """
    Verify that the custom templates (e.g., login_user.html) are actually
    overriding Flask-Security defaults by checking for specific classes
    added (like .form-container).
    """
    base_url = build_and_run_container
    response = requests.get(f"{base_url}/auth/login")
    soup = BeautifulSoup(response.content, 'html.parser')

    # The default Flask-Security template does NOT use .form-container
    # The override does
    form_container = soup.find('div', class_='form-container')
    assert form_container is not None, \
        "The customer login_user.html template is not being used (missing .form-container)"

def test_access_request_page_style(build_and_run_container):
    """
    Verify the Request Access page also inherits the navbar
    """
    base_url = build_and_run_container
    response = requests.get(f"{base_url}/auth/request-access")
    soup = BeautifulSoup(response.content, 'html.parser')

    # Check if the navbar exists on this page too
    navbar = soup.find('nav', class_='navbar')
    assert navbar is not None, "Request Access page is missing the navbar"
