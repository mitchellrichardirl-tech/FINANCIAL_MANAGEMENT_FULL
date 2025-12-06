import pytest
import sqlite3
from datetime import datetime

from src.database.connection import ConnectionManager, DatabaseError, init as init_connection
from src.database.schema import initialize_schema
from src.database.repositories.categories import CategoryRepository


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path"""
    return tmp_path / "test.db"


@pytest.fixture
def connection_manager(temp_db_path):
    """Create and initialize connection manager"""
    manager = ConnectionManager(temp_db_path)
    init_connection(temp_db_path)
    initialize_schema(manager)
    return manager


@pytest.fixture
def repo(connection_manager):
    """Create a category repository"""
    return CategoryRepository()


@pytest.fixture
def sample_hierarchy(repo):
    """Create a sample hierarchy and return IDs"""
    category_id = repo.add_category("Expenses", "All expenses")
    sub_category_id = repo.add_sub_category("Transportation", category_id, "Travel costs")
    type_id = repo.add_type("Fuel", sub_category_id, "Gas purchases")
    party_id = repo.add_party("Shell", type_id, "Shell gas stations")
    
    return {
        "category_id": category_id,
        "sub_category_id": sub_category_id,
        "type_id": type_id,
        "party_id": party_id
    }


class TestAddCategory:
    """Test adding categories"""
    
    def test_add_category_returns_id(self, repo):
        """Test that add_category returns an ID"""
        category_id = repo.add_category("Expenses")
        assert isinstance(category_id, int)
        assert category_id > 0
    
    def test_add_category_with_description(self, repo):
        """Test adding category with description"""
        category_id = repo.add_category("Expenses", "All expense transactions")
        category = repo.get_category_by_id(category_id)
        
        assert category["category"] == "Expenses"
        assert category["description"] == "All expense transactions"
    
    def test_add_category_without_description(self, repo):
        """Test adding category without description"""
        category_id = repo.add_category("Income")
        category = repo.get_category_by_id(category_id)
        
        assert category["category"] == "Income"
        assert category["description"] is None
    
    def test_add_category_sets_created_at(self, repo):
        """Test that created_at is set"""
        category_id = repo.add_category("Expenses")
        category = repo.get_category_by_id(category_id)
        
        assert category["created_at"] is not None
    
    def test_add_duplicate_category_raises_error(self, repo):
        """Test that adding duplicate category raises error"""
        repo.add_category("Expenses")
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_category("Expenses")
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_add_multiple_categories(self, repo):
        """Test adding multiple categories"""
        id1 = repo.add_category("Expenses")
        id2 = repo.add_category("Income")
        id3 = repo.add_category("Transfers")
        
        assert id1 != id2 != id3
        assert repo.get_category_by_id(id1) is not None
        assert repo.get_category_by_id(id2) is not None
        assert repo.get_category_by_id(id3) is not None


class TestUpdateCategory:
    """Test updating categories"""
    
    def test_update_category_name(self, repo):
        """Test updating category name"""
        category_id = repo.add_category("Expnses")  # Typo
        
        updated = repo.update_category(category_id, category="Expenses")
        
        assert updated["category"] == "Expenses"
    
    def test_update_category_description(self, repo):
        """Test updating category description"""
        category_id = repo.add_category("Expenses")
        
        updated = repo.update_category(category_id, description="Updated description")
        
        assert updated["description"] == "Updated description"
    
    def test_update_category_both_fields(self, repo):
        """Test updating both fields"""
        category_id = repo.add_category("Old", "Old desc")
        
        updated = repo.update_category(category_id, category="New", description="New desc")
        
        assert updated["category"] == "New"
        assert updated["description"] == "New desc"
    
    def test_update_category_no_changes(self, repo):
        """Test update with no changes"""
        category_id = repo.add_category("Expenses", "Description")
        
        updated = repo.update_category(category_id)
        
        assert updated["category"] == "Expenses"
        assert updated["description"] == "Description"
    
    def test_update_category_not_found(self, repo):
        """Test updating non-existent category"""
        updated = repo.update_category(999, category="Test")
        assert updated is None
    
    def test_update_category_to_duplicate_name_raises_error(self, repo):
        """Test updating to duplicate name raises error"""
        repo.add_category("Expenses")
        category_id = repo.add_category("Income")
        
        with pytest.raises(DatabaseError):
            repo.update_category(category_id, category="Expenses")


class TestGetCategoryById:
    """Test getting categories by ID"""
    
    def test_get_category_exists(self, repo):
        """Test getting existing category"""
        category_id = repo.add_category("Expenses", "Description")
        
        category = repo.get_category_by_id(category_id)
        
        assert category is not None
        assert category["id"] == category_id
        assert category["category"] == "Expenses"
        assert category["description"] == "Description"
    
    def test_get_category_not_exists(self, repo):
        """Test getting non-existent category"""
        category = repo.get_category_by_id(999)
        assert category is None
    
    def test_get_category_returns_dict(self, repo):
        """Test that result is a dictionary"""
        category_id = repo.add_category("Expenses")
        category = repo.get_category_by_id(category_id)
        
        assert isinstance(category, dict)


class TestAddSubCategory:
    """Test adding sub-categories"""
    
    def test_add_sub_category_returns_id(self, repo):
        """Test that add_sub_category returns an ID"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        
        assert isinstance(sub_category_id, int)
        assert sub_category_id > 0
    
    def test_add_sub_category_with_description(self, repo):
        """Test adding sub-category with description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id, "Travel costs")
        
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        
        assert sub_category["sub_category"] == "Transportation"
        assert sub_category["category_id"] == category_id
        assert sub_category["description"] == "Travel costs"
    
    def test_add_sub_category_without_description(self, repo):
        """Test adding sub-category without description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Food", category_id)
        
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        assert sub_category["description"] is None
    
    def test_add_sub_category_invalid_category_raises_error(self, repo):
        """Test adding sub-category with invalid category ID"""
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_sub_category("Transportation", 999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_add_duplicate_sub_category_same_category_raises_error(self, repo):
        """Test adding duplicate sub-category in same category"""
        category_id = repo.add_category("Expenses")
        repo.add_sub_category("Transportation", category_id)
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_sub_category("Transportation", category_id)
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_add_same_sub_category_different_categories(self, repo):
        """Test same sub-category name in different categories"""
        cat1_id = repo.add_category("Expenses")
        cat2_id = repo.add_category("Income")
        
        sub1_id = repo.add_sub_category("Other", cat1_id)
        sub2_id = repo.add_sub_category("Other", cat2_id)
        
        assert sub1_id != sub2_id
        assert repo.get_sub_category_by_id(sub1_id)["category_id"] == cat1_id
        assert repo.get_sub_category_by_id(sub2_id)["category_id"] == cat2_id
    
    def test_add_sub_category_sets_created_at(self, repo):
        """Test that created_at is set"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        assert sub_category["created_at"] is not None


class TestUpdateSubCategory:
    """Test updating sub-categories"""
    
    def test_update_sub_category_name(self, repo):
        """Test updating sub-category name"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transprt", category_id)
        
        updated = repo.update_sub_category(sub_category_id, sub_category="Transportation")
        
        assert updated["sub_category"] == "Transportation"
    
    def test_update_sub_category_description(self, repo):
        """Test updating sub-category description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        
        updated = repo.update_sub_category(sub_category_id, description="New description")
        
        assert updated["description"] == "New description"
    
    def test_update_sub_category_parent(self, repo):
        """Test moving sub-category to different category"""
        cat1_id = repo.add_category("Expenses")
        cat2_id = repo.add_category("Income")
        sub_category_id = repo.add_sub_category("Other", cat1_id)
        
        updated = repo.update_sub_category(sub_category_id, category_id=cat2_id)
        
        assert updated["category_id"] == cat2_id
    
    def test_update_sub_category_invalid_parent_raises_error(self, repo):
        """Test updating to invalid category ID"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.update_sub_category(sub_category_id, category_id=999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_update_sub_category_not_found(self, repo):
        """Test updating non-existent sub-category"""
        updated = repo.update_sub_category(999, sub_category="Test")
        assert updated is None
    
    def test_update_sub_category_to_duplicate_raises_error(self, repo):
        """Test updating to duplicate name in same category"""
        category_id = repo.add_category("Expenses")
        repo.add_sub_category("Transportation", category_id)
        sub_category_id = repo.add_sub_category("Food", category_id)
        
        with pytest.raises(DatabaseError):
            repo.update_sub_category(sub_category_id, sub_category="Transportation")


