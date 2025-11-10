import numpy as np
import pytesseract
import re
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from src.models.receipt import Receipt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReceiptExtractor:
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
        """Initialize the enhanced receipt processor."""
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Vendor patterns - all with capturing groups
        self.vendor_patterns = [
            r"(euro\s*giant|eurogiant)",
            r"(walmart|target|costco|kroger|safeway|cvs|walgreens)",
            r"(tesco|asda|sainsbury|morrisons|aldi|lidl)",
            r"([A-Z][A-Za-z\s&\-\.]{3,30}(?:store|shop|market|retail)?)",
        ]

        # Amount patterns
        self.amount_patterns = [
            r"(?:total|amount\s+due|balance|grand\s+total)[\s:€$£]*(\d+[.,]\d{2})",
            r"(?:total)[\s:]*[€$£]?\s*(\d+[.,]\d{2})",
            r"[€$£]\s*(\d+[.,]\d{2})",
            r"(\d+[.,]\d{2})\s*(?:EUR|USD|GBP|€|$|£)",
        ]

        # Date patterns
        self.date_patterns = [
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}",
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}",
        ]

    def extract_text_with_ocr(self, image: np.ndarray) -> str:
        """Extract text using Tesseract."""
        if image is None or image.size == 0:
            logger.warning("Invalid image provided for OCR")
            return ""
            
        configs = [
            "--psm 6 --oem 1",  # Uniform text block
            "--psm 4 --oem 1",  # Single column
            "--psm 3 --oem 1",  # Fully automatic
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
            except Exception as e:
                logger.warning(f"OCR failed with {config}: {e}")
                continue

        return best_text

    def clean_text(self, text: str) -> str:
        """Clean up OCR text."""
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove common OCR errors
        text = text.replace("|", "I").replace("!", "i")
        return text

    def extract_vendor_name(self, text: str) -> Optional[str]:
        """Extract vendor name."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Clean the text
        cleaned_lines = [self.clean_text(line) for line in lines]

        # Try patterns
        for pattern in self.vendor_patterns:
            for line in cleaned_lines[:self.VENDOR_SEARCH_LINES]:
                try:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        result = match.group(1)
                        return result.strip()
                except Exception:
                    continue

        # Heuristic: look for capitalized lines
        for line in lines[:self.VENDOR_HEURISTIC_LINES]:
            if (self.MIN_VENDOR_NAME_LENGTH < len(line) < 
                self.MAX_VENDOR_NAME_LENGTH):
                words = line.split()
                if words and words[0][0].isupper():
                    return line

        return None

    def extract_amount(self, text: str) -> Optional[float]:
        """Extract amount."""
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

        return max(amounts) if amounts else None

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string."""
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
        """Extract date."""
        for pattern in self.date_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    date_obj = self.parse_date(match)
                    if date_obj:
                        year = date_obj.year
                        current_year = datetime.now().year
                        if self.MIN_YEAR <= year <= current_year + 1:
                            return date_obj
            except Exception:
                continue

        return None

    def process_image_variant(self, image: np.ndarray, variant: str) -> Dict[str, Any]:
        """Process a single image variant and extract receipt information.
        
        Args:
            image: The processed image array
            variant: The processing method name used
            
        Returns:
            Dictionary containing extracted vendor, amount, date, confidence, etc.
        """
        text = self.extract_text_with_ocr(image).strip()
        if text:
            vendor = self.extract_vendor_name(text)
            amount = self.extract_amount(text)
            date = self.extract_date(text)

            confidence = sum(
                [vendor is not None, amount is not None, date is not None]
            )
            return {
                "vendor": vendor,
                "amount": amount,
                "date": date.isoformat() if date else None,
                "confidence": confidence,
                "method": variant,
                "text": text,
            }
        return {
            "vendor": None,
            "amount": None,
            "date": None,
            "confidence": 0,
            "method": variant,
            "text": "",
        }

    def process_receipt(self, receipt: Receipt) -> Receipt:
        """Process a receipt and extract information from its processed images.
        
        Args:
            receipt: Receipt object with processed_images attribute
            
        Returns:
            Updated receipt object with extracted information
        """
        if not hasattr(receipt, 'processed_images') or not receipt.processed_images:
            logger.warning("Receipt has no processed images")
            receipt.confidence = 0
            return receipt

        best_result = {
            "vendor": None, 
            "amount": None, 
            "date": None, 
            "confidence": 0,
            "method": None
        }

        for variant, proc_img in receipt.processed_images.items():
            logger.info(f"Extracting from variant: {variant}")
            result = self.process_image_variant(proc_img, variant)
            if result["confidence"] > best_result["confidence"]:
                logger.info(f"New best result with confidence {result['confidence']} from variant {variant}")
                best_result = result
            if best_result["confidence"] == 3:
                logger.info("Maximum confidence reached, stopping early.")
                break
        
        receipt.vendor = best_result["vendor"]
        receipt.amount = best_result["amount"]
        receipt.date = (
            datetime.fromisoformat(best_result["date"])
            if best_result["date"]
            else None
        )
        receipt.selected_method = best_result["method"]
        receipt.confidence = best_result["confidence"]
        return receipt
    

if __name__ == "__main__":
    from src.receipts.receipt_loader import ReceiptLoader

    receipt_loader = ReceiptLoader()
    extractor = ReceiptExtractor()

    for recipt in receipt_loader.process_files(
        "/workspaces/financial_management/data/Eimaer Filed Affidaivt of Means 23.9.25_280466.pdf", yield_pages=True
    ):
    
        result = extractor.process_receipt(recipt)
        print(f"Vendor: {result.vendor}, Amount: {result.amount}, Date: {result.date}, Confidence: {result.confidence}, Method: {result.selected_method}")