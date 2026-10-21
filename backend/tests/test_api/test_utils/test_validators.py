"""
Tests for src/api/utils/validators.py.

This module sits underneath every route validator, so it's tested first and
on its own: the per-route tests can then assert their own rules without
re-testing date parsing and pagination bounds.

Everything here is pure - no Flask, no database. Query-string helpers are
exercised with werkzeug's MultiDict as well as plain dicts, because that's
what `request.args` actually is.
"""
from datetime import datetime

import pytest
from werkzeug.datastructures import MultiDict

from src.api.utils.validators import (
    FieldValidator,
    RequestValidator,
    ValidationError,
    ValidationResult,
    add_string_filters,
    apply_defaults,
    parse_bool_from_string,
    parse_date,
    parse_float,
    parse_int,
    require_at_least_one,
    validate_amount,
    validate_boolean_fields,
    validate_confidence,
    validate_date_range_filters,
    validate_id_filters,
    validate_pagination,
    validate_positive_int,
    validate_receipt_date,
    validate_single_field,
    validate_sort_params,
)

IN_RANGE_TYPE_ERROR = pytest.mark.xfail(
    reason="in_range() compares with < and > without checking the value is "
           "numeric, so a non-numeric value raises TypeError instead of "
           "producing a validation error - backlog",
    strict=True,
)

BOOLEAN_FIELDS_NEVER_FAIL = pytest.mark.xfail(
    reason="validate_boolean_fields() writes straight into validator.validated "
           "via parse_bool_from_string, so unparseable input silently becomes "
           "False instead of a validation error - backlog",
    strict=True,
)


# --------------------------------------------------------------------------- #
# ValidationResult / ValidationError
# --------------------------------------------------------------------------- #
class TestValidationResult:

    def test_success(self):
        result = ValidationResult.success(42)
        assert result.is_valid is True
        assert result.value == 42
        assert result.error is None

    def test_failure(self):
        result = ValidationResult.failure('age', 'too small', 'min_value')
        assert result.is_valid is False
        assert result.value is None
        assert result.error == ValidationError('age', 'too small', 'min_value')

    def test_failure_code_defaults_to_invalid(self):
        assert ValidationResult.failure('f', 'bad').error.code == 'invalid'

    def test_success_accepts_none(self):
        """An optional field that was absent is a valid None."""
        assert ValidationResult.success(None).is_valid is True


# --------------------------------------------------------------------------- #
# FieldValidator - presence
# --------------------------------------------------------------------------- #
class TestRequiredAndOptional:

    def test_required_passes_when_present(self):
        assert FieldValidator('name', 'x').required().is_valid()

    def test_required_fails_when_none(self):
        result = FieldValidator('name', None).required().get_result()
        assert result.is_valid is False
        assert result.error.message == 'name is required'
        assert result.error.code == 'required'

    @pytest.mark.parametrize('value', ['', 0, False, []])
    def test_required_accepts_falsy_values(self, value):
        """Only None is 'missing' - an explicit 0 or '' is a provided value."""
        assert FieldValidator('f', value).required().is_valid()

    def test_optional_none_short_circuits_the_chain(self):
        """A None optional must not then fail a type or range check."""
        result = (FieldValidator('age', None)
                  .optional().is_type(int).in_range(1, 10).get_result())
        assert result.is_valid is True
        assert result.value is None

    def test_optional_present_continues_the_chain(self):
        result = FieldValidator('age', 'x').optional().is_type(int).get_result()
        assert result.is_valid is False

    def test_required_failure_stops_later_checks(self):
        result = FieldValidator('age', None).required().is_type(int).get_result()
        assert len(FieldValidator('age', None).required().is_type(int).errors) == 1
        assert result.error.code == 'required'


