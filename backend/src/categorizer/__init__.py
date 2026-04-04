from .party_matcher import PartyMatcher
from .party_matcher_raw import PartyMatcherRaw

def get_party_matcher(similarity_threshold: int = 70, use_db: bool = True) -> PartyMatcher:
    """
    Factory for obtaining a PartyMatcher.

    Args:
        similarity_threshold: Minimum score to accept a fuzzy match (0–100).
        use_db: If True, returns a `PartyMatcher` with full DB integration.
            If False, returns a `PartyMatcherRaw` (same algorithm, no DB —
            useful for testing or offline scoring).

    Returns:
        `PartyMatcher` or `PartyMatcherRaw` depending on `use_db`.
    """
    if use_db:
        return PartyMatcher(similarity_threshold=similarity_threshold)
    return PartyMatcherRaw(similarity_threshold=similarity_threshold)