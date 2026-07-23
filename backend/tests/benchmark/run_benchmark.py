"""
Entry point: A/B(/C) benchmark of receipt-extraction pipelines.

Usage:
    python -m tests.benchmark.run_benchmark \
        --receipts data/benchmark/images \
        --truth data/benchmark/ground_truth.json \
        [--dump-text] [--dump-dir benchmark_dumps] \
        [--sample-size 10] \
        [--llm] [--llm-model llama3.2] [--llm-gateway http://localhost:8000] \
        [--no-llm-fallback]
"""

import argparse
from pathlib import Path

from typing import Optional

import pandas as pd

from src.receipts.base import ReceiptExtractorBase
from src.receipts.engines.paddle_engine import PaddleEngine
from src.receipts.extractors.ocr_regex_extractor import OCRRegexExtractor
from src.receipts.field_extractors.llm_extractor import LLMFieldExtractor
from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.receipts.extractors.multimodal_extractor import MultimodalExtractor
from src.utils.logging import ContextLogger

from tests.benchmark.harness import BenchmarkHarness

ContextLogger.setup_logging(level='INFO')
logger = ContextLogger(__name__)


# ---------------------------------------------------------------------------
# Paddle-based pipelines share variant selection (try every preprocessed
# variant, keep the longest OCR text). OCR engine is injected so a single
# PaddleEngine instance can be reused across pipelines (model load is expensive).
# ---------------------------------------------------------------------------
class _PaddlePipeline(ReceiptExtractorBase):
    """Shared variant logic for all Paddle-based pipelines."""

    def _select_variants(self, receipt):
        return list((receipt.processed_images or {}).keys())


class PaddleRegexExtractor(_PaddlePipeline):
    """Paddle OCR + regex — isolates OCR engine change vs Tesseract baseline."""

    def __init__(self, ocr=None):
        super().__init__(ocr or PaddleEngine(use_gpu=True), RegexFieldExtractor())


class PaddleLLMExtractor(_PaddlePipeline):
    """Paddle OCR + LLM extraction — tests field-extractor ceiling."""
    def __init__(self, ocr=None, name: Optional[str] = None, **llm_kwargs):
        super().__init__(
            ocr or PaddleEngine(use_gpu=True),
            LLMFieldExtractor(**llm_kwargs),
        )
        if name:
            self.my_name = name

# ---------------------------------------------------------------------------
# LLM health reporting
# ---------------------------------------------------------------------------
def _print_llm_stats(pipelines):
    """Surface LLM call/failure ratio so a silently-all-regex run is visible."""
    for p in pipelines:
        extractor = getattr(p, "fields", None)
        calls = getattr(extractor, "llm_calls", 0)
        failures = getattr(extractor, "llm_failures", 0)
        if calls == 0:
            continue

        ratio = failures / calls
        marker = "✓" if ratio < 0.1 else "⚠" if ratio < 0.5 else "✗"
        print(
            f"  {marker} [{p.name}] LLM calls: {calls}, "
            f"failures: {failures} ({ratio:.0%})"
        )
        if ratio > 0.5:
            print(
                f"    └─ >50% failure rate — these results are mostly "
                f"regex backfill, not a real LLM test."
            )


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------
def main():
    ContextLogger.setup_logging(level='INFO')
    ap = argparse.ArgumentParser(
        description="A/B benchmark of receipt-extraction pipelines.",
    )
    ap.add_argument("--receipts", type=Path, default="../../../data/uploads")
    ap.add_argument("--truth", type=Path, default="ground_truth_better_amounts_dates.csv")
    ap.add_argument(
        "--dump-text",
        action="store_true",
        help="Write each pipeline's raw OCR text per receipt to disk.",
    )
    ap.add_argument(
        "--dump-dir",
        type=Path,
        default=None,
        help="Directory for dumped OCR text (default: ./benchmark_dumps).",
    )
    ap.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Randomly sample N receipts for a quicker run.",
    )

    llm_group = ap.add_argument_group("LLM pipeline")
    llm_group.add_argument(
        "--llm",
        action="store_true",
        help="Include the Paddle+LLM pipeline in the comparison.",
    )
    llm_group.add_argument(
        "--llm-model",
        type=str,
        nargs="+",
        default=["llama3.2"],
        help="One or more model names to test against the LLM gateway "
            "(default: llama3.2). Pass several to A/B models, e.g. "
            "--llm-model llama3.2 mistral qwen2.5:7b — each gets its own "
            "row in the report.",
    )
    llm_group.add_argument(
        "--llm-gateway",
        type=str,
        default="http://llm_gateway-api-1:8000",
        help="Base URL of the LLM gateway (default: http://llm_gateway-api-1:8000).",
    )
    llm_group.add_argument(
        "--no-llm-fallback",
        action="store_true",
        help="Disable regex backfill on LLM pipeline (measure LLM-alone).",
    )
    mm_group = ap.add_argument_group('MultiModal Pipeline')
    mm_group.add_argument(
        "--mm",
        action="store_true",
        help="Include the MultiModal pipeline in the comparison"
    )
    args = ap.parse_args()
    harness = BenchmarkHarness(
        args.receipts,
        args.truth,
        dump_text=args.dump_text,
        dump_dir=args.dump_dir,
        sample_size=args.sample_size,
    )

    # Shared Paddle engine — model loads once, reused by both Paddle pipelines.
    paddle = PaddleEngine(use_gpu=True)
    paddle.prime()
    pipelines: list[ReceiptExtractorBase] = [
        OCRRegexExtractor(),                # baseline: Tesseract + regex
        PaddleRegexExtractor(ocr=paddle),  # isolates OCR engine change
    ]

    if args.llm:
        seen = set()
        for model_name in args.llm_model:
            if model_name in seen:
                logger.warning(f"Skipping duplicate LLM model name: {model_name}")
                continue
            seen.add(model_name)
            pipelines.append(
                PaddleLLMExtractor(
                    ocr=paddle,
                    name=f"paddle+{model_name}",
                    base_url=args.llm_gateway,
                    model=model_name,
                    enable_fallback=not args.no_llm_fallback,
                    api_key="something-random",
                )
            )

    if args.mm:
        pipelines.append(MultimodalExtractor())

    reports, truth = harness.run(pipelines)

    # --- LLM health check (before leaderboard, so failures are visible) ---
    if args.llm:
        print("\n--- LLM call stats ---")
        _print_llm_stats(pipelines)

    # --- Leaderboard ---
    print("\n========== LEADERBOARD (overall field accuracy) ==========")
    for i, r in enumerate(sorted(
        reports,
        key=lambda x: x.vendor.accuracy + x.amount.accuracy + x.date.accuracy,
        reverse=True,
    )):
        if i == 0:
            best_detail = r.detail()
        overall = (r.vendor.accuracy + r.amount.accuracy + r.date.accuracy) / 3
        print(
            f"  {r.pipeline:20s} overall={overall:6.1%} "
            f"avg={r.total_seconds / max(r.n_receipts, 1):.2f}s"
        )
    best_detail['filename'] = list(truth.keys())
    for parameter in ['vendor', 'date', 'amount']:
        best_detail[f"true_{parameter}"] = [t.details[parameter] for t in truth.values()]

    print("\n========== BEST RESULT (results by receipt) ==========")
    print(pd.DataFrame.from_dict(best_detail))
    
if __name__ == "__main__":
    main()