# --------------------------------------------------------------------------- #
# FieldValidator - checks
# --------------------------------------------------------------------------- #
class TestIsType:

    def test_passes(self):
        assert FieldValidator('n', 5).is_type(int).is_valid()

    def test_fails(self):
        result = FieldValidator('n', 'five').is_type(int).get_result()
        assert result.error.message == 'n must be a int'
        assert result.error.code == 'type_error'

    def test_custom_type_name_is_used_in_the_message(self):
        result = FieldValidator('n', 'x').is_type(int, 'whole number').get_result()
        assert result.error.message == 'n must be a whole number'

    def test_bool_passes_an_int_check(self):
        """bool subclasses int, so True satisfies is_type(int)."""
        assert FieldValidator('f', True).is_type(int).is_valid()

    def test_failure_stops_the_chain(self):
        validator = FieldValidator('n', 'x').is_type(int).in_range(1, 10)
        assert len(validator.errors) == 1


class TestInRange:

    @pytest.mark.parametrize('value', [1, 5, 10])
    def test_within_bounds(self, value):
        assert FieldValidator('n', value).in_range(1, 10).is_valid()

    def test_bounds_are_inclusive(self):
        assert FieldValidator('n', 1).in_range(1, 10).is_valid()
        assert FieldValidator('n', 10).in_range(1, 10).is_valid()

    def test_below_minimum(self):
        result = FieldValidator('n', 0).in_range(1, 10).get_result()
        assert result.error.message == 'n must be at least 1'
        assert result.error.code == 'min_value'

    def test_above_maximum(self):
        result = FieldValidator('n', 11).in_range(1, 10).get_result()
        assert result.error.message == 'n must be at most 10'
        assert result.error.code == 'max_value'

    def test_minimum_only(self):
        assert FieldValidator('n', 1000).in_range(min_val=1).is_valid()

    def test_maximum_only(self):
        assert FieldValidator('n', -5).in_range(max_val=10).is_valid()

    def test_floats(self):
        assert FieldValidator('n', 1.5).in_range(1.0, 2.0).is_valid()

    def test_does_not_stop_the_chain(self):
        """Unlike the other checks, in_range leaves _stopped alone."""
        validator = FieldValidator('n', 0).in_range(1, 10).is_type(str)
        assert len(validator.errors) == 2

    @IN_RANGE_TYPE_ERROR
    def test_non_numeric_value_is_a_validation_error_not_a_crash(self):
        result = FieldValidator('n', 'abc').in_range(min_val=1).get_result()
        assert result.is_valid is False


class TestInSet:

    def test_passes(self):
        assert FieldValidator('s', 'asc').in_set({'asc', 'desc'}).is_valid()

    def test_fails(self):
        result = FieldValidator('s', 'sideways').in_set({'asc', 'desc'}).get_result()
        assert result.error.message == 's must be one of: asc, desc'
        assert result.error.code == 'not_in_set'

    def test_allowed_values_are_sorted_in_the_message(self):
        result = FieldValidator('s', 'x').in_set({'c', 'a', 'b'}).get_result()
        assert result.error.message.endswith('a, b, c')

    def test_case_sensitive_by_default(self):
        assert not FieldValidator('s', 'ASC').in_set({'asc'}).is_valid()

    def test_case_insensitive_option(self):
        assert FieldValidator('s', 'ASC').in_set({'asc'}, case_insensitive=True).is_valid()

    def test_case_insensitive_preserves_the_original_value(self):
        result = FieldValidator('s', 'ASC').in_set({'asc'}, case_insensitive=True).get_result()
        assert result.value == 'ASC'

    def test_case_insensitive_with_non_string_values(self):
        assert FieldValidator('s', 1).in_set({1, 2}, case_insensitive=True).is_valid()

    def test_failure_stops_the_chain(self):
        validator = FieldValidator('s', 'x').in_set({'a'}).is_type(int)
        assert len(validator.errors) == 1


class TestTransform:

    def test_applies_the_transformer(self):
        assert FieldValidator('n', '5').transform(parse_int).get_result().value == 5

    def test_value_error_becomes_a_validation_error(self):
        result = FieldValidator('n', 'abc').transform(parse_int).get_result()
        assert result.is_valid is False
        assert result.error.code == 'transform_error'

    def test_default_error_message(self):
        result = FieldValidator('n', 'abc').transform(parse_int).get_result()
        assert result.error.message == 'Invalid n format'

    def test_custom_error_message(self):
        result = FieldValidator('n', 'abc').transform(parse_int, 'Nope').get_result()
        assert result.error.message == 'Nope'

    def test_type_error_is_caught_too(self):
        result = FieldValidator('n', None).transform(parse_int).get_result()
        assert result.is_valid is False

    def test_other_exceptions_propagate(self):
        """Only ValueError/TypeError are treated as user input problems."""
        def boom(value):
            raise KeyError('internal')

        with pytest.raises(KeyError):
            FieldValidator('n', 'x').transform(boom)

    def test_failure_stops_the_chain(self):
        validator = FieldValidator('n', 'abc').transform(parse_int).in_range(1, 10)
        assert len(validator.errors) == 1

    def test_chained_transform_then_range(self):
        result = FieldValidator('n', '5').transform(parse_int).in_range(1, 10).get_result()
        assert result.value == 5


