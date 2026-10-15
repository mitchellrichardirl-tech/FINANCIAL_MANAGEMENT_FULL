"""
CategoryRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched tests are the DatabaseError-wrapping checks.
"""
import pytest

from src.database.errors import DatabaseError
from src.database.repositories.categories import (
    CategoryRepository,
    RemapConflictError,
)


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield CategoryRepository()


@pytest.fixture
def sample_hierarchy(repo):
    """Expenses → Transportation → Fuel → Shell."""
    category_id = repo.add_category("Expenses", "All expenses")
    sub_category_id = repo.add_sub_category(
        "Transportation", category_id, "Travel costs"
    )
    type_id = repo.add_type("Fuel", sub_category_id, "Gas purchases")
    party_id = repo.add_party("Shell", type_id, "Shell gas stations")

    return {
        "category_id": category_id,
        "sub_category_id": sub_category_id,
        "type_id": type_id,
        "party_id": party_id,
    }


@pytest.fixture
def make_party_transaction(app_with_db, test_data):
    """Factory: make_party_transaction(party_id, **overrides) -> transaction id."""
    upload_id = test_data.create_upload(app_with_db)

    def _make(party_id, **kwargs):
        kwargs.setdefault("amount", -10.00)
        return test_data.create_transaction(app_with_db, upload_id, party_id, **kwargs)

    return _make


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
class TestAddCategory:

    def test_returns_id_of_persisted_row(self, repo):
        category_id = repo.add_category("Expenses", "All expense transactions")
        assert isinstance(category_id, int) and category_id > 0

        category = repo.get_category_by_id(category_id)
        assert category["category"] == "Expenses"
        assert category["description"] == "All expense transactions"
        assert category["created_at"] is not None

    def test_description_defaults_to_null(self, repo):
        category_id = repo.add_category("Income")
        assert repo.get_category_by_id(category_id)["description"] is None

    def test_duplicate_name_rejected(self, repo):
        repo.add_category("Expenses")
        with pytest.raises(DatabaseError) as exc:
            repo.add_category("Expenses")
        assert "already exists" in str(exc.value).lower()

    def test_multiple_categories_get_distinct_ids(self, repo):
        ids = {repo.add_category(n) for n in ("Expenses", "Income", "Transfers")}
        assert len(ids) == 3
        assert all(repo.get_category_by_id(i) is not None for i in ids)


class TestUpdateCategory:

    def test_update_name(self, repo):
        category_id = repo.add_category("Expnses")  # typo
        assert repo.update_category(category_id, category="Expenses")["category"] == "Expenses"
        assert repo.get_category_by_id(category_id)["category"] == "Expenses"

    def test_update_description(self, repo):
        category_id = repo.add_category("Expenses")
        updated = repo.update_category(category_id, description="Updated description")
        assert updated["description"] == "Updated description"

    def test_update_both_fields(self, repo):
        category_id = repo.add_category("Old", "Old desc")
        updated = repo.update_category(category_id, category="New", description="New desc")
        assert (updated["category"], updated["description"]) == ("New", "New desc")

    def test_no_fields_returns_current_row(self, repo):
        category_id = repo.add_category("Expenses", "Description")
        assert repo.update_category(category_id) == repo.get_category_by_id(category_id)

    def test_description_can_be_cleared(self, repo):
        category_id = repo.add_category("Expenses", "Description")
        assert repo.update_category(category_id, description=None)["description"] is None

    def test_missing_category_returns_none(self, repo):
        assert repo.update_category(999, category="Test") is None

    def test_duplicate_name_rejected(self, repo):
        repo.add_category("Expenses")
        category_id = repo.add_category("Income")
        with pytest.raises(DatabaseError):
            repo.update_category(category_id, category="Expenses")
        assert repo.get_category_by_id(category_id)["category"] == "Income"


class TestGetCategories:

    def test_get_by_id_found(self, repo):
        category_id = repo.add_category("Expenses", "Description")
        category = repo.get_category_by_id(category_id)
        assert isinstance(category, dict)
        assert category["id"] == category_id

    def test_get_by_id_missing(self, repo):
        assert repo.get_category_by_id(999) is None

    def test_get_all_empty(self, repo):
        assert repo.get_all_categories() == []

    def test_get_all_sorted_by_name(self, repo):
        for name in ("Transfers", "Expenses", "Income"):
            repo.add_category(name)
        assert [c["category"] for c in repo.get_all_categories()] == [
            "Expenses", "Income", "Transfers"
        ]


class TestDeleteCategory:

    def test_delete_unused_category(self, repo):
        category_id = repo.add_category("Expenses")
        assert repo.delete_category(category_id) is True
        assert repo.get_category_by_id(category_id) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_category(999) is False

    def test_delete_with_sub_categories_rejected(self, repo, sample_hierarchy):
        with pytest.raises(DatabaseError) as exc:
            repo.delete_category(sample_hierarchy["category_id"])
        assert "1 associated sub-category(ies)" in str(exc.value)
        assert repo.get_category_by_id(sample_hierarchy["category_id"]) is not None


