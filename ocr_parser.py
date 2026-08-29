"""
ocr_parser.py

Extracts "units consumed" (kWh) from a photo/scan of an electricity
bill using Tesseract OCR, plus regex rules to find the right number
in the raw text.

Requirements:
    pip install pytesseract pillow opencv-python
    Also install the Tesseract OCR engine itself (system binary):
        - Windows: https://github.com/UB-Mannheim/tesseract/wiki
        - macOS:   brew install tesseract
        - Linux:   sudo apt install tesseract-ocr

Bill layouts vary a lot between providers, so the regex patterns
below are a starting point -- test against your own sample bills
in data/sample_bills/ and add patterns as needed.
"""

import re
import cv2
import pytesseract
from PIL import Image


# Common phrasings used on electricity bills for consumption, in order
# of how likely they are to appear. Add more patterns as you test real bills.
UNIT_PATTERNS = [
    r"units\s*consumed\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"total\s*units\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"consumption\s*\(kwh\)\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"kwh\s*consumed\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"(\d+(?:\.\d+)?)\s*kwh",
]


def preprocess_image(image_path: str):
    """
    Basic preprocessing to improve OCR accuracy: grayscale + thresholding.
    Returns a PIL Image ready for pytesseract.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Otsu's thresholding -- turns the image into clean black/white text
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresh)


def extract_raw_text(image_path: str) -> str:
    """
    Run OCR on a bill image and return the raw extracted text.
    Useful for debugging: print this first to see what Tesseract
    actually reads before writing/adjusting regex patterns.
    """
    processed = preprocess_image(image_path)
    return pytesseract.image_to_string(processed)


def extract_units_consumed(image_path: str) -> float | None:
    """
    Extract the electricity units consumed (kWh) from a bill image.
    Returns None if no pattern matched (caller should fall back to
    manual entry in that case).
    """
    text = extract_raw_text(image_path).lower()

    for pattern in UNIT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    return None


if __name__ == "__main__":
    # Quick manual test:
    #   python ocr_parser.py data/sample_bills/bill1.jpg
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ocr_parser.py <path_to_bill_image>")
    else:
        path = sys.argv[1]
        print("--- Raw OCR text ---")
        print(extract_raw_text(path))
        print("--- Extracted units ---")
        print(extract_units_consumed(path))
