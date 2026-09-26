import pytest
from unittest.mock import Mock, MagicMock, patch
import sqlite3

from src.database.repositories.accounts import AccountRepository
from src.database.connection import DatabaseError


class TestAccountRepository:
    """Tests for AccountRepository"""
    
    @pytest.fixture
    def repository(self, connection_manager):
        """Create an AccountRepository with mocked dependencies."""
        return AccountRepository()

    @pytest.fixture
    def mock_repository(self, mock_db_manager):
        """Create an AccountRepository with mocked dependencies."""
        with patch('src.database.repositories.accounts.get_manager', return_value=mock_db_manager):
            with patch('src.database.repositories.accounts.BaseRepository') as mock_base:
                repo = AccountRepository()
                repo.db = mock_db_manager
                repo.br = mock_base.return_value
                return repo
                
    @pytest.fixture
    def sample_account(self):
        """Sample account data."""
        return {
            'id': 1,
            'account_name': 'Test Checking',
            'account_type': 'checking',
            'created_at': '2024-01-15 10:30:00.000'
        }
    
    # ========== Create Tests ==========
    
    class TestAddAccount:
        """Tests for add_account method"""

        
        def test_add_account_success(self, repository):
            """Test successfully adding an account."""
            
            result = repository.add_account(
                account_name='Test Checking',
                account_type='checking'
                )
            assert isinstance(result, dict)
            assert result['id'] == 1

        # TODO add a unique constraint to account name!
        # def test_add_account_duplicate_raises_error(self, repository):
        #     """Test adding duplicate account raises DatabaseError."""

        #     repository.add_account('Duplicate Account', 'checking')
        #     with pytest.raises(DatabaseError) as exc_info:
        #         repository.add_account('Duplicate Account', 'checking')
            
        #     assert "Account already exists" in str(exc_info.value)
        
        def test_add_account_generic_integrity_error(self, mock_repository):
            """Test generic integrity error is handled."""
            mock_repository.br.insert_query.side_effect = sqlite3.IntegrityError(
                "some other constraint"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.add_account('Test Account', 'checking')
            
            assert "Failed to add account" in str(exc_info.value)
        
        def test_add_account_generic_exception(self, mock_repository):
            """Test generic exception is handled."""
            mock_repository.br.insert_query.side_effect = Exception("Database connection lost")
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.add_account('Test Account', 'checking')
            
            assert "Failed to add account" in str(exc_info.value)
    
    # ========== Read Tests ==========
    
    class TestGetAccountById:
        """Tests for get_account_by_id method"""
        
        def test_get_account_by_id_found(self, repository, sample_account):
            """Test retrieving an existing account by ID."""
            # Return a real dict - when dict() is called on it, it returns itself
            
            new_account = repository.add_account('Test Account', 'Current')
            
            result = repository.get_account_by_id(new_account['id'])
            
            assert result == new_account
        
        def test_get_account_by_id_not_found(self, repository):
            """Test retrieving non-existent account returns None."""
            
            result = repository.get_account_by_id(999)
            
            assert result is None
        
        def test_get_account_by_id_exception(self, mock_repository):
            """Test exception handling in get_account_by_id."""
            mock_repository.br.select_query.side_effect = Exception("Query failed")
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.get_account_by_id(1)
            
            assert "Failed to get account" in str(exc_info.value)
    
    class TestGetAccountByName:
        """Tests for get_account_by_name method"""
        
        def test_get_account_by_name_found(self, mock_repository, sample_account, mock_cursor):
            """Test retrieving an existing account by name."""
            mock_row = MagicMock()
            mock_row.__iter__ = Mock(return_value=iter(sample_account.items()))
            mock_row.keys.return_value = sample_account.keys()
            mock_cursor.fetchone.return_value = mock_row
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with patch('src.database.repositories.accounts.dict', return_value=sample_account):
                result = mock_repository.get_account_by_name('Test Checking')
            
            mock_cursor.execute.assert_called_once_with(
                "SELECT * FROM accounts WHERE account_name = ?",
                ('Test Checking',)
            )
        
        def test_get_account_by_name_not_found(self, mock_repository, mock_cursor):
            """Test retrieving non-existent account by name returns None."""
            mock_cursor.fetchone.return_value = None
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.get_account_by_name('Nonexistent')
            
            assert result is None
        
        def test_get_account_by_name_exception(self, mock_repository):
            """Test exception handling in get_account_by_name."""
            mock_repository.db.get_connection.return_value.__enter__.side_effect = Exception(
                "Connection failed"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.get_account_by_name('Test')
            
            assert "Failed to get account" in str(exc_info.value)
    
    class TestGetAllAccounts:
        """Tests for get_all_accounts method"""
        
        def test_get_all_accounts_success(self, mock_repository, mock_cursor):
            """Test retrieving all accounts."""
            mock_rows = [
                {'id': 1, 'account_name': 'Checking', 'account_type': 'checking'},
                {'id': 2, 'account_name': 'Savings', 'account_type': 'savings'},
            ]
            
            mock_row_objects = []
            for row in mock_rows:
                mock_row = MagicMock()
                mock_row.keys.return_value = row.keys()
                mock_row.__iter__ = Mock(return_value=iter(row.items()))
                mock_row_objects.append(mock_row)
            
            mock_cursor.fetchall.return_value = mock_row_objects
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.get_all_accounts()
            
            mock_cursor.execute.assert_called_once_with(
                "SELECT * FROM accounts ORDER BY account_name"
            )
        
        def test_get_all_accounts_empty(self, repository):
            """Test retrieving accounts when none exist."""
            
            result = repository.get_all_accounts()
            
            assert result == []
        
        def test_get_all_accounts_exception(self, mock_repository):
            """Test exception handling in get_all_accounts."""
            mock_repository.db.get_connection.return_value.__enter__.side_effect = Exception(
                "Database error"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.get_all_accounts()
            
            assert "Failed to get accounts" in str(exc_info.value)
    
    class TestGetAccountsByType:
        """Tests for get_accounts_by_type method"""
        
        def test_get_accounts_by_type_success(self, repository, mock_cursor):
            """Test retrieving accounts by type."""
            mock_rows = [
                {'id': 1, 'account_name': 'Main Checking', 'account_type': 'checking'},
                {'id': 3, 'account_name': 'Joint Checking', 'account_type': 'checking'},
            ]

            mock_accounts = {}
            for row in mock_rows:
                mock_account = repository.add_account(row['account_name'], row['account_type'])
                mock_accounts[mock_account['id']] = mock_account 

            result = repository.get_accounts_by_type('checking')
            
            for returned_ac in result:
                assert returned_ac['id'] in mock_accounts
                for key, val in returned_ac.items():
                    assert key in mock_accounts[returned_ac['id']]
                    assert val == mock_accounts[returned_ac['id']][key]
        
        def test_get_accounts_by_type_none_found(self, mock_repository, mock_cursor):
            """Test retrieving accounts by type when none match."""
            mock_cursor.fetchall.return_value = []
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.get_accounts_by_type('nonexistent_type')
            
            assert result == []
    
    # ========== Update Tests ==========
    
    class TestUpdateAccount:
        """Tests for update_account method"""
        
        def test_update_account_name_only(self, mock_repository, sample_account, mock_cursor):
            """Test updating only account name."""
            mock_cursor.rowcount = 1
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with patch.object(mock_repository, 'get_account_by_id', return_value=sample_account):
                result = mock_repository.update_account(1, account_name='New Name')
            
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args
            assert "account_name = ?" in call_args[0][0]
            assert call_args[0][1] == ['New Name', 1]
        
        def test_update_account_type_only(self, mock_repository, sample_account, mock_cursor):
            """Test updating only account type."""
            mock_cursor.rowcount = 1
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with patch.object(mock_repository, 'get_account_by_id', return_value=sample_account):
                result = mock_repository.update_account(1, account_type='savings')
            
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args
            assert "account_type = ?" in call_args[0][0]
            assert call_args[0][1] == ['savings', 1]
        
        def test_update_account_both_fields(self, mock_repository, sample_account, mock_cursor):
            """Test updating both account name and type."""
            mock_cursor.rowcount = 1
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with patch.object(mock_repository, 'get_account_by_id', return_value=sample_account):
                result = mock_repository.update_account(
                    1,
                    account_name='New Name',
                    account_type='savings'
                )
            
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args
            assert "account_name = ?" in call_args[0][0]
            assert "account_type = ?" in call_args[0][0]
            assert call_args[0][1] == ['New Name', 'savings', 1]
        
        def test_update_account_no_changes(self, repository, sample_account):
            """Test update with no changes returns current account."""
            with patch.object(repository, 'get_account_by_id', return_value=sample_account):
                result = repository.update_account(1)
            
            assert result == sample_account
        
        def test_update_account_not_found(self, mock_repository, mock_cursor):
            """Test updating non-existent account returns None."""
            mock_cursor.rowcount = 0
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.update_account(999, account_name='New Name')
            
            assert result is None
        
        def test_update_account_duplicate_name_error(self, mock_repository, mock_cursor):
            """Test updating to duplicate name raises error."""
            mock_cursor.execute.side_effect = sqlite3.IntegrityError(
                "UNIQUE constraint failed"
            )
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.update_account(1, account_name='Duplicate')
            
            assert "Account name already exists" in str(exc_info.value)
        
        def test_update_account_generic_exception(self, mock_repository):
            """Test generic exception handling in update."""
            mock_repository.db.transaction.return_value.__enter__.side_effect = Exception(
                "Transaction failed"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.update_account(1, account_name='New Name')
            
            assert "Failed to update account" in str(exc_info.value)
    
    # ========== Delete Tests ==========
    
    class TestDeleteAccount:
        """Tests for delete_account method"""
        
        def test_delete_account_success(self, mock_repository, mock_cursor):
            """Test successfully deleting an account."""
            # First call returns count of 0 transactions
            # Second call is the delete
            mock_cursor.fetchone.return_value = {'count': 0}
            mock_cursor.rowcount = 1
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.delete_account(1)
            
            assert result is True
            assert mock_cursor.execute.call_count == 2
            
            # Verify the delete was called
            delete_call = mock_cursor.execute.call_args_list[1]
            assert "DELETE FROM accounts" in delete_call[0][0]
        
        def test_delete_account_not_found(self, repository):
            """Test deleting non-existent account returns False."""
           
            result = repository.delete_account(999)
            
            assert result is False
        
        def test_delete_account_with_transactions_raises_error(self, mock_repository, mock_cursor):
            """Test deleting account with transactions raises error."""
            mock_cursor.fetchone.return_value = {'count': 5}
            
            conn_mock = mock_repository.db.transaction.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.delete_account(1)
            
            assert "Cannot delete account" in str(exc_info.value)
            assert "5 associated transaction(s)" in str(exc_info.value)
        
        def test_delete_account_generic_exception(self, mock_repository):
            """Test generic exception handling in delete."""
            mock_repository.db.transaction.return_value.__enter__.side_effect = Exception(
                "Transaction failed"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.delete_account(1)
            
            assert "Failed to delete account" in str(exc_info.value)
    
    # ========== Utility Tests ==========
    
    class TestGetAccountTransactionCount:
        """Tests for get_account_transaction_count method"""
        
        def test_get_transaction_count_success(self, mock_repository, mock_cursor):
            """Test getting transaction count for account."""
            mock_cursor.fetchone.return_value = {'count': 10}
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.get_account_transaction_count(1)
            
            assert result == 10
        
        def test_get_transaction_count_zero(self, mock_repository, mock_cursor):
            """Test getting transaction count when zero."""
            mock_cursor.fetchone.return_value = {'count': 0}
            
            conn_mock = mock_repository.db.get_connection.return_value.__enter__.return_value
            conn_mock.cursor.return_value = mock_cursor
            
            result = mock_repository.get_account_transaction_count(1)
            
            assert result == 0
        
        def test_get_transaction_count_no_result(self, repository, mock_cursor):
            """Test getting transaction count with no result."""
            
            result = repository.get_account_transaction_count(1)
            
            assert result == 0
        
        def test_get_transaction_count_exception(self, mock_repository):
            """Test exception handling in get_account_transaction_count."""
            mock_repository.db.get_connection.return_value.__enter__.side_effect = Exception(
                "Query failed"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.get_account_transaction_count(1)
            
            assert "Failed to get transaction count" in str(exc_info.value)
    
    class TestGetDistinctAccountTypes:
        """Tests for get_distinct_account_types method"""
        
        def test_get_distinct_types_success(self, repository, mock_cursor):
            """Test getting distinct account types."""
            mock_types = [
                'checking',
                'credit_card',
                'savings',
            ]

            for i, ac_type in enumerate(mock_types):
                repository.add_account(f'Test ac {i}', ac_type)
            
            result = repository.get_distinct_account_types()
            
            assert result == ['checking', 'credit_card', 'savings']

        def test_get_distinct_types_empty(self, repository, mock_cursor):
            """Test getting distinct types when none exist."""
            
            result = repository.get_distinct_account_types()
            
            assert result == []
        
        def test_get_distinct_types_exception(self, mock_repository):
            """Test exception handling in get_distinct_account_types."""
            mock_repository.db.get_connection.return_value.__enter__.side_effect = Exception(
                "Query failed"
            )
            
            with pytest.raises(DatabaseError) as exc_info:
                mock_repository.get_distinct_account_types()
            
            assert "Failed to get account types" in str(exc_info.value)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])