# --------------------------------------------------------------------------- #
# Sub-categories
# --------------------------------------------------------------------------- #
class TestAddSubCategory:

    def test_returns_id_of_persisted_row(self, repo):
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category(
            "Transportation", category_id, "Travel costs"
        )
        assert isinstance(sub_category_id, int) and sub_category_id > 0

        sub_category = repo.get_sub_category_by_id(sub_category_id)
        assert sub_category["sub_category"] == "Transportation"
        assert sub_category["category_id"] == category_id
        assert sub_category["description"] == "Travel costs"
        assert sub_category["created_at"] is not None

    def test_description_defaults_to_null(self, repo):
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Food", category_id)
        assert repo.get_sub_category_by_id(sub_category_id)["description"] is None

    def test_unknown_parent_rejected(self, repo):
        with pytest.raises(DatabaseError) as exc:
            repo.add_sub_category("Transportation", 999)
        assert "does not exist" in str(exc.value)

    def test_duplicate_within_same_category_rejected(self, repo):
        category_id = repo.add_category("Expenses")
        repo.add_sub_category("Transportation", category_id)
        with pytest.raises(DatabaseError) as exc:
            repo.add_sub_category("Transportation", category_id)
        assert "already exists" in str(exc.value).lower()

    def test_same_name_allowed_under_different_categories(self, repo):
        cat1 = repo.add_category("Expenses")
        cat2 = repo.add_category("Income")
        id1 = repo.add_sub_category("Other", cat1)
        id2 = repo.add_sub_category("Other", cat2)
        assert id1 != id2


class TestUpdateSubCategory:

    def test_update_name(self, repo):
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transprt", category_id)
        updated = repo.update_sub_category(sub_category_id, sub_category="Transportation")
        assert updated["sub_category"] == "Transportation"
        assert updated["category_id"] == category_id

    def test_update_description(self, repo, sample_hierarchy):
        updated = repo.update_sub_category(
            sample_hierarchy["sub_category_id"], description="New description"
        )
        assert updated["description"] == "New description"

    def test_no_fields_returns_current_row(self, repo, sample_hierarchy):
        sub_category_id = sample_hierarchy["sub_category_id"]
        assert repo.update_sub_category(sub_category_id) == repo.get_sub_category_by_id(
            sub_category_id
        )

    def test_missing_sub_category_returns_none(self, repo):
        assert repo.update_sub_category(999, sub_category="Test") is None

    def test_duplicate_name_in_same_category_rejected(self, repo):
        category_id = repo.add_category("Expenses")
        repo.add_sub_category("Transportation", category_id)
        sub_category_id = repo.add_sub_category("Food", category_id)
        with pytest.raises(DatabaseError):
            repo.update_sub_category(sub_category_id, sub_category="Transportation")


class TestRemapSubCategory:

    def test_moves_to_new_category(self, repo, sample_hierarchy):
        target = repo.add_category("Business")
        result = repo.remap_sub_category(sample_hierarchy["sub_category_id"], target)

        assert result["action"] == "remapped"
        assert result["old_category_id"] == sample_hierarchy["category_id"]
        assert result["new_category_id"] == target
        assert repo.get_sub_category_by_id(
            sample_hierarchy["sub_category_id"]
        )["category_id"] == target

    def test_same_category_is_noop(self, repo, sample_hierarchy):
        result = repo.remap_sub_category(
            sample_hierarchy["sub_category_id"], sample_hierarchy["category_id"]
        )
        assert result["action"] == "none"

    def test_name_collision_raises_conflict(self, repo, sample_hierarchy):
        target = repo.add_category("Business")
        conflicting = repo.add_sub_category("Transportation", target)

        with pytest.raises(RemapConflictError) as exc:
            repo.remap_sub_category(sample_hierarchy["sub_category_id"], target)
        assert exc.value.conflicting_id == conflicting
        assert repo.get_sub_category_by_id(
            sample_hierarchy["sub_category_id"]
        )["category_id"] == sample_hierarchy["category_id"]

    def test_unknown_sub_category_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_sub_category(999, sample_hierarchy["category_id"])

    def test_unknown_target_category_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_sub_category(sample_hierarchy["sub_category_id"], 999)


class TestGetSubCategories:

    def test_get_by_id_found(self, repo, sample_hierarchy):
        sub_category = repo.get_sub_category_by_id(sample_hierarchy["sub_category_id"])
        assert sub_category["id"] == sample_hierarchy["sub_category_id"]
        assert sub_category["sub_category"] == "Transportation"

    def test_get_by_id_missing(self, repo):
        assert repo.get_sub_category_by_id(999) is None

    def test_get_all_includes_parent_name(self, repo, sample_hierarchy):
        all_subs = repo.get_all_sub_categories()
        assert len(all_subs) == 1
        assert all_subs[0]["category_name"] == "Expenses"

    def test_get_all_empty(self, repo):
        assert repo.get_all_sub_categories() == []

    def test_get_by_category_sorted_by_name(self, repo, sample_hierarchy):
        category_id = sample_hierarchy["category_id"]
        repo.add_sub_category("Food", category_id)
        assert [s["sub_category"] for s in repo.get_sub_categories_by_category(category_id)] == [
            "Food", "Transportation"
        ]

    def test_get_by_unknown_category_is_empty(self, repo):
        assert repo.get_sub_categories_by_category(999) == []


