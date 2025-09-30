
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import os
from datetime import datetime

# ============== CONFIGURATION ==============
HEADLESS = True  # Set to False to see the browser window
# ===========================================

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

    driver = uc.Chrome(options=options)

    try:
        print(f"Accessing {url}...")
        driver.get(url)

        # Wait for the results to load
        wait = WebDriverWait(driver, 20)

        # Wait for the first result to be present
        first_result = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "coveo-result-item"))
        )

        # Find the first PDF link (which should be the latest based on the sort order)
        pdf_link_element = first_result.find_element(By.CLASS_NAME, "CoveoResultLink")
        pdf_url = pdf_link_element.get_attribute("href")
        pdf_title = pdf_link_element.get_attribute("title")

        print(f"Found latest report: {pdf_title}")
        print(f"PDF URL: {pdf_url}")

        # Download the PDF
        print("Downloading PDF...")
        response = requests.get(pdf_url, stream=True)
        response.raise_for_status()

        # Create a filename based on the title or use timestamp
        filename = os.path.join(output_folder, f"IMF_Weekly_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        # Save the PDF
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

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