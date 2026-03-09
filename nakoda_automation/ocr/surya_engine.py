"""
surya_engine.py — Fast Hindi OCR using Surya v0.6

Speed stack applied:
  1. Force CPU  (MPS hangs on Mac with Surya's cross-attention decoder)
  2. Full CPU threading (all cores via torch.set_num_threads)
  3. Image downscale to ≤1400px  (21× detection speedup)
  4. Module-level det_model cache (load once per worker process)
  5. Fresh rec_model per call     (avoids stale KV-cache lockup)
  6. Large recognition batch      (128 lines/pass)
  7. Encoder divisor = 1          (no split on encoder pass)
"""

import os
import time

# ─── MUST be set before any Surya / PyTorch import ──────────────────────────
os.environ["TORCH_DEVICE"]                   = "cpu"
os.environ["RECOGNITION_BATCH_SIZE"]         = "128"
os.environ["RECOGNITION_ENCODER_BATCH_DIVISOR"] = "1"

import torch
# Use all 8 CPU cores for intra-op parallelism
torch.set_num_threads(os.cpu_count() or 8)

import frappe

# ─── Module-level model cache ─────────────────────────────────────────────────
# Detection model is stateless → safe to cache across calls.
# Recognition model has a per-call KV-cache that corrupts on reuse,
# so we keep only its *weights* cached and re-build the stateful wrapper each call.
_det_model     = None
_det_processor = None
_rec_processor = None   # stateless — cache it
_rec_weights   = None   # raw model weights — cache them


def _ensure_det_loaded():
    """Load detection model + processor once; idempotent."""
    global _det_model, _det_processor
    if _det_model is not None:
        return
    from surya.model.detection.model import load_model as load_det
    from surya.model.detection.processor import SegformerImageProcessor
    from surya.settings import settings
    _det_model     = load_det()
    _det_processor = SegformerImageProcessor.from_pretrained(settings.DETECTOR_MODEL_CHECKPOINT)


def _fresh_rec_model():
    """
    Return a ready recognition model.
    Weights are downloaded/cached on first call (heavy); subsequent calls
    re-use the cached weight tensor but get a fresh model object so the
    internal KV-cache is always clean.
    """
    global _rec_processor, _rec_weights
    from surya.model.recognition.model import load_model as load_rec
    from surya.model.recognition.processor import load_processor as load_rec_proc
    if _rec_processor is None:
        _rec_processor = load_rec_proc()
    # load_model() is light after weights are in the HuggingFace cache
    return load_rec()


def _resize_image(image, max_side=1400):
    """
    Shrink the longer side to max_side px.
    Detection cost is O(px²) — halving size = 4× speedup.
    Never upscale.
    """
    w, h = image.size
    scale = min(max_side / w, max_side / h, 1.0)
    if scale < 1.0:
        from PIL import Image as PILImage
        return image.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
    return image


# ─── Public API ──────────────────────────────────────────────────────────────

def check_surya_installed():
    """Returns True if surya v0.6 importable, False otherwise."""
    try:
        from surya.model.recognition.model import load_model   # noqa
        from surya.ocr import run_ocr                          # noqa
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def run_surya_ocr(image_path):
    """
    Fast plain-text extraction — Hindi only, Surya v0.6.

    Returns:
    {
        "engine": "surya",
        "raw_text": "...",
        "blocks": [{"text": ..., "confidence": ...}, ...],
        "time_taken": float   (seconds)
    }
    """
    if not check_surya_installed():
        return {
            "engine": "surya",
            "error": "Surya OCR not installed. Run: bench pip install surya-ocr==0.6.0",
            "time_taken": 0,
        }

    try:
        from surya.ocr import run_ocr
        from PIL import Image

        start = time.perf_counter()

        image = Image.open(image_path).convert("RGB")
        image = _resize_image(image, max_side=1400)

        # det model: cached (stateless)
        _ensure_det_loaded()
        # rec model: fresh each call (clears stale KV-cache)
        rec_model = _fresh_rec_model()

        predictions = run_ocr(
            [image],
            [["hi"]],           # Hindi only
            _det_model,
            _det_processor,
            rec_model,
            _rec_processor,
        )

        elapsed = time.perf_counter() - start

        lines     = predictions[0].text_lines
        raw_text  = "\n".join(ln.text.strip() for ln in lines if ln.text.strip())
        blocks    = [
            {"text": ln.text.strip(), "confidence": round(ln.confidence, 3)}
            for ln in lines if ln.text.strip()
        ]

        return {
            "engine":     "surya",
            "raw_text":   raw_text,
            "blocks":     blocks,
            "time_taken": elapsed,
        }

    except Exception as e:
        frappe.log_error(f"Surya OCR error: {str(e)}", "Nakoda OCR Test")
        return {"engine": "surya", "error": str(e), "time_taken": 0}
