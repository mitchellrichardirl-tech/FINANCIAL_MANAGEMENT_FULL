from typing import Dict, Iterable, Optional
import pytest

from src.categorizer.party_matcher_raw import PartyMatcherRaw


class FakeCategoryRepository:
    """
    In-memory stand-in for CategoryRepository.

    Only needed when testing PartyMatcher (the DB-backed class) directly.
    For pure logic tests, use PartyMatcherRaw instead.
    """

    def __init__(self, aliases: Optional[Dict[str, int]] = None):
        self._aliases: Dict[str, int] = dict(aliases or {})
        self._next_id = (max(self._aliases.values()) + 1) if self._aliases else 1
        self.added_parties: list[str] = []
        self.bulk_added_parties: list[list[str]] = []
        self.prime_cache_calls = 0

    def get_all_party_aliases(self) -> Dict[str, int]:
        return dict(self._aliases)

    def add_party_unknown_type(self, party_name: str) -> int:
        pid = self._next_id
        self._next_id += 1
        self._aliases[party_name] = pid
        self.added_parties.append(party_name)
        return pid

    def bulk_add_parties_unknown_type(self, names: Iterable[str]) -> Dict[str, int]:
        names = list(names)
        self.bulk_added_parties.append(names)
        return {n: self.add_party_unknown_type(n) for n in names}

    def prime_unknown_type_cache(self) -> None:
        self.prime_cache_calls += 1


@pytest.fixture
def fake_repo():
    return FakeCategoryRepository()


@pytest.fixture
def make_matcher():
    """
    Factory: build a PartyMatcher with a fake repo, seeded with aliases.

        matcher, repo = make_matcher({"WALMART": 1})
    """
    from src.categorizer.party_matcher import PartyMatcher

    def _make(aliases: Optional[Dict[str, int]] = None, **kwargs):
        repo = FakeCategoryRepository(aliases)
        matcher = PartyMatcher(db=repo, **kwargs)
        return matcher, repo

    return _make


@pytest.fixture
def raw_matcher():
    """
    Factory: build a PartyMatcherRaw, optionally pre-seeded with aliases.

        matcher = raw_matcher({"WALMART": 1, "TARGET": 2})

    No DB involved at all.
    """
    def _make(
        aliases: Optional[Dict[str, int]] = None,
        similarity_threshold: int = 70,
    ) -> PartyMatcherRaw:
        matcher = PartyMatcherRaw(similarity_threshold=similarity_threshold)
        if aliases:
            matcher.alias_mapping = {
                matcher._normalize(k): v for k, v in aliases.items()
            }
            matcher._refresh_alias_keys()
        return matcher

    return _make


@pytest.fixture
def make_readonly_matcher():
    """
    Factory: build a PartyMatcherReadOnly backed by a fake repo.

        matcher, repo = make_readonly_matcher({"WALMART": 1})
    """
    from src.categorizer.party_matcher import PartyMatcherReadOnly

    def _make(aliases=None, **kwargs):
        repo = FakeCategoryRepository(aliases)
        return PartyMatcherReadOnly(db=repo, **kwargs), repo

    return _make

@pytest.fixture
def make_categorizer():
    """
    Factory: build a TransactionCategorizer with use_db=False and
    optionally seed the underlying matcher with aliases.

        cat = make_categorizer({"WALMART": 1}, similarity_threshold=70)
    """
    from src.categorizer.transaction_categorizer import TransactionCategorizer

    def _make(aliases=None, **kwargs):
        cat = TransactionCategorizer(use_db=False, **kwargs)
        if aliases:
            cat.matcher.alias_mapping = {
                cat.matcher._normalize(k): v for k, v in aliases.items()
            }
            cat.matcher._refresh_alias_keys()
        return cat

    return _make

@pytest.fixture
def extractor():
    """Default PartyExtractor, no custom patterns or stop words."""
    from src.categorizer.party_extractor import PartyExtractor
    return PartyExtractor()