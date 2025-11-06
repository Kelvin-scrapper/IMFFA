
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import os
import re
import subprocess
from datetime import datetime

# ============== CONFIGURATION ==============
HEADLESS = True  # Set to False to see the browser window
# ===========================================

def get_chrome_version():
    """Detect installed Chrome version"""
    try:
        # Try Windows registry
        result = subprocess.run(
            ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            version = re.search(r'version\s+REG_SZ\s+(\d+)', result.stdout)
            if version:
                return int(version.group(1))

        # Try reading Chrome executable version
        chrome_paths = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                result = subprocess.run([path, '--version'], capture_output=True, text=True)
                version = re.search(r'Chrome (\d+)', result.stdout)
                if version:
                    return int(version.group(1))
    except:
        pass
    return None

def download_latest_imf_pdf():
    """
    Downloads the latest PDF from IMF Financial Activities Index page
    """
    url = "https://www.imf.org/en/Publications/SPROLLs/imf-financial-activities-index#sort=%40imfdate%20descending"

    # Create output folder if it doesn't exist
    output_folder = "Downloads"
    os.makedirs(output_folder, exist_ok=True)

    # Setup undetected Chrome
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Auto-detect Chrome version
    chrome_version = get_chrome_version()
    if chrome_version:
        print(f"Detected Chrome version: {chrome_version}")
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=chrome_version)
    else:
        print("Chrome version auto-detection failed, using default")
        driver = uc.Chrome(options=options, use_subprocess=True)

    try:
        print(f"Accessing {url}...")
        driver.get(url)

        # Wait for the results to load
        wait = WebDriverWait(driver, 20)

        # Wait for results to be present - try multiple selectors
        result_selectors = [
            (By.CLASS_NAME, "coveo-result-item"),
            (By.CSS_SELECTOR, "[class*='result-item']"),
            (By.CSS_SELECTOR, "[class*='search-result']"),
            (By.TAG_NAME, "article")
        ]

        first_result = None
        for selector_type, selector_value in result_selectors:
            try:
                first_result = wait.until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                print(f"Found results using: {selector_value}")
                break
            except:
                continue

        if not first_result:
            raise Exception("Could not find any search results on page")

        # Find the first PDF link - try multiple approaches
        pdf_link_element = None
        link_selectors = [
            (By.CLASS_NAME, "CoveoResultLink"),
            (By.CSS_SELECTOR, "a[href*='.pdf']"),
            (By.CSS_SELECTOR, "a[href*='Publications']"),
            (By.TAG_NAME, "a")
        ]

        for selector_type, selector_value in link_selectors:
            try:
                pdf_link_element = first_result.find_element(selector_type, selector_value)
                if pdf_link_element.get_attribute("href"):
                    print(f"Found PDF link using: {selector_value}")
                    break
            except:
                continue

        if not pdf_link_element:
            raise Exception("Could not find PDF link in search results")

        pdf_url = pdf_link_element.get_attribute("href")
        pdf_title = pdf_link_element.get_attribute("title") or pdf_link_element.text or "IMF Report"

        print(f"Found latest report: {pdf_title}")
        print(f"PDF URL: {pdf_url}")

        # Fix internal URLs - replace any internal hostname with public one
        # Handle various internal hostnames that IMF might use
        internal_hosts = [
            "prd-sitecore-cm151p.imf.org",
            "sitecore-cm.imf.org",
            "cms.imf.org"
        ]

        for internal_host in internal_hosts:
            if internal_host in pdf_url:
                pdf_url = pdf_url.replace(internal_host, "www.imf.org")
                print(f"Fixed URL: {pdf_url}")
                break

        # Also handle protocol-relative and ensure HTTPS
        if pdf_url.startswith("//"):
            pdf_url = "https:" + pdf_url
        elif not pdf_url.startswith("http"):
            pdf_url = "https://www.imf.org" + pdf_url

        # Extract date from title if possible, otherwise use timestamp
        date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', pdf_title)
        if date_match:
            date_str = date_match.group(1).replace(',', '').replace(' ', '_')
            filename = os.path.join(output_folder, f"IMF_Report_{date_str}.pdf")
        else:
            from datetime import datetime
            filename = os.path.join(output_folder, f"IMF_Weekly_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        # Download the PDF using browser (to handle redirects and sessions)
        print("Downloading PDF...")

        # Method 1: Try direct download with requests and browser cookies
        try:
            # Get cookies from browser
            cookies = driver.get_cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])

            response = session.get(pdf_url, stream=True, timeout=30)
            response.raise_for_status()

            # Save the PDF
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        except Exception as e1:
            print(f"Method 1 failed: {e1}")
            print("Trying alternate method...")

            # Method 2: Navigate to PDF directly in browser and save
            try:
                driver.get(pdf_url)
                time.sleep(5)  # Wait for download to start

                # Check if file exists in Downloads
                import glob
                downloads = glob.glob(os.path.join(os.path.expanduser("~"), "Downloads", "*.pdf"))
                if downloads:
                    latest_download = max(downloads, key=os.path.getctime)
                    import shutil
                    shutil.move(latest_download, filename)
                else:
                    raise Exception("PDF not found in Downloads folder")

            except Exception as e2:
                print(f"Method 2 failed: {e2}")
                raise Exception("All download methods failed")

        file_size = os.path.getsize(filename)
        print(f"Successfully downloaded: {filename} ({file_size:,} bytes)")

        return {
            "filename": filename,
            "title": pdf_title,
            "url": pdf_url,
            "size": file_size
        }

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise

    finally:
        driver.quit()

if __name__ == "__main__":
    try:
        result = download_latest_imf_pdf()
        print("\nDownload completed successfully!")
        print(f"Title: {result['title']}")
        print(f"File: {result['filename']}")
    except Exception as e:
        print(f"\nFailed to download: {str(e)}")