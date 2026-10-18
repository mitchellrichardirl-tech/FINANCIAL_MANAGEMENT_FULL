"""
Tests for src/api/services/receipt_processor.py.

Three units live here:
  * `receipt_worker`       - sync worker for the OCR/multiprocessing path
  * `receipt_worker_async` - async worker for the Gemini path
  * `ReceiptStreamProcessor` - thin wrapper that builds tasks and delegates

Both workers follow the same shape: load pages -> extract -> pick best ->
persist -> report. The tests stub `src.receipts.worker_common` (imported inside
each worker, so patching the module attributes is enough) to drive each branch
without touching OCR, the filesystem or the database.

`worker_common.persist` itself is covered in tests/test_receipts; the contract
that a receipt is written as status='pending' before its success event is
covered in test_receipt_stream_processor.py.
"""
import asyncio

import pytest

import src.receipts.worker_common as wc
from src.api.models.processing import ProcessingResult, ProcessingTask
from src.api.services.receipt_processor import (
    ReceiptStreamProcessor,
    receipt_worker,
    receipt_worker_async,
)


class FakeReceipt:
    def __init__(self, confidence=2, vendor='Stub Vendor', amount=12.34):
        self.confidence = confidence
        self.vendor = vendor
        self.amount = amount
        self.date = None
        self.original_filename = None
        self.stored_filename = None
        self.file_path = None


class FakeExtractor:
    def __init__(self, exc=None):
        self.exc = exc
        self.calls = []

    def process_receipt(self, page):
        self.calls.append(page)
        if self.exc:
            raise self.exc
        return page

    async def aprocess_receipt(self, page):
        return self.process_receipt(page)


@pytest.fixture
def stub_worker_common(monkeypatch):
    """Patch the worker_common helpers both workers call.

    Returns a dict of call records so tests can assert on what was passed.
    """
    calls = {'load_pages': [], 'persist': [], 'select_best': []}
    state = {
        'pages': [FakeReceipt()],
        'receipt_id': 99,
        'stored_filename': 'stored.jpg',
        'load_error': None,
        'persist_error': None,
    }

    def fake_load_pages(temp_path, apply_methods=True):
        calls['load_pages'].append((temp_path, apply_methods))
        if state['load_error']:
            raise state['load_error']
        return state['pages']

    def fake_select_best(processed):
        calls['select_best'].append(processed)
        return processed[0]

    def fake_persist(temp_path, identifier, upload_folder, receipt, repository):
        calls['persist'].append(
            (temp_path, identifier, upload_folder, receipt, repository)
        )
        if state['persist_error']:
            raise state['persist_error']
        return state['receipt_id'], state['stored_filename']

    monkeypatch.setattr(wc, 'load_pages', fake_load_pages)
    monkeypatch.setattr(wc, 'select_best', fake_select_best)
    monkeypatch.setattr(wc, 'persist', fake_persist)
    return {'calls': calls, 'state': state}


@pytest.fixture
def stub_sync_deps(monkeypatch, stub_worker_common):
    """receipt_worker also constructs its own extractor and repository."""
    extractor = FakeExtractor()
    repos = []

    import src.receipts.extractor_factory as factory
    import src.database.repositories.receipts as receipts_repo

    monkeypatch.setattr(factory, 'get_extractor', lambda method: extractor)

    class FakeRepo:
        def __init__(self):
            repos.append(self)

    monkeypatch.setattr(receipts_repo, 'ReceiptRepository', FakeRepo)
    return {**stub_worker_common, 'extractor': extractor, 'repos': repos}


def sync_args(index=0, identifier='receipt.jpg', temp_path='/tmp/receipt.jpg',
              upload_folder='/uploads', ocr_method='tesseract'):
    """The tuple ParallelStreamProcessor builds: note the unused 5th slot."""
    return (index, identifier, temp_path, upload_folder, 'UNUSED', ocr_method)


