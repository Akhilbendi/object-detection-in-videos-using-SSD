"""
Incremental Hugging Face PDF Availability Checker

What it does:
1. Reads paper details and PDF URLs from the scraper CSV.
2. Checks only papers that are not already listed in the Excel report.
3. Appends newly checked papers to the existing Excel report.
4. Skips previously checked papers on later runs, whether their status
   was "Available" or "Not Available".

The Excel report uses Paper URL + Publication Date as the record identity.
If Paper URL is missing, PDF Name + Publication Date is used instead.

Run directly:
    python check_pdf_availability.py

Or call from Main.py after the scraper CSV has been saved:
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

CSV_PATH = BASE_DIR / "Huggingface_Data - MT-1354.csv"
REPORT_PATH = BASE_DIR / "pdf_availability_report.xlsx"

REQUEST_TIMEOUT = (5, 20)
DELAY_BETWEEN_REQUESTS = 0.5

SHEET_NAME = "PDF Availability"

HEADERS = [
    "PDF Name",
    "Publication Date",
    "Paper URL",
    "PDF Availability",
]


# ---------------------------------------------------------------------
# CSV HELPERS
# ---------------------------------------------------------------------

def find_column(fieldnames, possible_names):
    """Find a CSV column using case-insensitive matching."""
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
    """Create a safe PDF filename from the paper title."""
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
    """Read paper information and PDF URLs from the dataset CSV."""
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
                f"CSV columns found: {reader.fieldnames}"
            )

        if not pdf_url_column:
            raise ValueError(
                "Could not find the PDF URL column. "
                f"CSV columns found: {reader.fieldnames}"
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
# RECORD IDENTIFICATION
# ---------------------------------------------------------------------

def make_record_key(paper_url, publication_date, pdf_name):
    """
    Return a consistent key for identifying a paper across runs.

    Paper URL + publication date is preferred. If Paper URL is missing,
    PDF name + publication date is used.
    """
    paper_url = (paper_url or "").strip().lower()
    publication_date = (publication_date or "").strip().lower()
    pdf_name = (pdf_name or "").strip().lower()

    identity = paper_url if paper_url else pdf_name
    return identity, publication_date


def load_already_checked_records(report_path):
    """Read record keys already present in the Excel report."""
    checked_records = set()

    if not report_path.exists():
        return checked_records

    workbook = load_workbook(
        report_path,
        read_only=True,
        data_only=True
    )

    try:
        if SHEET_NAME not in workbook.sheetnames:
            return checked_records

        worksheet = workbook[SHEET_NAME]

        for row in worksheet.iter_rows(
            min_row=2,
            values_only=True
        ):
            # Expected report columns:
            # PDF Name, Publication Date, Paper URL, PDF Availability
            pdf_name = row[0] if len(row) > 0 else ""
            publication_date = row[1] if len(row) > 1 else ""
            paper_url = row[2] if len(row) > 2 else ""

            if not paper_url and not pdf_name:
                continue

            key = make_record_key(
                str(paper_url or ""),
                str(publication_date or ""),
                str(pdf_name or ""),
            )
            checked_records.add(key)

    finally:
        workbook.close()

    return checked_records


# ---------------------------------------------------------------------
# PDF URL CHECK
# ---------------------------------------------------------------------

def check_pdf_url(pdf_url):
    """
    Check whether the website URL responds with PDF content.

    This checks URL accessibility and PDF signature/content type.
    It does not check a locally downloaded PDF file.
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
# EXCEL REPORT
# ---------------------------------------------------------------------

