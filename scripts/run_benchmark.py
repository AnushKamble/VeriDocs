"""
CLI benchmark evaluation runner for VeriDocs.
Executes retrieval baselines, structured generation, numeric verification, and NLI audits,
exporting raw execution traces, aggregate metrics, and markdown reports.
"""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from veridocs.api.dependencies import (
    get_catalog,
    get_nli_auditor,
    get_numeric_comparator,
    get_policy_engine,
    get_retrieval_pipeline,
    get_structured_answerer,
)
from veridocs.evaluation.report_generator import ReportGenerator
from veridocs.evaluation.runner import BaselineType, BenchmarkRunner


def parse_args():
    parser = argparse.ArgumentParser(description="Run VeriDocs IR & Audit Benchmark Evaluation")
    parser.add_argument(
        "--split",
        type=str,
        default="dev",
        choices=["dev", "test", "all"],
        help="Benchmark split to evaluate (default: dev)",
    )
    parser.add_argument(
        "--baselines",
        type=str,
        default="bm25_structured,dense_bge,hybrid_rrf,hybrid_reranked,full_system",
        help="Comma-separated list of baselines to evaluate (or 'all')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of questions to evaluate",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k retrieval candidate limit (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmarks",
        help="Directory to save evaluation artifacts (default: benchmarks)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"=== Starting VeriDocs Benchmark Evaluation ===")
    print(f"Split: {args.split} | Top-k: {args.top_k} | Limit: {args.limit}")

    # 1. Resolve Baselines
    if args.baselines.strip().lower() == "all":
        baselines = [
            BaselineType.BM25_STRUCTURED,
            BaselineType.DENSE_BGE,
            BaselineType.HYBRID_RRF,
            BaselineType.RERANKED,
            BaselineType.FULL_SYSTEM,
            BaselineType.AUDIT_NO_NLI,
        ]
    else:
        baselines = []
        for name in args.baselines.split(","):
            name = name.strip()
            if name:
                baselines.append(BaselineType(name))

    print(f"Selected Baselines: {[b.value for b in baselines]}")

    # 2. Initialize Components
    print("Initializing retrieval and audit components...")
    t0 = time.perf_counter()
    catalog = get_catalog()
    pipeline = get_retrieval_pipeline()
    answerer = get_structured_answerer()
    numeric_comp = get_numeric_comparator()
    nli_auditor = get_nli_auditor()
    policy = get_policy_engine()
    print(f"Components initialized in {time.perf_counter() - t0:.2f}s")

    # 3. Execute Runner
    runner = BenchmarkRunner(
        retrieval_pipeline=pipeline,
        answerer=answerer,
        numeric_comparator=numeric_comp,
        nli_auditor=nli_auditor,
        policy_engine=policy,
        questions_path="benchmarks/questions.jsonl",
        splits_path="benchmarks/splits.json",
    )

    print(f"Evaluating {args.split} split...")
    results = runner.run_benchmark(
        split=args.split,
        baselines=baselines,
        limit=args.limit,
        top_k=args.top_k,
    )
    print(f"Evaluation complete. Questions evaluated: {results['total_questions']}")

    # 4. Generate Reports
    rep_gen = ReportGenerator(output_dir=args.output_dir)
    paths = rep_gen.generate_all(results)

    print("\n=== Evaluation Results Summary ===")
    for b_name, metrics in results["metrics_summary"].items():
        print(f"\n--- Baseline: {b_name} ---")
        print(f"  Recall@1: {metrics['recall_at_1']:.4f} | Recall@5: {metrics['recall_at_5']:.4f}")
        print(f"  MRR: {metrics['mrr']:.4f} | nDCG@5: {metrics['ndcg_at_5']:.4f}")
        print(f"  Numeric Exactness: {metrics['numeric_exactness']:.4f}")
        print(f"  Citation Precision: {metrics['citation_precision']:.4f}")
        print(f"  Abstention Accuracy: {metrics['abstention_accuracy']:.4f}")
        print(f"  Mean Latency: {metrics['mean_latency_ms']:.1f}ms")

    print("\n=== Generated Artifacts ===")
    for k, p in paths.items():
        print(f"  {k.capitalize()}: {p}")


if __name__ == "__main__":
    main()