class TestDeleteSubCategory:

    def test_delete_unused(self, repo):
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        assert repo.delete_sub_category(sub_category_id) is True
        assert repo.get_sub_category_by_id(sub_category_id) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_sub_category(999) is False

    def test_delete_with_types_rejected(self, repo, sample_hierarchy):
        with pytest.raises(DatabaseError) as exc:
            repo.delete_sub_category(sample_hierarchy["sub_category_id"])
        assert "1 associated type(s)" in str(exc.value)


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #
class TestAddType:

    def test_returns_id_of_persisted_row(self, repo):
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id, "Gas purchases")
        assert isinstance(type_id, int) and type_id > 0

        type_row = repo.get_type_by_id(type_id)
        assert type_row["type"] == "Fuel"
        assert type_row["sub_category_id"] == sub_category_id
        assert type_row["description"] == "Gas purchases"
        assert type_row["created_at"] is not None

    def test_description_defaults_to_null(self, repo, sample_hierarchy):
        type_id = repo.add_type("Parking", sample_hierarchy["sub_category_id"])
        assert repo.get_type_by_id(type_id)["description"] is None

    def test_unknown_parent_rejected(self, repo):
        with pytest.raises(DatabaseError) as exc:
            repo.add_type("Fuel", 999)
        assert "does not exist" in str(exc.value)

    def test_duplicate_within_same_sub_category_rejected(self, repo, sample_hierarchy):
        with pytest.raises(DatabaseError) as exc:
            repo.add_type("Fuel", sample_hierarchy["sub_category_id"])
        assert "already exists" in str(exc.value).lower()

    def test_same_name_allowed_under_different_sub_categories(self, repo, sample_hierarchy):
        other_sub = repo.add_sub_category("Food", sample_hierarchy["category_id"])
        assert repo.add_type("Fuel", other_sub) != sample_hierarchy["type_id"]


class TestUpdateType:

    def test_update_name(self, repo, sample_hierarchy):
        updated = repo.update_type(sample_hierarchy["type_id"], type_name="Gas")
        assert updated["type"] == "Gas"
        assert updated["sub_category_id"] == sample_hierarchy["sub_category_id"]

    def test_update_description(self, repo, sample_hierarchy):
        updated = repo.update_type(sample_hierarchy["type_id"], description="New description")
        assert updated["description"] == "New description"

    def test_no_fields_returns_current_row(self, repo, sample_hierarchy):
        type_id = sample_hierarchy["type_id"]
        assert repo.update_type(type_id) == repo.get_type_by_id(type_id)

    def test_missing_type_returns_none(self, repo):
        assert repo.update_type(999, type_name="Test") is None

    def test_duplicate_name_in_same_sub_category_rejected(self, repo, sample_hierarchy):
        type_id = repo.add_type("Maintenance", sample_hierarchy["sub_category_id"])
        with pytest.raises(DatabaseError):
            repo.update_type(type_id, type_name="Fuel")


class TestRemapType:

    def test_moves_to_new_sub_category(self, repo, sample_hierarchy):
        target = repo.add_sub_category("Food", sample_hierarchy["category_id"])
        result = repo.remap_type(sample_hierarchy["type_id"], target)

        assert result["action"] == "remapped"
        assert repo.get_type_by_id(sample_hierarchy["type_id"])["sub_category_id"] == target

    def test_same_sub_category_is_noop(self, repo, sample_hierarchy):
        result = repo.remap_type(
            sample_hierarchy["type_id"], sample_hierarchy["sub_category_id"]
        )
        assert result["action"] == "none"

    def test_name_collision_raises_conflict(self, repo, sample_hierarchy):
        target = repo.add_sub_category("Food", sample_hierarchy["category_id"])
        conflicting = repo.add_type("Fuel", target)

        with pytest.raises(RemapConflictError) as exc:
            repo.remap_type(sample_hierarchy["type_id"], target)
        assert exc.value.conflicting_id == conflicting

    def test_unknown_type_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_type(999, sample_hierarchy["sub_category_id"])

    def test_unknown_target_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_type(sample_hierarchy["type_id"], 999)


class TestGetTypes:

    def test_get_by_id_found(self, repo, sample_hierarchy):
        assert repo.get_type_by_id(sample_hierarchy["type_id"])["type"] == "Fuel"

    def test_get_by_id_missing(self, repo):
        assert repo.get_type_by_id(999) is None

    def test_get_all(self, repo, sample_hierarchy):
        repo.add_type("Maintenance", sample_hierarchy["sub_category_id"])
        assert {t["type"] for t in repo.get_all_types()} == {"Fuel", "Maintenance"}

    def test_get_all_empty(self, repo):
        assert repo.get_all_types() == []

    def test_get_by_sub_category_sorted_by_name(self, repo, sample_hierarchy):
        sub_category_id = sample_hierarchy["sub_category_id"]
        repo.add_type("Airfare", sub_category_id)
        assert [t["type"] for t in repo.get_types_by_sub_category(sub_category_id)] == [
            "Airfare", "Fuel"
        ]

    def test_get_by_unknown_sub_category_is_empty(self, repo):
        assert repo.get_types_by_sub_category(999) == []


class TestDeleteType:

    def test_delete_unused(self, repo, sample_hierarchy):
        type_id = repo.add_type("Maintenance", sample_hierarchy["sub_category_id"])
        assert repo.delete_type(type_id) is True
        assert repo.get_type_by_id(type_id) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_type(999) is False

    def test_delete_with_parties_rejected(self, repo, sample_hierarchy):
        with pytest.raises(DatabaseError) as exc:
            repo.delete_type(sample_hierarchy["type_id"])
        assert "1 associated part" in str(exc.value)


