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
    # Plain "Consumption : 4100" style, with no "(kWh)"/"(Units)" qualifier --
    # common on bills that just label the field "Consumption".
    r"consumption\s*[:\-]\s*(\d+(?:\.\d+)?)",
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


# Patterns for the "Present Reading" and "Previous Reading" meter values.
# Almost every Indian electricity bill (regardless of state/provider or
# exact wording for "consumption") prints these two numbers, since they're
# what the meter reader actually recorded -- so calculating their
# difference is a very reliable, provider-independent way to get units
# consumed, even when the bill's specific "Consumption" label/phrasing
# isn't one we've coded a pattern for.
PRESENT_READING_PATTERNS = [
    r"pres(?:ent)?\.?\s*r(?:d|e)g\.?\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"present\s*reading\s*[:\-]?\s*(\d+(?:\.\d+)?)",
]
PREVIOUS_READING_PATTERNS = [
    r"prev(?:ious)?\.?\s*r(?:d|e)g\.?\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"previous\s*reading\s*[:\-]?\s*(\d+(?:\.\d+)?)",
]
CONSTANT_PATTERNS = [
    r"constant\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    r"m(?:eter)?\.?\s*constant\s*[:\-]?\s*(\d+(?:\.\d+)?)",
]


def _first_match(patterns: list, text_lower: str):
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            cleaned = _clean_ocr_digits(match.group(1))
            try:
                return float(cleaned)
            except ValueError:
                continue
    return None


def extract_units_from_meter_readings(text: str):
    """
    Provider-independent fallback: units consumed = (present reading -
    previous reading) x meter constant (constant defaults to 1 if not
    found/printed). Validated against multiple real Indian bill formats
    where the direct "Consumption" label wasn't reliably OCR'd, but the
    Present/Previous Reading numbers were.
    """
    text_lower = text.lower()
    present = _first_match(PRESENT_READING_PATTERNS, text_lower)
    previous = _first_match(PREVIOUS_READING_PATTERNS, text_lower)

    if present is None or previous is None:
        return None

    constant = _first_match(CONSTANT_PATTERNS, text_lower)
    if constant is None or constant <= 0:
        constant = 1.0

    diff = (present - previous) * constant
    if diff < 0:
        return None  # reading rollover / OCR error -- not trustworthy, don't guess

    return round(diff, 2)


