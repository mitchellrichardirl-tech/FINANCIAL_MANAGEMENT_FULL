"""
Tests for src/api/utils/response_helpers.py.

These build the envelope every endpoint returns, so the shape is a contract
with the frontend (and with the `unwrap` fixture in tests/conftest.py, which
assumes `success`/`data`/`error` keys).

`jsonify` needs an application context but not the real app, so these run
against a bare Flask instance - no database, no blueprints.
"""
import pytest
from flask import Flask

from src.api.utils.errors import AppError, ErrorCode, not_found
from src.api.utils.response_helpers import (
    error_response,
    paginated_response,
    search_response,
    success_response,
)

HAS_MORE_ON_EMPTY_PAGE = pytest.mark.xfail(
    reason="paginated_response computes has_more as len(items) == limit, so an "
           "empty page with limit=0 reports has_more=True, and a final page "
           "that exactly fills the limit reports more results than exist "
           "- backlog",
    strict=True,
)


@pytest.fixture
def ctx():
    """A bare app context - jsonify needs one, nothing else here does."""
    app = Flask(__name__)
    with app.app_context():
        yield app


def unpack(response):
    """(body_dict, status_code) from a (Response, status) tuple."""
    body, status = response
    return body.get_json(), status


# --------------------------------------------------------------------------- #
# success_response
# --------------------------------------------------------------------------- #
class TestSuccessResponse:

    def test_minimal(self, ctx):
        body, status = unpack(success_response())
        assert body == {'success': True}
        assert status == 200

    def test_with_data(self, ctx):
        body, _ = unpack(success_response(data={'id': 1}))
        assert body == {'success': True, 'data': {'id': 1}}

    def test_with_message(self, ctx):
        body, _ = unpack(success_response(message='Created'))
        assert body == {'success': True, 'message': 'Created'}

    def test_with_both(self, ctx):
        body, _ = unpack(success_response(data=[1], message='ok'))
        assert body == {'success': True, 'data': [1], 'message': 'ok'}

    def test_custom_status_code(self, ctx):
        _, status = unpack(success_response(data={}, status_code=201))
        assert status == 201

    def test_empty_list_is_included(self, ctx):
        """`is not None`, so an empty result set still sends a data key."""
        body, _ = unpack(success_response(data=[]))
        assert body['data'] == []

    def test_empty_dict_is_included(self, ctx):
        body, _ = unpack(success_response(data={}))
        assert body['data'] == {}

    def test_zero_is_included(self, ctx):
        body, _ = unpack(success_response(data=0))
        assert body['data'] == 0

    def test_explicit_none_data_is_omitted(self, ctx):
        assert 'data' not in unpack(success_response(data=None))[0]

    def test_empty_message_is_omitted(self, ctx):
        """Truthiness here, unlike data - message='' drops out."""
        assert 'message' not in unpack(success_response(message=''))[0]

    def test_success_key_is_always_first_and_true(self, ctx):
        body, _ = unpack(success_response(data={'success': False}))
        assert body['success'] is True
        assert body['data'] == {'success': False}


# --------------------------------------------------------------------------- #
# error_response
# --------------------------------------------------------------------------- #
class TestErrorResponse:

    def test_app_error_payload(self, ctx):
        body, status = unpack(error_response(not_found('Receipt', 42)))
        assert body == {
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Receipt 42 not found',
                'entity': 'Receipt',
                'details': {'identifier': 42},
            },
        }
        assert status == 404

    def test_app_error_status_wins_over_the_argument(self, ctx):
        _, status = unpack(error_response(not_found('X'), status_code=400))
        assert status == 404

    def test_string_error_is_wrapped(self, ctx):
        body, status = unpack(error_response('something broke'))
        assert body == {
            'success': False,
            'error': {'code': 'INTERNAL_ERROR', 'message': 'something broke'},
        }
        assert status == 400

    def test_string_error_honours_the_status_argument(self, ctx):
        _, status = unpack(error_response('nope', status_code=503))
        assert status == 503

    def test_non_app_error_exception_is_stringified(self, ctx):
        body, _ = unpack(error_response(ValueError('bad input')))
        assert body['error']['message'] == 'bad input'
        assert body['error']['code'] == 'INTERNAL_ERROR'

    def test_field_is_included_when_set(self, ctx):
        error = AppError(code=ErrorCode.INVALID_VALUE, message='bad',
                         field='amount')
        body, _ = unpack(error_response(error))
        assert body['error']['field'] == 'amount'

    def test_success_flag_is_false(self, ctx):
        body, _ = unpack(error_response('x'))
        assert body['success'] is False

    def test_no_data_key_on_errors(self, ctx):
        body, _ = unpack(error_response('x'))
        assert 'data' not in body


