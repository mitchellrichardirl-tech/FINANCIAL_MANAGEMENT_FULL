"""
UploadRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched tests are the DatabaseError-wrapping checks.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.database.errors import DatabaseError
from src.database.repositories.uploads import UploadRepository


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield UploadRepository()


@pytest.fixture
def upload_id(repo):
    """A simple upload with no data rows."""
    return repo.create_upload(
        filename='statement.csv',
        file_type='csv',
        row_count=3,
        column_count=2,
        columns=['date', 'amount'],
    )


@pytest.fixture
def rows():
    return [
        {'date': '2024-01-01', 'amount': '1.00'},
        {'date': '2024-01-02', 'amount': '2.00'},
        {'date': '2024-01-03', 'amount': '3.00'},
    ]


@pytest.fixture
def upload_with_rows(repo, upload_id, rows):
    repo.save_upload_data(upload_id, rows)
    return upload_id


# --------------------------------------------------------------------------- #
# create_upload
# --------------------------------------------------------------------------- #
class TestCreateUpload:

    def test_returns_id_of_persisted_row(self, repo):
        new_id = repo.create_upload(filename='test.csv', file_type='csv',
                                    row_count=10, column_count=3)
        assert new_id > 0

        upload = repo.get_upload_by_id(new_id)
        assert upload['filename'] == 'test.csv'
        assert upload['original_filename'] == 'test.csv'
        assert upload['file_type'] == 'csv'
        assert upload['row_count'] == 10
        assert upload['column_count'] == 3
        assert upload['columns'] is None

    def test_columns_round_trip_as_list(self, repo):
        columns = ['id', 'name', 'value']
        new_id = repo.create_upload(filename='test.xlsx', file_type='xlsx',
                                    row_count=100, column_count=3, columns=columns)
        assert repo.get_upload_by_id(new_id)['columns'] == columns

    def test_counts_default_to_zero(self, repo):
        new_id = repo.create_upload(filename='default.csv', file_type='csv')
        upload = repo.get_upload_by_id(new_id)
        assert (upload['row_count'], upload['column_count']) == (0, 0)

    def test_original_filename_kept_when_given(self, repo):
        new_id = repo.create_upload(filename='stored_1.csv', file_type='csv',
                                    original_filename='My Statement.csv')
        upload = repo.get_upload_by_id(new_id)
        assert upload['filename'] == 'stored_1.csv'
        assert upload['original_filename'] == 'My Statement.csv'

    def test_ids_increment(self, repo):
        a = repo.create_upload(filename='a.csv', file_type='csv')
        b = repo.create_upload(filename='b.csv', file_type='csv')
        assert b > a

    def test_null_filename_rejected(self, repo):
        with pytest.raises(DatabaseError) as exc:
            repo.create_upload(filename=None, file_type='csv')
        assert 'Failed to create upload' in str(exc.value)


# --------------------------------------------------------------------------- #
# get_upload_by_id
# --------------------------------------------------------------------------- #
class TestGetUploadById:

    def test_found(self, repo, upload_id):
        upload = repo.get_upload_by_id(upload_id)
        assert upload['id'] == upload_id
        assert upload['columns'] == ['date', 'amount']
        assert upload['upload_date'] is not None

    def test_missing_returns_none(self, repo):
        assert repo.get_upload_by_id(999) is None

    def test_invalid_columns_json_becomes_empty_list(self, repo, upload_id, db_manager):
        with db_manager.transaction() as conn:
            conn.execute("UPDATE uploads SET columns = 'not json' WHERE id = ?", (upload_id,))
        assert repo.get_upload_by_id(upload_id)['columns'] == []


# --------------------------------------------------------------------------- #
# get_all_uploads
# --------------------------------------------------------------------------- #
class TestGetAllUploads:

    @pytest.fixture
    def several(self, repo):
        return {
            'csv1': repo.create_upload(filename='alpha.csv', file_type='csv',
                                       original_filename='Alpha Report.csv'),
            'csv2': repo.create_upload(filename='beta.csv', file_type='csv',
                                       original_filename='Beta Report.csv'),
            'xlsx': repo.create_upload(filename='gamma.xlsx', file_type='xlsx',
                                       original_filename='Gamma Report.xlsx'),
        }

    def test_empty_database(self, repo):
        assert repo.get_all_uploads() == []

    def test_returns_all(self, repo, several):
        assert {u['id'] for u in repo.get_all_uploads()} == set(several.values())

    def test_ordered_newest_first(self, repo, several):
        ids = [u['id'] for u in repo.get_all_uploads()]
        dates = [u['upload_date'] for u in repo.get_all_uploads()]
        assert dates == sorted(dates, reverse=True)
        assert set(ids) == set(several.values())

    def test_limit_and_offset(self, repo, several):
        page1 = repo.get_all_uploads(limit=2, offset=0)
        page2 = repo.get_all_uploads(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 1
        assert not {u['id'] for u in page1} & {u['id'] for u in page2}

    def test_filter_by_file_type(self, repo, several):
        assert {u['id'] for u in repo.get_all_uploads(file_type='csv')} == {
            several['csv1'], several['csv2']
        }

    def test_filter_by_filename_substring(self, repo, several):
        found = repo.get_all_uploads(filename='beta')
        assert [u['id'] for u in found] == [several['csv2']]

    def test_filter_by_original_filename_substring(self, repo, several):
        found = repo.get_all_uploads(original_filename='Gamma')
        assert [u['id'] for u in found] == [several['xlsx']]

    def test_filter_by_date_range(self, repo, several):
        now = datetime.now()
        assert len(repo.get_all_uploads(
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=1)
        )) == 3
        assert repo.get_all_uploads(start_date=now + timedelta(days=1)) == []

    def test_multiple_filters_are_anded(self, repo, several):
        assert repo.get_all_uploads(file_type='xlsx', filename='beta') == []
        found = repo.get_all_uploads(file_type='csv', filename='alpha')
        assert [u['id'] for u in found] == [several['csv1']]

    def test_no_match_returns_empty(self, repo, several):
        assert repo.get_all_uploads(file_type='pdf') == []


# --------------------------------------------------------------------------- #
# update_upload
# --------------------------------------------------------------------------- #
class TestUpdateUpload:

    def test_update_single_field(self, repo, upload_id):
        updated = repo.update_upload(upload_id, filename='renamed.csv')
        assert updated['filename'] == 'renamed.csv'
        assert updated['file_type'] == 'csv'
        assert repo.get_upload_by_id(upload_id)['filename'] == 'renamed.csv'

    def test_update_multiple_fields(self, repo, upload_id):
        updated = repo.update_upload(
            upload_id,
            original_filename='Original.xlsx',
            filename='new.xlsx',
            file_type='xlsx',
            row_count=99,
            column_count=4,
        )
        assert updated['original_filename'] == 'Original.xlsx'
        assert updated['filename'] == 'new.xlsx'
        assert updated['file_type'] == 'xlsx'
        assert updated['row_count'] == 99
        assert updated['column_count'] == 4

    def test_update_columns_round_trips(self, repo, upload_id):
        updated = repo.update_upload(upload_id, columns=['x', 'y', 'z'])
        assert updated['columns'] == ['x', 'y', 'z']

    def test_no_fields_returns_current_row_unchanged(self, repo, upload_id):
        before = repo.get_upload_by_id(upload_id)
        assert repo.update_upload(upload_id) == before

    def test_missing_upload_returns_none(self, repo):
        assert repo.update_upload(999, filename='x.csv') is None


# --------------------------------------------------------------------------- #
# delete_upload
# --------------------------------------------------------------------------- #
class TestDeleteUpload:

    def test_delete_removes_row(self, repo, upload_id):
        assert repo.delete_upload(upload_id) is True
        assert repo.get_upload_by_id(upload_id) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_upload(999) is False

    def test_delete_cascades_to_data(self, repo, upload_with_rows):
        assert repo.count_upload_data_rows(upload_with_rows) == 3
        assert repo.delete_upload(upload_with_rows) is True
        assert repo.count_upload_data_rows(upload_with_rows) == 0


# --------------------------------------------------------------------------- #
# count_uploads
# --------------------------------------------------------------------------- #
class TestCountUploads:

    def test_count_empty(self, repo):
        assert repo.count_uploads() == 0

    def test_count_all(self, repo):
        for i in range(3):
            repo.create_upload(filename=f'f{i}.csv', file_type='csv')
        assert repo.count_uploads() == 3

    def test_count_filtered_by_type(self, repo):
        repo.create_upload(filename='a.csv', file_type='csv')
        repo.create_upload(filename='b.xlsx', file_type='xlsx')
        assert repo.count_uploads(file_type='csv') == 1
        assert repo.count_uploads(file_type='pdf') == 0

    def test_count_filtered_by_date_range(self, repo, upload_id):
        now = datetime.now()
        assert repo.count_uploads(start_date=now - timedelta(days=1),
                                  end_date=now + timedelta(days=1)) == 1
        assert repo.count_uploads(start_date=now + timedelta(days=1)) == 0


# --------------------------------------------------------------------------- #
# save_upload_data
# --------------------------------------------------------------------------- #
class TestSaveUploadData:

    def test_saves_and_returns_count(self, repo, upload_id, rows):
        assert repo.save_upload_data(upload_id, rows) == 3
        assert repo.count_upload_data_rows(upload_id) == 3

    def test_row_data_round_trips(self, repo, upload_id, rows):
        repo.save_upload_data(upload_id, rows)
        stored = repo.get_upload_data(upload_id)
        assert [r['row_data'] for r in stored] == rows

    def test_row_index_is_sequential_across_batches(self, repo, upload_id):
        many = [{'n': i} for i in range(25)]
        assert repo.save_upload_data(upload_id, many, batch_size=10) == 25
        stored = repo.get_upload_data(upload_id)
        assert [r['row_index'] for r in stored] == list(range(25))
        assert [r['row_data']['n'] for r in stored] == list(range(25))

    def test_empty_list_inserts_nothing(self, repo, upload_id):
        assert repo.save_upload_data(upload_id, []) == 0
        assert repo.count_upload_data_rows(upload_id) == 0

    def test_unknown_upload_id_rejected(self, repo, rows):
        with pytest.raises(DatabaseError) as exc:
            repo.save_upload_data(999, rows)
        assert 'Failed to save upload data' in str(exc.value)

    def test_duplicate_row_index_rejected(self, repo, upload_id, rows):
        repo.save_upload_data(upload_id, rows)
        with pytest.raises(DatabaseError):
            repo.save_upload_data(upload_id, rows)
        assert repo.count_upload_data_rows(upload_id) == 3

    def test_failed_save_rolls_back(self, repo, upload_id):
        good = [{'n': i} for i in range(5)]
        repo.save_upload_data(upload_id, good[:1])
        with pytest.raises(DatabaseError):
            repo.save_upload_data(upload_id, good)
        assert repo.count_upload_data_rows(upload_id) == 1


# --------------------------------------------------------------------------- #
# get_upload_data
# --------------------------------------------------------------------------- #
class TestGetUploadData:

    def test_all_rows_ordered_by_index(self, repo, upload_with_rows, rows):
        stored = repo.get_upload_data(upload_with_rows)
        assert [r['row_index'] for r in stored] == [0, 1, 2]
        assert stored[0]['row_data'] == rows[0]

    def test_unknown_upload_returns_empty(self, repo):
        assert repo.get_upload_data(999) == []

    def test_limit_and_offset(self, repo, upload_with_rows):
        page = repo.get_upload_data(upload_with_rows, limit=2, offset=1)
        assert [r['row_index'] for r in page] == [1, 2]

    def test_row_range_is_inclusive(self, repo, upload_id):
        repo.save_upload_data(upload_id, [{'n': i} for i in range(10)])
        got = repo.get_upload_data(upload_id, start_row=2, end_row=4)
        assert [r['row_index'] for r in got] == [2, 3, 4]

    def test_row_range_combined_with_limit(self, repo, upload_id):
        repo.save_upload_data(upload_id, [{'n': i} for i in range(10)])
        got = repo.get_upload_data(upload_id, start_row=2, end_row=8, limit=3, offset=1)
        assert [r['row_index'] for r in got] == [3, 4, 5]

    def test_invalid_row_data_json_becomes_empty_dict(self, repo, upload_with_rows, db_manager):
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE upload_data SET row_data = 'oops' WHERE upload_id = ? AND row_index = 0",
                (upload_with_rows,),
            )
        assert repo.get_upload_data(upload_with_rows)[0]['row_data'] == {}


# --------------------------------------------------------------------------- #
# get_upload_data_row
# --------------------------------------------------------------------------- #
class TestGetUploadDataRow:

    def test_found(self, repo, upload_with_rows, rows):
        row = repo.get_upload_data_row(upload_with_rows, 1)
        assert row['row_index'] == 1
        assert row['row_data'] == rows[1]

    def test_missing_index_returns_none(self, repo, upload_with_rows):
        assert repo.get_upload_data_row(upload_with_rows, 99) is None

    def test_missing_upload_returns_none(self, repo):
        assert repo.get_upload_data_row(999, 0) is None


# --------------------------------------------------------------------------- #
# update_upload_data_row
# --------------------------------------------------------------------------- #
class TestUpdateUploadDataRow:

    def test_replaces_row_data(self, repo, upload_with_rows):
        new_data = {'date': '2099-12-31', 'amount': '42.00'}
        updated = repo.update_upload_data_row(upload_with_rows, 0, new_data)
        assert updated['row_data'] == new_data
        assert repo.get_upload_data_row(upload_with_rows, 0)['row_data'] == new_data

    def test_other_rows_untouched(self, repo, upload_with_rows, rows):
        repo.update_upload_data_row(upload_with_rows, 0, {'changed': True})
        assert repo.get_upload_data_row(upload_with_rows, 1)['row_data'] == rows[1]

    def test_missing_row_returns_none(self, repo, upload_with_rows):
        assert repo.update_upload_data_row(upload_with_rows, 99, {'a': 1}) is None


# --------------------------------------------------------------------------- #
# delete_upload_data / count_upload_data_rows
# --------------------------------------------------------------------------- #
class TestDeleteUploadData:

    def test_deletes_rows_but_keeps_upload(self, repo, upload_with_rows):
        assert repo.delete_upload_data(upload_with_rows) == 3
        assert repo.count_upload_data_rows(upload_with_rows) == 0
        assert repo.get_upload_by_id(upload_with_rows) is not None

    def test_no_rows_returns_zero(self, repo, upload_id):
        assert repo.delete_upload_data(upload_id) == 0

    def test_only_affects_target_upload(self, repo, upload_with_rows, rows):
        other = repo.create_upload(filename='other.csv', file_type='csv')
        repo.save_upload_data(other, rows)
        repo.delete_upload_data(upload_with_rows)
        assert repo.count_upload_data_rows(other) == 3


class TestCountUploadDataRows:

    def test_counts_rows(self, repo, upload_with_rows):
        assert repo.count_upload_data_rows(upload_with_rows) == 3

    def test_zero_for_unknown_upload(self, repo):
        assert repo.count_upload_data_rows(999) == 0


# --------------------------------------------------------------------------- #
# create_upload_with_data
# --------------------------------------------------------------------------- #
class TestCreateUploadWithData:

    def test_creates_upload_and_rows(self, repo, rows):
        result = repo.create_upload_with_data(
            filename='combined.csv', file_type='csv',
            columns=['date', 'amount'], rows=rows,
        )
        assert result['rows_inserted'] == 3

        upload = repo.get_upload_by_id(result['upload_id'])
        assert upload['row_count'] == 3
        assert upload['column_count'] == 2
        assert upload['columns'] == ['date', 'amount']
        assert [r['row_data'] for r in repo.get_upload_data(upload['id'])] == rows

    def test_original_filename_defaults_to_filename(self, repo, rows):
        result = repo.create_upload_with_data(
            filename='combined.csv', file_type='csv', columns=['a'], rows=rows,
        )
        upload = repo.get_upload_by_id(result['upload_id'])
        assert upload['original_filename'] == 'combined.csv'

    def test_large_dataset_spans_batches(self, repo):
        many = [{'n': i} for i in range(2500)]
        result = repo.create_upload_with_data(
            filename='big.csv', file_type='csv', columns=['n'], rows=many,
            batch_size=1000,
        )
        assert result['rows_inserted'] == 2500
        assert repo.count_upload_data_rows(result['upload_id']) == 2500
        assert repo.get_upload_data_row(result['upload_id'], 2499)['row_data'] == {'n': 2499}

    def test_failure_rolls_back_the_whole_upload(self, repo, monkeypatch):
        before = repo.count_uploads()

        original_dumps = json.dumps
        calls = {'n': 0}

        def exploding_dumps(obj, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] > 2:
                raise ValueError('boom')
            return original_dumps(obj, *args, **kwargs)

        monkeypatch.setattr('src.database.repositories.uploads.json.dumps', exploding_dumps)

        with pytest.raises(DatabaseError):
            repo.create_upload_with_data(
                filename='bad.csv', file_type='csv', columns=['a'],
                rows=[{'a': 1}, {'a': 2}],
            )

        monkeypatch.undo()
        assert repo.count_uploads() == before


# --------------------------------------------------------------------------- #
# get_upload_with_data
# --------------------------------------------------------------------------- #
class TestGetUploadWithData:

    def test_returns_metadata_and_rows(self, repo, upload_with_rows, rows):
        result = repo.get_upload_with_data(upload_with_rows)
        assert result['id'] == upload_with_rows
        assert [r['row_data'] for r in result['data']] == rows

    def test_missing_upload_returns_none(self, repo):
        assert repo.get_upload_with_data(999) is None

    def test_pagination_applies_to_data(self, repo, upload_with_rows):
        result = repo.get_upload_with_data(upload_with_rows, data_limit=1, data_offset=2)
        assert [r['row_index'] for r in result['data']] == [2]

    def test_upload_without_data_has_empty_list(self, repo, upload_id):
        assert repo.get_upload_with_data(upload_id)['data'] == []


# --------------------------------------------------------------------------- #
# get_upload_stats
# --------------------------------------------------------------------------- #
class TestGetUploadStats:

    def test_empty_database(self, repo):
        stats = repo.get_upload_stats()
        assert stats['total_uploads'] == 0
        assert stats['total_rows'] is None
        assert stats['by_file_type'] == []
        assert stats['recent_uploads'] == []

    def test_aggregates(self, repo):
        repo.create_upload(filename='a.csv', file_type='csv', row_count=10, column_count=3)
        repo.create_upload(filename='b.csv', file_type='csv', row_count=20, column_count=3)
        repo.create_upload(filename='c.xlsx', file_type='xlsx', row_count=30, column_count=5)

        stats = repo.get_upload_stats()
        assert stats['total_uploads'] == 3
        assert stats['total_rows'] == 60
        assert stats['avg_rows_per_upload'] == 20
        assert stats['avg_columns'] == pytest.approx(11 / 3)
        assert stats['earliest_upload'] <= stats['latest_upload']

        by_type = {t['file_type']: t for t in stats['by_file_type']}
        assert by_type['csv']['count'] == 2
        assert by_type['csv']['total_rows'] == 30
        assert by_type['xlsx']['count'] == 1

    def test_recent_uploads_capped_at_ten(self, repo):
        for i in range(12):
            repo.create_upload(filename=f'f{i}.csv', file_type='csv')
        recent = repo.get_upload_stats()['recent_uploads']
        assert len(recent) == 10
        assert set(recent[0]) == {'id', 'filename', 'file_type', 'row_count', 'upload_date'}


# --------------------------------------------------------------------------- #
# error wrapping
# --------------------------------------------------------------------------- #
class TestErrorWrapping:

    @pytest.fixture
    def broken_repo(self, repo):
        class Boom:
            def get_connection(self):
                raise RuntimeError('connection exploded')

            def transaction(self):
                raise RuntimeError('connection exploded')

        repo.db = Boom()
        return repo

    @pytest.mark.parametrize('call', [
        lambda r: r.create_upload('x.csv', 'csv'),
        lambda r: r.get_upload_by_id(1),
        lambda r: r.get_all_uploads(),
        lambda r: r.update_upload(1, filename='x.csv'),
        lambda r: r.delete_upload(1),
        lambda r: r.count_uploads(),
        lambda r: r.save_upload_data(1, [{'a': 1}]),
        lambda r: r.get_upload_data(1),
        lambda r: r.get_upload_data_row(1, 0),
        lambda r: r.update_upload_data_row(1, 0, {'a': 1}),
        lambda r: r.delete_upload_data(1),
        lambda r: r.count_upload_data_rows(1),
        lambda r: r.create_upload_with_data('x.csv', 'csv', ['a'], [{'a': 1}]),
        lambda r: r.get_upload_stats(),
    ])
    def test_db_failures_surface_as_database_error(self, broken_repo, call):
        with pytest.raises(DatabaseError):
            call(broken_repo)