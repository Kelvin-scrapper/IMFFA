
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os
import re
from datetime import datetime
import logging
import sys
import traceback
import requests

# ============================================================================
# DIRECTORY SETUP
# ============================================================================
os.makedirs('downloads', exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('Downloads', exist_ok=True)  # For downloaded PDFs

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{timestamp}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# ============================================================================
# CONFIGURATION
# ============================================================================
HEADLESS = True  # Set to False to see the browser window
BROWSER = "chrome"  # Options: "chromium", "chrome", "firefox", "webkit"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def save_html_structure(page, filename_prefix="page_structure"):
    """Save HTML structure for analysis"""
    try:
        html_path = f'logs/{filename_prefix}_{timestamp}.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        logging.info(f"HTML structure saved: {html_path}")
        return html_path
    except Exception as e:
        logging.error(f"Failed to save HTML structure: {e}")
        return None

def save_screenshot(page, filename_prefix="screenshot"):
    """Save screenshot for debugging"""
    try:
        screenshot_path = f'logs/{filename_prefix}_{timestamp}.png'
        page.screenshot(path=screenshot_path, full_page=True)
        logging.info(f"Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logging.error(f"Failed to save screenshot: {e}")
        return None

def assert_with_log(condition, message):
    """Assert with logging"""
    if not condition:
        logging.error(f"ASSERTION FAILED: {message}")
        raise AssertionError(message)
    logging.debug(f"Assertion passed: {message}")
    return True

def assert_file_exists(filepath, file_description=""):
    """Assert that a file exists"""
    desc = file_description or filepath
    if not os.path.exists(filepath):
        msg = f"File not found: {desc} at {filepath}"
        logging.error(f"ASSERTION FAILED: {msg}")
        raise AssertionError(msg)
    logging.info(f"File verified: {desc}")
    return filepath

def download_latest_imf_pdf():
    """
    Downloads the latest PDF from IMF Financial Activities Index page using Playwright
    """
    logging.info("="*80)
    logging.info("STARTING IMF PDF DOWNLOAD (Playwright)")
    logging.info("="*80)

    url = "https://www.imf.org/en/Publications/SPROLLs/imf-financial-activities-index"

    # Create output folder
    output_folder = "Downloads"
    os.makedirs(output_folder, exist_ok=True)
    logging.info(f"Output folder: {output_folder}")

    with sync_playwright() as p:
        # Launch browser
        logging.info(f"Launching {BROWSER} browser (headless={HEADLESS})...")

        # Select browser based on config
        if BROWSER == "chrome":
            browser = p.chromium.launch(channel="chrome", headless=HEADLESS)
        elif BROWSER == "firefox":
            browser = p.firefox.launch(headless=HEADLESS)
        elif BROWSER == "webkit":
            browser = p.webkit.launch(headless=HEADLESS)
        else:  # default to chromium
            browser = p.chromium.launch(headless=HEADLESS)

        # Create context with download path
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            # Navigate to page - use 'domcontentloaded' instead of 'networkidle' for faster, more reliable loading
            logging.info(f"Accessing URL: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            logging.info("Page loaded, waiting for content to render...")

            # Wait for Coveo search results to fully load
            try:
                # Wait for atomic-result-list with populated content
                logging.info("Waiting for Coveo search results to load...")
                page.wait_for_selector("atomic-result-list", timeout=15000)
                logging.info("Results container detected")

                # Wait for actual content inside - look for any element with "Weekly Report" text
                page.wait_for_selector("text=Weekly Report", timeout=15000)
                logging.info("Weekly Report content detected")
            except Exception as e:
                logging.warning(f"Content detection failed: {e}")
                logging.info("Waiting additional time for JavaScript...")

            # Additional wait for JavaScript to fully populate content
            page.wait_for_timeout(8000)  # 8 seconds for dynamic content to fully render

            # Save initial page structure
            save_html_structure(page, "initial_page")
            save_screenshot(page, "initial_page")

            # Wait for dynamic content
            logging.info("="*80)
            logging.info("SEARCHING FOR 'WEEKLY REPORT' LINKS")
            logging.info("="*80)

            # Save page after dynamic load
            save_html_structure(page, "after_dynamic_load")
            save_screenshot(page, "after_dynamic_load")

            # Context-aware search: Find link with "Weekly Report" text
            logging.info("Strategy: Looking for links containing 'Weekly Report' text...")

            pdf_title = None
            download_path = None

            try:
                # Method 1: Use text selector to find "Weekly Report" links directly
                logging.info("Method 1: Searching for 'Weekly Report' text on page...")

                # Use Playwright's built-in text selector
                weekly_reports = page.locator("text=Weekly Report").all()
                logging.info(f"Found {len(weekly_reports)} elements with 'Weekly Report' text")

                weekly_report_links = []
                for elem in weekly_reports:
                    try:
                        text = elem.inner_text(timeout=2000)
                        # Get the href from the element or its ancestor link
                        href = None
                        if elem.evaluate("el => el.tagName") == 'A':
                            href = elem.get_attribute('href')
                        else:
                            ancestor_link = elem.locator("xpath=./ancestor::a").first
                            if ancestor_link.count() > 0:
                                href = ancestor_link.get_attribute('href')

                        if href:
                            weekly_report_links.append({
                                'href': href,
                                'text': text.strip()
                            })
                            logging.info(f"  Found: {text.strip()[:60]}")
                            logging.info(f"    href: {href[:80]}...")
                    except Exception as e:
                        logging.debug(f"  Skipping element: {e}")
                        continue

                if weekly_report_links:
                    # Take the first one (latest)
                    latest = weekly_report_links[0]
                    pdf_title = latest['text']
                    pdf_url = latest['href']

                    logging.info(f"✓ SUCCESS: Selected latest report")
                    logging.info(f"  Title: {pdf_title}")
                    logging.info(f"  URL: {pdf_url}")

                    # Extract date from title for filename
                    date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', pdf_title)
                    if date_match:
                        date_str = date_match.group(1).replace(',', '').replace(' ', '_')
                        filename = f"IMF_Report_{date_str}.pdf"
                    else:
                        filename = f"IMF_Weekly_Report_{timestamp}.pdf"

                    download_path = os.path.join(output_folder, filename)

                    # Download the PDF using requests with browser cookies
                    logging.info(f"Downloading PDF to: {download_path}")

                    # Get cookies from browser context
                    cookies = context.cookies()
                    cookie_dict = {c['name']: c['value'] for c in cookies}

                    # Use requests to download
                    response = requests.get(pdf_url, cookies=cookie_dict, timeout=60)
                    response.raise_for_status()

                    with open(download_path, 'wb') as f:
                        f.write(response.content)

                    logging.info(f"Download complete: {len(response.content):,} bytes")

                else:
                    raise Exception("No 'Weekly Report' links found on page")

            except Exception as e1:
                logging.warning(f"Method 1 failed: {e1}")
                logging.info("Method 2: Trying direct selector approach...")

                # Method 2: Try direct selector with text match
                try:
                    # Use Playwright's text selector
                    link_locator = page.get_by_role("link", name=re.compile(r"Weekly Report.*2025"))

                    if link_locator.count() > 0:
                        pdf_title = link_locator.first.inner_text()
                        pdf_url = link_locator.first.get_attribute('href')
                        logging.info(f"Found link: {pdf_title}")
                        logging.info(f"URL: {pdf_url}")

                        # Extract date from title
                        date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', pdf_title)
                        if date_match:
                            date_str = date_match.group(1).replace(',', '').replace(' ', '_')
                            filename = f"IMF_Report_{date_str}.pdf"
                        else:
                            filename = f"IMF_Weekly_Report_{timestamp}.pdf"

                        download_path = os.path.join(output_folder, filename)

                        # Download using requests
                        cookies = context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}
                        response = requests.get(pdf_url, cookies=cookie_dict, timeout=60)
                        response.raise_for_status()

                        with open(download_path, 'wb') as f:
                            f.write(response.content)

                        logging.info(f"Download complete: {len(response.content):,} bytes")
                    else:
                        raise Exception("No matching links found")

                except Exception as e2:
                    logging.error(f"Method 2 failed: {e2}")
                    save_html_structure(page, "final_failure")
                    save_screenshot(page, "final_failure")
                    raise Exception("All methods failed to find PDF link")

            # Verify download
            if not download_path:
                raise Exception("Download path not set")

            assert_file_exists(download_path, "Downloaded PDF")

            file_size = os.path.getsize(download_path)
            logging.info("="*80)
            logging.info("DOWNLOAD SUCCESSFUL")
            logging.info("="*80)
            logging.info(f"File: {download_path}")
            logging.info(f"Size: {file_size:,} bytes ({file_size/1024:.2f} KB)")

            # Validation: Check if file is actually a PDF
            logging.info("Validating PDF file...")
            with open(download_path, 'rb') as f:
                header = f.read(4)
                if header != b'%PDF':
                    logging.warning(f"WARNING: Downloaded file may not be a valid PDF (header: {header})")
                else:
                    logging.info("✓ Valid PDF header confirmed")

            # Validation: Reasonable file size (IMF reports are typically 300KB - 2MB)
            if file_size < 50000:  # Less than 50KB
                logging.warning(f"WARNING: File size ({file_size:,} bytes) seems too small for an IMF report")
            elif file_size > 10000000:  # More than 10MB
                logging.warning(f"WARNING: File size ({file_size:,} bytes) seems unusually large for an IMF weekly report")
            else:
                logging.info("✓ File size within expected range")

            return {
                "filename": download_path,
                "title": pdf_title or "IMF Financial Activities Report",
                "size": file_size
            }

        except Exception as e:
            logging.error("="*80)
            logging.error("ERROR OCCURRED")
            logging.error("="*80)
            logging.error(f"Error: {str(e)}")
            logging.error(f"Full traceback:\n{traceback.format_exc()}")

            # Save debug information
            save_html_structure(page, "error_state")
            save_screenshot(page, "error_state")
            raise

        finally:
            # Cleanup
            try:
                context.close()
                browser.close()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.warning(f"Error closing browser: {e}")

if __name__ == "__main__":
    try:
        result = download_latest_imf_pdf()
        logging.info("="*80)
        logging.info("WORKFLOW COMPLETED SUCCESSFULLY")
        logging.info("="*80)
        logging.info(f"Title: {result['title']}")
        logging.info(f"File: {result['filename']}")
        logging.info(f"Log file: logs/{timestamp}.log")
        sys.exit(0)
    except Exception as e:
        logging.error("="*80)
        logging.error("WORKFLOW FAILED")
        logging.error("="*80)
        logging.error(f"Error: {str(e)}")
        logging.error(f"Check log file for details: logs/{timestamp}.log")
        sys.exit(1)
