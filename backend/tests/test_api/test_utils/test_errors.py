"""
Tests for src/api/utils/errors.py.

`AppError` is the contract between the backend and the frontend's error
handling: `to_dict()` produces the payload the client switches on, and the
factory functions fix the code/status pairing for each failure kind. Both are
easy to change by accident, so they're pinned here.

Pure - no Flask, no database.
"""
import pytest

from src.api.utils.errors import (
    AppError,
    ErrorCode,
    conflict,
    duplicate,
    has_dependencies,
    invalid_value,
    not_found,
    required,
)


# --------------------------------------------------------------------------- #
# ErrorCode
# --------------------------------------------------------------------------- #
class TestErrorCode:

    def test_is_a_string_enum(self):
        """Members compare equal to their wire value, so JSON stays readable."""
        assert ErrorCode.NOT_FOUND == 'NOT_FOUND'
        assert isinstance(ErrorCode.NOT_FOUND, str)

    def test_value_matches_name(self):
        for member in ErrorCode:
            assert member.value == member.name

    def test_expected_members_exist(self):
        """The frontend mirrors this enum by hand (see the Test drift note),
        so adding or renaming a member is a cross-repo change."""
        assert {m.value for m in ErrorCode} == {
            'REQUIRED_FIELD', 'INVALID_FORMAT', 'INVALID_VALUE', 'CONFLICT',
            'DUPLICATE_NAME', 'FOREIGN_KEY_VIOLATION', 'HAS_DEPENDENCIES',
            'NOT_FOUND', 'PARENT_NOT_FOUND',
            'DATABASE_ERROR', 'INTERNAL_ERROR', 'UNSUPPORTED_FILE_TYPE',
            'INSUFFICIENT_CAPACITY',
        }


# --------------------------------------------------------------------------- #
# AppError
# --------------------------------------------------------------------------- #
class TestAppError:

    def test_is_raisable(self):
        with pytest.raises(AppError):
            raise AppError(code=ErrorCode.NOT_FOUND, message='gone')

    def test_message_reaches_the_exception(self):
        """__post_init__ feeds the message to Exception, so str() works."""
        error = AppError(code=ErrorCode.NOT_FOUND, message='gone')
        assert str(error) == 'gone'

    def test_defaults(self):
        error = AppError(code=ErrorCode.INVALID_VALUE, message='bad')
        assert error.status_code == 400
        assert error.field is None
        assert error.entity is None
        assert error.details == {}

    def test_details_default_is_not_shared(self):
        first = AppError(code=ErrorCode.INVALID_VALUE, message='a')
        second = AppError(code=ErrorCode.INVALID_VALUE, message='b')
        first.details['x'] = 1
        assert second.details == {}

    def test_can_be_caught_as_exception(self):
        try:
            raise AppError(code=ErrorCode.INTERNAL_ERROR, message='boom')
        except Exception as exc:
            assert isinstance(exc, AppError)


class TestAppErrorToDict:

    def test_minimal_payload(self):
        error = AppError(code=ErrorCode.NOT_FOUND, message='gone')
        assert error.to_dict() == {'code': 'NOT_FOUND', 'message': 'gone'}

    def test_code_is_serialised_as_its_value(self):
        assert isinstance(
            AppError(code=ErrorCode.NOT_FOUND, message='x').to_dict()['code'], str
        )

    def test_optional_keys_are_included_when_set(self):
        error = AppError(
            code=ErrorCode.INVALID_VALUE, message='bad', field='amount',
            entity='Transaction', details={'value': -1},
        )
        assert error.to_dict() == {
            'code': 'INVALID_VALUE',
            'message': 'bad',
            'field': 'amount',
            'entity': 'Transaction',
            'details': {'value': -1},
        }

    @pytest.mark.parametrize('kwargs', [
        {'field': None}, {'entity': None}, {'details': {}},
    ])
    def test_empty_optional_keys_are_omitted(self, kwargs):
        payload = AppError(code=ErrorCode.NOT_FOUND, message='x',
                           **kwargs).to_dict()
        assert set(payload) == {'code', 'message'}

    def test_status_code_is_not_in_the_payload(self):
        """It travels as the HTTP status, not in the body."""
        error = AppError(code=ErrorCode.NOT_FOUND, message='x', status_code=404)
        assert 'status_code' not in error.to_dict()

    def test_empty_string_field_is_omitted(self):
        """Truthiness, not presence - field='' drops out."""
        error = AppError(code=ErrorCode.NOT_FOUND, message='x', field='')
        assert 'field' not in error.to_dict()