# --------------------------------------------------------------------------- #
# receipt_worker (sync / OCR path)
# --------------------------------------------------------------------------- #
class TestReceiptWorkerSuccess:

    def test_returns_a_success_result(self, stub_sync_deps):
        result = receipt_worker(sync_args())
        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.index == 0
        assert result.identifier == 'receipt.jpg'

    def test_result_payload(self, stub_sync_deps):
        result = receipt_worker(sync_args())
        assert result.data['receipt_id'] == 99
        assert result.data['receipt_status'] == 'pending'
        assert result.data['stored_filename'] == 'stored.jpg'
        assert result.data['original_filename'] == 'receipt.jpg'
        assert result.data['extracted_data']['vendor'] == 'Stub Vendor'
        assert result.data['extracted_data']['amount'] == 12.34

    def test_unpacks_the_args_tuple_positionally(self, stub_sync_deps):
        receipt_worker(sync_args(index=3, identifier='a.png',
                                 temp_path='/tmp/a.png',
                                 upload_folder='/up'))
        temp_path, apply_methods = stub_sync_deps['calls']['load_pages'][0]
        assert temp_path == '/tmp/a.png'
        persisted = stub_sync_deps['calls']['persist'][0]
        assert persisted[0] == '/tmp/a.png'
        assert persisted[1] == 'a.png'
        assert persisted[2] == '/up'

    def test_loads_pages_without_preprocessing(self, stub_sync_deps):
        """OCR preprocessing happens in the extractor, not the loader."""
        receipt_worker(sync_args())
        assert stub_sync_deps['calls']['load_pages'][0][1] is False

    def test_selects_the_best_page(self, stub_sync_deps, monkeypatch):
        pages = [FakeReceipt(confidence=1), FakeReceipt(confidence=3)]
        stub_sync_deps['state']['pages'] = pages
        monkeypatch.setattr(wc, 'select_best', lambda processed: max(
            processed, key=lambda r: r.confidence))

        receipt_worker(sync_args())
        persisted_receipt = stub_sync_deps['calls']['persist'][0][3]
        assert persisted_receipt.confidence == 3

    def test_every_page_is_extracted(self, stub_sync_deps):
        stub_sync_deps['state']['pages'] = [FakeReceipt(), FakeReceipt()]
        receipt_worker(sync_args())
        assert len(stub_sync_deps['extractor'].calls) == 2

    def test_builds_its_own_repository(self, stub_sync_deps):
        """The sync path runs in a subprocess, so it can't share a connection."""
        receipt_worker(sync_args())
        assert len(stub_sync_deps['repos']) == 1


class TestReceiptWorkerFailures:

    def test_no_pages_is_reported_not_raised(self, stub_sync_deps):
        stub_sync_deps['state']['pages'] = []
        result = receipt_worker(sync_args())
        assert result.success is False
        assert result.error == 'Unable to process image'
        assert result.identifier == 'receipt.jpg'

    def test_no_pages_skips_persistence(self, stub_sync_deps):
        stub_sync_deps['state']['pages'] = []
        receipt_worker(sync_args())
        assert stub_sync_deps['calls']['persist'] == []

    def test_persist_returning_none_is_a_failure(self, stub_sync_deps):
        stub_sync_deps['state']['receipt_id'] = None
        result = receipt_worker(sync_args())
        assert result.success is False
        assert result.error == 'Failed to save to database'

    def test_loader_exception_is_caught(self, stub_sync_deps):
        stub_sync_deps['state']['load_error'] = OSError('bad file')
        result = receipt_worker(sync_args())
        assert result.success is False
        assert 'bad file' in result.error

    def test_persist_exception_is_caught(self, stub_sync_deps):
        stub_sync_deps['state']['persist_error'] = RuntimeError('disk full')
        result = receipt_worker(sync_args())
        assert result.success is False
        assert 'disk full' in result.error

    def test_extractor_exception_is_caught(self, stub_sync_deps, monkeypatch):
        import src.receipts.extractor_factory as factory
        monkeypatch.setattr(
            factory, 'get_extractor',
            lambda method: FakeExtractor(exc=RuntimeError('ocr died')),
        )
        result = receipt_worker(sync_args())
        assert result.success is False
        assert 'ocr died' in result.error

    def test_failures_keep_the_index_for_the_client(self, stub_sync_deps):
        stub_sync_deps['state']['pages'] = []
        result = receipt_worker(sync_args(index=4, identifier='d.jpg'))
        assert (result.index, result.identifier) == (4, 'd.jpg')

    def test_base_exceptions_are_not_swallowed(self, stub_sync_deps):
        """`except Exception` deliberately lets KeyboardInterrupt/SystemExit
        through so a pool shutdown isn't reported as a per-file failure."""
        stub_sync_deps['state']['load_error'] = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            receipt_worker(sync_args())


# --------------------------------------------------------------------------- #
# receipt_worker_async (Gemini path)
# --------------------------------------------------------------------------- #
def run_async_worker(task=None, upload_folder='/uploads', extractor=None,
                     repository=None):
    task = task or ProcessingTask(index=0, identifier='receipt.jpg',
                                  data='/tmp/receipt.jpg')
    return asyncio.run(receipt_worker_async(
        task, upload_folder, extractor or FakeExtractor(),
        repository or object(),
    ))