# --------------------------------------------------------------------------- #
# Parties
# --------------------------------------------------------------------------- #
class TestAddParty:

    def test_returns_id_of_persisted_row(self, repo, sample_hierarchy):
        party_id = repo.add_party("BP", sample_hierarchy["type_id"], "BP stations")
        assert isinstance(party_id, int) and party_id > 0

        party = repo.get_party_by_id(party_id)
        assert party["name"] == "BP"
        assert party["type_id"] == sample_hierarchy["type_id"]
        assert party["description"] == "BP stations"
        assert party["created_at"] is not None

    def test_description_defaults_to_null(self, repo, sample_hierarchy):
        party_id = repo.add_party("Esso", sample_hierarchy["type_id"])
        assert repo.get_party_by_id(party_id)["description"] is None

    def test_unknown_type_rejected(self, repo):
        with pytest.raises(DatabaseError) as exc:
            repo.add_party("Shell", 999)
        assert "does not exist" in str(exc.value)

    def test_duplicate_within_same_type_rejected(self, repo, sample_hierarchy):
        with pytest.raises(DatabaseError) as exc:
            repo.add_party("Shell", sample_hierarchy["type_id"])
        assert "already exists" in str(exc.value).lower()

    def test_same_name_allowed_under_different_types(self, repo, sample_hierarchy):
        other_type = repo.add_type("Convenience", sample_hierarchy["sub_category_id"])
        assert repo.add_party("Shell", other_type) != sample_hierarchy["party_id"]


class TestUpdateParty:

    def test_update_name(self, repo, sample_hierarchy):
        updated = repo.update_party(sample_hierarchy["party_id"], name="Shell Gas")
        assert updated["name"] == "Shell Gas"

    def test_update_description(self, repo, sample_hierarchy):
        updated = repo.update_party(sample_hierarchy["party_id"], description="Updated desc")
        assert updated["description"] == "Updated desc"

    def test_no_changes_returns_current_row(self, repo, sample_hierarchy):
        party_id = sample_hierarchy["party_id"]
        assert repo.update_party(party_id) == repo.get_party_by_id(party_id)

    def test_missing_party_returns_none(self, repo):
        assert repo.update_party(999, name="Test") is None

    def test_duplicate_name_in_same_type_rejected(self, repo, sample_hierarchy):
        repo.add_party("BP", sample_hierarchy["type_id"])
        with pytest.raises(DatabaseError):
            repo.update_party(sample_hierarchy["party_id"], name="BP")

    def test_changing_type_is_rejected(self, repo, sample_hierarchy):
        other_type = repo.add_type("Convenience", sample_hierarchy["sub_category_id"])
        with pytest.raises(ValueError) as exc:
            repo.update_party(sample_hierarchy["party_id"], type_id=other_type)
        assert "remap_party()" in str(exc.value)


class TestAddPartyUnknownType:

    def test_creates_unknown_hierarchy_on_first_use(self, repo):
        party_id = repo.add_party_unknown_type("Mystery Shop")

        hierarchy = repo.get_party_hierarchy(party_id)
        assert hierarchy["category_name"] == "Unknown"
        assert hierarchy["sub_category_name"] == "Unknown"
        assert hierarchy["type_name"] == "Unknown"

    def test_reuses_existing_unknown_hierarchy(self, repo):
        first = repo.add_party_unknown_type("Mystery Shop")
        second = repo.add_party_unknown_type("Other Shop")

        assert repo.get_party_by_id(first)["type_id"] == repo.get_party_by_id(second)["type_id"]
        assert len(repo.get_all_categories()) == 1

    def test_duplicate_rejected(self, repo):
        repo.add_party_unknown_type("Mystery Shop")
        with pytest.raises(DatabaseError) as exc:
            repo.add_party_unknown_type("Mystery Shop")
        assert "already exists" in str(exc.value).lower()

    def test_prime_cache_returns_unknown_type_id(self, repo):
        type_id = repo.prime_unknown_type_cache()
        assert repo.get_type_by_id(type_id)["type"] == "Unknown"
        assert repo.prime_unknown_type_cache() == type_id


class TestBulkAddPartiesUnknownType:

    def test_returns_name_to_id_mapping(self, repo):
        result = repo.bulk_add_parties_unknown_type(["Tesco", "Lidl", "Aldi"])
        assert set(result) == {"Tesco", "Lidl", "Aldi"}
        for name, party_id in result.items():
            assert repo.get_party_by_id(party_id)["name"] == name

    def test_empty_input_returns_empty_dict(self, repo):
        assert repo.bulk_add_parties_unknown_type([]) == {}

    def test_duplicate_names_deduplicated(self, repo):
        result = repo.bulk_add_parties_unknown_type(["Tesco", "Tesco"])
        assert list(result) == ["Tesco"]

    def test_existing_parties_are_reused_not_duplicated(self, repo):
        existing = repo.add_party_unknown_type("Tesco")
        result = repo.bulk_add_parties_unknown_type(["Tesco", "Lidl"])
        assert result["Tesco"] == existing
        assert len(repo.get_parties_by_type(repo.prime_unknown_type_cache())) == 2


