"""
Browserless downloader for the IMF Weekly Financial Activities Index report.

The SPROLLs listing page and a cold PDF request are both blocked by IMF's
Akamai bot protection (HTTP 403). However:
  * GET https://www.imf.org/external/index.htm succeeds and sets an `ak_bmsc`
    cookie, and
  * each report lives at a date-stamped URL:
        https://www.imf.org/-/media/files/publications/fa-index/{YYYY}/{MMDDYY}.pdf
With the warm-up cookie in hand, `requests` can fetch that PDF directly.

So this script does no browser automation at all: warm up, then walk backwards
day by day from today and download the first date that returns a PDF - i.e.
whatever the latest report is, regardless of which weekday it was published.

Drop-in alternative to main.py (Playwright). Same output layout / filename
convention / return shape, so extract_final.py and orchestrator.py work
unchanged.
"""

import os
import sys
import logging
import traceback
from datetime import date, datetime, timedelta

import requests

# ============================================================================
# DIRECTORY SETUP
# ============================================================================
os.makedirs('logs', exist_ok=True)
os.makedirs('Downloads', exist_ok=True)

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

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ============================================================================
# CONFIGURATION
# ============================================================================
OUTPUT_FOLDER = "Downloads"
MEDIA_URL_TMPL = "https://www.imf.org/-/media/files/publications/fa-index/{year}/{mmddyy}.pdf"
DAYS_BACK = 21                     # how many days back from today to probe before giving up
REQUEST_TIMEOUT = 60

# Open entry points used only to earn the Akamai `ak_bmsc` cookie. Tried in
# order; the first that returns HTTP 200 wins.
WARMUP_URLS = [
    "https://www.imf.org/external/index.htm",
    "https://www.imf.org/robots.txt",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)

# ============================================================================
# HELPERS
# ============================================================================

def assert_file_exists(filepath, file_description=""):
    desc = file_description or filepath
    if not os.path.exists(filepath):
        msg = f"File not found: {desc} at {filepath}"
        logging.error(f"ASSERTION FAILED: {msg}")
        raise AssertionError(msg)
    logging.info(f"File verified: {desc}")
    return filepath


def build_session():
    """A requests session warmed up so Akamai has issued its bot cookie."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    for url in WARMUP_URLS:
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            logging.info(f"Warm-up {url} -> HTTP {resp.status_code}")
            if resp.status_code == 200:
                break
        except requests.RequestException as e:
            logging.warning(f"Warm-up {url} failed: {e}")
    else:
        logging.warning("No warm-up URL returned 200; continuing without a fresh cookie")

    if "ak_bmsc" not in session.cookies.get_dict():
        logging.warning("ak_bmsc cookie not set after warm-up; PDF fetch may 403")
    else:
        logging.info("Akamai cookie acquired (ak_bmsc)")
    return session


def candidate_dates(n=DAYS_BACK, today=None):
    """Every date from today back `n` days, newest first."""
    d = today or date.today()
    return [d - timedelta(days=i) for i in range(n)]


def looks_like_pdf(resp):
    ctype = resp.headers.get("content-type", "").lower()
    return (
        resp.status_code == 200
        and (ctype.startswith("application/pdf") or resp.content[:4] == b"%PDF")
        and len(resp.content) > 50_000
    )


def find_latest_report(session):
    """Walk backwards from today; return (report_date, url, response) for the newest PDF."""
    for dt in candidate_dates():
        url = MEDIA_URL_TMPL.format(year=dt.year, mmddyy=dt.strftime("%m%d%y"))
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            logging.warning(f"  {dt} {url.split('/')[-1]}: request error {e}")
            continue

        if looks_like_pdf(resp):
            logging.info(f"  {dt} {url.split('/')[-1]}: HTTP 200, {len(resp.content):,} bytes  <-- latest")
            return dt, url, resp

        logging.info(f"  {dt} {url.split('/')[-1]}: HTTP {resp.status_code} "
                     f"({resp.headers.get('content-type', '?')}) - skip")

    raise Exception(
        f"No report PDF found in the last {DAYS_BACK} days. "
        "The URL scheme may have changed."
    )


# ============================================================================
# MAIN
# ============================================================================

def download_latest_imf_pdf():
    logging.info("=" * 80)
    logging.info("STARTING IMF PDF DOWNLOAD (browserless: warm-up cookie + requests)")
    logging.info("=" * 80)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    logging.info(f"Output folder: {OUTPUT_FOLDER}")

    try:
        session = build_session()

        logging.info(f"Probing report URLs day-by-day back {DAYS_BACK} days (newest first)...")
        report_date, pdf_url, resp = find_latest_report(session)

        pdf_title = f"Weekly Report {report_date.strftime('%B')} {report_date.day}, {report_date.year}"
        filename = f"IMF_Report_{report_date.strftime('%B')}_{report_date.day}_{report_date.year}.pdf"
        download_path = os.path.join(OUTPUT_FOLDER, filename)

        logging.info("SUCCESS: Found latest report")
        logging.info(f"  Title: {pdf_title}")
        logging.info(f"  URL: {pdf_url}")
        logging.info(f"Downloading PDF to: {download_path}")

        with open(download_path, 'wb') as f:
            f.write(resp.content)
        logging.info(f"Download complete: {len(resp.content):,} bytes")

        assert_file_exists(download_path, "Downloaded PDF")

        file_size = os.path.getsize(download_path)
        logging.info("=" * 80)
        logging.info("DOWNLOAD SUCCESSFUL")
        logging.info("=" * 80)
        logging.info(f"File: {download_path}")
        logging.info(f"Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")

        logging.info("Validating PDF file...")
        with open(download_path, 'rb') as f:
            header = f.read(4)
        if header != b'%PDF':
            logging.warning(f"WARNING: file may not be a valid PDF (header: {header})")
        else:
            logging.info("Valid PDF header confirmed")

        if file_size < 50000:
            logging.warning(f"WARNING: File size ({file_size:,} bytes) seems too small")
        elif file_size > 10000000:
            logging.warning(f"WARNING: File size ({file_size:,} bytes) seems unusually large")
        else:
            logging.info("File size within expected range")

        return {"filename": download_path, "title": pdf_title, "size": file_size}

    except Exception as e:
        logging.error("=" * 80)
        logging.error("ERROR OCCURRED")
        logging.error("=" * 80)
        logging.error(f"Error: {str(e)}")
        logging.error(f"Full traceback:\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    try:
        result = download_latest_imf_pdf()
        logging.info("=" * 80)
        logging.info("WORKFLOW COMPLETED SUCCESSFULLY")
        logging.info("=" * 80)
        logging.info(f"Title: {result['title']}")
        logging.info(f"File: {result['filename']}")
        logging.info(f"Log file: logs/{timestamp}.log")
        sys.exit(0)
    except Exception as e:
        logging.error("=" * 80)
        logging.error("WORKFLOW FAILED")
        logging.error("=" * 80)
        logging.error(f"Error: {str(e)}")
        logging.error(f"Check log file for details: logs/{timestamp}.log")
        sys.exit(1)
