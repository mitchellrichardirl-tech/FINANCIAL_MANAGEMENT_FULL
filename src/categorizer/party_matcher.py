from typing import Dict, List, Optional, Tuple
import logging

from fuzzywuzzy import fuzz, process

from src.database.repositories.categories import CategoryRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class PartyMatcher:
    """Handles party identification and fuzzy matching."""
    
    def __init__(
            self,
            db: Optional[CategoryRepository] = None,
            similarity_threshold: int = 70
            ):
        """Initialize the matcher with similarity threshold."""
        if not 0 <= similarity_threshold <= 100:
            raise ValueError(
                f"Similarity threshold must be between 0 and 100. {similarity_threshold} provided"
                )
        self.similarity_threshold = similarity_threshold
        self.db = db if db else CategoryRepository()
        self._load_known_parties()
        self.last_match_score: int = 0  # Track the last match score
        self.new_aliases = 0
        self.new_parties = 0
    
    def _load_known_parties(self) -> Dict[str, int]:
        """
        Load known party names and aliases from JSON file and/or database.
        
        Args:
            file_path: Path to known parties JSON file
            db_path: Path to database file (optional)
            
        Returns:
            Tuple of (alias mapping dict, canonical parties list)
        """
        logging.info("Loading known parties...")
        
        self.alias_mapping = self.db.get_all_parties()
              
        total_unique = len(set(self.alias_mapping.values()))
        total_aliases = len(self.alias_mapping)
        
        if total_unique > 0:
            logging.info(f"Total: {total_unique} unique parties with {total_aliases} total aliases")
        
        return self.alias_mapping
        
    def _check_exact_match(self, party_name: str) -> int:
        """Check for exact matches in all party lists."""
        # Check aliases
        try:
            return self.alias_mapping[party_name]
        except KeyError:
            raise KeyError(f"No exact match found for party name {party_name}")

    @staticmethod
    def custom_scorer(s1, s2):
        """Custom scorer that balances character and token matching."""
        # Character-level similarity (good for typos)
        char_score = fuzz.ratio(s1, s2)
        
        # Partial matching (good when one is substring of other)
        partial_score = fuzz.partial_ratio(s1, s2)
        
        # Take the higher score, with slight preference for character matching
        return max(char_score, partial_score * 0.95)

    def _check_fuzzy_match(self, party_name: str) -> Tuple[int, int]:
        """Check for fuzzy matches against all known parties."""
        
        if not self.alias_mapping:
            raise LookupError(f"No known parties to check against for party name {party_name}")
        
        # Find best fuzzy match
        best_match = process.extractOne(
            party_name,
            list(self.alias_mapping.keys()),
            scorer=self.custom_scorer
        )
        
        if best_match and best_match[1] >= self.similarity_threshold:
            matched_name, score = best_match[0], best_match[1]
            self.last_match_score = score
            party_id = self.alias_mapping[matched_name]
            
            # Add as alias for future exact matches (optional behavior)
            # Only add if not already an exact match somewhere
            if party_name not in self.alias_mapping:
                self.alias_mapping[party_name] = party_id
                self.new_aliases += 1
            
            return party_id, score
        
        raise KeyError(
            f"No match for party name '{party_name}' above threshold of "
            f"{self.similarity_threshold} found"
            )
    
    def find_match(self, party_name: str) -> Tuple[int, int]:
        """Find the best matching party for a given name."""

        if not party_name or party_name.strip() == "":
            raise ValueError("No party name provided")
        # Reset last match score
        self.last_match_score = 0
        
        try:
            party_id = self._check_exact_match(party_name)
            self.last_match_score = 100
            return party_id, self.last_match_score
        except KeyError as e:
            logging.debug(e)
     
        try:
            party_id, score = self._check_fuzzy_match(party_name)
            self.last_match_score = score
            return party_id, self.last_match_score
        except (LookupError, KeyError) as e:
            logging.debug(e)
        
        party_id = self.db.add_party_unknown_type(party_name)
        self.alias_mapping[party_name] = party_id
        self.new_parties += 1
        logging.info(f"New party name '{party_name}' created with id {party_id}")
        return party_id, 100
    
    def reset_counts(self):
        """Reset the counts of new aliases and parties."""
        self.new_aliases = 0
        self.new_parties = 0

    def get_new_counts(self) -> Tuple[int, int]:
        """Get the counts of new aliases and parties added."""
        return self.new_aliases, self.new_parties
        
if __name__ == '__main__':
    matcher = PartyMatcher()
    print(matcher.find_match("New party"))