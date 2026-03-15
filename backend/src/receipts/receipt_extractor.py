import numpy as np
import pytesseract
import re
from datetime import datetime
from typing import Dict, Any, Optional

from src.models.receipt import Receipt
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ReceiptExtractor:
    """Extracts vendor, amount, and date from receipt images using OCR."""

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
        """Initialize the receipt extractor."""
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.debug(f"Using custom Tesseract path: {tesseract_path}")

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
        """Extract text using Tesseract with multiple PSM configs."""
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
        """Clean up OCR text."""
        text = re.sub(r"\s+", " ", text)
        text = text.replace("|", "I").replace("!", "i")
        return text

    def extract_vendor_name(self, text: str) -> Optional[str]:
        """Extract vendor name from OCR text."""
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
        """Extract amount from OCR text."""
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
        """Parse date string against known formats."""
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
        """Extract date from OCR text."""
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
        """
        Process a single image variant and extract receipt information.
        
        Args:
            image: The processed image array
            variant: The processing method name used
            
        Returns:
            Dictionary containing extracted vendor, amount, date, confidence, etc.
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
        """
        Process a receipt and extract information from its processed images.
        
        Args:
            receipt: Receipt object with processed_images attribute
            
        Returns:
            Updated receipt object with extracted information
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