"""
Unit tests for ReportGenerator producing manifest, raw results, summary json, and markdown report.
"""

import json
from pathlib import Path
import tempfile
import pytest

from veridocs.evaluation.report_generator import ReportGenerator


def test_report_generator_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)
        manifest = gen.generate_manifest({"custom_key": "custom_val"})

        assert "environment" in manifest
        assert "models" in manifest
        assert "parameters" in manifest
        assert manifest["custom_key"] == "custom_val"

        p = gen.save_manifest(manifest)
        assert p.exists()
        with open(p, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded["custom_key"] == "custom_val"


def test_report_generator_all_artifacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(output_dir=tmpdir)

        dummy_results = {
            "split": "dev",
            "total_questions": 2,
            "metrics_summary": {
                "bm25_structured": {
                    "recall_at_1": 0.5,
                    "recall_at_3": 0.5,
                    "recall_at_5": 1.0,
                    "recall_at_10": 1.0,
                    "mrr": 0.75,
                    "ndcg_at_5": 0.82,
                    "numeric_exactness": 1.0,
                    "citation_precision": 1.0,
                    "abstention_accuracy": 1.0,
                    "mean_latency_ms": 15.2,
                    "confidence_intervals_95": {
                        "recall_at_5": [0.8, 1.0],
                        "mrr": [0.6, 0.9],
                    },
                },
                "full_system": {
                    "recall_at_1": 0.8,
                    "recall_at_3": 1.0,
                    "recall_at_5": 1.0,
                    "recall_at_10": 1.0,
                    "mrr": 0.9,
                    "ndcg_at_5": 0.95,
                    "numeric_exactness": 1.0,
                    "citation_precision": 1.0,
                    "abstention_accuracy": 1.0,
                    "mean_latency_ms": 120.0,
                    "confidence_intervals_95": {
                        "recall_at_5": [0.9, 1.0],
                    },
                },
            },
            "raw_results": {
                "bm25_structured": [
                    {
                        "question_id": "q01",
                        "baseline": "bm25_structured",
                        "recall_at_5": 1.0,
                        "mrr": 1.0,
                        "total_latency_ms": 15.0,
                    }
                ]
            },
        }

        artifacts = gen.generate_all(dummy_results)
        assert artifacts["manifest"].exists()
        assert artifacts["raw"].exists()
        assert artifacts["summary"].exists()
        assert artifacts["markdown"].exists()

        # Check markdown content
        with open(artifacts["markdown"], "r", encoding="utf-8") as f:
            md_text = f.read()
            assert "# VeriDocs Benchmark Evaluation Report" in md_text
            assert "bm25_structured" in md_text
            assert "full_system" in md_text
            assert "RQ1: Structure & Table-Aware Chunking" in md_text
            assert "RQ4: Numeric Consistency & Claim-Level Auditing" in md_text
