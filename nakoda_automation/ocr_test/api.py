import frappe
import os

@frappe.whitelist()
def test_hindi_ocr(file_url):
    if not file_url:
        return {
            "engine": "paddle_hindi",
            "error": "File missing",
            "time_taken": 0
        }
        
    ext = file_url.split('.')[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'pdf']:
        return {
            "engine": "paddle_hindi",
            "error": "Invalid file format. Only jpg, jpeg, png, pdf are allowed.",
            "time_taken": 0
        }

    try:
        from nakoda_automation.ocr_test.engine import run_ocr
        from nakoda_automation.ocr_test.pdf_engine import run_pdf_ocr
    except ImportError:
        return {
            "engine": "paddle_hindi",
            "error": "Paddle not installed or engine module missing.",
            "time_taken": 0
        }

    try:
        file_path = frappe.get_site_path("public", "files", file_url.split('/')[-1])
        if not os.path.exists(file_path):
            file_path = frappe.get_site_path("private", "files", file_url.split('/')[-1])
            if "/private/" not in file_url:
                # If neither works, try standard method
                file_path = frappe.get_site_path() + file_url
            
        if not os.path.exists(file_path):
            return {
                "engine": "paddle_hindi",
                "error": f"File not found on server at {file_path}",
                "time_taken": 0
            }

        if ext == 'pdf':
            result = run_pdf_ocr(file_path)
        else:
            result = run_ocr(file_path)
        
#
        return {
            "engine": "paddle_hindi",
            "paddle_version": result.get("paddle_version"),
            "device": result.get("device"),
            "image_original_size": result.get("image_original_size", ""),
            "image_resized_size": result.get("image_resized_size", ""),
            "time_taken": result.get("time_taken", 0),
            "block_count": result.get("block_count", 0),
            "raw_text": result.get("raw_text", ""),
            "blocks": result.get("blocks", [])
        }

    except Exception as e:
        return {
            "engine": "paddle_hindi",
            "error": f"OCR fails: {str(e)}",
            "time_taken": 0
        }