# --------------------------------------------------------------------------- #
# paginated_response
# --------------------------------------------------------------------------- #
class TestPaginatedResponse:

    def test_shape(self, ctx):
        body, status = unpack(paginated_response([{'id': 1}], limit=50, offset=0))
        assert status == 200
        assert body == {
            'success': True,
            'data': {
                'items': [{'id': 1}],
                'pagination': {
                    'limit': 50, 'offset': 0, 'count': 1, 'has_more': False
                },
            },
        }

    def test_custom_data_key(self, ctx):
        body, _ = unpack(paginated_response([], limit=10, offset=0,
                                            data_key='transactions'))
        assert 'transactions' in body['data']
        assert 'items' not in body['data']

    def test_extra_data_is_merged_alongside_items(self, ctx):
        body, _ = unpack(paginated_response([], limit=10, offset=0, total=99))
        assert body['data']['total'] == 99

    def test_count_reflects_the_page_not_the_total(self, ctx):
        body, _ = unpack(paginated_response([1, 2, 3], limit=50, offset=0))
        assert body['data']['pagination']['count'] == 3

    def test_offset_is_echoed(self, ctx):
        body, _ = unpack(paginated_response([], limit=10, offset=30))
        assert body['data']['pagination']['offset'] == 30

    def test_has_more_true_when_the_page_is_full(self, ctx):
        body, _ = unpack(paginated_response([1, 2], limit=2, offset=0))
        assert body['data']['pagination']['has_more'] is True

    def test_has_more_false_on_a_partial_page(self, ctx):
        body, _ = unpack(paginated_response([1], limit=2, offset=0))
        assert body['data']['pagination']['has_more'] is False

    def test_has_more_false_on_an_empty_page(self, ctx):
        body, _ = unpack(paginated_response([], limit=50, offset=100))
        assert body['data']['pagination']['has_more'] is False

    @HAS_MORE_ON_EMPTY_PAGE
    def test_has_more_is_false_when_limit_is_zero(self, ctx):
        body, _ = unpack(paginated_response([], limit=0, offset=0))
        assert body['data']['pagination']['has_more'] is False

    def test_extra_data_can_overwrite_the_pagination_block(self, ctx):
        """update() runs last, so a colliding extra key wins. ('items' can't
        collide - it's the `items` positional - but 'pagination' can.)"""
        body, _ = unpack(paginated_response([1], limit=10, offset=0,
                                            pagination='clobbered'))
        assert body['data']['pagination'] == 'clobbered'

    def test_data_key_colliding_with_pagination_is_overwritten(self, ctx):
        body, _ = unpack(paginated_response([1], limit=10, offset=0,
                                            data_key='pagination'))
        assert body['data']['pagination'] == {
            'limit': 10, 'offset': 0, 'count': 1, 'has_more': False
        }


# --------------------------------------------------------------------------- #
# search_response
# --------------------------------------------------------------------------- #
class TestSearchResponse:

    def test_shape(self, ctx):
        body, status = unpack(search_response([{'id': 1}], {'amount': 10}))
        assert status == 200
        assert body == {
            'success': True,
            'data': {
                'results': [{'id': 1}],
                'search_parameters': {'amount': 10},
                'count': 1,
            },
        }

    def test_custom_results_key(self, ctx):
        body, _ = unpack(search_response([], {}, results_key='transactions'))
        assert 'transactions' in body['data']

    def test_empty_results(self, ctx):
        body, _ = unpack(search_response([], {'q': 'nothing'}))
        assert body['data']['count'] == 0
        assert body['data']['results'] == []

    def test_parameters_are_echoed_verbatim(self, ctx):
        params = {'amount': 10.5, 'party_name': 'Tesco', 'limit': 50}
        body, _ = unpack(search_response([], params))
        assert body['data']['search_parameters'] == params

    def test_datetime_parameters_echo_back_as_http_dates_not_iso(self, ctx):
        """Flask's JSON encoder renders datetimes as RFC 822, so an echoed
        start_date comes back as 'Mon, 01 Jan 2024 00:00:00 GMT' rather than
        the ISO string the client sent. Documented, not endorsed."""
        from datetime import datetime

        body, _ = unpack(search_response([], {'start_date': datetime(2024, 1, 1)}))
        assert body['data']['search_parameters']['start_date'] == (
            'Mon, 01 Jan 2024 00:00:00 GMT'
        )


# --------------------------------------------------------------------------- #
# envelope invariants
# --------------------------------------------------------------------------- #
class TestEnvelopeInvariants:
    """tests/conftest.py's `unwrap` fixture and the frontend both rely on
    these, so they're asserted across all four builders."""

    def test_every_success_builder_sets_success_true(self, ctx):
        for response in (
            success_response(data={}),
            paginated_response([], limit=10, offset=0),
            search_response([], {}),
        ):
            body, _ = unpack(response)
            assert body['success'] is True
            assert 'error' not in body

    def test_error_builder_never_sets_data(self, ctx):
        body, _ = unpack(error_response(not_found('X')))
        assert body['success'] is False
        assert 'data' not in body

    def test_error_payload_always_has_code_and_message(self, ctx):
        for error in (not_found('X'), 'legacy string', ValueError('boom')):
            body, _ = unpack(error_response(error))
            assert body['error']['code']
            assert body['error']['message']