"""
A/B benchmark harness for receipt-extraction pipelines.

Runs one or more ReceiptExtractorBase implementations over a folder of
receipts, compares results against ground truth, and reports per-field
accuracy plus timing. Pipelines are interchangeable thanks to the
shared abstract base class.
"""

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.receipts.base import ReceiptExtractorBase
from src.models.receipt import Receipt
from src.receipts.receipt_loader import ReceiptLoader
from tests.benchmark.ground_truth import GroundTruth, load_ground_truth
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def _vendor_match(pred: Optional[str], truth: Optional[str]) -> bool:
    """Lenient vendor comparison: case-insensitive substring either way."""
    if not pred or not truth:
        return pred is None and truth is None
    p, t = pred.lower().strip(), truth.lower().strip()
    return p in t or t in p


def _amount_match(pred: Optional[float], truth: Optional[float]) -> bool:
    if pred is None or truth is None:
        return pred is None and truth is None
    return abs(pred - truth) < 0.01


def _date_match(pred, truth) -> bool:
    if pred is None or truth is None:
        return pred is None and truth is None
    return pred.date() == truth.date()


def _safe_stem(name: str) -> str:
    """Turn a receipt filename into a filesystem-safe stem for dump files."""
    return Path(name).stem.replace(" ", "_")


def _extract_raw_text(pipeline: ReceiptExtractorBase, receipt: Receipt) -> Optional[str]:
    """Best-effort extraction of the raw OCR text associated with a receipt,
    after pipeline.process_receipt() has run.

    Tries several conventions so this works regardless of which pipeline
    implementation is in play:
      1. receipt.raw_text / receipt.ocr_text attribute set by the pipeline.
      2. pipeline.last_ocr_text (if the pipeline caches its most recent run).
      3. pipeline.ocr_engine.extract_text(receipt) re-run directly.
    """
    for attr in ("raw_text", "ocr_text"):
        text = getattr(receipt, attr, None)
        if text:
            return text

    text = getattr(pipeline, "last_ocr_text", None)
    if text:
        return text

    logger.error(
        f"[{pipeline.name}] last_ocr_text not cached — falling back to re-running "
        f"OCR for dump. This may not match the exact variant that was scored."
    )
    
    ocr_engine = getattr(pipeline, "ocr_engine", None)
    if ocr_engine is not None and hasattr(ocr_engine, "extract_text"):
        try:
            return ocr_engine.extract_text(receipt)
        except Exception as e:
            logger.warning(f"Could not re-run OCR engine for text dump: {e}")

    return None


@dataclass
class FieldScore:
    correct: int = 0
    total: int = 0

    def add(self, ok: bool):
        self.total += 1
        self.correct += int(ok)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class PipelineReport:
    pipeline: str
    vendor: FieldScore = field(default_factory=FieldScore)
    amount: FieldScore = field(default_factory=FieldScore)
    date: FieldScore = field(default_factory=FieldScore)
    total_seconds: float = 0.0
    n_receipts: int = 0
    errors: int = 0

    def summary(self) -> str:
        avg = self.total_seconds / self.n_receipts if self.n_receipts else 0
        return (
            f"\n=== {self.pipeline} ===\n"
            f"  receipts:     {self.n_receipts} ({self.errors} errors)\n"
            f"  vendor acc:   {self.vendor.accuracy:6.1%} "
            f"({self.vendor.correct}/{self.vendor.total})\n"
            f"  amount acc:   {self.amount.accuracy:6.1%} "
            f"({self.amount.correct}/{self.amount.total})\n"
            f"  date acc:     {self.date.accuracy:6.1%} "
            f"({self.date.correct}/{self.date.total})\n"
            f"  avg time:     {avg:6.2f}s/receipt "
            f"(total {self.total_seconds:.1f}s)\n"
        )


