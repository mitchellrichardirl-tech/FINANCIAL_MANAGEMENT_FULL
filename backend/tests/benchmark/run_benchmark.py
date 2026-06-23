"""
Entry point: A/B the legacy and new extraction pipelines.

Usage:
    python -m tests.benchmark.run_benchmark \
        --receipts data/benchmark/images \
        --truth data/benchmark/ground_truth.json \
        [--dump-text] [--dump-dir benchmark_dumps]
"""

import argparse
from pathlib import Path

from src.receipts.extractors.ocr_regex_extractor import OCRRegexExtractor
from src.receipts.engines.paddle_engine import PaddleEngine
from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.receipts.base import ReceiptExtractorBase
from tests.benchmark.harness import BenchmarkHarness

from src.utils.logging import ContextLogger


class PaddleRegexExtractor(ReceiptExtractorBase):
    """Diagnostic pipeline: new OCR, old parsing — isolates OCR vs parse gains."""
    def __init__(self):
        super().__init__(PaddleEngine(use_gpu=True), RegexFieldExtractor())

    def _select_variants(self, receipt):
        return list((receipt.processed_images or {}).keys())


def main():
    ContextLogger.setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipts", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument(
        "--dump-text", action="store_true",
        help="Write each pipeline's raw OCR text per receipt to disk "
             "for manual inspection of failure cases.",
    )
    ap.add_argument(
        "--dump-dir", type=Path, default=None,
        help="Directory to write dumped OCR text into "
             "(only used with --dump-text). Defaults to ./benchmark_dumps",
    )
    args = ap.parse_args()

    harness = BenchmarkHarness(
        args.receipts, args.truth,
        dump_text=args.dump_text, dump_dir=args.dump_dir,
    )

    # OCR-focused comparison: same field extractor (regex) held constant,
    # OCR engine varied. LLM pipeline deliberately excluded for now.
    pipelines = [
        OCRRegexExtractor(),     # baseline (Tesseract + regex)
        PaddleRegexExtractor(),  # isolates OCR engine change
    ]

    reports = harness.run(pipelines)

    print("\n========== LEADERBOARD (overall field accuracy) ==========")
    for r in sorted(
        reports,
        key=lambda x: x.vendor.accuracy + x.amount.accuracy + x.date.accuracy,
        reverse=True,
    ):
        overall = (r.vendor.accuracy + r.amount.accuracy + r.date.accuracy) / 3
        print(f"  {r.pipeline:20s} overall={overall:6.1%} "
              f"avg={r.total_seconds / max(r.n_receipts, 1):.2f}s")

    if args.dump_text:
        dump_dir = args.dump_dir or Path("benchmark_dumps")
        print(f"\nRaw OCR text dumped to: {dump_dir.resolve()}")


if __name__ == "__main__":
    main()