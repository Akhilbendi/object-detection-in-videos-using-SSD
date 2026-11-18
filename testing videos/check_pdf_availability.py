"""
Check PDF availability directly from the paper's PDF URL.

This script does NOT require PDFs to be downloaded locally.
It reads the scraper CSV and creates an Excel report containing:
    - PDF Name
    - Publication Date
    - Paper URL
    - PDF Availability

Only "Not Available" cells are formatted in red.
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Keep the dataset CSV in the same folder as this script, or change this path.
CSV_PATH = BASE_DIR / "Huggingface_Data - MT-1354.csv"

# Excel report will be created beside this script.
REPORT_PATH = BASE_DIR / "pdf_availability_report.xlsx"

REQUEST_TIMEOUT = (5, 20)
DELAY_BETWEEN_REQUESTS = 0.5


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def find_column(fieldnames, possible_names):
    """Find a CSV column without depending on its letter case."""
    normalized = {
        str(name).strip().lower(): name
        for name in (fieldnames or [])
        if name is not None
    }

    for candidate in possible_names:
        actual_name = normalized.get(candidate.strip().lower())
        if actual_name:
            return actual_name

    return None


def clean_pdf_name(title):
    """Create a readable PDF filename from a paper title."""
    filename = (title or "").strip()
    filename = filename.replace("\n", " ")
    filename = re.sub(r'[\\/:*?"<>|]', "", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = filename.strip("._ ")

    if len(filename) > 251:
        filename = filename[:251]

    if filename and not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return filename or "Unknown.pdf"


def check_pdf_url(url):
    """
    Check whether the URL currently returns a PDF.

    A successful HTTP response alone is not enough: the response should
    identify itself as a PDF or begin with the PDF file signature.
    """
    if not url:
        return "Not Available"

    url = url.strip()
    parsed_url = urlparse(url)

    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        return "Not Available"

    response = None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PDFAvailabilityChecker/1.0)",
            "Range": "bytes=0-4",
        }

        response = requests.get(
            url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code not in (200, 206):
            return "Not Available"

        content_type = response.headers.get("Content-Type", "").lower()

        # Read only the first small chunk needed to inspect the PDF signature.
        first_bytes = b""
        for chunk in response.iter_content(chunk_size=5):
            if chunk:
                first_bytes = chunk[:5]
                break

        if "application/pdf" in content_type or first_bytes.startswith(b"%PDF-"):
            return "Available"

        return "Not Available"

    except requests.RequestException:
        return "Not Available"

    finally:
        if response is not None:
            response.close()


def load_paper_rows(csv_path):
    """Read paper details from the scraper CSV."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Dataset CSV was not found:\n{csv_path}\n"
            "Place the CSV beside this script or update CSV_PATH."
        )

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        title_column = find_column(reader.fieldnames, ["Title", "Paper Title"])
        date_column = find_column(
            reader.fieldnames,
            ["published", "Publication Date", "Date"],
        )
        paper_url_column = find_column(
            reader.fieldnames,
            ["Page URL", "Case Link", "Paper URL"],
        )
        pdf_url_column = find_column(
            reader.fieldnames,
            ["pdf link", "PDF Link", "PDF URL"],
        )

        if not title_column:
            raise ValueError(
                "Could not find the paper title column. "
                f"CSV columns found: {reader.fieldnames}"
            )

        if not pdf_url_column:
            raise ValueError(
                "Could not find the PDF URL column. "
                f"CSV columns found: {reader.fieldnames}"
            )

        rows = []
        for row in reader:
            title = (row.get(title_column) or "").strip()
            pdf_url = (row.get(pdf_url_column) or "").strip()

            # Ignore empty/header-like rows.
            if not title or title.lower() == "title":
                continue

            publication_date = (
                (row.get(date_column) or "").strip() if date_column else ""
            )

            paper_url = (
                (row.get(paper_url_column) or "").strip()
                if paper_url_column
                else ""
            )

            rows.append(
                {
                    "pdf_name": clean_pdf_name(title),
                    "publication_date": publication_date,
                    "paper_url": paper_url,
                    "pdf_url": pdf_url,
                }
            )

    return rows


# ---------------------------------------------------------------------
# EXCEL REPORT
# ---------------------------------------------------------------------

def create_excel_report(rows, report_path):
    """Create and format the PDF availability Excel report."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PDF Availability"

    headers = [
        "PDF Name",
        "Publication Date",
        "Paper URL",
        "PDF Availability",
    ]
    worksheet.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill

    for item in rows:
        worksheet.append(
            [
                item["pdf_name"],
                item["publication_date"],
                item["paper_url"],
                item["status"],
            ]
        )

        row_number = worksheet.max_row

        # Make the paper URL clickable when it is a valid web URL.
        paper_url_cell = worksheet.cell(row=row_number, column=3)
        if paper_url_cell.value:
            parsed = urlparse(str(paper_url_cell.value))
            if parsed.scheme in ("http", "https") and parsed.netloc:
                paper_url_cell.hyperlink = paper_url_cell.value
                paper_url_cell.style = "Hyperlink"

        # Only "Not Available" is red. "Available" keeps normal font colour.
        status_cell = worksheet.cell(row=row_number, column=4)
        if status_cell.value == "Not Available":
            status_cell.font = Font(color="FF0000")

    # Make the report easier to read.
    column_widths = {
        1: 55,
        2: 20,
        3: 65,
        4: 22,
    }

    for column_number, width in column_widths.items():
        worksheet.column_dimensions[
            get_column_letter(column_number)
        ].width = width

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    workbook.save(report_path)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    print("=" * 65)
    print("PDF WEBSITE AVAILABILITY CHECK")
    print("=" * 65)
    print(f"Dataset: {CSV_PATH}")

    try:
        paper_rows = load_paper_rows(CSV_PATH)

        if not paper_rows:
            print("No paper records were found in the dataset.")
            return

        print(f"Total papers to check: {len(paper_rows)}")
        print("Checking PDF URLs on the website...\n")

        available_count = 0
        unavailable_count = 0

        for index, item in enumerate(paper_rows, start=1):
            item["status"] = check_pdf_url(item["pdf_url"])

            if item["status"] == "Available":
                available_count += 1
            else:
                unavailable_count += 1

            print(
                f"[{index}/{len(paper_rows)}] "
                f"{item['status']} - {item['pdf_name']}"
            )

            if index < len(paper_rows):
                time.sleep(DELAY_BETWEEN_REQUESTS)

        create_excel_report(paper_rows, REPORT_PATH)

        print("\n" + "=" * 65)
        print("PDF AVAILABILITY CHECK COMPLETED")
        print(f"Total checked    : {len(paper_rows)}")
        print(f"Available        : {available_count}")
        print(f"Not Available    : {unavailable_count}")
        print(f"Excel report     : {REPORT_PATH}")
        print("=" * 65)

    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"\nERROR: {error}")


if __name__ == "__main__":
    main()
