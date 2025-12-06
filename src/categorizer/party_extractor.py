import re
from typing import List, Set, Optional
import pandas as pd


class PartyExtractor:
    """Handles cleaning and normalization of transaction descriptions."""
    
    DEFAULT_PATTERNS = [
        # Transaction type prefixes
        r'^(PAYMENT TO|TRANSFER TO|TRANSFER FROM|PURCHASE AT|POS TRANSACTION|'
        r'ONLINE PAYMENT|DIRECT DEBIT|DIRECT CREDIT|DEBIT CARD|CREDIT CARD)\s+',
        
        # Common merchant code prefixes
        r'^(POS|CNC|TKN|DD|CT|VPP|INET|Rtd)\s+',
        r'^(PAYMENT|TRANSFER|PURCHASE|DEBIT|CREDIT)\s+',
        
        # Dates and reference numbers
        r'\s+\d{2}/\d{2}/\d{2,4}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}:\d{2}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}$',
        r'\s+\d{4,}$',
        r'\s+REF:.*$',
        r'\s+\*{4}\d{4}$',
        r'\s+\d{2}-\d{2}-\d{2,4}.*$',
        
        # Time stamps
        r'\s+\d{1,2}:\d{2}.*$',
        
        # Location/branch codes
        r'\s+\d{1,3}$',  # Remove trailing numbers
        r'\s+[A-Z]\d{1,3}$',  # Like "G 28" or "D 25"
        r'\s+#\d+.*$',
    ]
    
    DEFAULT_STOP_WORDS = {
        # General
        'THE', 'AND', 'OR', 'FOR', 'WITH', 'AT', 'IN', 'ON', 'TO', 'FROM',
        
        # Transaction types
        'PAYMENT', 'TRANSFER', 'TRANSACTION', 'PURCHASE', 'DEBIT', 'CREDIT',
        'ONLINE', 'DIRECT', 'WITHDRAWAL', 'DEPOSIT', 'FOREIGN',
        
        # Card types
        'CARD', 'VISA', 'MASTERCARD', 'AMEX', 'AMERICAN', 'EXPRESS',
        
        # Common codes
        'POS', 'ATM', 'CNC', 'TKN', 'DD', 'CT', 'VPP', 'INET', 'RTD',
        
        # Generic terms
        'STORE', 'STORES', 'SHOP', 'CASH', 'FEE', 'FEES', 'CHARGE', 'CHARGES',
        'INTEREST', 'BRANCH', 'LOCATION', 'MERCHANT', 'SERVICE', 'SERVICES',
        
        # Company suffixes
        'LTD', 'LIMITED', 'LLC', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION',
        'PTY', 'COMPANY', 'CO', 'GROUP', 'HOLDINGS',
        
        # Country/location markers
        'IRELAND', 'IRISH', 'DUBLIN', 'IE', 'IRL', 'UK', 'GB', 'USA', 'US',
        'AUSTRALIA', 'AUS', 'AU',
        
        # Days/time
        'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
        'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY',
    }
    
    def __init__(self,
                 custom_patterns: Optional[List[str]] = None,
                 custom_stop_words: Optional[Set[str]] = None
                 ):
        """
        Initialize the cleaner with optional custom patterns and stop words.
        
        Args:
            custom_patterns: Additional regex patterns to remove
            custom_stop_words: Additional stop words to filter
        """
        self.patterns = self.DEFAULT_PATTERNS + (custom_patterns or [])
        self.stop_words = self.DEFAULT_STOP_WORDS.union(custom_stop_words or set())
    
    def clean(self, description: str) -> str:
        """
        Clean and normalize a description string.
        
        Args:
            description: Raw description text
            
        Returns:
            Cleaned description
        """
        if pd.isna(description):
            return ""
        
        text = str(description).upper()
        
        # Apply all removal patterns
        for pattern in self.patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove special characters, keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove any standalone single characters that aren't meaningful
        text = re.sub(r'\s+[A-Z]\s+', ' ', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    def extract_party_name(self, description: str, max_words: int = 3) -> str:
        """
        Extract potential party name from cleaned description.
        
        Args:
            description: Cleaned description text
            max_words: Maximum number of words to use for party name
            
        Returns:
            Extracted party name or "UNKNOWN"
        """
        if not description:
            return "UNKNOWN"
        
        words = description.split()
        
        # Filter out stop words and very short words
        meaningful_words = [
            word for word in words 
            if word not in self.stop_words and len(word) > 1
        ]
        
        if meaningful_words:
            # Take the first meaningful words as the party name
            party_name = ' '.join(meaningful_words[:max_words])
            
            return party_name.strip()
        
        # Fallback to truncated description
        return description[:30] if len(description) > 30 else description