class TestRemapParty:

    def test_moves_to_new_type(self, repo, sample_hierarchy, make_party_transaction):
        target = repo.add_type("Convenience", sample_hierarchy["sub_category_id"])
        make_party_transaction(sample_hierarchy["party_id"])

        result = repo.remap_party(sample_hierarchy["party_id"], target)

        assert result["action"] == "remapped"
        assert result["old_type_id"] == sample_hierarchy["type_id"]
        assert result["new_type_id"] == target
        assert result["transactions_affected"] == 1
        assert repo.get_party_by_id(sample_hierarchy["party_id"])["type_id"] == target

    def test_same_type_is_noop(self, repo, sample_hierarchy):
        result = repo.remap_party(sample_hierarchy["party_id"], sample_hierarchy["type_id"])
        assert result["action"] == "none"

    def test_name_collision_merges_and_moves_transactions(
        self, repo, sample_hierarchy, make_party_transaction
    ):
        target_type = repo.add_type("Convenience", sample_hierarchy["sub_category_id"])
        target_party = repo.add_party("Shell", target_type)

        old_party = sample_hierarchy["party_id"]
        make_party_transaction(old_party)
        make_party_transaction(old_party)

        result = repo.remap_party(old_party, target_type)

        assert result["action"] == "merged"
        assert result["new_party_id"] == target_party
        assert result["transactions_moved"] == 2
        assert repo.get_party_by_id(old_party) is None
        assert len(repo.get_transactions_by_party(target_party)) == 2

    def test_unknown_party_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_party(999, sample_hierarchy["type_id"])

    def test_unknown_target_type_raises_value_error(self, repo, sample_hierarchy):
        with pytest.raises(ValueError):
            repo.remap_party(sample_hierarchy["party_id"], 999)


class TestGetParties:

    def test_get_by_id_found(self, repo, sample_hierarchy):
        party = repo.get_party_by_id(sample_hierarchy["party_id"])
        assert party["id"] == sample_hierarchy["party_id"]
        assert party["name"] == "Shell"

    def test_get_by_id_missing(self, repo):
        assert repo.get_party_by_id(999) is None

    def test_get_by_type_sorted_by_name(self, repo, sample_hierarchy):
        repo.add_party("BP", sample_hierarchy["type_id"])
        names = [p["name"] for p in repo.get_parties_by_type(sample_hierarchy["type_id"])]
        assert names == ["BP", "Shell"]

    def test_get_by_unknown_type_is_empty(self, repo):
        assert repo.get_parties_by_type(999) == []

    def test_with_transaction_counts_includes_hierarchy(
        self, repo, sample_hierarchy, make_party_transaction
    ):
        make_party_transaction(sample_hierarchy["party_id"])
        make_party_transaction(sample_hierarchy["party_id"])
        repo.add_party("BP", sample_hierarchy["type_id"])

        parties = {p["name"]: p for p in repo.get_all_parties_with_transaction_counts()}
        assert parties["Shell"]["transaction_count"] == 2
        assert parties["BP"]["transaction_count"] == 0
        assert parties["Shell"]["type_name"] == "Fuel"
        assert parties["Shell"]["sub_category_name"] == "Transportation"
        assert parties["Shell"]["category_name"] == "Expenses"

    def test_with_transaction_counts_empty(self, repo):
        assert repo.get_all_parties_with_transaction_counts() == []


class TestDeleteParty:

    def test_delete_unused(self, repo, sample_hierarchy):
        assert repo.delete_party(sample_hierarchy["party_id"]) is True
        assert repo.get_party_by_id(sample_hierarchy["party_id"]) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_party(999) is False

    def test_delete_with_transactions_rejected(
        self, repo, sample_hierarchy, make_party_transaction
    ):
        make_party_transaction(sample_hierarchy["party_id"])
        with pytest.raises(DatabaseError) as exc:
            repo.delete_party(sample_hierarchy["party_id"])
        assert "1 associated transaction(s)" in str(exc.value)

    @pytest.mark.xfail(
        reason="delete_party ignores soft-deleted transactions in its guard, "
               "but the FK still RESTRICTs the delete - backlog",
        strict=True,
    )
    def test_soft_deleted_transactions_do_not_block_delete(
        self, repo, sample_hierarchy, make_party_transaction, app_with_db, test_data
    ):
        transaction_id = make_party_transaction(sample_hierarchy["party_id"])
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.delete_party(sample_hierarchy["party_id"]) is True


class TestGetTransactionsByParty:

    def test_returns_transactions_with_account_name(
        self, repo, sample_hierarchy, make_party_transaction, app_with_db, db_manager
    ):
        with db_manager.transaction() as conn:
            account_id = conn.execute(
                "INSERT INTO accounts (account_name, account_type) VALUES (?, ?)",
                ("Main Checking", "checking"),
            ).lastrowid

        make_party_transaction(sample_hierarchy["party_id"], account_id=account_id)

        transactions = repo.get_transactions_by_party(sample_hierarchy["party_id"])
        assert len(transactions) == 1
        assert transactions[0]["account_name"] == "Main Checking"

    def test_ordered_by_date_descending(
        self, repo, sample_hierarchy, make_party_transaction
    ):
        make_party_transaction(sample_hierarchy["party_id"], transaction_date="2024-01-01")
        make_party_transaction(sample_hierarchy["party_id"], transaction_date="2024-03-01")
        dates = [t["transaction_date"] for t in
                 repo.get_transactions_by_party(sample_hierarchy["party_id"])]
        assert dates == ["2024-03-01", "2024-01-01"]

    def test_excludes_soft_deleted(
        self, repo, sample_hierarchy, make_party_transaction, app_with_db, test_data
    ):
        keep = make_party_transaction(sample_hierarchy["party_id"])
        drop = make_party_transaction(sample_hierarchy["party_id"],
                                      transaction_date="2024-02-01")
        test_data.soft_delete_transaction(app_with_db, drop)

        transactions = repo.get_transactions_by_party(sample_hierarchy["party_id"])
        assert [t["id"] for t in transactions] == [keep]

    def test_no_transactions_is_empty(self, repo, sample_hierarchy):
        assert repo.get_transactions_by_party(sample_hierarchy["party_id"]) == []


