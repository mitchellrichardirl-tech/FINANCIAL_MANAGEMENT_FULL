"""
OCR-based data extraction from receipt images.

Provides the `ReceiptExtractor` class, which takes pre-processed receipt
images, runs Tesseract OCR against multiple configurations, and parses
out structured fields (vendor, amount, date) using regex heuristics.

This is the second stage of the receipt pipeline:

    ReceiptLoader (images)
        → ReceiptExtractor (OCR + field parsing)  ← this module
            → ReceiptRepository (database persistence)

Extraction strategy:
    1. Each processed image variant is OCR'd with multiple Tesseract
       page-segmentation modes; the longest output wins.
    2. Vendor, amount, and date are extracted independently via regex.
    3. A confidence score (0–3) counts how many fields were found.
    4. The variant with the highest confidence is selected; processing
       stops early if all three fields are found (confidence = 3).
"""

import numpy as np
import pytesseract
import re
from datetime import datetime
from typing import Dict, Any, Optional

from src.models.receipt import Receipt
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ReceiptExtractor:
    """Extracts vendor, amount, and date from receipt images using OCR.

    Tries multiple OCR configurations and image-processing variants to
    maximise extraction accuracy. The best result (by confidence score)
    is written back to the `Receipt` object.

    Class-level constants control validation bounds and search limits.
    Instance-level pattern lists can be extended for additional vendor
    names or date formats.

    Constants:
        MIN_AMOUNT / MAX_AMOUNT: Plausible receipt total range. Values
            outside this are discarded.
        MIN_YEAR: Earliest year accepted for extracted dates.
        MAX_VENDOR_NAME_LENGTH / MIN_VENDOR_NAME_LENGTH: Length bounds
            for heuristic vendor-name detection.
        VENDOR_SEARCH_LINES: How many lines from the top of the OCR
            text to search with regex patterns.
        VENDOR_HEURISTIC_LINES: How many lines to try the capitalised-
            line heuristic on.
        OCR_TIMEOUT: Per-config Tesseract timeout in seconds.

    Attributes:
        vendor_patterns: Ordered list of regex patterns for vendor
            extraction. Checked top-to-bottom; first match wins.
        amount_patterns: Ordered list of regex patterns for total-amount
            extraction. All matches are collected and the largest is
            selected (assumed to be the grand total).
        date_patterns: Regex patterns for date-string detection.
            Matched strings are then parsed against known date formats.
    """

    # Constants
    MIN_AMOUNT = 0.01
    MAX_AMOUNT = 10000
    MIN_YEAR = 2000
    MAX_VENDOR_NAME_LENGTH = 50
    MIN_VENDOR_NAME_LENGTH = 3
    VENDOR_SEARCH_LINES = 10
    VENDOR_HEURISTIC_LINES = 5
    OCR_TIMEOUT = 20

    def __init__(self, tesseract_path: Optional[str] = None):
        """Initialize the extractor with regex patterns and optional Tesseract path.

        Args:
            tesseract_path: Override path to the Tesseract binary. If
                None, uses the system default or whatever pytesseract
                is already configured to use.
        """
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.debug(f"Using custom Tesseract path: {tesseract_path}")

        #TODO: Expand vendor patterns with more known chains or local stores and experiment if catch all is causing false positives
        self.vendor_patterns = [
            r"(euro\s*giant|eurogiant)",
            r"(walmart|target|costco|kroger|safeway|cvs|walgreens)",
            r"(tesco|asda|sainsbury|morrisons|aldi|lidl)",
            r"([A-Z][A-Za-z\s&\-\.]{3,30}(?:store|shop|market|retail)?)",
        ]

        self.amount_patterns = [
            r"(?:total|amount\s+due|balance|grand\s+total)[\s:€$£]*(\d+[.,]\d{2})",
            r"(?:total)[\s:]*[€$£]?\s*(\d+[.,]\d{2})",
            r"[€$£]\s*(\d+[.,]\d{2})",
            r"(\d+[.,]\d{2})\s*(?:EUR|USD|GBP|€|$|£)",
        ]

        self.date_patterns = [
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}",
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}",
        ]

        logger.debug("Initialized ReceiptExtractor")

    def extract_text_with_ocr(self, image: np.ndarray) -> str:
        """Run Tesseract OCR on an image using multiple page-segmentation modes.

        Tries three PSM configs (6, 4, 3) and keeps the result that
        produces the most text, on the assumption that more text means
        better segmentation.

        Args:
            image: Pre-processed image as a NumPy array (H×W or H×W×C).

        Returns:
            The longest OCR text output across all configs. Empty string
            if the image is invalid or all configs fail.
        """
        if image is None or image.size == 0:
            logger.warning("Invalid image provided for OCR")
            return ""

        configs = [
            "--psm 6 --oem 1",
            "--psm 4 --oem 1",
            "--psm 3 --oem 1",
        ]

        best_text = ""
        max_length = 0

        for config in configs:
            try:
                text = pytesseract.image_to_string(
                    image, config=config, timeout=self.OCR_TIMEOUT
                )
                if len(text) > max_length:
                    max_length = len(text)
                    best_text = text
                    logger.debug(f"OCR config '{config}' produced {len(text)} chars")
            except Exception as e:
                logger.warning(f"OCR failed with config '{config}': {e}")
                continue

        if not best_text:
            logger.warning("All OCR configs produced empty text")
        else:
            logger.debug(f"Best OCR result: {max_length} chars")

        return best_text

    def clean_text(self, text: str) -> str:
        """Normalise OCR text for pattern matching.

        Collapses whitespace runs and fixes common OCR misreads
        (pipe → I, exclamation → i).

        Args:
            text: Raw OCR output.

        Returns:
            Cleaned text string.
        """
        text = re.sub(r"\s+", " ", text)
        text = text.replace("|", "I").replace("!", "i")
        return text

    def extract_vendor_name(self, text: str) -> Optional[str]:
        """Extract the vendor/merchant name from OCR text.

        Uses a two-pass approach:
            1. Try each regex pattern in `vendor_patterns` against the
               first `VENDOR_SEARCH_LINES` lines. Returns on first match.
            2. Fall back to a heuristic: look for capitalised lines of
               reasonable length near the top of the receipt.

        Args:
            text: OCR text (may contain newlines).

        Returns:
            Extracted vendor name, or None if nothing matched.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        cleaned_lines = [self.clean_text(line) for line in lines]

        # Try regex patterns
        for pattern in self.vendor_patterns:
            for line in cleaned_lines[:self.VENDOR_SEARCH_LINES]:
                try:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        result = match.group(1).strip()
                        logger.debug(f"Vendor matched by pattern: '{result}'")
                        return result
                except Exception:
                    continue

        # Heuristic: capitalized lines near top
        for line in lines[:self.VENDOR_HEURISTIC_LINES]:
            if (self.MIN_VENDOR_NAME_LENGTH < len(line) <
                    self.MAX_VENDOR_NAME_LENGTH):
                words = line.split()
                if words and words[0][0].isupper():
                    logger.debug(f"Vendor matched by heuristic: '{line}'")
                    return line

        logger.debug("No vendor name extracted")
        return None

    def extract_amount(self, text: str) -> Optional[float]:
        """Extract the receipt total from OCR text.

        Tries each pattern in `amount_patterns`, collects all plausible
        amounts (within `MIN_AMOUNT`–`MAX_AMOUNT`), and returns the
        largest — on the assumption that the grand total is the highest
        number on the receipt.

        Handles comma-as-decimal (European format) by normalising to
        dot-decimal before parsing.

        Args:
            text: OCR text.

        Returns:
            The extracted total as a float, or None if no plausible
            amount was found.
        """
        amounts = []

        for pattern in self.amount_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    try:
                        amount_str = (
                            match.replace("€", "").replace("$", "").replace("£", "")
                        )
                        amount_str = amount_str.replace(",", ".").strip()
                        amount = float(amount_str)
                        if self.MIN_AMOUNT <= amount <= self.MAX_AMOUNT:
                            amounts.append(amount)
                    except ValueError:
                        continue
            except Exception:
                continue

        if amounts:
            result = max(amounts)
            logger.debug(f"Extracted amount: {result} (from {len(amounts)} candidates)")
            return result

        logger.debug("No amount extracted")
        return None

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Try to parse a date string against a list of known formats.

        Attempts day-first (European) formats before month-first
        (American) formats, since the app targets Irish/European users.

        Args:
            date_str: A date string extracted by regex (e.g.
                "15/03/2024", "15 Mar 2024").

        Returns:
            Parsed `datetime`, or None if no format matched.
        """
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
            "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y",
            "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def extract_date(self, text: str) -> Optional[datetime]:
        """Extract a date from OCR text.

        Finds all date-like strings via `date_patterns`, parses each
        with `parse_date()`, and returns the first that falls within
        a plausible year range (`MIN_YEAR` to next year).

        Args:
            text: OCR text.

        Returns:
            Parsed `datetime`, or None if no valid date was found.
        """
        for pattern in self.date_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    date_obj = self.parse_date(match)
                    if date_obj:
                        year = date_obj.year
                        current_year = datetime.now().year
                        if self.MIN_YEAR <= year <= current_year + 1:
                            logger.debug(f"Extracted date: {date_obj.date()}")
                            return date_obj
            except Exception:
                continue

        logger.debug("No date extracted")
        return None

    def process_image_variant(self, image: np.ndarray, variant: str) -> Dict[str, Any]:
        """OCR and extract fields from a single processed image variant.

        Runs the full extraction pipeline (OCR → vendor, amount, date)
        on one image and returns all results in a dict.

        Args:
            image: A pre-processed image array from
                `Receipt.processed_images`.
            variant: Name of the processing method that produced this
                image (e.g. "enhanced", "bilateral"). Included in the
                result for traceability.

        Returns:
            Dict with keys:
                - `vendor`: Extracted name or None.
                - `amount`: Extracted total or None.
                - `date`: ISO date string or None.
                - `confidence`: 0–3, counting non-None fields.
                - `method`: The `variant` name.
                - `extracted_text`: Raw OCR output.
        """
        text = self.extract_text_with_ocr(image).strip()

        if not text:
            logger.debug(f"Variant '{variant}' produced no text")
            return {
                "vendor": None,
                "amount": None,
                "date": None,
                "confidence": 0,
                "method": variant,
                "extracted_text": "",
            }

        vendor = self.extract_vendor_name(text)
        amount = self.extract_amount(text)
        date = self.extract_date(text)

        confidence = sum([
            vendor is not None,
            amount is not None,
            date is not None
        ])

        logger.debug(
            f"Variant '{variant}': confidence={confidence} "
            f"(vendor={'yes' if vendor else 'no'}, "
            f"amount={'yes' if amount else 'no'}, "
            f"date={'yes' if date else 'no'})"
        )

        return {
            "vendor": vendor,
            "amount": amount,
            "date": date.isoformat() if date else None,
            "confidence": confidence,
            "method": variant,
            "extracted_text": text,
        }

    def process_receipt(self, receipt: Receipt) -> Receipt:
        """Extract data from a receipt by trying all its image variants.

        Iterates through `receipt.processed_images`, runs OCR and field
        extraction on each variant, and keeps the result with the
        highest confidence score. Short-circuits if confidence reaches
        3 (all fields found).

        Mutates and returns the same `Receipt` instance with these
        fields populated: `vendor`, `amount`, `date`, `extracted_text`,
        `selected_method`, `confidence`.

        Args:
            receipt: A `Receipt` with `processed_images` populated by
                `ReceiptLoader`.

        Returns:
            The same `Receipt` instance, updated in place with
            extraction results. If no processed images are available,
            `confidence` is set to 0 and all other fields remain None.
        """
        if not hasattr(receipt, 'processed_images') or not receipt.processed_images:
            logger.warning("Receipt has no processed images")
            receipt.confidence = 0
            return receipt

        variant_count = len(receipt.processed_images)
        logger.debug(f"Processing receipt with {variant_count} image variants")

        best_result = {
            "vendor": None,
            "amount": None,
            "date": None,
            "confidence": 0,
            "method": None,
            "extracted_text": None
        }

        variants_tried = 0
        for variant, proc_img in receipt.processed_images.items():
            variants_tried += 1
            result = self.process_image_variant(proc_img, variant)

            if result["confidence"] > best_result["confidence"]:
                best_result = result
                logger.debug(
                    f"New best result: confidence={result['confidence']} "
                    f"from variant '{variant}'"
                )

            if best_result["confidence"] == 3:
                logger.debug(
                    f"Maximum confidence reached after "
                    f"{variants_tried}/{variant_count} variants"
                )
                break

        receipt.vendor = best_result["vendor"]
        receipt.amount = best_result["amount"]
        receipt.date = (
            datetime.fromisoformat(best_result["date"])
            if best_result["date"]
            else None
        )
        receipt.extracted_text = best_result["extracted_text"]
        receipt.selected_method = best_result["method"]
        receipt.confidence = best_result["confidence"]

        logger.debug(
            f"Extraction complete: vendor={receipt.vendor}, "
            f"amount={receipt.amount}, confidence={receipt.confidence}, "
            f"method={receipt.selected_method}"
        )

        return receipt