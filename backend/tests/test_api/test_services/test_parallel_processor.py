"""
Tests for src/api/services/parallel_processor.py.

`ParallelStreamProcessor.process()` is a generator that drives a real
`ProcessPoolExecutor`, so the worker functions here are module-level (they have
to be picklable) and deliberately trivial - the point is the event protocol and
the argument marshalling, not the work itself.

SSE payloads are parsed back out of the `data: {...}\\n\\n` wire format so the
assertions read against the JSON the frontend actually consumes.
"""
import json
import multiprocessing

import pytest

from src.api.models.processing import ProcessingResult, ProcessingTask
from src.api.services.parallel_processor import (
    ParallelStreamProcessor,
    get_optimal_workers,
)


# --------------------------------------------------------------------------- #
# Module-level workers (must be importable for pickling)
# --------------------------------------------------------------------------- #
def echo_worker(args):
    """Succeeds, echoing the args tuple it was handed."""
    index, identifier = args[0], args[1]
    return ProcessingResult(
        index=index,
        identifier=identifier,
        success=True,
        data={'received_args': [str(a) for a in args]},
    )


def failing_worker(args):
    """Returns a failure result - the worker caught its own error."""
    return ProcessingResult(
        index=args[0], identifier=args[1], success=False, error='worker said no'
    )


def crashing_worker(args):
    """Raises - the error escapes the worker entirely."""
    raise RuntimeError('worker exploded')


def mixed_worker(args):
    """Succeeds for even indexes, fails for odd ones."""
    index, identifier = args[0], args[1]
    if index % 2:
        return ProcessingResult(index=index, identifier=identifier,
                                success=False, error='odd index')
    return ProcessingResult(index=index, identifier=identifier,
                            success=True, data={})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse(event: str) -> dict:
    """Turn one SSE chunk back into the dict the client receives."""
    assert event.startswith('data: ') and event.endswith('\n\n')
    return json.loads(event[len('data: '):])


def statuses(events):
    return [parse(e)['status'] for e in events]


def tasks(count=2):
    return [
        ProcessingTask(index=i, identifier=f'file_{i}.jpg', data=f'/tmp/{i}')
        for i in range(count)
    ]


@pytest.fixture
def run():
    """Run a processor to exhaustion and return the parsed events."""
    def _run(worker=echo_worker, task_list=None, extra_worker_args=(), **kwargs):
        processor = ParallelStreamProcessor(worker, **kwargs)
        return list(processor.process(
            tasks() if task_list is None else task_list,
            extra_worker_args=extra_worker_args,
        ))
    return _run


# --------------------------------------------------------------------------- #
# get_optimal_workers
# --------------------------------------------------------------------------- #
class TestGetOptimalWorkers:

    def test_explicit_value_wins(self):
        assert get_optimal_workers(max_workers=7) == 7

    def test_explicit_value_ignores_the_cpu_limit(self):
        assert get_optimal_workers(max_workers=99, cpu_limit=2) == 99

    def test_defaults_to_cpu_count_capped_at_four(self):
        assert get_optimal_workers() == min(4, multiprocessing.cpu_count())

    def test_cpu_limit_is_configurable(self):
        assert get_optimal_workers(cpu_limit=1) == 1

    def test_never_exceeds_cpu_count(self):
        assert get_optimal_workers(cpu_limit=1000) == multiprocessing.cpu_count()

    def test_zero_is_treated_as_explicit(self):
        """0 is not None, so it is returned as-is, and ProcessPoolExecutor
        then rejects it at upload time. See backlog item 17."""
        assert get_optimal_workers(max_workers=0) == 0

    def test_zero_workers_blows_up_when_the_pool_is_built(self):
        processor = ParallelStreamProcessor(echo_worker, max_workers=0)
        stream = processor.process(tasks(1))
        with pytest.raises(ValueError, match='max_workers must be greater than 0'):
            list(stream)


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #
class TestConstruction:

    def test_resolves_worker_count_eagerly(self):
        assert ParallelStreamProcessor(echo_worker, max_workers=3).max_workers == 3

    def test_defaults_applied(self):
        processor = ParallelStreamProcessor(echo_worker)
        assert processor.max_workers == min(4, multiprocessing.cpu_count())
        assert processor.ocr_method == 'tesseract'

    def test_ocr_method_is_configurable(self):
        processor = ParallelStreamProcessor(echo_worker, ocr_method='paddle')
        assert processor.ocr_method == 'paddle'

    def test_worker_function_is_stored(self):
        assert ParallelStreamProcessor(echo_worker).worker_function is echo_worker