def open_or_create_report(report_path):
    """Open the existing workbook or create a new report workbook."""
    if report_path.exists():
        workbook = load_workbook(report_path)

        if SHEET_NAME in workbook.sheetnames:
            worksheet = workbook[SHEET_NAME]
        else:
            worksheet = workbook.create_sheet(SHEET_NAME)

        if worksheet.max_row == 1 and all(
            worksheet.cell(1, column).value is None
            for column in range(1, len(HEADERS) + 1)
        ):
            for column, heading in enumerate(HEADERS, start=1):
                worksheet.cell(1, column).value = heading

    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = SHEET_NAME

        for column, heading in enumerate(HEADERS, start=1):
            worksheet.cell(1, column).value = heading

    current_headers = [
        worksheet.cell(1, column).value
        for column in range(1, len(HEADERS) + 1)
    ]

    if current_headers != HEADERS:
        workbook.close()
        raise ValueError(
            "The existing Excel report has unexpected column headers. "
            "Please check the report before running the checker."
        )

    return workbook, worksheet


def format_report(worksheet):
    """Apply header, column, hyperlink and status formatting."""
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78"
    )

    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill

    widths = {
        1: 55,
        2: 20,
        3: 65,
        4: 22,
    }

    for column_number, width in widths.items():
        worksheet.column_dimensions[
            get_column_letter(column_number)
        ].width = width

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


def append_new_records(papers, report_path):
    """Append only the newly checked papers to the Excel report."""
    workbook, worksheet = open_or_create_report(report_path)

    for item in papers:
        row_number = worksheet.max_row + 1

        values = [
            item.get("pdf_name", ""),
            item.get("publication_date", ""),
            item.get("paper_url", ""),
            item.get("status", "Not Available"),
        ]

        for column_number, value in enumerate(values, start=1):
            worksheet.cell(row_number, column_number).value = value

    format_report(worksheet)
    workbook.save(report_path)
    workbook.close()


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    """Check only new paper records and update the cumulative report."""
    print("=" * 65)
    print("HUGGING FACE PDF WEBSITE AVAILABILITY CHECK")
    print("=" * 65)
    print(f"Dataset CSV : {CSV_PATH}")
    print(f"Excel report: {REPORT_PATH}")

    papers = load_paper_rows(CSV_PATH)

    if not papers:
        print("\nNo paper records found in the dataset CSV.")
        return

    already_checked = load_already_checked_records(REPORT_PATH)

    papers_to_check = []
    seen_in_current_csv = set()

    for item in papers:
        key = make_record_key(
            item["paper_url"],
            item["publication_date"],
            item["pdf_name"],
        )

        # Avoid checking duplicate entries within the same CSV as well.
        if key in already_checked or key in seen_in_current_csv:
            continue

        seen_in_current_csv.add(key)
        papers_to_check.append(item)

    skipped_count = len(papers) - len(papers_to_check)

    print(f"\nTotal records in CSV       : {len(papers)}")
    print(f"Already checked / skipped : {skipped_count}")
    print(f"New papers to check        : {len(papers_to_check)}")

    if not papers_to_check:
        print("\nNo new papers to check.")
        print("All papers in the CSV are already recorded in the Excel report.")
        print(f"Existing report: {REPORT_PATH}")
        return

    print("\nChecking only new PDF URLs...\n")

    available_count = 0
    unavailable_count = 0

    for index, item in enumerate(papers_to_check, start=1):
        item["status"] = check_pdf_url(item["pdf_url"])

        if item["status"] == "Available":
            available_count += 1
        else:
            unavailable_count += 1

        print(
            f"[{index}/{len(papers_to_check)}] "
            f"{item['status']} - {item['pdf_name']}"
        )

        if index < len(papers_to_check):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    append_new_records(papers_to_check, REPORT_PATH)

    print("\n" + "=" * 65)
    print("PDF AVAILABILITY CHECK COMPLETED")
    print(f"Total checked this run : {len(papers_to_check)}")
    print(f"Already checked/skipped: {skipped_count}")
    print(f"Available              : {available_count}")
    print(f"Not Available          : {unavailable_count}")
    print(f"New rows added         : {len(papers_to_check)}")
    print(f"Excel report           : {REPORT_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    main()