class TestAsBoolAndStripString:

    @pytest.mark.parametrize('value,expected', [
        ('true', True), ('TRUE', True), ('1', True), ('yes', True),
        ('false', False), ('no', False), ('0', False), ('', False),
        (True, True), (False, False),
    ])
    def test_as_bool(self, value, expected):
        assert FieldValidator('f', value).as_bool().get_result().value is expected

    def test_as_bool_leaves_none_alone(self):
        assert FieldValidator('f', None).optional().as_bool().get_result().value is None

    def test_strip_string(self):
        assert FieldValidator('s', '  x  ').strip_string().get_result().value == 'x'

    def test_strip_string_rejects_whitespace_only(self):
        result = FieldValidator('s', '   ').strip_string().get_result()
        assert result.is_valid is False
        assert result.error.code == 'empty_string'

    def test_strip_string_ignores_none(self):
        assert FieldValidator('s', None).strip_string().is_valid()

    def test_strip_string_ignores_non_strings(self):
        assert FieldValidator('s', 5).strip_string().get_result().value == 5


# --------------------------------------------------------------------------- #
# RequestValidator
# --------------------------------------------------------------------------- #
class TestRequestValidator:

    def test_collects_validated_values(self):
        validator = RequestValidator({'a': '1', 'b': '2'})
        validator.validate_field('a', validator.field('a').transform(parse_int))
        validator.validate_field('b', validator.field('b').transform(parse_int))
        assert validator.validated == {'a': 1, 'b': 2}

    def test_absent_optional_fields_are_not_added(self):
        validator = RequestValidator({})
        validator.validate_field('a', validator.field('a').optional().transform(parse_int))
        assert validator.validated == {}

    def test_collects_errors(self):
        validator = RequestValidator({'a': 'x', 'b': 'y'})
        validator.validate_field('a', validator.field('a').transform(parse_int))
        validator.validate_field('b', validator.field('b').transform(parse_int))
        assert validator.is_valid() is False
        assert len(validator.get_errors()) == 2

    def test_first_error_message(self):
        validator = RequestValidator({'a': None})
        validator.validate_field('a', validator.field('a').required())
        assert validator.first_error_message() == 'a is required'

    def test_first_error_message_is_none_when_valid(self):
        assert RequestValidator({}).first_error_message() is None

    def test_error_dict_shape(self):
        validator = RequestValidator({'a': None})
        validator.validate_field('a', validator.field('a').required())
        assert validator.get_errors() == [
            {'field': 'a', 'message': 'a is required', 'code': 'required'}
        ]

    def test_none_data_is_tolerated(self):
        assert RequestValidator(None).data == {}

    def test_validate_field_is_chainable(self):
        validator = RequestValidator({'a': '1'})
        assert validator.validate_field('a', validator.field('a')) is validator

    def test_works_with_multidict(self):
        validator = RequestValidator(MultiDict([('a', '1')]))
        validator.validate_field('a', validator.field('a').transform(parse_int))
        assert validator.validated == {'a': 1}


# --------------------------------------------------------------------------- #
# transformers
# --------------------------------------------------------------------------- #
class TestTransformers:

    def test_parse_date(self):
        assert parse_date('2024-01-15') == datetime(2024, 1, 15)

    def test_parse_date_accepts_full_iso(self):
        assert parse_date('2024-01-15T10:30:00') == datetime(2024, 1, 15, 10, 30)

    @pytest.mark.parametrize('value', ['15/01/2024', 'not a date', ''])
    def test_parse_date_rejects_other_formats(self, value):
        with pytest.raises(ValueError):
            parse_date(value)

    def test_parse_float(self):
        assert parse_float('1.5') == 1.5

    def test_parse_int(self):
        assert parse_int('5') == 5

    def test_parse_int_rejects_decimal_strings(self):
        with pytest.raises(ValueError):
            parse_int('5.5')

    def test_parse_int_truncates_floats(self):
        assert parse_int(5.9) == 5


