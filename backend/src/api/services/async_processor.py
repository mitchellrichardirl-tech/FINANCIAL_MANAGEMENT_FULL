import asyncio
import queue
import threading

from typing import Optional

from flask import current_app

from src.receipts.extractor_factory import create_extractor

from src.api.services.receipt_processor import receipt_worker_async

from src.api.services.parallel_processor import ProcessingTask
from src.api.utils.stream_reporter import StreamEventReporter

from src.database.repositories.receipts import ReceiptRepository

class AsyncReceiptStreamProcessor:
    def __init__(self, upload_folder, allowed_extensions,
                 max_concurrency: Optional[int], extractor_config=None):
        self.upload_folder = upload_folder
        self.max_concurrency = (
            max_concurrency if max_concurrency
            else current_app.config.get("GEMINI_MAX_CONCURRENCY")
        )
        self.extractor_config = extractor_config or {}

    async def _aprocess(self, temp_files):
        tasks = [
          ProcessingTask(i, fn, tp) for i, (fn, tp) in enumerate(temp_files)
          ]
        reporter = StreamEventReporter(total=len(tasks))
        yield reporter.starting(workers=self.max_concurrency)
        extractor = create_extractor("multimodal", self.extractor_config)
        repository = ReceiptRepository()
        sem = asyncio.Semaphore(self.max_concurrency)
        async def bounded(task):
            async with sem:
                return await receipt_worker_async(
                  task,
                  self.upload_folder,
                  extractor,
                  repository
                  )
        futures = []
        for task in tasks:
            yield reporter.queued(task)        # same queue-time events as the mp path
            futures.append(asyncio.ensure_future(bounded(task)))
        for fut in asyncio.as_completed(futures):
            yield reporter.result(await fut)   # worker catches its own exceptions
        yield reporter.completed()

    def process_files(self, temp_files, form_data=None):
        q, SENTINEL = queue.Queue(), object()
        stop = threading.Event()
        async def runner():
            try:
                async for event in self._aprocess(temp_files):
                    if stop.is_set():
                        break
                    q.put(event)
            finally:
                q.put(SENTINEL)
        thread = threading.Thread(target=lambda: asyncio.run(runner()), daemon=True)
        thread.start()
        try:
            while True:
                item = q.get()
                if item is SENTINEL:
                    break
                yield item
            thread.join()
        except GeneratorExit:
            stop.set()   # in-flight awaits finish, no new results emitted
            raise