# --------------------------------------------------------------------------- #
# Hierarchy
# --------------------------------------------------------------------------- #
class TestGetPartyHierarchy:

    def test_complete_path(self, repo, sample_hierarchy):
        hierarchy = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        assert hierarchy == {
            "party_id": sample_hierarchy["party_id"],
            "party_name": "Shell",
            "type_id": sample_hierarchy["type_id"],
            "type_name": "Fuel",
            "sub_category_id": sample_hierarchy["sub_category_id"],
            "sub_category_name": "Transportation",
            "category_id": sample_hierarchy["category_id"],
            "category_name": "Expenses",
        }

    def test_missing_party_returns_none(self, repo):
        assert repo.get_party_hierarchy(999) is None

    def test_parties_sharing_a_type_share_ancestors(self, repo, sample_hierarchy):
        other = repo.add_party("BP", sample_hierarchy["type_id"])
        h1 = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        h2 = repo.get_party_hierarchy(other)

        assert (h1["type_id"], h1["sub_category_id"], h1["category_id"]) == (
            h2["type_id"], h2["sub_category_id"], h2["category_id"]
        )
        assert {h1["party_name"], h2["party_name"]} == {"Shell", "BP"}

    def test_different_branches_differ_below_the_category(self, repo, sample_hierarchy):
        sub2 = repo.add_sub_category("Food", sample_hierarchy["category_id"])
        type2 = repo.add_type("Groceries", sub2)
        party2 = repo.add_party("Walmart", type2)

        h1 = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        h2 = repo.get_party_hierarchy(party2)

        assert h1["category_id"] == h2["category_id"]
        assert h1["sub_category_name"] != h2["sub_category_name"]
        assert h1["type_name"] != h2["type_name"]


class TestGetAllPartyAliases:

    def test_empty_database(self, repo):
        assert repo.get_all_party_aliases() == {}

    def test_party_names_are_upper_cased(self, repo, sample_hierarchy):
        assert repo.get_all_party_aliases() == {
            "SHELL": sample_hierarchy["party_id"]
        }

    def test_includes_transaction_descriptions(
        self, repo, sample_hierarchy, make_party_transaction
    ):
        make_party_transaction(
            sample_hierarchy["party_id"], cleaned_description="shell station 42"
        )
        aliases = repo.get_all_party_aliases()
        assert aliases["SHELL STATION 42"] == sample_hierarchy["party_id"]
        assert aliases["SHELL"] == sample_hierarchy["party_id"]

    def test_excludes_soft_deleted_transactions(
        self, repo, sample_hierarchy, make_party_transaction, app_with_db, test_data
    ):
        transaction_id = make_party_transaction(
            sample_hierarchy["party_id"], cleaned_description="shell station 42"
        )
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert "SHELL STATION 42" not in repo.get_all_party_aliases()


class TestGetHierarchyTree:

    def test_empty_database(self, repo):
        assert repo.get_hierarchy_tree() == []

    def test_nests_three_levels_and_excludes_parties(self, repo, sample_hierarchy):
        tree = repo.get_hierarchy_tree()
        assert len(tree) == 1

        category = tree[0]
        assert (category["id"], category["name"], category["level"]) == (
            sample_hierarchy["category_id"], "Expenses", "category"
        )

        sub_category = category["children"][0]
        assert (sub_category["name"], sub_category["level"]) == (
            "Transportation", "sub_category"
        )

        type_node = sub_category["children"][0]
        assert (type_node["name"], type_node["level"]) == ("Fuel", "type")
        assert type_node["children"] == []  # parties deliberately excluded

    def test_childless_category_has_empty_children(self, repo):
        repo.add_category("Empty")
        assert repo.get_hierarchy_tree()[0]["children"] == []

    def test_childless_sub_category_has_empty_children(self, repo):
        category_id = repo.add_category("Expenses")
        repo.add_sub_category("Transportation", category_id)
        tree = repo.get_hierarchy_tree()
        assert tree[0]["children"][0]["children"] == []

    def test_sorted_alphabetically_at_every_level(self, repo):
        category_id = repo.add_category("Expenses")
        transport = repo.add_sub_category("Transportation", category_id)
        repo.add_sub_category("Food", category_id)
        repo.add_type("Fuel", transport)
        repo.add_type("Airfare", transport)
        repo.add_category("Assets")

        tree = repo.get_hierarchy_tree()
        assert [c["name"] for c in tree] == ["Assets", "Expenses"]
        expenses = tree[1]
        assert [s["name"] for s in expenses["children"]] == ["Food", "Transportation"]
        transport_node = expenses["children"][1]
        assert [t["name"] for t in transport_node["children"]] == ["Airfare", "Fuel"]


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
@pytest.fixture
def hierarchy_with_transactions(repo, sample_hierarchy, make_party_transaction):
    """Shell has two transactions (-10, -15); BP (same type) has none."""
    make_party_transaction(sample_hierarchy["party_id"], amount=-10.00)
    make_party_transaction(sample_hierarchy["party_id"], amount=-15.00)
    sample_hierarchy["other_party_id"] = repo.add_party("BP", sample_hierarchy["type_id"])
    return sample_hierarchy


