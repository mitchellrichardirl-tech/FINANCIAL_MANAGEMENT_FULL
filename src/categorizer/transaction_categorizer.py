import logging
from typing import Optional, Tuple, Dict, List, Union

from src.categorizer.party_extractor import PartyExtractor
from src.categorizer.party_matcher import PartyMatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class TransactionCategorizer:
    """Main categorizer class that orchestrates the categorization process."""
    
    def __init__(
        self,
        similarity_threshold: int = 80
        ):
        
        # Initialize components
        self.extractor = PartyExtractor()
        self.matcher = PartyMatcher(similarity_threshold=similarity_threshold)
        
        logging.info('Cleaner and matcher initialized')
    
    def categorize(self, transactions: List[str]) -> List[Dict[str, Union[int, None]]]:

        if not transactions:
            raise ValueError("No transactions data provided")
        
        logging.info("Starting categorization process")
        party_mapping_ids = []
        self.matcher.reset_counts()
        # Process each transaction
        for idx, description in enumerate(transactions):
               
            if (idx + 1) % 100 == 0:
                logging.info(f"Processing transaction {idx + 1}/{len(transactions)}")
            
            if not description or description.strip() == '':
                extracted = 'UNKNOWN'
            else:
                # Clean and extract party name
                cleaned = self.extractor.clean(description)
                extracted = self.extractor.extract_party_name(cleaned)
                    
            party_id, confidence = self.matcher.find_match(extracted)

            party_mapping_ids.append({
                'cleaned_description': extracted,
                'party_id': party_id,
                'confidence': confidence
                })            
        
        new_aliases, new_parties = self.matcher.get_new_counts()
        logging.info(f"{len(party_mapping_ids)} transactions mapped to parties."
                     f"{new_parties} new parties added,"
                     f" and {new_aliases} new aliases")
        
        return party_mapping_ids
    
if __name__ == "__main__":
    categorizer = TransactionCategorizer()
    print(categorizer.categorize(['New Party']))