class TestParseBoolFromString:

    @pytest.mark.parametrize('value', ['true', 'True', 'TRUE', '1', 'yes', 'YES'])
    def test_truthy_strings(self, value):
        assert parse_bool_from_string(value) is True

    @pytest.mark.parametrize('value', ['false', 'no', '0', '', 'off'])
    def test_everything_else_is_false(self, value):
        assert parse_bool_from_string(value) is False

    def test_none_stays_none(self):
        assert parse_bool_from_string(None) is None

    def test_bools_pass_through(self):
        assert parse_bool_from_string(True) is True
        assert parse_bool_from_string(False) is False

    def test_non_strings_use_truthiness(self):
        assert parse_bool_from_string(1) is True
        assert parse_bool_from_string(0) is False
        assert parse_bool_from_string([]) is False

    def test_unrecognised_string_is_false_not_an_error(self):
        """'maybe' is indistinguishable from 'false' - see backlog."""
        assert parse_bool_from_string('maybe') is False


# --------------------------------------------------------------------------- #
# receipt field validators
# --------------------------------------------------------------------------- #
class TestReceiptFieldValidators:

    @pytest.mark.parametrize('value', [0, 1, 2, 3])
    def test_confidence_in_range(self, value):
        assert validate_confidence(value).is_valid

    @pytest.mark.parametrize('value', [-1, 4])
    def test_confidence_out_of_range(self, value):
        assert validate_confidence(value).is_valid is False

    def test_confidence_rejects_non_int(self):
        result = validate_confidence('3')
        assert result.is_valid is False
        assert result.error.code == 'type_error'

    def test_confidence_optional(self):
        assert validate_confidence(None).is_valid

    def test_amount_parses_strings(self):
        assert validate_amount('12.34').value == 12.34

    def test_amount_rejects_junk(self):
        result = validate_amount('abc')
        assert result.is_valid is False
        assert result.error.message == 'Invalid amount format'

    def test_amount_allows_negative(self):
        """No sign constraint here - the repository enforces that."""
        assert validate_amount('-5').value == -5.0

    def test_receipt_date(self):
        assert validate_receipt_date('2024-01-15').value == datetime(2024, 1, 15)

    def test_receipt_date_rejects_junk(self):
        result = validate_receipt_date('15/01/2024')
        assert result.is_valid is False
        assert 'Use YYYY-MM-DD' in result.error.message

    def test_positive_int(self):
        assert validate_positive_int('party_id', '5').value == 5

    @pytest.mark.parametrize('value', [0, -1])
    def test_positive_int_rejects_non_positive(self, value):
        assert validate_positive_int('party_id', value).is_valid is False


# --------------------------------------------------------------------------- #
# validate_pagination
# --------------------------------------------------------------------------- #
class TestValidatePagination:

    def test_defaults(self):
        ok, values, error = validate_pagination({})
        assert (ok, values, error) == (True, {'limit': 50, 'offset': 0}, None)

    def test_parses_strings(self):
        ok, values, _ = validate_pagination({'limit': '10', 'offset': '20'})
        assert (ok, values) == (True, {'limit': 10, 'offset': 20})

    def test_limit_bounds_are_inclusive(self):
        assert validate_pagination({'limit': '1'})[1]['limit'] == 1
        assert validate_pagination({'limit': '500'})[1]['limit'] == 500

    @pytest.mark.parametrize('limit', ['0', '501'])
    def test_limit_out_of_range(self, limit):
        ok, values, error = validate_pagination({'limit': limit})
        assert ok is False and values == {} and error

    def test_negative_offset_rejected(self):
        assert validate_pagination({'offset': '-1'})[0] is False

    def test_unparseable_limit(self):
        ok, _, error = validate_pagination({'limit': 'abc'})
        assert ok is False
        assert error == 'Invalid limit format'

    def test_one_bad_field_defaults_nothing(self):
        """A partial failure returns an empty dict, not half the values."""
        assert validate_pagination({'limit': 'abc', 'offset': '5'})[1] == {}

    def test_works_with_multidict(self):
        ok, values, _ = validate_pagination(MultiDict([('limit', '10')]))
        assert ok and values['limit'] == 10