# --------------------------------------------------------------------------- #
# event protocol
# --------------------------------------------------------------------------- #
class TestEventProtocol:

    def test_event_sequence(self, run):
        events = run()
        assert statuses(events)[0] == 'starting'
        assert statuses(events)[1:3] == ['processing', 'processing']
        assert statuses(events)[-1] == 'completed'

    def test_one_queued_event_per_task(self, run):
        events = run(task_list=tasks(3))
        assert statuses(events).count('processing') == 3

    def test_one_result_event_per_task(self, run):
        events = run(task_list=tasks(3))
        assert statuses(events).count('success') == 3

    def test_starting_event_reports_totals_and_workers(self, run):
        event = parse(run(max_workers=2)[0])
        assert event['status'] == 'starting'
        assert event['total_files'] == 2
        assert event['workers'] == 2

    def test_queued_events_name_each_file(self, run):
        queued = [parse(e) for e in run() if parse(e)['status'] == 'processing']
        assert [q['filename'] for q in queued] == ['file_0.jpg', 'file_1.jpg']
        assert [q['file_index'] for q in queued] == [0, 1]
        assert all(q['message'] == 'Queued for processing...' for q in queued)

    def test_queued_events_precede_every_result(self, run):
        kinds = statuses(run(task_list=tasks(3)))
        assert kinds.index('success') > max(
            i for i, k in enumerate(kinds) if k == 'processing'
        )

    def test_completed_event_carries_the_tally(self, run):
        event = parse(run(worker=mixed_worker, task_list=tasks(4))[-1])
        assert event['status'] == 'completed'
        assert event['successes'] == 2
        assert event['errors'] == 2

    def test_progress_counts_up_to_the_total(self, run):
        results = [parse(e) for e in run(task_list=tasks(3))
                   if parse(e)['status'] in ('success', 'error')]
        assert sorted(r['progress']['current'] for r in results) == [1, 2, 3]
        assert all(r['progress']['total'] == 3 for r in results)

    def test_empty_task_list_still_brackets_the_stream(self, run):
        events = run(task_list=[])
        assert statuses(events) == ['starting', 'completed']
        assert parse(events[-1])['total_processed'] == 0

    def test_single_task(self, run):
        assert statuses(run(task_list=tasks(1))) == [
            'starting', 'processing', 'success', 'completed'
        ]

    def test_events_are_well_formed_sse(self, run):
        for event in run():
            assert event.startswith('data: ')
            assert event.endswith('\n\n')
            json.loads(event[6:])


# --------------------------------------------------------------------------- #
# worker argument marshalling
# --------------------------------------------------------------------------- #
class TestWorkerArgs:

    def test_args_tuple_shape(self, run):
        """(index, identifier, data, *extra, ocr_method) - worker_common and
        receipt_worker both unpack positionally, so the order is load-bearing."""
        events = run(
            task_list=tasks(1),
            extra_worker_args=('/uploads', 'EXTRA'),
            ocr_method='tesseract',
        )
        received = next(
            parse(e)['received_args'] for e in events
            if parse(e)['status'] == 'success'
        )
        assert received == ['0', 'file_0.jpg', '/tmp/0', '/uploads', 'EXTRA',
                            'tesseract']

    def test_ocr_method_is_always_last(self, run):
        events = run(task_list=tasks(1), extra_worker_args=('a', 'b', 'c'),
                     ocr_method='paddle')
        received = next(
            parse(e)['received_args'] for e in events
            if parse(e)['status'] == 'success'
        )
        assert received[-1] == 'paddle'

    def test_no_extra_args(self, run):
        events = run(task_list=tasks(1))
        received = next(
            parse(e)['received_args'] for e in events
            if parse(e)['status'] == 'success'
        )
        assert received == ['0', 'file_0.jpg', '/tmp/0', 'tesseract']

    def test_each_task_gets_its_own_args(self, run):
        events = run(task_list=tasks(3))
        received = [parse(e)['received_args'] for e in events
                    if parse(e)['status'] == 'success']
        assert sorted(r[1] for r in received) == [
            'file_0.jpg', 'file_1.jpg', 'file_2.jpg'
        ]


# --------------------------------------------------------------------------- #
# failure handling
# --------------------------------------------------------------------------- #
class TestFailures:

    def test_worker_returned_failure_becomes_an_error_event(self, run):
        events = run(worker=failing_worker, task_list=tasks(1))
        error = parse(events[-2])
        assert error['status'] == 'error'
        assert error['error'] == 'worker said no'
        assert error['filename'] == 'file_0.jpg'

    def test_worker_exception_becomes_an_error_event(self, run):
        events = run(worker=crashing_worker, task_list=tasks(1))
        error = parse(events[-2])
        assert error['status'] == 'error'
        assert 'worker exploded' in error['error']

    def test_worker_exception_does_not_kill_the_stream(self, run):
        events = run(worker=crashing_worker, task_list=tasks(2))
        assert statuses(events)[-1] == 'completed'
        assert parse(events[-1])['errors'] == 2

    def test_failures_and_successes_are_tallied_separately(self, run):
        event = parse(run(worker=mixed_worker, task_list=tasks(4))[-1])
        assert (event['successes'], event['errors']) == (2, 2)

    def test_one_failure_does_not_block_other_results(self, run):
        events = run(worker=mixed_worker, task_list=tasks(4))
        assert statuses(events).count('success') == 2
        assert statuses(events).count('error') == 2


# --------------------------------------------------------------------------- #
# laziness
# --------------------------------------------------------------------------- #
class TestGeneratorBehaviour:

    def test_nothing_runs_until_iterated(self):
        """process() is a generator, so building it must not submit work."""
        processor = ParallelStreamProcessor(crashing_worker, max_workers=1)
        processor.process(tasks(1))  # not consumed - must not raise

    def test_starting_event_is_yielded_before_work_is_submitted(self):
        processor = ParallelStreamProcessor(echo_worker, max_workers=1)
        stream = processor.process(tasks(2))
        assert parse(next(stream))['status'] == 'starting'
        stream.close()

    def test_partial_consumption_shuts_the_pool_down(self):
        """Abandoning the generator must not leave the executor hanging."""
        processor = ParallelStreamProcessor(echo_worker, max_workers=1)
        stream = processor.process(tasks(2))
        next(stream)
        next(stream)
        stream.close()