import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from freezegun import freeze_time

from src.receipts.receipt_extractor import ReceiptExtractor
from src.models.receipt import Receipt


@pytest.fixture
def extractor():
    """Create a ReceiptExtractor instance."""
    return ReceiptExtractor()


@pytest.fixture
def mock_receipt():
    """Create a mock receipt object."""
    receipt = Mock(spec=Receipt)
    receipt.processed_images = {}
    receipt.vendor = None
    receipt.amount = None
    receipt.date = None
    receipt.confidence = 0
    receipt.selected_method = None
    return receipt


@pytest.fixture
def sample_image():
    """Create a sample image array."""
    return np.ones((100, 100), dtype=np.uint8) * 128


class TestReceiptExtractorInit:
    """Test ReceiptExtractor initialization."""
    
    def test_init_default(self):
        """Test default initialization."""
        extractor = ReceiptExtractor()
        assert len(extractor.vendor_patterns) == 4
        assert len(extractor.amount_patterns) == 4
        assert len(extractor.date_patterns) == 3
        assert extractor.MIN_AMOUNT == 0.01
        assert extractor.MAX_AMOUNT == 10000
    
    @patch('pytesseract.pytesseract')
    def test_init_with_tesseract_path(self, mock_tesseract):
        """Test initialization with custom tesseract path."""
        test_path = "/usr/bin/tesseract"
        extractor = ReceiptExtractor(tesseract_path=test_path)
        assert mock_tesseract.tesseract_cmd == test_path
    
    def test_constants(self):
        """Test that all constants are properly set."""
        extractor = ReceiptExtractor()
        assert extractor.MIN_AMOUNT == 0.01
        assert extractor.MAX_AMOUNT == 10000
        assert extractor.MIN_YEAR == 2000
        assert extractor.MAX_VENDOR_NAME_LENGTH == 50
        assert extractor.MIN_VENDOR_NAME_LENGTH == 3
        assert extractor.VENDOR_SEARCH_LINES == 10
        assert extractor.VENDOR_HEURISTIC_LINES == 5
        assert extractor.OCR_TIMEOUT == 20


class TestTextCleaning:
    """Test text cleaning functionality."""
    
    def test_clean_text_whitespace(self, extractor):
        """Test that excessive whitespace is removed."""
        text = "Hello    World  \n  Test"
        result = extractor.clean_text(text)
        assert result == "Hello World Test"
    
    def test_clean_text_ocr_errors(self, extractor):
        """Test OCR error corrections."""
        text = "He||o Wor!d"
        result = extractor.clean_text(text)
        assert result == "HeIIo Worid"
    
    def test_clean_text_empty(self, extractor):
        """Test cleaning empty string."""
        result = extractor.clean_text("")
        assert result == ""
    
    def test_clean_text_combined(self, extractor):
        """Test combined cleaning operations."""
        text = "TO|TAL:   $25.99   !tem"
        result = extractor.clean_text(text)
        assert "  " not in result
        assert "|" not in result
        assert "!" not in result