# --------------------------------------------------------------------------- #
# validate_sort_params
# --------------------------------------------------------------------------- #
class TestValidateSortParams:

    ALLOWED = {'name', 'date'}

    def test_defaults(self):
        ok, values, _ = validate_sort_params({}, self.ALLOWED, 'date', 'desc')
        assert (ok, values) == (True, {'sort_by': 'date', 'sort_dir': 'desc'})

    def test_accepts_allowed_field(self):
        ok, values, _ = validate_sort_params({'sort_by': 'name'}, self.ALLOWED)
        assert values['sort_by'] == 'name'

    def test_rejects_unknown_field(self):
        ok, _, error = validate_sort_params({'sort_by': 'nope'}, self.ALLOWED)
        assert ok is False
        assert error == 'sort_by must be one of: date, name'

    def test_direction_is_case_insensitive_and_lowered(self):
        ok, values, _ = validate_sort_params({'sort_dir': 'DESC'}, self.ALLOWED)
        assert values['sort_dir'] == 'desc'

    def test_rejects_unknown_direction(self):
        assert validate_sort_params({'sort_dir': 'sideways'}, self.ALLOWED)[0] is False

    def test_default_field_may_be_none(self):
        ok, values, _ = validate_sort_params({}, self.ALLOWED, None)
        assert values['sort_by'] is None

    def test_empty_allowed_set_rejects_everything(self):
        assert validate_sort_params({'sort_by': 'name'}, set())[0] is False


# --------------------------------------------------------------------------- #
# filter helpers
# --------------------------------------------------------------------------- #
class TestValidateIdFilters:

    def test_parses_present_fields(self):
        validator = RequestValidator({'party_id': '5'})
        validate_id_filters(validator, {'party_id': '5'}, ['party_id', 'account_id'])
        assert validator.validated == {'party_id': 5}

    def test_absent_fields_are_skipped(self):
        validator = RequestValidator({})
        validate_id_filters(validator, {}, ['party_id'])
        assert validator.validated == {}

    @pytest.mark.parametrize('value', ['0', '-1'])
    def test_rejects_non_positive_ids(self, value):
        validator = RequestValidator({'party_id': value})
        validate_id_filters(validator, {'party_id': value}, ['party_id'])
        assert validator.is_valid() is False

    def test_rejects_unparseable_ids(self):
        validator = RequestValidator({'party_id': 'abc'})
        validate_id_filters(validator, {'party_id': 'abc'}, ['party_id'])
        assert validator.is_valid() is False

    def test_is_chainable(self):
        validator = RequestValidator({})
        assert validate_id_filters(validator, {}, []) is validator


class TestValidateBooleanFields:

    def test_parses_present_fields(self):
        validator = RequestValidator({})
        validate_boolean_fields(validator, {'is_kids': 'true'}, ['is_kids'])
        assert validator.validated == {'is_kids': True}

    def test_absent_fields_are_skipped(self):
        validator = RequestValidator({})
        validate_boolean_fields(validator, {}, ['is_kids'])
        assert validator.validated == {}

    def test_explicit_false_is_kept(self):
        validator = RequestValidator({})
        validate_boolean_fields(validator, {'is_kids': 'false'}, ['is_kids'])
        assert validator.validated == {'is_kids': False}

    @BOOLEAN_FIELDS_NEVER_FAIL
    def test_unparseable_value_is_an_error(self):
        validator = RequestValidator({})
        validate_boolean_fields(validator, {'is_kids': 'maybe'}, ['is_kids'])
        assert validator.is_valid() is False


