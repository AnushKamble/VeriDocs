"""
FastAPI route handlers for benchmark dataset inspection and evaluation execution.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from veridocs.schemas.benchmark_models import BenchmarkCase, BenchmarkManifest

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])
BENCHMARK_DIR = Path(__file__).resolve().parents[4] / "benchmarks"


class EvaluationRunRequest(BaseModel):
    split: str = "dev"  # "dev" or "test"
    top_k: int = 5
    retriever_mode: str = "hybrid_rrf"


@router.get("/benchmark")
async def get_benchmark_manifest() -> Dict[str, Any]:
    """Retrieve benchmark metadata, splits, and question distribution."""
    manifest_file = BENCHMARK_DIR / "manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Benchmark manifest not found.")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    splits_file = BENCHMARK_DIR / "splits.json"
    splits_data = {}
    if splits_file.exists():
        with open(splits_file, "r", encoding="utf-8") as f:
            splits_data = json.load(f)

    return {
        "manifest": manifest_data,
        "splits": splits_data,
    }


@router.get("/benchmark/questions")
async def list_benchmark_questions(split: Optional[str] = None) -> List[Dict[str, Any]]:
    """List benchmark questions, optionally filtered by split."""
    questions_file = BENCHMARK_DIR / "questions.jsonl"
    splits_file = BENCHMARK_DIR / "splits.json"
    if not questions_file.exists():
        raise HTTPException(status_code=404, detail="Benchmark questions file not found.")

    allowed_ids = None
    if split and splits_file.exists():
        with open(splits_file, "r", encoding="utf-8") as f:
            splits = json.load(f)
            allowed_ids = set(splits.get(split, []))

    cases = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = BenchmarkCase.model_validate_json(line)
            if allowed_ids is None or case.question_id in allowed_ids:
                cases.append(case.model_dump())

    return cases


@router.get("/results")
async def get_evaluation_results() -> Dict[str, Any]:
    """Retrieve the latest evaluation metrics report if available."""
    report_file = BENCHMARK_DIR / "evaluation_report.json"
    if not report_file.exists():
        return {
            "status": "no_runs_yet",
            "message": "No evaluation runs have been recorded yet.",
        }

    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)
