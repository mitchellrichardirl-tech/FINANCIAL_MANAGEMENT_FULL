from datetime import datetime
from typing import Any, Dict, List, Optional


class ReceiptFormatter:
    """Formats receipt data for API responses."""
    
    @staticmethod
    def format_date(date_value: Any) -> Optional[str]:
        """Format a date value to ISO string."""
        if date_value is None:
            return None
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        if isinstance(date_value, str):
            return date_value
        return str(date_value)
    
    @classmethod
    def summary(cls, receipt: Dict) -> Dict:
        """Format receipt for list views (minimal data)."""
        return {
            'id': receipt['id'],
            'original_filename': receipt['original_filename'],
            'vendor': receipt['vendor'],
            'amount': receipt['amount'],
            'date': cls.format_date(receipt.get('date')),
            'confidence': receipt['confidence'],
            'created_at': receipt.get('created_at'),
        }
    
    @classmethod
    def detail(cls, receipt: Dict) -> Dict:
        """Format receipt for detail views (full data)."""
        return {
            'id': receipt['id'],
            'original_filename': receipt['original_filename'],
            'stored_filename': receipt['stored_filename'],
            'vendor': receipt['vendor'],
            'amount': receipt['amount'],
            'date': cls.format_date(receipt.get('date')),
            'confidence': receipt['confidence'],
            'selected_method': receipt.get('selected_method'),
            'raw_text': receipt.get('raw_text'),
            'metadata': receipt.get('metadata', {}),
            'created_at': receipt.get('created_at'),
            'updated_at': receipt.get('updated_at'),
        }
    
    @classmethod
    def summary_list(cls, receipts: List[Dict]) -> List[Dict]:
        """Format a list of receipts for list views."""
        return [cls.summary(r) for r in receipts]
    
    @classmethod
    def extracted_data(cls, receipt) -> Dict:
        """Format extracted data from a processed receipt object."""
        return {
            'vendor': receipt.vendor,
            'amount': receipt.amount,
            'date': cls.format_date(receipt.date),
            'confidence': getattr(receipt, 'confidence', None),
            'selected_method': getattr(receipt, 'selected_method', None),
            'raw_text': getattr(receipt, 'extracted_text', None),
        }