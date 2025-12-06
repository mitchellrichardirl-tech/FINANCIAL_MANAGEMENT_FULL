from pathlib import Path
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from src.database.repositories.categories import CategoryRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class ConfigurationLoader:
    """Handles loading and parsing of configuration files."""
    
    @staticmethod
    def load_json_file(file_path: Path) -> Dict:
        """Load and parse a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.warning(f"Configuration file '{file_path}' not found")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON in '{file_path}': {e}")
            return {}
        except Exception as e:
            logging.error(f"Error loading configuration from '{file_path}': {e}")
            return {}
    
    @staticmethod
    def load_custom_terms(file_path: Optional[Path]) -> Tuple[List[str], Set[str]]:
        """
        Load custom patterns and stop words from configuration file.
        
        Args:
            file_path: Path to custom terms file
            
        Returns:
            Tuple of (patterns list, stop words set)
        """
        if not file_path:
            return [], set()
        
        data = ConfigurationLoader.load_json_file(file_path)
        patterns = data.get('patterns', [])
        stop_words = {word.upper() for word in data.get('stop_words', [])}
        
        logging.info(f"Loaded {len(patterns)} patterns and {len(stop_words)} stop words")
        return patterns, stop_words
    
    @staticmethod
    def load_known_parties(
        file_path: Optional[Path],
        db: Optional[CategoryRepository] = None
        ) -> Tuple[Dict[str, str], List[str]]:
        """
        Load known party names and aliases from JSON file and/or database.
        
        Args:
            file_path: Path to known parties JSON file
            db_path: Path to database file (optional)
            
        Returns:
            Tuple of (alias mapping dict, canonical parties list)
        """
        logging.info("Loading known parties...")
        alias_mapping = {}
        canonical_parties = []
        
        # Load from database if path provided
        if db:
            db_aliases, db_canonical = db.get_all_parties()
            alias_mapping.update(db_aliases)
            canonical_parties.extend(db_canonical)
        
        # Load from JSON file if provided
        if file_path:
            data = ConfigurationLoader.load_json_file(file_path)
            
            for party_data in data.get('parties', []):
                if 'name' not in party_data:
                    continue
                    
                party_id = party_data['id']
                canonical_name = party_data['name'].upper()
                
                # Add if not already in list
                if canonical_name not in canonical_parties:
                    canonical_parties.append(canonical_name)
                    alias_mapping[canonical_name] = party_id
                
                # Add all aliases
                for alias in party_data.get('aliases', []):
                    alias_upper = alias.upper()
                    alias_mapping[alias_upper] = party_id
            
            logging.info(f"Loaded {len([p for p in data.get('parties', [])])} parties from JSON")
        
        total_unique = len(canonical_parties)
        total_aliases = len(alias_mapping)
        
        if total_unique > 0:
            logging.info(f"Total: {total_unique} unique parties with {total_aliases} total aliases")
        
        return alias_mapping, canonical_parties