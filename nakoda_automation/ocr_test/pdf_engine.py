import time
import os
import gc
import cv2
import numpy as np
import pdfplumber
from nakoda_automation.ocr_test.engine import run_ocr

def inspect_characters(text):
    result = []
    for c in text:
        result.append({
            "char": c,
            "unicode_hex": hex(ord(c)),
            "is_devanagari": 0x0900 <= ord(c) <= 0x097F
        })
    return result

def remove_zero_width(text):
    return text.replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')

def run_unicode_diagnostic(pdf_path):
    import unicodedata
    start_time = time.perf_counter()
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]  # Just check first page
        
        # Step 1: Extract using multiple methods
        words = page.extract_words()
        text_words = " ".join([w["text"] for w in words]) if words else ""
        text_text = page.extract_text() or ""
        text_layout = page.extract_text(layout=True) or ""
        
        snippet = text_text[:500] if text_text else ""
        
        # Step 2: Character inspection
        char_analysis = inspect_characters(snippet)
        
        # Step 3: Normalize
        normalized_variants = {
            "NFC": unicodedata.normalize("NFC", snippet),
            "NFD": unicodedata.normalize("NFD", snippet),
            "NFKC": unicodedata.normalize("NFKC", snippet),
            "NFKD": unicodedata.normalize("NFKD", snippet),
        }
        
        # Step 4: Remove Zero Width Characters
        zero_width_removed = remove_zero_width(snippet)
        
        # Step 5: ASCII Detection
        suspicious_ascii = []
        for c in snippet:
            # ord(c) < 128 and not a standard punctuation/number/letter
            if ord(c) < 128 and not c.isalnum() and c not in [' ', ',', '.', '/', '-', '\n', '(', ')']:
                if c not in suspicious_ascii:
                    suspicious_ascii.append(c)
                    
        res = {
            "extraction_variants": {
                "extract_words": text_words[:500],
                "extract_text": text_text[:500],
                "extract_text_layout": text_layout[:500]
            },
            "normalized_variants": {
                "NFC": normalized_variants["NFC"][:200],
                "NFKC": normalized_variants["NFKC"][:200]
            },
            "zero_width_removed": zero_width_removed[:200],
            "character_analysis": char_analysis[:100],  # Return first 100 for readability
            "suspicious_ascii": suspicious_ascii
        }
        
        return res

def run_pdf_ocr(pdf_path):
    """
    Enhanced PDF extractor using pdfplumber.
    1. Attempts to extract embedded text natively (blazing fast, < 1s).
    2. Falls back to image rendering + PaddleOCR if no text layer exists.
    """
    start_time = time.perf_counter()
    
    combined_raw_text = []
    combined_blocks = []
    engine_device = "cpu"
    paddle_version = "N/A"
    orig_sizes = []
    resized_sizes = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                # Try native text extraction first
                words = page.extract_words()
                text = page.extract_text()
                
                if text and len(text.strip()) > 50:
                    # Native PDF Digital Text Detected!
                    engine_device = "native_pdf_dom (pdfplumber)"
                    paddle_version = "none"
                    orig_sizes.append(f"{page.width}x{page.height}")
                    resized_sizes.append("N/A (No resize needed)")
                    
                    combined_raw_text.append(f"--- PAGE {i+1} ---")
                    combined_raw_text.append(text)
                    
                    for w in words:
                        # Convert pdfplumber bbox to standard 4-point PaddleOCR format
                        # bbox: (x0, top, x1, bottom) -> [[x0, top], [x1, top], [x1, bottom], [x0, bottom]]
                        x0, top, x1, bottom = w["x0"], w["top"], w["x1"], w["bottom"]
                        bbox = [[x0, top], [x1, top], [x1, bottom], [x0, bottom]]
                        combined_blocks.append({
                            "text": w["text"],
                            "confidence": 1.0,  # Native text is always 100% confident
                            "bbox": bbox,
                            "page": i + 1
                        })
                else:
                    # Fallback to OCR for scanned/image-based PDF Pages
                    im = page.to_image(resolution=144)
                    pil_image = im.original
                    
                    # Convert PIL to BGR OpenCV format
                    open_cv_image = np.array(pil_image) 
                    if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 3:
                        open_cv_image = open_cv_image[:, :, ::-1].copy() 
                    
                    tmp_path = f"/tmp/pdf_page_{time.time()}_{i}.jpg"
                    cv2.imwrite(tmp_path, open_cv_image)
                    
                    res = run_ocr(tmp_path)
                    
                    if res and not res.get("error"):
                        combined_raw_text.append(f"--- PAGE {i+1} ---")
                        if res.get("raw_text"):
                            combined_raw_text.append(res["raw_text"])
                        
                        blocks = res.get("blocks", [])
                        for b in blocks:
                            b["page"] = i + 1
                        combined_blocks.extend(blocks)
                        
                        engine_device = res.get("device", engine_device)
                        paddle_version = res.get("paddle_version", paddle_version)
                        
                        if res.get("image_original_size"):
                            orig_sizes.append(res["image_original_size"])
                        if res.get("image_resized_size"):
                            resized_sizes.append(res["image_resized_size"])
                            
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                        
                    del im
                    del pil_image
                    del open_cv_image
                    gc.collect()
            
    except Exception as e:
        import traceback
        return {
            "engine": "pdfplumber_hybrid",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "time_taken": round(time.perf_counter() - start_time, 2)
        }
    
    time_taken = round(time.perf_counter() - start_time, 2)
    
    return {
        "engine": "pdfplumber_hybrid",
        "paddle_version": paddle_version,
        "device": engine_device,
        "image_original_size": f"{page_count} pages ({orig_sizes[0]} ea)" if orig_sizes else "",
        "image_resized_size": f"{page_count} pages ({resized_sizes[0]} ea)" if resized_sizes else "",
        "time_taken": time_taken,
        "block_count": len(combined_blocks),
        "page_count": page_count,
        "raw_text": "\n".join(combined_raw_text),
        "blocks": combined_blocks
    }
