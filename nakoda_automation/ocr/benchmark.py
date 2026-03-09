import frappe
import os
from nakoda_automation.ocr.surya_engine import run_surya_ocr, check_surya_installed

@frappe.whitelist()
def run_surya_test(file_url):
    """
    Validates file exists
    Checks Surya installed
    Calls run_surya_ocr
    Returns structured JSON
    """
    if not file_url:
        return {"error": "No file URL provided"}

    # Validate file path
    # In Frappe, file_url starts with /files/ or /private/files/
    # We need the absolute path
    if file_url.startswith("/"):
        file_path = frappe.get_site_path(file_url.lstrip("/"))
    else:
        file_path = frappe.get_site_path(file_url)

    if not os.path.exists(file_path):
        return {"error": f"File not found at {file_path}"}

    # Verify file extension
    allowed_extensions = [".jpg", ".jpeg", ".png"]
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in allowed_extensions:
        return {"error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}

    if not check_surya_installed():
        return {
            "status": "error",
            "message": "Surya OCR is not installed. Run: bench pip install surya-ocr"
        }

    # Run OCR
    result = run_surya_ocr(file_path)
    return result