class TestVendorExtraction:
    """Test vendor name extraction."""
    
    def test_extract_vendor_eurogiant(self, extractor):
        """Test extraction of EuroGiant."""
        text = "EURO GIANT\nMain Street\nTotal: €25.99"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "euro" in vendor.lower() and "giant" in vendor.lower()
    
    def test_extract_vendor_walmart(self, extractor):
        """Test extraction of Walmart."""
        text = "WALMART SUPERCENTER\n123 Main St\nTotal: $45.67"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "walmart" in vendor.lower()
    
    def test_extract_vendor_tesco(self, extractor):
        """Test extraction of Tesco."""
        text = "Tesco Express\nHigh Street\nTotal: £12.34"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "tesco" in vendor.lower()
    
    def test_extract_vendor_generic_pattern(self, extractor):
        """Test extraction with generic pattern."""
        text = "SuperMarket Store\n123 Main St\nTotal: $25.99"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "SuperMarket" in vendor
    
    def test_extract_vendor_heuristic(self, extractor):
        """Test heuristic extraction (capitalized line)."""
        text = "FreshMart\nAddress line\nTotal: $15.50"
        vendor = extractor.extract_vendor_name(text)
        assert vendor == "FreshMart"
    
    def test_extract_vendor_none(self, extractor):
        """Test when no vendor is found."""
        # Use numeric and symbolic text that won't match any patterns
        text = "$25.99\n01/01/2024\n###\n***"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is None
    
    def test_extract_vendor_case_insensitive(self, extractor):
        """Test case-insensitive matching."""
        text = "walmart\nMain Street\nTotal: $45.67"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "walmart" in vendor.lower()
    
    def test_extract_vendor_with_special_chars(self, extractor):
        """Test vendor with special characters."""
        text = "Smith & Sons Market\nAddress\nTotal: $30.00"
        vendor = extractor.extract_vendor_name(text)
        assert vendor is not None
        assert "Smith" in vendor
    
    def test_extract_vendor_too_short(self, extractor):
        """Test that very short names are skipped by heuristic."""
        text = "AB\nsome text\nTotal: $25.99"
        # Should not match the heuristic
        # May still match if it's in patterns, but the heuristic requires >3 chars


class TestAmountExtraction:
    """Test amount extraction."""
    
    def test_extract_amount_with_total_label(self, extractor):
        """Test extraction with 'total' label."""
        text = "Total: €25.99"
        amount = extractor.extract_amount(text)
        assert amount == 25.99
    
    def test_extract_amount_with_currency_symbol(self, extractor):
        """Test extraction with currency symbol."""
        text = "Amount: $45.67"
        amount = extractor.extract_amount(text)
        assert amount == 45.67
    
    def test_extract_amount_with_currency_code(self, extractor):
        """Test extraction with currency code."""
        text = "Total: 123.45 EUR"
        amount = extractor.extract_amount(text)
        assert amount == 123.45
    
    def test_extract_amount_comma_separator(self, extractor):
        """Test extraction with comma as decimal separator."""
        text = "Total: €25,99"
        amount = extractor.extract_amount(text)
        assert amount == 25.99
    
    def test_extract_amount_multiple_amounts(self, extractor):
        """Test that maximum amount is returned."""
        text = "Subtotal: $10.00\nTax: $2.50\nTotal: $12.50"
        amount = extractor.extract_amount(text)
        assert amount == 12.50
    
    def test_extract_amount_none(self, extractor):
        """Test when no amount is found."""
        text = "Some receipt text without amounts"
        amount = extractor.extract_amount(text)
        assert amount is None
    
    def test_extract_amount_out_of_range_low(self, extractor):
        """Test that amounts below minimum are ignored."""
        text = "Total: $0.00"
        amount = extractor.extract_amount(text)
        assert amount is None
    
    def test_extract_amount_out_of_range_high(self, extractor):
        """Test that amounts above maximum are ignored."""
        text = "Total: $99999.99"
        amount = extractor.extract_amount(text)
        assert amount is None
    
    def test_extract_amount_at_boundaries(self, extractor):
        """Test amounts at min/max boundaries."""
        text1 = "Total: $0.01"
        amount1 = extractor.extract_amount(text1)
        assert amount1 == 0.01
        
        text2 = "Total: $10000.00"
        amount2 = extractor.extract_amount(text2)
        assert amount2 == 10000.00
    
    def test_extract_amount_pound_sign(self, extractor):
        """Test extraction with pound sign."""
        text = "Total: £50.00"
        amount = extractor.extract_amount(text)
        assert amount == 50.00
    
    def test_extract_amount_various_labels(self, extractor):
        """Test extraction with various labels."""
        texts = [
            "Amount Due: $25.99",
            "Balance: $25.99",
            "Grand Total: $25.99"
        ]
        for text in texts:
            amount = extractor.extract_amount(text)
            assert amount == 25.99