def preprocess_image(image_path: str):
    """
    Basic preprocessing to improve OCR accuracy: grayscale + thresholding.
    Returns a PIL Image ready for pytesseract. Kept for backwards
    compatibility / simple single-pass use.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Otsu's thresholding -- turns the image into clean black/white text
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresh)


def _generate_preprocessing_variants(image_path: str):
    """
    Produce a couple of differently-processed versions of the same image.
    Different bill photos respond better to different treatment (blurry,
    low-contrast, uneven lighting), so instead of a single fixed pipeline,
    we try a small number and let OCR run on each. Kept intentionally
    small (2 variants) so the total OCR time stays reasonable for a live
    demo -- more variants catch more edge cases but get slow fast.
    Returns a list of PIL Images.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small/low-res photos -- OCR struggles with small text.
    # Capped at 1400px (rather than higher) to keep OCR time reasonable.
    h, w = gray.shape
    if max(h, w) < 1400:
        scale = 1400 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    variants = []

    # Variant 1: contrast boost (CLAHE) + Otsu threshold -- handles most
    # everyday cases: mild blur, faded print, moderate lighting issues.
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    contrast_boosted = clahe.apply(gray)
    _, otsu = cv2.threshold(contrast_boosted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(Image.fromarray(otsu))

    # Variant 2: adaptive thresholding -- handles uneven lighting/shadows/
    # folded paper, which Otsu alone often struggles with.
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    variants.append(Image.fromarray(adaptive))

    return variants


def extract_raw_text(image_path: str) -> str:
    """
    Run OCR on a bill image and return the raw extracted text using a
    single, simple preprocessing pass. Kept for quick debugging
    (e.g. `python ocr_parser.py <image>`), where seeing one clear
    output is more useful than a merged multi-pass result.
    """
    processed = preprocess_image(image_path)
    return pytesseract.image_to_string(processed)


def extract_raw_text_multi(image_path: str) -> str:
    """
    Run OCR across a couple of preprocessing variants and Tesseract page
    segmentation modes, then combine all the text together. Running a
    few attempts and merging catches cases where one specific variant
    misses text that another reads correctly -- more robust on unclear
    real-world bill photos than a single pass, while staying fast enough
    (2 variants x 2 configs = 4 passes) for a live demo.
    """
    variants = _generate_preprocessing_variants(image_path)
    psm_configs = ["--psm 6", "--psm 11"]  # different layout assumptions

    all_text = []
    for variant in variants:
        for config in psm_configs:
            try:
                text = pytesseract.image_to_string(variant, config=config)
                if text.strip():
                    all_text.append(text)
            except Exception:
                continue  # skip a failed pass, keep trying others

    return "\n".join(all_text)


def extract_all_candidate_numbers(text: str) -> list:
    """
    Fallback for when no specific pattern matches (bill layout not
    covered by UNIT_PATTERNS). Prioritizes numbers found near
    consumption-related keywords (much more likely to be the right
    value), then fills in with other plausible numbers on the bill.
    Typical household electricity consumption is between 1 and 2000
    units. Capped at 10 candidates so the dropdown stays usable.
    """
    cleaned_text = _clean_ocr_digits(text)
    lines = cleaned_text.lower().split("\n")

    keywords = ["consumption", "energy charge", "units", "kwh", "consumed"]

    priority_numbers = []
    other_numbers = []
    seen = set()

    for line in lines:
        numbers_in_line = re.findall(r"\d+(?:\.\d+)?", line)
        is_priority_line = any(kw in line for kw in keywords)
        for raw in numbers_in_line:
            value = float(raw)
            # Wide range: covers both small household bills and larger
            # commercial/industrial connections. Excludes only clearly
            # implausible values (e.g. huge bill-amount or barcode numbers).
            if 1 <= value <= 100000 and value not in seen:
                seen.add(value)
                (priority_numbers if is_priority_line else other_numbers).append(value)

    ordered = priority_numbers + other_numbers
    return ordered[:10]


def extract_units_consumed(image_path: str):
    """
    Extract the electricity units consumed (kWh) from a bill image.

    Strategy (fast path first, escalating only if needed):
        1. Try a single fast preprocessing pass -- works well for most
           clear, well-lit bill photos and keeps the app responsive.
        2. If that finds nothing, retry with several preprocessing
           variants + OCR configs combined -- slower, but catches more
           on blurry/uneven-lighting photos the fast pass misses.
        3. If a known pattern still doesn't match, fall back to a
           prioritized list of candidate numbers for the user to pick.

    Returns a tuple: (units_or_none, candidates)
        - If a known pattern matched: (units, [])
        - If nothing matched but numbers were found: (None, [list of candidate numbers])
        - If OCR found nothing usable at all: (None, [])
    """
    fast_text = extract_raw_text(image_path)
    units = extract_units_from_text(fast_text)
    if units is not None:
        return units, []

    # Try the provider-independent meter-reading-difference method before
    # escalating to slower multi-pass OCR -- cheap to check, and often
    # works even when the direct "Consumption" label wasn't matched.
    units = extract_units_from_meter_readings(fast_text)
    if units is not None:
        return units, []

    thorough_text = extract_raw_text_multi(image_path)
    units = extract_units_from_text(thorough_text)
    if units is not None:
        return units, []

    units = extract_units_from_meter_readings(thorough_text)
    if units is not None:
        return units, []

    combined_text = fast_text + "\n" + thorough_text
    return None, extract_all_candidate_numbers(combined_text)


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
