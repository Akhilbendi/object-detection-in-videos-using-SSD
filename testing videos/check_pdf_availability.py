"""
Hugging Face PDF Website Availability Checker

Reads the scraper dataset CSV and checks each paper's PDF URL directly
on the website. It does not require PDFs to be downloaded locally.

Creates/updates one Excel workbook:
    pdf_availability_report.xlsx

Report columns:
    PDF Name
    Publication Date
    Paper URL
    PDF Availability

When the report already exists:
    - New papers are appended.
    - Existing papers (identified by PDF URL + publication date) are updated.
    - Previous records are retained.
    - "Not Available" is formatted in red.
    - "Available" uses the normal font colour.

Run separately:
    python check_pdf_availability.py

Or call from Main.py after the dataset CSV has been saved:
    import check_pdf_availability
    check_pdf_availability.main()
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# The dataset CSV should be in the same folder as this script.
CSV_PATH = BASE_DIR / "Huggingface_Data - MT-1354.csv"

# The cumulative Excel report is saved in the same folder.
REPORT_PATH = BASE_DIR / "pdf_availability_report.xlsx"

REQUEST_TIMEOUT = (5, 20)
DELAY_BETWEEN_REQUESTS = 0.5

REPORT_SHEET_NAME = "PDF Availability"

REPORT_HEADERS = [
    "PDF Name",
    "Publication Date",
    "Paper URL",
    "PDF Availability",
]


# ---------------------------------------------------------------------
# CSV HELPERS
# ---------------------------------------------------------------------

def find_column(fieldnames, possible_names):
    """Find a CSV column using case-insensitive column names."""
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
    """Convert a paper title into a safe, readable PDF filename."""
    filename = (title or "").strip().replace("\n", " ")
    filename = re.sub(r'[\\/:*?"<>|]', "", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = filename.strip("._ ")

    if len(filename) > 240:
        filename = filename[:240]

    if filename and not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return filename or "Unknown.pdf"


def load_paper_rows(csv_path):
    """Load paper title, publication date, paper URL and PDF URL."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Dataset CSV not found: {csv_path}\n"
            "Place the CSV beside this script or update CSV_PATH."
        )

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        title_column = find_column(
            reader.fieldnames,
            ["Title", "Paper Title"]
        )
        date_column = find_column(
            reader.fieldnames,
            ["published", "Publication Date", "Date"]
        )
        paper_url_column = find_column(
            reader.fieldnames,
            ["Page URL", "Case Link", "Paper URL"]
        )
        pdf_url_column = find_column(
            reader.fieldnames,
            ["pdf link", "PDF Link", "PDF URL"]
        )

        if not title_column:
            raise ValueError(
                "Could not find the paper title column. "
                f"CSV columns: {reader.fieldnames}"
            )

        if not pdf_url_column:
            raise ValueError(
                "Could not find the PDF URL column. "
                f"CSV columns: {reader.fieldnames}"
            )

        papers = []

        for record in reader:
            title = (record.get(title_column) or "").strip()

            if not title or title.lower() == "title":
                continue

            publication_date = (
                (record.get(date_column) or "").strip()
                if date_column else ""
            )

            paper_url = (
                (record.get(paper_url_column) or "").strip()
                if paper_url_column else ""
            )

            pdf_url = (
                (record.get(pdf_url_column) or "").strip()
                if pdf_url_column else ""
            )

            papers.append({
                "pdf_name": clean_pdf_name(title),
                "publication_date": publication_date,
                "paper_url": paper_url,
                "pdf_url": pdf_url,
            })

    return papers


# ---------------------------------------------------------------------
# WEBSITE PDF URL CHECK
# ---------------------------------------------------------------------

