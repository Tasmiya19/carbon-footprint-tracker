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

import platform
import re
import cv2
import pytesseract
from PIL import Image

# On Windows, Tesseract isn't automatically on PATH after installing, so we
# point pytesseract at the default install location. On Linux (e.g. Streamlit
# Cloud, where packages.txt installs tesseract-ocr) and macOS (via Homebrew),
# it's already on PATH, so we leave pytesseract to find it automatically.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# Common phrasings used on electricity bills for consumption, in order
# of how likely they are to appear. Add more patterns as you test real bills.
UNIT_PATTERNS = [
    r"units\s*consumed\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"total\s*units\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"consumption\s*\(kwh\)\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"kwh\s*consumed\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    # Matches bills like "Consumption(Units)" or "Consumption (Units)" followed
    # by the number on the same line or the line right after it.
    r"consumption\s*\(\s*units?\s*\)\s*[:\-]?\s*\n?\s*(\d+(?:\.\d+)?)",
    r"(\d+(?:\.\d+)?)\s*kwh",
    # Fallback for tabular "Energy Charges (Unit, Rate, Amount)" bills where
    # the units value sits alone on the next line, e.g.:
    #   Energy Charges (Unit Rate, Amount)
    #   141          4.15          585.15
    r"energy\s*charges[^\n]*\n\s*([\d\]\)]{1,4})\s",
]


def _clean_ocr_digits(raw: str) -> str:
    """
    Tesseract commonly misreads the digit '1' as ']' or ')' in noisy scans
    (e.g. "141" -> "14]"). Undo that specific, common substitution before
    converting to a number.
    """
    return raw.replace("]", "1").replace(")", "1")


def extract_units_from_text(text: str):
    """
    Given already-extracted OCR text, try each pattern in turn.
    Split out from extract_units_consumed() so it can be tested/reused
    without needing an actual image file.
    """
    text_lower = text.lower()
    for pattern in UNIT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            cleaned = _clean_ocr_digits(match.group(1))
            try:
                return float(cleaned)
            except ValueError:
                continue  # this match wasn't actually numeric after cleanup, try next pattern
    return None


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


def extract_all_candidate_numbers(text: str) -> list:
    """
    Fallback for when no specific pattern matches (bill layout not
    covered by UNIT_PATTERNS). Pulls out every plausible standalone
    number from the OCR text -- typical household electricity
    consumption is between 1 and 2000 units -- so the user can pick
    the correct one instead of the system giving up entirely.
    Numbers are de-duplicated and returned in the order they first appear.
    """
    cleaned_text = _clean_ocr_digits(text)
    raw_matches = re.findall(r"\d+(?:\.\d+)?", cleaned_text)

    candidates = []
    seen = set()
    for raw in raw_matches:
        value = float(raw)
        if 1 <= value <= 2000 and value not in seen:
            candidates.append(value)
            seen.add(value)

    return candidates


def extract_units_consumed(image_path: str):
    """
    Extract the electricity units consumed (kWh) from a bill image.

    Returns a tuple: (units_or_none, candidates)
        - If a known pattern matched: (units, [])
        - If nothing matched but numbers were found: (None, [list of candidate numbers])
        - If OCR found nothing usable at all: (None, [])
    Caller should fall back to manual entry only in the last case,
    and otherwise let the user pick from candidates.
    """
    text = extract_raw_text(image_path)
    units = extract_units_from_text(text)
    if units is not None:
        return units, []
    return None, extract_all_candidate_numbers(text)


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
        units, candidates = extract_units_consumed(path)
        print(units)
        print("--- Candidate numbers (if no direct match) ---")
        print(candidates)