class TestGetSubCategoryById:
    """Test getting sub-categories by ID"""
    
    def test_get_sub_category_exists(self, repo):
        """Test getting existing sub-category"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id, "Desc")
        
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        
        assert sub_category is not None
        assert sub_category["id"] == sub_category_id
        assert sub_category["sub_category"] == "Transportation"
        assert sub_category["category_id"] == category_id
    
    def test_get_sub_category_not_exists(self, repo):
        """Test getting non-existent sub-category"""
        sub_category = repo.get_sub_category_by_id(999)
        assert sub_category is None


class TestAddType:
    """Test adding types"""
    
    def test_add_type_returns_id(self, repo):
        """Test that add_type returns an ID"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        
        assert isinstance(type_id, int)
        assert type_id > 0
    
    def test_add_type_with_description(self, repo):
        """Test adding type with description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id, "Gas station purchases")
        
        type_obj = repo.get_type_by_id(type_id)
        
        assert type_obj["type"] == "Fuel"
        assert type_obj["sub_category_id"] == sub_category_id
        assert type_obj["description"] == "Gas station purchases"
    
    def test_add_type_without_description(self, repo):
        """Test adding type without description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Maintenance", sub_category_id)
        
        type_obj = repo.get_type_by_id(type_id)
        assert type_obj["description"] is None
    
    def test_add_type_invalid_sub_category_raises_error(self, repo):
        """Test adding type with invalid sub-category ID"""
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_type("Fuel", 999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_add_duplicate_type_same_sub_category_raises_error(self, repo):
        """Test adding duplicate type in same sub-category"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        repo.add_type("Fuel", sub_category_id)
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_type("Fuel", sub_category_id)
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_add_same_type_different_sub_categories(self, repo):
        """Test same type name in different sub-categories"""
        category_id = repo.add_category("Expenses")
        sub1_id = repo.add_sub_category("Transportation", category_id)
        sub2_id = repo.add_sub_category("Home", category_id)
        
        type1_id = repo.add_type("Maintenance", sub1_id)
        type2_id = repo.add_type("Maintenance", sub2_id)
        
        assert type1_id != type2_id
    
    def test_add_type_sets_created_at(self, repo):
        """Test that created_at is set"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        
        type_obj = repo.get_type_by_id(type_id)
        assert type_obj["created_at"] is not None


class TestUpdateType:
    """Test updating types"""
    
    def test_update_type_name(self, repo):
        """Test updating type name"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fule", sub_category_id)
        
        updated = repo.update_type(type_id, type_name="Fuel")
        
        assert updated["type"] == "Fuel"
    
    def test_update_type_description(self, repo):
        """Test updating type description"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        
        updated = repo.update_type(type_id, description="New description")
        
        assert updated["description"] == "New description"
    
    def test_update_type_parent(self, repo):
        """Test moving type to different sub-category"""
        category_id = repo.add_category("Expenses")
        sub1_id = repo.add_sub_category("Transportation", category_id)
        sub2_id = repo.add_sub_category("Other", category_id)
        type_id = repo.add_type("Fuel", sub1_id)
        
        updated = repo.update_type(type_id, sub_category_id=sub2_id)
        
        assert updated["sub_category_id"] == sub2_id
    
    def test_update_type_invalid_parent_raises_error(self, repo):
        """Test updating to invalid sub-category ID"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.update_type(type_id, sub_category_id=999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_update_type_not_found(self, repo):
        """Test updating non-existent type"""
        updated = repo.update_type(999, type_name="Test")
        assert updated is None
    
    def test_update_type_to_duplicate_raises_error(self, repo):
        """Test updating to duplicate name in same sub-category"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        repo.add_type("Fuel", sub_category_id)
        type_id = repo.add_type("Maintenance", sub_category_id)
        
        with pytest.raises(DatabaseError):
            repo.update_type(type_id, type_name="Fuel")


class TestGetTypeById:
    """Test getting types by ID"""
    
    def test_get_type_exists(self, repo):
        """Test getting existing type"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id, "Desc")
        
        type_obj = repo.get_type_by_id(type_id)
        
        assert type_obj is not None
        assert type_obj["id"] == type_id
        assert type_obj["type"] == "Fuel"
        assert type_obj["sub_category_id"] == sub_category_id
    
    def test_get_type_not_exists(self, repo):
        """Test getting non-existent type"""
        type_obj = repo.get_type_by_id(999)
        assert type_obj is None


class TestAddParty:
    """Test adding parties"""
    
    def test_add_party_returns_id(self, repo, sample_hierarchy):
        """Test that add_party returns an ID"""
        party_id = repo.add_party("BP", sample_hierarchy["type_id"])
        
        assert isinstance(party_id, int)
        assert party_id > 0
    
    def test_add_party_with_description(self, repo, sample_hierarchy):
        """Test adding party with description"""
        party_id = repo.add_party("BP", sample_hierarchy["type_id"], "BP gas stations")
        
        party = repo.get_party_by_id(party_id)
        
        assert party["name"] == "BP"
        assert party["type_id"] == sample_hierarchy["type_id"]
        assert party["description"] == "BP gas stations"
    
    def test_add_party_without_description(self, repo, sample_hierarchy):
        """Test adding party without description"""
        party_id = repo.add_party("Chevron", sample_hierarchy["type_id"])
        
        party = repo.get_party_by_id(party_id)
        assert party["description"] is None
    
    def test_add_party_invalid_type_raises_error(self, repo):
        """Test adding party with invalid type ID"""
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_party("Shell", 999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_add_duplicate_party_same_type_raises_error(self, repo, sample_hierarchy):
        """Test adding duplicate party in same type"""
        repo.add_party("BP", sample_hierarchy["type_id"])
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.add_party("BP", sample_hierarchy["type_id"])
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_add_same_party_different_types(self, repo):
        """Test same party name in different types"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type1_id = repo.add_type("Fuel", sub_category_id)
        type2_id = repo.add_type("Convenience", sub_category_id)
        
        party1_id = repo.add_party("Shell", type1_id)
        party2_id = repo.add_party("Shell", type2_id)
        
        assert party1_id != party2_id
    
    def test_add_party_sets_created_at(self, repo, sample_hierarchy):
        """Test that created_at is set"""
        party_id = repo.add_party("BP", sample_hierarchy["type_id"])
        
        party = repo.get_party_by_id(party_id)
        assert party["created_at"] is not None


class TestUpdateParty:
    """Test updating parties"""
    
    def test_update_party_name(self, repo, sample_hierarchy):
        """Test updating party name"""
        updated = repo.update_party(sample_hierarchy["party_id"], name="Shell Gas")
        
        assert updated["name"] == "Shell Gas"
    
    def test_update_party_description(self, repo, sample_hierarchy):
        """Test updating party description"""
        updated = repo.update_party(sample_hierarchy["party_id"], description="Updated desc")
        
        assert updated["description"] == "Updated desc"
    
    def test_update_party_type(self, repo, sample_hierarchy):
        """Test moving party to different type"""
        new_type_id = repo.add_type("Convenience", sample_hierarchy["sub_category_id"])
        
        updated = repo.update_party(sample_hierarchy["party_id"], type_id=new_type_id)
        
        assert updated["type_id"] == new_type_id
    
    def test_update_party_invalid_type_raises_error(self, repo, sample_hierarchy):
        """Test updating to invalid type ID"""
        with pytest.raises(DatabaseError) as exc_info:
            repo.update_party(sample_hierarchy["party_id"], type_id=999)
        
        assert "does not exist" in str(exc_info.value)
    
    def test_update_party_not_found(self, repo):
        """Test updating non-existent party"""
        updated = repo.update_party(999, name="Test")
        assert updated is None
    
    def test_update_party_to_duplicate_raises_error(self, repo, sample_hierarchy):
        """Test updating to duplicate name in same type"""
        repo.add_party("BP", sample_hierarchy["type_id"])
        
        with pytest.raises(DatabaseError):
            repo.update_party(sample_hierarchy["party_id"], name="BP")
    
    def test_update_party_no_changes(self, repo, sample_hierarchy):
        """Test update with no changes"""
        original = repo.get_party_by_id(sample_hierarchy["party_id"])
        updated = repo.update_party(sample_hierarchy["party_id"])
        
        assert updated["name"] == original["name"]
        assert updated["type_id"] == original["type_id"]


class TestGetPartyById:
    """Test getting parties by ID"""
    
    def test_get_party_exists(self, repo, sample_hierarchy):
        """Test getting existing party"""
        party = repo.get_party_by_id(sample_hierarchy["party_id"])
        
        assert party is not None
        assert party["id"] == sample_hierarchy["party_id"]
        assert party["name"] == "Shell"
        assert party["type_id"] == sample_hierarchy["type_id"]
    
    def test_get_party_not_exists(self, repo):
        """Test getting non-existent party"""
        party = repo.get_party_by_id(999)
        assert party is None


class TestGetPartyHierarchy:
    """Test getting party hierarchy"""
    
    def test_get_party_hierarchy_complete(self, repo, sample_hierarchy):
        """Test getting complete hierarchy"""
        hierarchy = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        
        assert hierarchy is not None
        assert hierarchy["party_id"] == sample_hierarchy["party_id"]
        assert hierarchy["party_name"] == "Shell"
        assert hierarchy["type_id"] == sample_hierarchy["type_id"]
        assert hierarchy["type_name"] == "Fuel"
        assert hierarchy["sub_category_id"] == sample_hierarchy["sub_category_id"]
        assert hierarchy["sub_category_name"] == "Transportation"
        assert hierarchy["category_id"] == sample_hierarchy["category_id"]
        assert hierarchy["category_name"] == "Expenses"
    
    def test_get_party_hierarchy_not_found(self, repo):
        """Test getting hierarchy for non-existent party"""
        hierarchy = repo.get_party_hierarchy(999)
        assert hierarchy is None
    
    def test_get_party_hierarchy_returns_dict(self, repo, sample_hierarchy):
        """Test that hierarchy is returned as dictionary"""
        hierarchy = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        assert isinstance(hierarchy, dict)
    
    def test_get_party_hierarchy_all_keys_present(self, repo, sample_hierarchy):
        """Test that all expected keys are present"""
        hierarchy = repo.get_party_hierarchy(sample_hierarchy["party_id"])
        
        expected_keys = {
            "party_id", "party_name",
            "type_id", "type_name",
            "sub_category_id", "sub_category_name",
            "category_id", "category_name"
        }
        
        assert set(hierarchy.keys()) == expected_keys
    
    def test_get_party_hierarchy_multiple_parties(self, repo):
        """Test hierarchy for different parties in same hierarchy"""
        category_id = repo.add_category("Expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        
        party1_id = repo.add_party("Shell", type_id)
        party2_id = repo.add_party("BP", type_id)
        
        hierarchy1 = repo.get_party_hierarchy(party1_id)
        hierarchy2 = repo.get_party_hierarchy(party2_id)
        
        # Same hierarchy except party info
        assert hierarchy1["type_id"] == hierarchy2["type_id"]
        assert hierarchy1["sub_category_id"] == hierarchy2["sub_category_id"]
        assert hierarchy1["category_id"] == hierarchy2["category_id"]
        
        # Different party info
        assert hierarchy1["party_id"] != hierarchy2["party_id"]
        assert hierarchy1["party_name"] == "Shell"
        assert hierarchy2["party_name"] == "BP"
    
    def test_get_party_hierarchy_different_branches(self, repo):
        """Test hierarchies from different branches"""
        category_id = repo.add_category("Expenses")
        
        # Branch 1: Transportation -> Fuel -> Shell
        sub1_id = repo.add_sub_category("Transportation", category_id)
        type1_id = repo.add_type("Fuel", sub1_id)
        party1_id = repo.add_party("Shell", type1_id)
        
        # Branch 2: Food -> Groceries -> Walmart
        sub2_id = repo.add_sub_category("Food", category_id)
        type2_id = repo.add_type("Groceries", sub2_id)
        party2_id = repo.add_party("Walmart", type2_id)
        
        hierarchy1 = repo.get_party_hierarchy(party1_id)
        hierarchy2 = repo.get_party_hierarchy(party2_id)
        
        # Same category
        assert hierarchy1["category_id"] == hierarchy2["category_id"]
        assert hierarchy1["category_name"] == "Expenses"
        
        # Different sub-categories
        assert hierarchy1["sub_category_name"] == "Transportation"
        assert hierarchy2["sub_category_name"] == "Food"
        
        # Different types
        assert hierarchy1["type_name"] == "Fuel"
        assert hierarchy2["type_name"] == "Groceries"
        
        # Different parties
        assert hierarchy1["party_name"] == "Shell"
        assert hierarchy2["party_name"] == "Walmart"


class TestEdgeCases:
    """Test edge cases"""
    
    def test_empty_description(self, repo):
        """Test empty string description"""
        category_id = repo.add_category("Expenses", "")
        category = repo.get_category_by_id(category_id)
        
        assert category["description"] == ""
    
    def test_very_long_name(self, repo):
        """Test very long category name"""
        long_name = "A" * 1000
        category_id = repo.add_category(long_name)
        category = repo.get_category_by_id(category_id)
        
        assert category["category"] == long_name
    
    def test_special_characters_in_name(self, repo):
        """Test special characters in names"""
        category_id = repo.add_category("Expenses & Income (2024)")
        category = repo.get_category_by_id(category_id)
        
        assert category["category"] == "Expenses & Income (2024)"
    
    def test_unicode_characters(self, repo):
        """Test unicode characters"""
        category_id = repo.add_category("Café Expenses")
        sub_category_id = repo.add_sub_category("日本語", category_id)
        
        category = repo.get_category_by_id(category_id)
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        
        assert category["category"] == "Café Expenses"
        assert sub_category["sub_category"] == "日本語"
    
    def test_update_to_empty_description(self, repo):
        """Test updating description to empty string"""
        category_id = repo.add_category("Expenses", "Original description")
        updated = repo.update_category(category_id, description="")
        
        assert updated["description"] == ""


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.integration
    def test_full_hierarchy_lifecycle(self, repo):
        """Test complete CRUD cycle for hierarchy"""
        # Create
        category_id = repo.add_category("Expenses", "All expenses")
        sub_category_id = repo.add_sub_category("Transportation", category_id)
        type_id = repo.add_type("Fuel", sub_category_id)
        party_id = repo.add_party("Shell", type_id)
        
        # Read hierarchy
        hierarchy = repo.get_party_hierarchy(party_id)
        assert hierarchy["category_name"] == "Expenses"
        assert hierarchy["party_name"] == "Shell"
        
        # Update each level
        repo.update_category(category_id, category="Business Expenses")
        repo.update_sub_category(sub_category_id, sub_category="Vehicle")
        repo.update_type(type_id, type_name="Gas")
        repo.update_party(party_id, name="Shell Gas Station")
        
        # Verify updates in hierarchy
        hierarchy = repo.get_party_hierarchy(party_id)
        assert hierarchy["category_name"] == "Business Expenses"
        assert hierarchy["sub_category_name"] == "Vehicle"
        assert hierarchy["type_name"] == "Gas"
        assert hierarchy["party_name"] == "Shell Gas Station"
    
    @pytest.mark.integration
    def test_multiple_branches(self, repo):
        """Test creating multiple branches"""
        # Create category
        category_id = repo.add_category("Expenses")
        
        # Create multiple sub-categories
        transport_id = repo.add_sub_category("Transportation", category_id)
        food_id = repo.add_sub_category("Food", category_id)
        
        # Create types under each
        fuel_id = repo.add_type("Fuel", transport_id)
        maintenance_id = repo.add_type("Maintenance", transport_id)
        groceries_id = repo.add_type("Groceries", food_id)
        
        # Create parties
        shell_id = repo.add_party("Shell", fuel_id)
        jiffy_id = repo.add_party("Jiffy Lube", maintenance_id)
        walmart_id = repo.add_party("Walmart", groceries_id)
        
        # Verify each hierarchy
        shell_hierarchy = repo.get_party_hierarchy(shell_id)
        assert shell_hierarchy["type_name"] == "Fuel"
        assert shell_hierarchy["sub_category_name"] == "Transportation"
        
        jiffy_hierarchy = repo.get_party_hierarchy(jiffy_id)
        assert jiffy_hierarchy["type_name"] == "Maintenance"
        assert jiffy_hierarchy["sub_category_name"] == "Transportation"
        
        walmart_hierarchy = repo.get_party_hierarchy(walmart_id)
        assert walmart_hierarchy["type_name"] == "Groceries"
        assert walmart_hierarchy["sub_category_name"] == "Food"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])