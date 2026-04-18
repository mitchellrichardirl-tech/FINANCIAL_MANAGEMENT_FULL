from pathlib import Path
import json
from typing import Dict, List, Optional, Set, Tuple

from src.database.repositories.categories import CategoryRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ConfigurationLoader:
    """Handles loading and parsing of configuration files."""

    @staticmethod
    def load_json_file(file_path: Path) -> Dict:
        """Load and parse a JSON file."""
        logger.debug(f"Loading JSON file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Successfully loaded: {file_path}")
            return data

        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {file_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
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
            logger.debug("No custom terms file specified")
            return [], set()

        data = ConfigurationLoader.load_json_file(file_path)

        if not data:
            return [], set()

        patterns = data.get('patterns', [])
        stop_words = {word.upper() for word in data.get('stop_words', [])}

        logger.info(
            f"Loaded custom terms from {file_path.name}: "
            f"{len(patterns)} patterns, {len(stop_words)} stop words"
        )
        return patterns, stop_words

    @staticmethod
    def load_known_parties(
        file_path: Optional[Path],
        db: Optional[CategoryRepository] = None
    ) -> Tuple[Dict[str, int], List[str]]:
        """
        Load known party names and aliases from JSON file and/or database.
        
        Args:
            file_path: Path to known parties JSON file
            db: CategoryRepository instance (optional)
            
        Returns:
            Tuple of (alias mapping dict, canonical parties list)
        """
        logger.info("Loading known parties")

        alias_mapping: Dict[str, int] = {}
        canonical_parties: List[str] = []
        db_count = 0
        json_count = 0

        # Load from database if provided
        if db:
            logger.debug("Loading parties from database")
            try:
                db_aliases = db.get_all_party_aliases()
                alias_mapping.update(db_aliases)
                db_count = len(db_aliases)
                logger.debug(f"Loaded {db_count} aliases from database")
            except Exception as e:
                logger.error(f"Failed to load parties from database: {e}")

        # Load from JSON file if provided
        if file_path:
            logger.debug(f"Loading parties from JSON: {file_path}")
            data = ConfigurationLoader.load_json_file(file_path)

            parties_data = data.get('parties', [])
            for party_data in parties_data:
                if 'name' not in party_data:
                    logger.debug(f"Skipping party entry without name: {party_data}")
                    continue

                party_id = party_data.get('id')
                if party_id is None:
                    logger.warning(f"Party '{party_data['name']}' has no ID, skipping")
                    continue

                canonical_name = party_data['name'].upper()

                if canonical_name not in canonical_parties:
                    canonical_parties.append(canonical_name)
                    alias_mapping[canonical_name] = party_id

                for alias in party_data.get('aliases', []):
                    alias_upper = alias.upper()
                    if alias_upper not in alias_mapping:
                        alias_mapping[alias_upper] = party_id

            json_count = len(parties_data)
            logger.debug(f"Loaded {json_count} parties from JSON")

        total_aliases = len(alias_mapping)
        total_canonical = len(canonical_parties)

        if total_aliases > 0:
            logger.info(
                f"Loaded parties: {total_canonical} canonical names, "
                f"{total_aliases} total aliases "
                f"(db={db_count}, json={json_count})"
            )
        else:
            logger.warning("No parties loaded from any source")

        return alias_mapping, canonical_parties