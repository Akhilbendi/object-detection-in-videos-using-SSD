import os
import pandas as pd
from pypdf import PdfReader


def validate_pdf_folder(folder_path):
    """
    Validate PDF files in the selected download folder and all its subfolders.
    The report is saved as pdf_open_validation_report.csv in the current
    working directory.
    """
    results = []

    if not os.path.isdir(folder_path):
        print("Invalid PDF folder path.")
        return

    pdf_files = []

    # Search the main folder and every date-wise subfolder.
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            if file_name.lower().endswith(".pdf"):
                file_path = os.path.join(root, file_name)
                pdf_files.append((file_name, file_path))

    print(f"Total PDFs found: {len(pdf_files)}")

    for file_name, file_path in pdf_files:
        try:
            reader = PdfReader(file_path, strict=True)

            if reader.is_encrypted:
                raise ValueError("PDF is encrypted")

            page_count = len(reader.pages)

            results.append({
                "PDF Name": file_name,
                "File Path": file_path,
                "Validation Status": "Valid",
                "Failure Reason": ""
            })

            print(f"VALID: {file_name} ({page_count} pages)")

        except Exception as ex:
            results.append({
                "PDF Name": file_name,
                "File Path": file_path,
                "Validation Status": "Failed",
                "Failure Reason": str(ex)
            })

            print(f"FAILED: {file_name} - {ex}")

    report = pd.DataFrame(
        results,
        columns=[
            "PDF Name",
            "File Path",
            "Validation Status",
            "Failure Reason"
        ]
    )

    report.to_csv(
        "pdf_open_validation_report.csv",
        index=False
    )

    valid_count = sum(
        item["Validation Status"] == "Valid" for item in results
    )
    failed_count = sum(
        item["Validation Status"] == "Failed" for item in results
    )

    print("\nPDF Validation completed")
    print(f"Total PDFs checked: {len(results)}")
    print(f"Valid PDFs: {valid_count}")
    print(f"Failed PDFs: {failed_count}")
    print("Report saved: pdf_open_validation_report.csv")


if __name__ == "__main__":
    pdf_download_path = input(
        "Enter Your PDF download folder path: "
    ).strip().strip('"')

    validate_pdf_folder(pdf_download_path)
