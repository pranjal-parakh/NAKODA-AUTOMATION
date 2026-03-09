import os
import time
import gc
import cv2
import psutil

# Disable model source check
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import paddle
from paddleocr import PaddleOCR
from nakoda_automation.ocr.utils import safe_resize
from nakoda_automation.ocr.row_cluster import cluster_rows

# Step 2: Global initialization (run once)
ocr = PaddleOCR(
    use_angle_cls=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    lang='hi'
    # Dropped show_log=False because paddleocr v3.4 will crash (Unknown argument)
)

def run_anchor_ocr(image_path):
    start = time.perf_counter()
    
    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
            
        # Step 1: Safe resize
        image, orig_size, res_size = safe_resize(image)
        
        # Step 3: Full Page Anchor Search
        try:
            # 3.4+ API
            result = list(ocr.predict(image))
            is_predict = True
        except AttributeError:
            # < 2.x API
            result = ocr.ocr(image, cls=False)
            is_predict = False
            
        blocks = []
        if is_predict:
            for page in result:
                if not page:
                    continue
                rec_texts = page.get("rec_texts", [])
                rec_scores = page.get("rec_scores", [])
                dt_polys = page.get("dt_polys", [])
                for text, score, bbox in zip(rec_texts, rec_scores, dt_polys):
                    blocks.append({
                        "text": text.strip(),
                        "bbox": bbox,
                        "conf": float(score)
                    })
        else:
            if result and result[0]:
                for line in result[0]:
                    bbox, (text, conf) = line[0], line[1]
                    blocks.append({
                        "text": text.strip(),
                        "bbox": bbox,
                        "conf": float(conf)
                    })
                    
        y_udhaari = None
        y_total = None
        
        for b in blocks:
            text = b["text"].upper()
            y_min = min(point[1] for point in b["bbox"])
            
            # Identify Udhaari block
            if "उधारी" in text or "उधार" in text or "UDHARI" in text:
                if y_udhaari is None:
                    y_udhaari = y_min
                    
            # Identify first Total block AFTER Udhaari
            elif "TOTAL" in text:
                if y_udhaari is not None and y_min > y_udhaari:
                    if y_total is None or y_min < y_total:
                        y_total = y_min
                        
        if y_udhaari is None or y_total is None:
            time_taken = round(time.perf_counter() - start, 2)
            res = {
                "engine": "paddle_anchor_roi",
                "error": "Anchors not found",
                "y_udhaari": y_udhaari,
                "y_total": y_total,
                "time_taken": time_taken,
                "blocks_found": len(blocks)
            }
            if time_taken > 10.0:
                res["diagnostics"] = {
                    "cpu_percent": psutil.cpu_percent(interval=0.5),
                    "memory_percent": psutil.virtual_memory().percent,
                    "device_backend": str(paddle.device.get_device()),
                    "paddle_version": paddle.__version__
                }
            return res
            
        # Step 4: Crop Dynamic ROI
        margin = 10
        crop_y1 = max(0, int(y_udhaari) - margin)
        # Handle cases where y_total is unexpectedly close to y_udhaari
        if crop_y1 > int(y_total):
           crop_y1 = max(0, int(y_total) - margin) 
           
        crop_y2 = min(image.shape[0], int(y_total) + margin)
        
        roi = image[crop_y1:crop_y2, :]
        
        # Step 5: Detect inside ROI
        try:
            roi_result = list(ocr.predict(roi))
        except AttributeError:
            roi_result = ocr.ocr(roi, cls=False)
            
        roi_blocks = []
        if is_predict:
            for page in roi_result:
                if not page:
                    continue
                rec_texts = page.get("rec_texts", [])
                rec_scores = page.get("rec_scores", [])
                dt_polys = page.get("dt_polys", [])
                for text, score, bbox in zip(rec_texts, rec_scores, dt_polys):
                    text = text.strip()
                    if text:
                        roi_blocks.append({
                            "text": text,
                            "bbox": bbox,
                            "conf": float(score)
                        })
        else:
            if roi_result and roi_result[0]:
                for line in roi_result[0]:
                    bbox, (text, conf) = line[0], line[1]
                    text = text.strip()
                    if text:
                        roi_blocks.append({
                            "text": text,
                            "bbox": bbox,
                            "conf": float(conf)
                        })
                        
        # Step 6 & 7: Row Clustering
        rows = cluster_rows(roi_blocks, y_threshold=15)
        
        time_taken = round(time.perf_counter() - start, 2)
        
        # Memory safety
        del image
        del roi
        gc.collect()
        
        res = {
            "engine": "paddle_anchor_roi",
            "image_original_size": orig_size,
            "image_resized_size": res_size,
            "y_udhaari": crop_y1,
            "y_total": crop_y2,
            "roi_height": crop_y2 - crop_y1,
            "rows_detected": len(rows),
            "time_taken": time_taken,
            "rows": rows
        }
        
        # Step 8: Diagnostics if performance > 10s
        if time_taken > 10.0:
            res["diagnostics"] = {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
                "device_backend": str(paddle.device.get_device()),
                "paddle_version": paddle.__version__
            }
            
        return res
        
    except Exception as e:
        import traceback
        return {
            "engine": "paddle_anchor_roi",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "time_taken": round(time.perf_counter() - start, 2)
        }