class TestDateParsing:
    """Test date parsing functionality."""
    
    def test_parse_date_slash_format(self, extractor):
        """Test parsing date with slash separator."""
        date = extractor.parse_date("25/12/2023")
        assert date == datetime(2023, 12, 25)
    
    def test_parse_date_dash_format(self, extractor):
        """Test parsing date with dash separator."""
        date = extractor.parse_date("25-12-2023")
        assert date == datetime(2023, 12, 25)
    
    def test_parse_date_short_year(self, extractor):
        """Test parsing date with 2-digit year."""
        date = extractor.parse_date("25/12/23")
        assert date == datetime(2023, 12, 25)
    
    def test_parse_date_month_name(self, extractor):
        """Test parsing date with month name."""
        date = extractor.parse_date("25 Dec 2023")
        assert date == datetime(2023, 12, 25)
    
    def test_parse_date_full_month_name(self, extractor):
        """Test parsing date with full month name."""
        date = extractor.parse_date("25 December 2023")
        assert date == datetime(2023, 12, 25)
    
    def test_parse_date_us_format(self, extractor):
        """Test parsing US date format (MM/DD/YYYY)."""
        date = extractor.parse_date("12/25/2023")
        # Could be Dec 25 or invalid day 25 in month 12
        assert date is not None
    
    def test_parse_date_invalid(self, extractor):
        """Test parsing invalid date."""
        date = extractor.parse_date("invalid date")
        assert date is None
    
    def test_parse_date_with_whitespace(self, extractor):
        """Test parsing date with extra whitespace."""
        date = extractor.parse_date("  25/12/2023  ")
        assert date == datetime(2023, 12, 25)


class TestDateExtraction:
    """Test date extraction from text."""
    
    @freeze_time("2024-01-15")
    def test_extract_date_slash_format(self, extractor):
        """Test extraction of date in slash format."""
        text = "Receipt Date: 15/01/2024\nTotal: $25.99"
        date = extractor.extract_date(text)
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15
    
    @freeze_time("2024-01-15")
    def test_extract_date_with_month_name(self, extractor):
        """Test extraction of date with month name."""
        text = "Date: 15 Jan 2024\nTotal: $25.99"
        date = extractor.extract_date(text)
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
    
    @freeze_time("2024-01-15")
    def test_extract_date_none(self, extractor):
        """Test when no date is found."""
        text = "Total: $25.99"
        date = extractor.extract_date(text)
        assert date is None
    
    def test_extract_date_old_year_rejected(self, extractor):
        """Test that very old dates are rejected."""
        text = "Date: 15/01/1999\nTotal: $25.99"
        date = extractor.extract_date(text)
        assert date is None
    
    @freeze_time("2024-01-15")
    def test_extract_date_future_year_accepted(self, extractor):
        """Test that next year is accepted."""
        text = "Date: 15/01/2025\nTotal: $25.99"
        date = extractor.extract_date(text)
        assert date is not None
        assert date.year == 2025
    
    @freeze_time("2024-01-15")
    def test_extract_date_far_future_rejected(self, extractor):
        """Test that far future dates are rejected."""
        text = "Date: 15/01/2030\nTotal: $25.99"
        date = extractor.extract_date(text)
        assert date is None
    
    @freeze_time("2024-01-15")
    def test_extract_date_multiple_valid_dates(self, extractor):
        """Test extraction returns first valid date when multiple valid dates exist."""
        text = "Issued: 01/01/2020\nValid: 15/01/2024\nTotal: $25.99"
        date = extractor.extract_date(text)
        # Returns first valid date found
        assert date is not None
        assert date.year == 2020

    @freeze_time("2024-01-15")
    def test_extract_date_skips_old_dates(self, extractor):
        """Test extraction skips dates before MIN_YEAR and finds valid one."""
        text = "Issued: 01/01/1999\nExpired: 01/01/1998\nValid: 15/01/2024\nTotal: $25.99"
        date = extractor.extract_date(text)
        # Should skip 1999 and 1998 (before MIN_YEAR=2000) and get 2024
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15