class TestAddStringFilters:

    def test_adds_present_fields(self):
        assert add_string_filters({}, {'description': 'tesco'}, ['description']) == {
            'description': 'tesco'
        }

    def test_skips_absent_fields(self):
        assert add_string_filters({}, {}, ['description']) == {}

    def test_skips_empty_strings(self):
        assert add_string_filters({}, {'description': ''}, ['description']) == {}

    def test_mutates_and_returns_the_same_dict(self):
        validated = {}
        assert add_string_filters(validated, {'a': 'x'}, ['a']) is validated

    def test_does_not_strip_whitespace(self):
        assert add_string_filters({}, {'a': ' x '}, ['a']) == {'a': ' x '}


class TestValidateDateRangeFilters:

    def test_parses_both_ends(self):
        ok, values, _ = validate_date_range_filters(
            {'start_date': '2024-01-01', 'end_date': '2024-01-31'}
        )
        assert ok is True
        assert values == {
            'start_date': datetime(2024, 1, 1), 'end_date': datetime(2024, 1, 31)
        }

    def test_absent_dates_are_omitted(self):
        assert validate_date_range_filters({}) == (True, {}, None)

    def test_rejects_bad_start_date(self):
        ok, _, error = validate_date_range_filters({'start_date': '01/01/2024'})
        assert ok is False
        assert error == 'Invalid start_date format. Use YYYY-MM-DD'

    def test_custom_field_names(self):
        ok, values, _ = validate_date_range_filters(
            {'from': '2024-01-01'}, start_date_field='from', end_date_field='to'
        )
        assert values == {'from': datetime(2024, 1, 1)}

    def test_inverted_range_is_accepted(self):
        """No ordering check here - start after end is passed straight through."""
        ok, values, _ = validate_date_range_filters(
            {'start_date': '2024-12-31', 'end_date': '2024-01-01'}
        )
        assert ok is True


class TestRequireAtLeastOne:

    def test_returns_none_when_one_is_present(self):
        assert require_at_least_one({'a': 1}, ['a', 'b']) is None

    def test_returns_a_message_when_none_are_present(self):
        assert require_at_least_one({}, ['a', 'b']) == 'At least one of a, b is required'

    def test_custom_message(self):
        assert require_at_least_one({}, ['a'], 'Need something') == 'Need something'

    def test_explicit_none_does_not_count(self):
        assert require_at_least_one({'a': None}, ['a']) is not None

    def test_falsy_values_do_count(self):
        """0 and '' are provided values, unlike None."""
        assert require_at_least_one({'a': 0}, ['a']) is None
        assert require_at_least_one({'a': ''}, ['a']) is None


class TestApplyDefaults:

    def test_fills_missing_keys(self):
        assert apply_defaults({}, {'limit': 50}) == {'limit': 50}

    def test_does_not_overwrite_present_keys(self):
        assert apply_defaults({'limit': 10}, {'limit': 50}) == {'limit': 10}

    def test_does_not_overwrite_explicit_none(self):
        assert apply_defaults({'limit': None}, {'limit': 50}) == {'limit': None}

    def test_mutates_and_returns_the_same_dict(self):
        data = {}
        assert apply_defaults(data, {'a': 1}) is data


# --------------------------------------------------------------------------- #
# validate_single_field
# --------------------------------------------------------------------------- #
class TestValidateSingleField:

    def test_optional_by_default(self):
        assert validate_single_field('f', None).is_valid

    def test_required(self):
        result = validate_single_field('f', None, required=True)
        assert result.is_valid is False
        assert result.error.code == 'required'

    def test_type_check(self):
        assert validate_single_field('f', 'x', field_type=int).is_valid is False

    def test_transformer(self):
        assert validate_single_field('f', '5', transformer=parse_int).value == 5

    def test_range_applies_after_the_transformer(self):
        result = validate_single_field('f', '50', transformer=parse_int, max_val=10)
        assert result.is_valid is False
        assert result.error.code == 'max_value'

    def test_custom_error_message(self):
        result = validate_single_field('f', 'x', transformer=parse_int,
                                       error_message='Nope')
        assert result.error.message == 'Nope'

    def test_all_options_together(self):
        result = validate_single_field(
            'f', '5', required=True, field_type=str, transformer=parse_int,
            min_val=1, max_val=10,
        )
        assert result.is_valid is True
        assert result.value == 5