class TestReceiptWorkerAsync:

    def test_returns_a_success_result(self, stub_worker_common):
        result = run_async_worker()
        assert result.success is True
        assert result.data['receipt_id'] == 99
        assert result.data['receipt_status'] == 'pending'

    def test_uses_the_injected_extractor_and_repository(self, stub_worker_common):
        extractor, repository = FakeExtractor(), object()
        run_async_worker(extractor=extractor, repository=repository)
        assert len(extractor.calls) == 1
        assert stub_worker_common['calls']['persist'][0][4] is repository

    def test_reads_the_task_fields(self, stub_worker_common):
        task = ProcessingTask(index=5, identifier='b.png', data='/tmp/b.png')
        result = run_async_worker(task=task)
        assert (result.index, result.identifier) == (5, 'b.png')
        assert stub_worker_common['calls']['load_pages'][0][0] == '/tmp/b.png'

    def test_loads_pages_without_preprocessing(self, stub_worker_common):
        run_async_worker()
        assert stub_worker_common['calls']['load_pages'][0][1] is False

    def test_all_pages_are_extracted_concurrently(self, stub_worker_common):
        stub_worker_common['state']['pages'] = [FakeReceipt(), FakeReceipt(),
                                                FakeReceipt()]
        extractor = FakeExtractor()
        run_async_worker(extractor=extractor)
        assert len(extractor.calls) == 3

    def test_no_pages_is_reported_not_raised(self, stub_worker_common):
        stub_worker_common['state']['pages'] = []
        result = run_async_worker()
        assert result.success is False
        assert result.error == 'Unable to process image'

    def test_persist_returning_none_is_a_failure(self, stub_worker_common):
        stub_worker_common['state']['receipt_id'] = None
        result = run_async_worker()
        assert result.success is False
        assert result.error == 'Failed to save to database'

    def test_loader_exception_is_caught(self, stub_worker_common):
        stub_worker_common['state']['load_error'] = OSError('bad file')
        result = run_async_worker()
        assert result.success is False
        assert 'bad file' in result.error

    def test_extractor_exception_is_caught(self, stub_worker_common):
        result = run_async_worker(extractor=FakeExtractor(
            exc=RuntimeError('gemini 500')))
        assert result.success is False
        assert 'gemini 500' in result.error

    def test_persist_exception_is_caught(self, stub_worker_common):
        stub_worker_common['state']['persist_error'] = RuntimeError('disk full')
        result = run_async_worker()
        assert result.success is False
        assert 'disk full' in result.error

    def test_both_workers_agree_on_the_payload(self, stub_sync_deps):
        """The two paths feed the same frontend, so their data must match."""
        sync_result = receipt_worker(sync_args())
        async_result = run_async_worker()
        assert sync_result.data.keys() == async_result.data.keys()
        assert sync_result.data['receipt_status'] == \
            async_result.data['receipt_status']


# --------------------------------------------------------------------------- #
# ReceiptStreamProcessor
# --------------------------------------------------------------------------- #
class RecordingProcessor:
    """Stands in for ParallelStreamProcessor."""

    def __init__(self):
        self.process_calls = []

    def process(self, tasks, extra_worker_args=()):
        self.process_calls.append((list(tasks), extra_worker_args))
        yield 'event-1'
        yield 'event-2'


@pytest.fixture
def stream_processor(tmp_path):
    processor = ReceiptStreamProcessor(
        upload_folder=tmp_path, allowed_extensions={'jpg', 'png'},
        ocr_method='tesseract', max_workers=2,
    )
    processor._processor = RecordingProcessor()
    return processor


class TestReceiptStreamProcessor:

    def test_configures_the_parallel_processor(self, tmp_path):
        processor = ReceiptStreamProcessor(
            upload_folder=tmp_path, allowed_extensions={'jpg'},
            ocr_method='paddle', max_workers=3,
        )
        assert processor._processor.worker_function is receipt_worker
        assert processor._processor.max_workers == 3
        assert processor._processor.ocr_method == 'paddle'

    def test_defaults_to_tesseract(self, tmp_path):
        processor = ReceiptStreamProcessor(tmp_path, {'jpg'})
        assert processor.ocr_method == 'tesseract'

    def test_builds_one_task_per_file_in_order(self, stream_processor):
        list(stream_processor.process_files([
            ('a.jpg', '/tmp/a'), ('b.jpg', '/tmp/b'),
        ]))
        tasks, _ = stream_processor._processor.process_calls[0]
        assert [(t.index, t.identifier, t.data) for t in tasks] == [
            (0, 'a.jpg', '/tmp/a'), (1, 'b.jpg', '/tmp/b'),
        ]

    def test_passes_upload_folder_and_extensions_as_extra_args(
        self, stream_processor, tmp_path
    ):
        list(stream_processor.process_files([('a.jpg', '/tmp/a')]))
        _, extra = stream_processor._processor.process_calls[0]
        assert extra == (str(tmp_path), {'jpg', 'png'})

    def test_yields_the_underlying_events_unchanged(self, stream_processor):
        events = list(stream_processor.process_files([('a.jpg', '/tmp/a')]))
        assert events == ['event-1', 'event-2']

    def test_empty_file_list(self, stream_processor):
        list(stream_processor.process_files([]))
        tasks, _ = stream_processor._processor.process_calls[0]
        assert tasks == []

    def test_form_data_is_accepted_and_ignored(self, stream_processor):
        events = list(stream_processor.process_files(
            [('a.jpg', '/tmp/a')], form_data={'vendor': 'Tesco'}
        ))
        assert events == ['event-1', 'event-2']

    def test_is_lazy(self, stream_processor):
        stream_processor.process_files([('a.jpg', '/tmp/a')])
        assert stream_processor._processor.process_calls == []