class TestStats:

    def test_all_categories_with_stats(self, repo, hierarchy_with_transactions):
        repo.add_category("Empty")
        stats = {c["category"]: c for c in repo.get_all_categories_with_stats()}

        assert stats["Expenses"]["transaction_count"] == 2
        assert stats["Expenses"]["total_value"] == pytest.approx(-25.00)
        assert stats["Empty"]["transaction_count"] == 0
        assert stats["Empty"]["total_value"] == 0

    def test_all_categories_with_stats_empty(self, repo):
        assert repo.get_all_categories_with_stats() == []

    def test_category_with_stats(self, repo, hierarchy_with_transactions):
        stats = repo.get_category_with_stats(hierarchy_with_transactions["category_id"])
        assert stats["transaction_count"] == 2
        assert stats["total_value"] == pytest.approx(-25.00)
        assert stats["child_count"] == 1

    def test_category_with_stats_missing(self, repo):
        assert repo.get_category_with_stats(999) is None

    def test_sub_category_with_stats(self, repo, hierarchy_with_transactions):
        stats = repo.get_sub_category_with_stats(
            hierarchy_with_transactions["sub_category_id"]
        )
        assert stats["category_name"] == "Expenses"
        assert stats["transaction_count"] == 2
        assert stats["total_value"] == pytest.approx(-25.00)
        assert stats["child_count"] == 1

    def test_sub_category_with_stats_missing(self, repo):
        assert repo.get_sub_category_with_stats(999) is None

    def test_type_with_stats(self, repo, hierarchy_with_transactions):
        stats = repo.get_type_with_stats(hierarchy_with_transactions["type_id"])
        assert stats["sub_category_name"] == "Transportation"
        assert stats["category_name"] == "Expenses"
        assert stats["transaction_count"] == 2
        assert stats["child_count"] == 2  # Shell + BP

    def test_type_with_stats_missing(self, repo):
        assert repo.get_type_with_stats(999) is None

    def test_party_with_stats(self, repo, hierarchy_with_transactions):
        stats = repo.get_party_with_stats(hierarchy_with_transactions["party_id"])
        assert stats["name"] == "Shell"
        assert stats["type_name"] == "Fuel"
        assert stats["sub_category_name"] == "Transportation"
        assert stats["category_name"] == "Expenses"
        assert stats["transaction_count"] == 2
        assert stats["total_value"] == pytest.approx(-25.00)

    def test_party_with_stats_missing(self, repo):
        assert repo.get_party_with_stats(999) is None

    def test_sub_categories_with_stats(self, repo, hierarchy_with_transactions):
        repo.add_sub_category("Food", hierarchy_with_transactions["category_id"])
        rows = {r["sub_category"]: r for r in repo.get_sub_categories_with_stats(
            hierarchy_with_transactions["category_id"]
        )}
        assert rows["Transportation"]["transaction_count"] == 2
        assert rows["Food"]["transaction_count"] == 0
        assert rows["Food"]["total_value"] == 0

    def test_sub_categories_with_stats_unknown_parent(self, repo):
        assert repo.get_sub_categories_with_stats(999) == []

    def test_types_with_stats(self, repo, hierarchy_with_transactions):
        repo.add_type("Parking", hierarchy_with_transactions["sub_category_id"])
        rows = {r["type"]: r for r in repo.get_types_with_stats(
            hierarchy_with_transactions["sub_category_id"]
        )}
        assert rows["Fuel"]["transaction_count"] == 2
        assert rows["Parking"]["transaction_count"] == 0

    def test_types_with_stats_unknown_parent(self, repo):
        assert repo.get_types_with_stats(999) == []

    def test_parties_with_stats(self, repo, hierarchy_with_transactions):
        rows = {r["name"]: r for r in repo.get_parties_with_stats(
            hierarchy_with_transactions["type_id"]
        )}
        assert rows["Shell"]["transaction_count"] == 2
        assert rows["Shell"]["total_value"] == pytest.approx(-25.00)
        assert rows["BP"]["transaction_count"] == 0

    def test_parties_with_stats_unknown_parent(self, repo):
        assert repo.get_parties_with_stats(999) == []


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #
class TestEdgeCases:

    def test_empty_description_is_preserved(self, repo):
        category_id = repo.add_category("Expenses", "")
        assert repo.get_category_by_id(category_id)["description"] == ""

    def test_very_long_name(self, repo):
        long_name = "A" * 1000
        category_id = repo.add_category(long_name)
        assert repo.get_category_by_id(category_id)["category"] == long_name

    def test_special_characters_in_name(self, repo):
        category_id = repo.add_category("Expenses & Income (2024)")
        assert repo.get_category_by_id(category_id)["category"] == "Expenses & Income (2024)"

    def test_unicode_characters(self, repo):
        category_id = repo.add_category("Café Expenses")
        sub_category_id = repo.add_sub_category("日本語", category_id)
        assert repo.get_category_by_id(category_id)["category"] == "Café Expenses"
        assert repo.get_sub_category_by_id(sub_category_id)["sub_category"] == "日本語"

    def test_update_to_empty_description(self, repo):
        category_id = repo.add_category("Expenses", "Original description")
        assert repo.update_category(category_id, description="")["description"] == ""