# --------------------------------------------------------------------------- #
# factory functions
# --------------------------------------------------------------------------- #
class TestNotFound:

    def test_without_identifier(self):
        error = not_found('Receipt')
        assert error.code == ErrorCode.NOT_FOUND
        assert error.status_code == 404
        assert error.message == 'Receipt not found'
        assert error.entity == 'Receipt'
        assert error.details == {}

    def test_with_identifier(self):
        error = not_found('Receipt', 42)
        assert error.message == 'Receipt 42 not found'
        assert error.details == {'identifier': 42}

    def test_string_identifier(self):
        error = not_found('StatementFormat', 'builtin:aib_current')
        assert error.message == 'StatementFormat builtin:aib_current not found'

    def test_zero_identifier_appears_in_the_message_but_not_the_details(self):
        """`if identifier` is falsy for 0, while the message uses `is None`."""
        error = not_found('Receipt', 0)
        assert error.message == 'Receipt 0 not found'
        assert error.details == {}


class TestDuplicate:

    def test_defaults(self):
        error = duplicate('Category')
        assert error.code == ErrorCode.DUPLICATE_NAME
        assert error.status_code == 409
        assert error.message == 'Category with this name already exists'
        assert error.field == 'name'
        assert error.details == {}

    def test_custom_field(self):
        assert duplicate('Account', field='account_name').message == (
            'Account with this account_name already exists'
        )

    def test_with_value(self):
        error = duplicate('Category', value='Groceries')
        assert error.message == 'Category "Groceries" already exists'
        assert error.details == {'value': 'Groceries'}

    def test_field_is_reported_even_when_a_value_is_given(self):
        assert duplicate('Category', field='label', value='X').field == 'label'


class TestRequired:

    def test_shape(self):
        error = required('amount')
        assert error.code == ErrorCode.REQUIRED_FIELD
        assert error.status_code == 400
        assert error.message == 'amount is required'
        assert error.field == 'amount'

    def test_entity_is_not_set(self):
        assert required('amount').entity is None


class TestHasDependencies:

    def test_shape(self):
        error = has_dependencies('Account', 'transactions')
        assert error.code == ErrorCode.HAS_DEPENDENCIES
        assert error.status_code == 409
        assert error.message == 'Cannot delete Account: has associated transactions'
        assert error.entity == 'Account'
        assert error.details == {'dependency': 'transactions'}


class TestInvalidValue:

    def test_shape(self):
        error = invalid_value('limit must be at most 500')
        assert error.code == ErrorCode.INVALID_VALUE
        assert error.status_code == 400
        assert error.message == 'limit must be at most 500'
        assert error.field is None

    def test_with_field(self):
        assert invalid_value('bad', field='limit').field == 'limit'

    def test_message_is_passed_through_verbatim(self):
        """Unlike the other factories this takes a ready-made message."""
        assert invalid_value('anything at all').message == 'anything at all'


class TestConflict:

    def test_shape(self):
        error = conflict('Receipt', 'Receipt is already linked')
        assert error.code == ErrorCode.CONFLICT
        assert error.status_code == 409
        assert error.message == 'Receipt is already linked'
        assert error.entity == 'Receipt'
        assert error.details == {}

    def test_extra_kwargs_become_details(self):
        error = conflict('Receipt', 'already linked', receipt_id=1,
                         transaction_id=2)
        assert error.details == {'receipt_id': 1, 'transaction_id': 2}


# --------------------------------------------------------------------------- #
# cross-factory invariants
# --------------------------------------------------------------------------- #
class TestFactoryInvariants:
    """These pairings are what the frontend switches on."""

    @pytest.mark.parametrize('error,expected_status', [
        (not_found('X'), 404),
        (duplicate('X'), 409),
        (required('x'), 400),
        (has_dependencies('X', 'y'), 409),
        (invalid_value('x'), 400),
        (conflict('X', 'x'), 409),
    ])
    def test_status_codes(self, error, expected_status):
        assert error.status_code == expected_status

    @pytest.mark.parametrize('error', [
        not_found('X', 1), duplicate('X', value='v'), required('x'),
        has_dependencies('X', 'y'), invalid_value('x', field='f'),
        conflict('X', 'x', a=1),
    ])
    def test_every_factory_produces_a_serialisable_payload(self, error):
        import json

        payload = error.to_dict()
        assert payload['code'] in {m.value for m in ErrorCode}
        assert payload['message']
        json.dumps(payload)  # must not raise

    @pytest.mark.parametrize('error', [
        not_found('X'), duplicate('X'), required('x'),
        has_dependencies('X', 'y'), invalid_value('x'), conflict('X', 'x'),
    ])
    def test_every_factory_returns_a_raisable_app_error(self, error):
        with pytest.raises(AppError):
            raise error