class BenchmarkHarness:
    """Runs and scores multiple extraction pipelines on the same data.

    Args:
        receipts_dir: Folder of receipt image/PDF files.
        ground_truth_path: JSON file of correct field values.
        loader: ReceiptLoader (so preprocessing is shared/consistent).
        dump_text: If True, write each pipeline's raw OCR text per receipt
            to `dump_dir` for manual inspection of failure cases.
        dump_dir: Directory to write dumped text into. Defaults to
            `benchmark_dumps/` under the current working directory.
    """

    def __init__(self, receipts_dir: Path, ground_truth_path: Path,
                 loader: Optional[ReceiptLoader] = None,
                 dump_text: bool = False,
                 dump_dir: Optional[Path] = None):
        self.receipts_dir = Path(receipts_dir)
        self.truth = load_ground_truth(ground_truth_path)
        self.loader = loader or ReceiptLoader()
        self.dump_text = dump_text
        self.dump_dir = Path(dump_dir) if dump_dir else Path("benchmark_dumps")
        if self.dump_text:
            self.dump_dir.mkdir(parents=True, exist_ok=True)

    def _load_receipts(self) -> List[Receipt]:
        """Preprocess every file once; reuse across all pipelines."""
        receipts = []
        for fname in self.truth:
            fpath = self.receipts_dir / fname
            logger.info(f"Loading benchmark receipt {fpath}")
            if not fpath.exists():
                logger.warning(f"Missing benchmark file: {fpath}")
                continue
            # page 0 only for benchmark simplicity
            pages = list(self.loader.process_file(fpath))
            if pages:
                pages[0]._benchmark_filename = fname  # tag for lookup
                receipts.append(pages[0])
        return receipts

    def _dump_text_for(self, pipeline: ReceiptExtractorBase, receipt: Receipt,
                        fname: str) -> None:
        text = _extract_raw_text(pipeline, receipt)
        if text is None:
            logger.warning(
                f"[{pipeline.name}] no raw OCR text available to dump for {fname}"
            )
            text = "<no raw text available>"

        pipeline_dir = self.dump_dir / pipeline.name
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        out_path = pipeline_dir / f"{_safe_stem(fname)}.txt"
        out_path.write_text(text, encoding="utf-8")

    def run(self, pipelines: List[ReceiptExtractorBase]) -> List[PipelineReport]:
        receipts = self._load_receipts()
        logger.info(f"Loaded {len(receipts)} receipts for benchmarking")

        reports = []
        for pipeline in pipelines:
            report = PipelineReport(pipeline=pipeline.name)
            for receipt in receipts:
                fname = receipt._benchmark_filename
                gt = self.truth[fname]
                logger.info(f"[{pipeline.name}] processing {fname} with ground truth {gt}")
                try:
                    start = time.perf_counter()
                    pipeline.process_receipt(receipt)
                    report.total_seconds += time.perf_counter() - start

                    if self.dump_text:
                        self._dump_text_for(pipeline, receipt, fname)

                    report.vendor.add(_vendor_match(receipt.vendor, gt.vendor))
                    report.amount.add(_amount_match(receipt.amount, gt.amount))
                    report.date.add(_date_match(receipt.date, gt.date))
                    report.n_receipts += 1
                except Exception as e:
                    report.errors += 1
                    logger.error(f"[{pipeline.name}] failed on {fname}: {e}")
            reports.append(report)
            print(report.summary())
        if self.dump_text:
            print(f"\nRaw OCR text dumped to: {self.dump_dir.resolve()}")
        return reports


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A/B benchmark harness for receipt-extraction pipelines."
    )
    parser.add_argument(
        "--receipts-dir", type=Path, required=True,
        help="Folder of receipt image/PDF files.",
    )
    parser.add_argument(
        "--ground-truth", type=Path, required=True,
        help="JSON file of correct field values.",
    )
    parser.add_argument(
        "--dump-text", action="store_true",
        help="Write each pipeline's raw OCR text per receipt to disk "
             "(default: benchmark_dumps/<pipeline_name>/<file_stem>.txt) "
             "for manual inspection of failure cases.",
    )
    parser.add_argument(
        "--dump-dir", type=Path, default=None,
        help="Directory to write dumped OCR text into "
             "(only used with --dump-text). Defaults to ./benchmark_dumps",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    harness = BenchmarkHarness(
        receipts_dir=args.receipts_dir,
        ground_truth_path=args.ground_truth,
        dump_text=args.dump_text,
        dump_dir=args.dump_dir,
    )

    # Wire up the pipelines to compare; import lazily so --help works
    # even if optional deps (paddle/ollama) aren't installed.
    from src.receipts.pipelines import (
        OCRRegexExtractor,
        OCRLLMExtractor,
        PaddleRegexExtractor,
    )

    pipelines = [
        OCRRegexExtractor(),
        PaddleRegexExtractor(),
        OCRLLMExtractor(),
    ]

    harness.run(pipelines)