# --------------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------------- #
class TestIntegration:

    @pytest.mark.integration
    def test_full_hierarchy_lifecycle(self, repo):
        category_id = repo.add_category("Expenses", "All expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        party_id = repo.add_party("Shell", type_id)

        hierarchy = repo.get_party_hierarchy(party_id)
        assert hierarchy["category_name"] == "Expenses"
        assert hierarchy["party_name"] == "Shell"

        repo.update_category(category_id, category="Business Expenses")
        repo.update_sub_category(sub_category_id, sub_category="Vehicle")
        repo.update_type(type_id, type_name="Gas")
        repo.update_party(party_id, name="Shell Gas Station")

        hierarchy = repo.get_party_hierarchy(party_id)
        assert hierarchy["category_name"] == "Business Expenses"
        assert hierarchy["sub_category_name"] == "Vehicle"
        assert hierarchy["type_name"] == "Gas"
        assert hierarchy["party_name"] == "Shell Gas Station"

        # Teardown must happen leaf-first because of the RESTRICT constraints
        assert repo.delete_party(party_id) is True
        assert repo.delete_type(type_id) is True
        assert repo.delete_sub_category(sub_category_id) is True
        assert repo.delete_category(category_id) is True
        assert repo.get_all_categories() == []

    @pytest.mark.integration
    def test_multiple_branches(self, repo):
        category_id = repo.add_category("Expenses")

        transport_id = repo.add_sub_category("Transportation", category_id)
        food_id = repo.add_sub_category("Food", category_id)

        fuel_id = repo.add_type("Fuel", transport_id)
        maintenance_id = repo.add_type("Maintenance", transport_id)
        groceries_id = repo.add_type("Groceries", food_id)

        shell_id = repo.add_party("Shell", fuel_id)
        jiffy_id = repo.add_party("Jiffy Lube", maintenance_id)
        walmart_id = repo.add_party("Walmart", groceries_id)

        for party_id, type_name, sub_name in [
            (shell_id, "Fuel", "Transportation"),
            (jiffy_id, "Maintenance", "Transportation"),
            (walmart_id, "Groceries", "Food"),
        ]:
            hierarchy = repo.get_party_hierarchy(party_id)
            assert hierarchy["type_name"] == type_name
            assert hierarchy["sub_category_name"] == sub_name


# --------------------------------------------------------------------------- #
# error wrapping
# --------------------------------------------------------------------------- #
class TestErrorWrapping:

    @pytest.fixture
    def broken_repo(self, repo):
        class Boom:
            def get_connection(self):
                raise RuntimeError("connection exploded")

            def transaction(self):
                raise RuntimeError("connection exploded")

        repo.db = Boom()
        return repo

    @pytest.mark.parametrize("call", [
        lambda r: r.add_sub_category("x", 1),
        lambda r: r.update_sub_category(1, sub_category="x"),
        lambda r: r.remap_sub_category(1, 2),
        lambda r: r.get_sub_category_by_id(1),
        lambda r: r.get_all_sub_categories(),
        lambda r: r.get_sub_categories_by_category(1),
        lambda r: r.delete_sub_category(1),
        lambda r: r.add_type("x", 1),
        lambda r: r.update_type(1, type_name="x"),
        lambda r: r.remap_type(1, 2),
        lambda r: r.get_type_by_id(1),
        lambda r: r.get_all_types(),
        lambda r: r.get_types_by_sub_category(1),
        lambda r: r.delete_type(1),
        lambda r: r.add_party("x", 1),
        lambda r: r.update_party(1, name="x"),
        lambda r: r.remap_party(1, 2),
        lambda r: r.get_party_by_id(1),
        lambda r: r.get_parties_by_type(1),
        lambda r: r.get_all_parties_with_transaction_counts(),
        lambda r: r.delete_party(1),
        lambda r: r.get_transactions_by_party(1),
        lambda r: r.get_party_hierarchy(1),
        lambda r: r.get_all_party_aliases(),
        lambda r: r.get_hierarchy_tree(),
        lambda r: r.get_all_categories(),
        lambda r: r.get_all_categories_with_stats(),
        lambda r: r.get_category_with_stats(1),
        lambda r: r.get_sub_category_with_stats(1),
        lambda r: r.get_type_with_stats(1),
        lambda r: r.get_party_with_stats(1),
        lambda r: r.get_sub_categories_with_stats(1),
        lambda r: r.get_types_with_stats(1),
        lambda r: r.get_parties_with_stats(1),
        lambda r: r.delete_category(1),
        lambda r: r.update_category(1, category="x"),
    ])
    def test_db_failures_surface_as_database_error(self, broken_repo, call):
        with pytest.raises(DatabaseError):
            call(broken_repo)