class TestOCRExtraction:
    """Test OCR text extraction."""
    
    @patch('pytesseract.image_to_string')
    def test_extract_text_success(self, mock_ocr, extractor, sample_image):
        """Test successful text extraction."""
        mock_ocr.return_value = "WALMART\nTotal: $25.99"
        
        text = extractor.extract_text_with_ocr(sample_image)
        
        assert text == "WALMART\nTotal: $25.99"
        assert mock_ocr.call_count >= 1
    
    @patch('pytesseract.image_to_string')
    def test_extract_text_tries_multiple_configs(self, mock_ocr, extractor, sample_image):
        """Test that multiple OCR configs are tried."""
        mock_ocr.side_effect = ["short", "longer text", "medium"]
        
        text = extractor.extract_text_with_ocr(sample_image)
        
        # Should return the longest result
        assert text == "longer text"
        assert mock_ocr.call_count == 3
    
    @patch('pytesseract.image_to_string')
    def test_extract_text_handles_ocr_failure(self, mock_ocr, extractor, sample_image):
        """Test handling of OCR failures."""
        mock_ocr.side_effect = [
            Exception("OCR Error"),
            "Success",
            Exception("Another error")
        ]
        
        text = extractor.extract_text_with_ocr(sample_image)
        
        assert text == "Success"
    
    @patch('pytesseract.image_to_string')
    def test_extract_text_all_configs_fail(self, mock_ocr, extractor, sample_image):
        """Test when all OCR configs fail."""
        mock_ocr.side_effect = Exception("OCR Error")
        
        text = extractor.extract_text_with_ocr(sample_image)
        
        assert text == ""
    
    def test_extract_text_invalid_image_none(self, extractor):
        """Test with None image."""
        text = extractor.extract_text_with_ocr(None)
        assert text == ""
    
    def test_extract_text_empty_image(self, extractor):
        """Test with empty image."""
        empty_image = np.array([])
        text = extractor.extract_text_with_ocr(empty_image)
        assert text == ""
    
    @patch('pytesseract.image_to_string')
    def test_extract_text_timeout_parameter(self, mock_ocr, extractor, sample_image):
        """Test that timeout parameter is passed to OCR."""
        mock_ocr.return_value = "Test"
        
        extractor.extract_text_with_ocr(sample_image)
        
        # Check that timeout was passed
        call_kwargs = mock_ocr.call_args[1]
        assert 'timeout' in call_kwargs
        assert call_kwargs['timeout'] == 20


class TestProcessImageVariant:
    """Test processing of image variants."""
    
    @patch.object(ReceiptExtractor, 'extract_text_with_ocr')
    def test_process_image_variant_full_data(self, mock_ocr, extractor, sample_image):
        """Test processing with all data present."""
        mock_ocr.return_value = "WALMART\nDate: 15/01/2024\nTotal: $25.99"
        
        result = extractor.process_image_variant(sample_image, "denoise")
        
        assert result["vendor"] is not None
        assert result["amount"] == 25.99
        assert result["date"] is not None
        assert result["confidence"] == 3
        assert result["method"] == "denoise"
        assert len(result["text"]) > 0
    
    @patch.object(ReceiptExtractor, 'extract_text_with_ocr')
    def test_process_image_variant_partial_data(self, mock_ocr, extractor, sample_image):
        """Test processing with partial data."""
        mock_ocr.return_value = "WALMART\nTotal: $25.99"
        
        result = extractor.process_image_variant(sample_image, "clahe")
        
        assert result["vendor"] is not None
        assert result["amount"] == 25.99
        assert result["date"] is None
        assert result["confidence"] == 2
        assert result["method"] == "clahe"
    
    @patch.object(ReceiptExtractor, 'extract_text_with_ocr')
    def test_process_image_variant_no_data(self, mock_ocr, extractor, sample_image):
        """Test processing with no extractable data."""
        # Use garbled OCR text that shouldn't match any patterns
        mock_ocr.return_value = "... ... ...\n####### \n12 34 56\n"
        
        result = extractor.process_image_variant(sample_image, "morphological")
        
        assert result["vendor"] is None
        assert result["amount"] is None
        assert result["date"] is None
        assert result["confidence"] == 0
        assert result["method"] == "morphological"
    
    @patch.object(ReceiptExtractor, 'extract_text_with_ocr')
    def test_process_image_variant_empty_text(self, mock_ocr, extractor, sample_image):
        """Test processing when OCR returns empty text."""
        mock_ocr.return_value = ""
        
        result = extractor.process_image_variant(sample_image, "test_method")
        
        assert result["vendor"] is None
        assert result["amount"] is None
        assert result["date"] is None
        assert result["confidence"] == 0
        assert result["text"] == ""
    
    @patch.object(ReceiptExtractor, 'extract_text_with_ocr')
    def test_process_image_variant_date_isoformat(self, mock_ocr, extractor, sample_image):
        """Test that date is returned in ISO format."""
        mock_ocr.return_value = "Date: 15/01/2024\nTotal: $25.99"
        
        result = extractor.process_image_variant(sample_image, "test")
        
        if result["date"]:
            # Should be ISO format string
            assert isinstance(result["date"], str)
            assert "2024" in result["date"]
            # Should be parseable back to datetime
            datetime.fromisoformat(result["date"])