def check_pdf_url(pdf_url):
    """
    Check whether a PDF URL currently responds with a PDF.

    A URL is marked Available when:
      - HTTP status is 200 or 206, and
      - Content-Type indicates PDF, or the response begins with %PDF-.

    This checks website URL accessibility, not local file existence or
    full PDF integrity.
    """
    if not pdf_url:
        return "Not Available"

    pdf_url = pdf_url.strip()
    parsed_url = urlparse(pdf_url)

    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        return "Not Available"

    response = None

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; "
                "HuggingFacePDFAvailabilityChecker/1.0)"
            ),
            "Range": "bytes=0-4",
        }

        response = requests.get(
            pdf_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code not in (200, 206):
            return "Not Available"

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        first_bytes = b""

        for chunk in response.iter_content(chunk_size=5):
            if chunk:
                first_bytes = chunk[:5]
                break

        if (
            "application/pdf" in content_type
            or first_bytes.startswith(b"%PDF-")
        ):
            return "Available"

        return "Not Available"

    except requests.RequestException:
        return "Not Available"

    finally:
        if response is not None:
            response.close()


# ---------------------------------------------------------------------
# EXCEL REPORT HELPERS
# ---------------------------------------------------------------------

def get_or_create_workbook(report_path):
    """Open the existing report workbook or create a new one."""
    if report_path.exists():
        workbook = load_workbook(report_path)

        if REPORT_SHEET_NAME in workbook.sheetnames:
            worksheet = workbook[REPORT_SHEET_NAME]
        else:
            worksheet = workbook.create_sheet(REPORT_SHEET_NAME)

        # Add headers if the selected sheet is empty.
        if worksheet.max_row == 1 and all(
            worksheet.cell(1, column).value is None
            for column in range(1, len(REPORT_HEADERS) + 1)
        ):
            worksheet.append(REPORT_HEADERS)

    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = REPORT_SHEET_NAME
        worksheet.append(REPORT_HEADERS)

    # Ensure the expected header row exists.
    current_headers = [
        worksheet.cell(1, column).value
        for column in range(1, len(REPORT_HEADERS) + 1)
    ]

    if current_headers != REPORT_HEADERS:
        raise ValueError(
            "The existing Excel report has unexpected column headers. "
            "Please check the workbook before continuing."
        )

    return workbook, worksheet


def make_record_key(pdf_url, publication_date, paper_url, pdf_name):
    """
    Build a stable key to prevent duplicate report rows.

    Prefer PDF URL + publication date. If the PDF URL is empty, use
    paper URL + publication date; otherwise use PDF name + date.
    """
    primary_url = (pdf_url or "").strip()
    paper_url = (paper_url or "").strip()
    publication_date = (publication_date or "").strip()
    pdf_name = (pdf_name or "").strip()

    if primary_url:
        identity = primary_url
    elif paper_url:
        identity = paper_url
    else:
        identity = pdf_name

    return identity, publication_date


def format_report(worksheet):
    """Apply readable table formatting and status colours."""
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78"
    )

    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill

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

    # Reapply status formatting to all rows, including older rows.
    for row_number in range(2, worksheet.max_row + 1):
        status_cell = worksheet.cell(row_number, 4)

        if status_cell.value == "Not Available":
            status_cell.font = Font(color="FF0000")
        else:
            status_cell.font = Font(color="000000")

        paper_url_cell = worksheet.cell(row_number, 3)
        paper_url = paper_url_cell.value

        if isinstance(paper_url, str):
            parsed_url = urlparse(paper_url)
            if parsed_url.scheme in ("http", "https") and parsed_url.netloc:
                paper_url_cell.hyperlink = paper_url
                paper_url_cell.style = "Hyperlink"

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions


def create_or_update_excel_report(papers, report_path):
    """
    Append new papers and update existing records in the same workbook.

    Existing rows are not deleted. A repeated paper is updated using its
    PDF URL + publication date key, avoiding duplicate rows.
    """
    workbook, worksheet = get_or_create_workbook(report_path)

    existing_records = {}

    for row_number in range(2, worksheet.max_row + 1):
        pdf_name = worksheet.cell(row_number, 1).value or ""
        publication_date = worksheet.cell(row_number, 2).value or ""
        paper_url = worksheet.cell(row_number, 3).value or ""

        # The old workbook doesn't have a separate PDF URL column.
        # The report's specified Paper URL is used as a fallback key.
        key = make_record_key(
            "",
            str(publication_date),
            paper_url,
            str(pdf_name),
        )
        existing_records[key] = row_number

    appended_count = 0
    updated_count = 0

    for item in papers:
        # The report stores the paper URL, not the PDF URL, so use
        # Paper URL + Publication Date consistently as the record key.
        key = make_record_key(
            "",
            item.get("publication_date", ""),
            item.get("paper_url", ""),
            item.get("pdf_name", ""),
        )

        values = [
            item.get("pdf_name", ""),
            item.get("publication_date", ""),
            item.get("paper_url", ""),
            item.get("status", "Not Available"),
        ]

        if key in existing_records:
            row_number = existing_records[key]
            updated_count += 1
        else:
            worksheet.append(values)
            row_number = worksheet.max_row
            existing_records[key] = row_number
            appended_count += 1

        for column_number, value in enumerate(values, start=1):
            worksheet.cell(row_number, column_number).value = value

    format_report(worksheet)
    workbook.save(report_path)

    return appended_count, updated_count, worksheet.max_row - 1


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    """Run website URL checks and update the cumulative Excel report."""
    print("=" * 65)
    print("HUGGING FACE PDF WEBSITE AVAILABILITY CHECK")
    print("=" * 65)
    print(f"Dataset CSV : {CSV_PATH}")
    print(f"Excel report: {REPORT_PATH}")

    try:
        papers = load_paper_rows(CSV_PATH)

        if not papers:
            print("No paper records were found in the dataset.")
            return

        print(f"\nTotal paper records found: {len(papers)}")
        print("Checking PDF URLs directly on the website...\n")

        available_count = 0
        unavailable_count = 0

        for index, item in enumerate(papers, start=1):
            item["status"] = check_pdf_url(item["pdf_url"])

            if item["status"] == "Available":
                available_count += 1
            else:
                unavailable_count += 1

            print(
                f"[{index}/{len(papers)}] "
                f"{item['status']} - {item['pdf_name']}"
            )

            if index < len(papers):
                time.sleep(DELAY_BETWEEN_REQUESTS)

        appended_count, updated_count, total_records = (
            create_or_update_excel_report(papers, REPORT_PATH)
        )

        print("\n" + "=" * 65)
        print("PDF AVAILABILITY CHECK COMPLETED")
        print(f"Total checked this run : {len(papers)}")
        print(f"Available              : {available_count}")
        print(f"Not Available          : {unavailable_count}")
        print(f"New rows appended      : {appended_count}")
        print(f"Existing rows updated  : {updated_count}")
        print(f"Total report records   : {total_records}")
        print(f"Excel report           : {REPORT_PATH}")
        print("=" * 65)

    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"\nPDF availability check failed: {error}")
        raise


if __name__ == "__main__":
    main()
