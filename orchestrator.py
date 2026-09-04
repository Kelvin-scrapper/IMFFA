"""
Orchestrator - Automates the complete IMF data extraction workflow
1. Downloads latest PDF from IMF website
2. Extracts and maps data from all PDFs
3. Outputs single Excel file with all data
"""
import subprocess
import sys
import os
from datetime import datetime

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*80)
    print(title.center(80))
    print("="*80 + "\n")

def run_script(script_name, description):
    """Run a Python script and handle errors"""
    print(f"Running: {description}...")
    print(f"Script: {script_name}\n")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=False,
            text=True,
            check=True
        )
        print(f"\n[SUCCESS] {description} completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] {description} failed with error code {e.returncode}")
        return False

    except Exception as e:
        print(f"\n[ERROR] {description} failed: {str(e)}")
        return False

def main():
    start_time = datetime.now()

    print_header("IMF FINANCIAL ACTIVITIES DATA EXTRACTION ORCHESTRATOR")

    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Download PDF
    # Try the browserless downloader first; fall back to the Playwright scraper.
    print_header("STEP 1: DOWNLOAD LATEST PDF")

    success = False
    for script, desc in (("main_requests.py", "PDF Download (browserless)"),
                         ("main.py", "PDF Download (Playwright fallback)")):
        if not os.path.exists(script):
            continue
        success = run_script(script, desc)
        if success:
            break
        print(f"\n⚠ {desc} failed; trying next method...")

    if not success:
        print("\n⚠ Warning: PDF download failed. Will proceed with existing PDFs...")

    # Step 2: Extract and map data
    print_header("STEP 2: EXTRACT AND MAP DATA FROM ALL PDFS")

    if not os.path.exists("extract_final.py"):
        print("✗ ERROR: extract_final.py not found")
        return

    success = run_script("extract_final.py", "Data Extraction and Mapping")

    if not success:
        print("\n✗ ERROR: Data extraction failed")
        return

    # Complete
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print_header("EXTRACTION COMPLETE")

    print(f"Start time:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time:      {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration:      {duration:.1f} seconds")

    # Find output file (extract_final.py writes output/IMFFA_DATA_OUTPUT.xlsx)
    output_path = os.path.join('output', 'IMFFA_DATA_OUTPUT.xlsx')
    if os.path.exists(output_path):
        print(f"\nOutput file:   {output_path}")

    print("\n" + "="*80)
    print("WORKFLOW COMPLETED SUCCESSFULLY".center(80))
    print("="*80 + "\n")

if __name__ == "__main__":
    main()