class TestProcessReceipt:
    """Test full receipt processing."""
    
    @patch.object(ReceiptExtractor, 'process_image_variant')
    def test_process_receipt_single_image(self, mock_process, extractor, mock_receipt, sample_image):
        """Test processing receipt with single image."""
        mock_receipt.processed_images = {"denoise": sample_image}
        mock_process.return_value = {
            "vendor": "WALMART",
            "amount": 25.99,
            "date": "2024-01-15T00:00:00",
            "confidence": 3,
            "method": "denoise",
            "text": "WALMART\nTotal: $25.99"
        }
        
        result = extractor.process_receipt(mock_receipt)
        
        assert result.vendor == "WALMART"
        assert result.amount == 25.99
        assert result.date == datetime(2024, 1, 15)
        assert result.confidence == 3
        assert result.selected_method == "denoise"
    
    @patch.object(ReceiptExtractor, 'process_image_variant')
    def test_process_receipt_multiple_images(self, mock_process, extractor, mock_receipt, sample_image):
        """Test processing receipt with multiple images."""
        mock_receipt.processed_images = {
            "denoise": sample_image,
            "clahe": sample_image,
            "morphological": sample_image
        }
        
        # Return different confidence levels
        mock_process.side_effect = [
            {"vendor": None, "amount": None, "date": None, "confidence": 0, "method": "denoise"},
            {"vendor": "WALMART", "amount": 25.99, "date": "2024-01-15T00:00:00", "confidence": 3, "method": "clahe"},
            {"vendor": "WAL", "amount": 25.99, "date": None, "confidence": 2, "method": "morphological"}
        ]
        
        result = extractor.process_receipt(mock_receipt)
        
        assert result.vendor == "WALMART"
        assert result.confidence == 3
        assert result.selected_method == "clahe"
        # Should stop after finding confidence 3
        assert mock_process.call_count == 2  # First two calls only
    
    @patch.object(ReceiptExtractor, 'process_image_variant')
    def test_process_receipt_picks_best_result(self, mock_process, extractor, mock_receipt, sample_image):
        """Test that best result is selected."""
        mock_receipt.processed_images = {
            "method1": sample_image,
            "method2": sample_image,
            "method3": sample_image
        }
        
        mock_process.side_effect = [
            {"vendor": "W", "amount": None, "date": None, "confidence": 1, "method": "method1"},
            {"vendor": "WALMART", "amount": 25.99, "date": None, "confidence": 2, "method": "method2"},
            {"vendor": "WAL", "amount": 20.00, "date": "2024-01-15T00:00:00", "confidence": 2, "method": "method3"}
        ]
        
        result = extractor.process_receipt(mock_receipt)
        
        # Should pick method2 as it was the first with confidence 2
        assert result.confidence == 2
        assert result.selected_method == "method2"
    
    def test_process_receipt_no_processed_images(self, extractor, mock_receipt):
        """Test processing receipt with no processed images."""
        mock_receipt.processed_images = {}
        
        result = extractor.process_receipt(mock_receipt)
        
        assert result.confidence == 0
    
    def test_process_receipt_missing_attribute(self, extractor):
        """Test processing receipt without processed_images attribute."""
        receipt = Mock(spec=[])  # No attributes
        receipt.confidence = 0
        
        result = extractor.process_receipt(receipt)
        
        assert result.confidence == 0
    
    @patch.object(ReceiptExtractor, 'process_image_variant')
    def test_process_receipt_none_date(self, mock_process, extractor, mock_receipt, sample_image):
        """Test processing when date is None."""
        mock_receipt.processed_images = {"test": sample_image}
        mock_process.return_value = {
            "vendor": "WALMART",
            "amount": 25.99,
            "date": None,
            "confidence": 2,
            "method": "test",
            "text": "text"
        }
        
        result = extractor.process_receipt(mock_receipt)
        
        assert result.date is None


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_extract_vendor_empty_text(self, extractor):
        """Test vendor extraction with empty text."""
        vendor = extractor.extract_vendor_name("")
        assert vendor is None
    
    def test_extract_amount_empty_text(self, extractor):
        """Test amount extraction with empty text."""
        amount = extractor.extract_amount("")
        assert amount is None
    
    def test_extract_date_empty_text(self, extractor):
        """Test date extraction with empty text."""
        date = extractor.extract_date("")
        assert date is None
    
    def test_extract_vendor_newlines_only(self, extractor):
        """Test vendor extraction with only newlines."""
        vendor = extractor.extract_vendor_name("\n\n\n")
        assert vendor is None
    
    def test_extract_amount_invalid_format(self, extractor):
        """Test amount extraction with invalid formats."""
        texts = [
            "Total: ABC.99",
            "Total: $$$",
            "Total: ...",
        ]
        for text in texts:
            amount = extractor.extract_amount(text)
            # Should either be None or ignore invalid amounts
    
    def test_extract_vendor_special_characters_only(self, extractor):
        """Test vendor extraction with special characters."""
        vendor = extractor.extract_vendor_name("@#$%\n!!!!\n***")
        # Should not crash
        assert vendor is None or isinstance(vendor, str)
    
    def test_clean_text_unicode(self, extractor):
        """Test text cleaning with unicode characters."""
        text = "Café\u00A0Restaurant"
        result = extractor.clean_text(text)
        assert isinstance(result, str)
    
    @freeze_time("2024-01-15")
    def test_extract_date_ambiguous_format(self, extractor):
        """Test date extraction with ambiguous format."""
        # 01/02/2024 could be Jan 2 or Feb 1
        text = "Date: 01/02/2024"
        date = extractor.extract_date(text)
        # Should parse successfully (interpretation may vary)
        assert date is not None
        assert date.year == 2024


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.integration
    @patch('pytesseract.image_to_string')
    def test_full_receipt_processing_flow(self, mock_ocr, sample_image):
        """Test complete flow from image to extracted data."""
        # Create extractor
        extractor = ReceiptExtractor()
        
        # Mock OCR output
        mock_ocr.return_value = """
        WALMART SUPERCENTER
        123 Main Street
        Date: 15/01/2024
        
        Item 1    $10.00
        Item 2    $15.99
        
        Subtotal  $25.99
        Tax       $2.08
        Total     $28.07
        
        Thank you for shopping!
        """
        
        # Create receipt
        receipt = Mock(spec=Receipt)
        receipt.processed_images = {"test_method": sample_image}
        receipt.vendor = None
        receipt.amount = None
        receipt.date = None
        receipt.confidence = 0
        receipt.selected_method = None
        
        # Process
        result = extractor.process_receipt(receipt)
        
        # Verify
        assert result.vendor is not None
        assert "walmart" in result.vendor.lower()
        assert result.amount == 28.07  # Should extract the total
        assert result.date is not None
        assert result.date.day == 15
        assert result.date.month == 1
        assert result.date.year == 2024
        assert result.confidence == 3