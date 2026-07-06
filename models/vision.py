"""
Vision capabilities - screenshot and image understanding
Uses a lightweight vision model from HuggingFace

Grounded OCR (Phase 3): extract_text_boxes() / find_text() locate on-screen
text and its pixel coordinates via Tesseract. These are ADDITIVE - the BLIP
caption path above is untouched.
"""

import difflib
import io
import logging
import os

import pyautogui
import pytesseract
import torch
from PIL import Image
from transformers import pipeline

logger = logging.getLogger(__name__)


def _configure_tesseract():
    """
    Point pytesseract at the Tesseract binary. winget installs it to a known
    location that is NOT always on the current process PATH, so probe a few
    candidates explicitly and fall back to whatever is on PATH.
    """
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Tesseract binary: {path}")
            return
    logger.info("Tesseract binary not found at known paths; relying on PATH")


_configure_tesseract()


class VisionAnalyzer:
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        """
        Initialize vision model for image understanding

        Args:
            model_name: HuggingFace vision model ID

        Options:
          - "Salesforce/blip-image-captioning-base" (lightweight, fast)
          - "Salesforce/blip-image-captioning-large" (more accurate, slower)
          - "microsoft/git-base" (another good option)
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Loading vision model: {model_name} on {self.device}")
        self.captioner = pipeline(
            "image-text-to-text",
            model=model_name,
            device=0 if self.device == "cuda" else -1,
        )
        logger.info("Vision model ready")

    def take_screenshot(self, region=None):
        """
        Take a screenshot

        Args:
            region: Optional tuple (x, y, width, height) for partial screenshot

        Returns:
            PIL Image object
        """
        try:
            if region:
                # Partial screenshot
                x, y, w, h = region
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
            else:
                # Full screenshot
                screenshot = pyautogui.screenshot()

            logger.info(f"Screenshot taken: {screenshot.size}")
            return screenshot

        except Exception as e:
            logger.error(f"Screenshot error: {e}", exc_info=True)
            return None

    def save_screenshot(self, filepath="screenshot.png"):
        """Take and save screenshot"""
        try:
            img = self.take_screenshot()
            if img:
                img.save(filepath)
                logger.info(f"Screenshot saved to {filepath}")
                return filepath
        except Exception as e:
            logger.error(f"Save screenshot error: {e}", exc_info=True)
        return None

    def analyze_image(self, image_path_or_pil):
        """
        Analyze an image and describe what's in it

        Args:
            image_path_or_pil: File path (str) or PIL Image object

        Returns:
            Description of the image
        """
        try:
            if isinstance(image_path_or_pil, str):
                image = Image.open(image_path_or_pil)
            else:
                image = image_path_or_pil

            # Generate caption
            results = self.captioner(image)
            caption = results[0]["generated_text"]

            logger.info(f"Image analysis: {caption}")
            return caption

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return "Could not analyze image"

    def analyze_current_screen(self):
        """Take screenshot and analyze what's on the screen"""
        try:
            img = self.take_screenshot()
            if img:
                return self.analyze_image(img)
        except Exception as e:
            logger.error(f"Screen analysis error: {e}")
        return "Could not analyze screen"

    def find_on_screen(self, description):
        """
        Advanced: Find something on screen based on natural language
        This is a placeholder for more sophisticated vision-based interaction
        """
        # Future: Use object detection or layout analysis
        # For now, just analyze what's there
        return self.analyze_current_screen()

    # ------------------------------------------------------------------
    # Grounded OCR (Phase 3) - locate on-screen text + pixel coordinates
    # ------------------------------------------------------------------

    def _resolve_image(self, image):
        """image: None -> live screenshot; str -> open file; PIL Image -> as-is."""
        if image is None:
            return self.take_screenshot()
        if isinstance(image, str):
            return Image.open(image)
        return image

    def extract_text_boxes(self, image=None, min_conf=50, upscale=1.0):
        """
        OCR the image and return each confident text token with its bounding
        box AND center, in the ORIGINAL image's pixel coordinates.

        Args:
            image: None (live screenshot), a file path, or a PIL Image.
            min_conf: drop tokens below this Tesseract confidence (0-100).
            upscale: pre-OCR magnification for small UI text (e.g. 2.0). Boxes
                are divided back by this factor so returned coordinates are
                always in the ORIGINAL image space - never the upscaled space.

        Returns:
            List of dicts: {text, conf, left, top, width, height, cx, cy}.
            cx,cy is the box center - the point a grounded click would target.
            Empty list on OCR failure (never raises).

        NOTE ON COORDINATES: coordinates are in screenshot-PIXEL space. Whether
        that equals pyautogui click space at this display scaling is verified
        empirically by the Phase 3 DPI test - do not assume 1:1 without it.
        """
        try:
            img = self._resolve_image(image)
            if img is None:
                logger.error("extract_text_boxes: no image to OCR")
                return []

            ocr_img = img
            if upscale and upscale != 1.0:
                ocr_img = img.resize(
                    (int(img.width * upscale), int(img.height * upscale)),
                    Image.LANCZOS,
                )

            data = pytesseract.image_to_data(
                ocr_img, output_type=pytesseract.Output.DICT
            )

            boxes = []
            n = len(data["text"])
            for i in range(n):
                text = data["text"][i].strip()
                if not text:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1.0
                if conf < min_conf:
                    continue

                # Map back from upscaled space to original image pixels.
                left = data["left"][i] / upscale
                top = data["top"][i] / upscale
                width = data["width"][i] / upscale
                height = data["height"][i] / upscale

                boxes.append(
                    {
                        "text": text,
                        "conf": conf,
                        "left": int(round(left)),
                        "top": int(round(top)),
                        "width": int(round(width)),
                        "height": int(round(height)),
                        "cx": int(round(left + width / 2)),
                        "cy": int(round(top + height / 2)),
                    }
                )

            logger.info(f"extract_text_boxes: {len(boxes)} tokens (min_conf={min_conf})")
            return boxes

        except Exception as e:
            logger.error(f"extract_text_boxes failed: {e}", exc_info=True)
            return []

    def find_text(self, query, image=None, min_conf=50, upscale=1.0, min_score=0.6):
        """
        Locate the on-screen text token best matching `query` (fuzzy).

        Matching: case-insensitive. A token that CONTAINS the query (or vice
        versa) scores 1.0; otherwise a difflib similarity ratio is used. The
        best token at or above min_score wins.

        Args:
            query: text to look for (e.g. "Submit", "File").
            image/min_conf/upscale: passed to extract_text_boxes().
            min_score: minimum match score in [0,1] to accept.

        Returns:
            {text, score, cx, cy, box} for the best match, or None if nothing
            clears min_score. cx,cy is the click target (original-image pixels).
        """
        q = (query or "").strip().lower()
        if not q:
            return None

        boxes = self.extract_text_boxes(image, min_conf=min_conf, upscale=upscale)

        best = None
        best_score = 0.0
        for box in boxes:
            token = box["text"].lower()
            if q in token or token in q:
                score = 1.0
            else:
                score = difflib.SequenceMatcher(None, q, token).ratio()
            if score > best_score:
                best_score = score
                best = box

        if best is None or best_score < min_score:
            logger.info(
                f"find_text({query!r}): no match >= {min_score} "
                f"(best={best_score:.2f})"
            )
            return None

        logger.info(
            f"find_text({query!r}): matched {best['text']!r} "
            f"score={best_score:.2f} at ({best['cx']},{best['cy']})"
        )
        return {
            "text": best["text"],
            "score": round(best_score, 3),
            "cx": best["cx"],
            "cy": best["cy"],
            "box": best,
        }
