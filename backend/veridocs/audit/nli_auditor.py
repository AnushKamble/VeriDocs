"""
Natural Language Inference (NLI) Auditor.
Audits claim hypotheses against source filing premises using cross-encoder/nli-deberta-v3-small.
Applies softmax normalization and verified label mappings.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field
import torch
from sentence_transformers import CrossEncoder

from veridocs.utils.logging import get_logger

logger = get_logger("veridocs.audit.nli")


class NLIScores(BaseModel):
    entailment: float = Field(..., ge=0.0, le=1.0)
    contradiction: float = Field(..., ge=0.0, le=1.0)
    neutral: float = Field(..., ge=0.0, le=1.0)
    dominant_label: str
    premise_excerpt: str = ""
    hypothesis_text: str = ""


class NLIAuditor:
    """NLI audit engine evaluating premise -> hypothesis directional entailment."""

    _instance: Optional["NLIAuditor"] = None

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small", device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model_name = model_name
        logger.info(f"Loading NLI cross-encoder '{model_name}' on {device}...")
        self.model = CrossEncoder(model_name, max_length=512, device=device)

        # Inspect label mapping from model config
        config = getattr(self.model.model, "config", None)
        id2label = getattr(config, "id2label", None) if config else None

        # Standard DeBERTa NLI mapping fallback: 0: contradiction, 1: entailment, 2: neutral
        self.label_indices: Dict[str, int] = {"contradiction": 0, "entailment": 1, "neutral": 2}

        if id2label and isinstance(id2label, dict):
            for idx, lbl in id2label.items():
                lbl_clean = str(lbl).lower().strip()
                if "contra" in lbl_clean:
                    self.label_indices["contradiction"] = int(idx)
                elif "entail" in lbl_clean:
                    self.label_indices["entailment"] = int(idx)
                elif "neut" in lbl_clean:
                    self.label_indices["neutral"] = int(idx)

        logger.info(f"NLI label indices verified: {self.label_indices}")

    @classmethod
    def get_instance(cls, model_name: str = "cross-encoder/nli-deberta-v3-small") -> "NLIAuditor":
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    def audit_pair(self, premise: str, hypothesis: str) -> NLIScores:
        """
        Evaluate directional entailment: Does premise entail or contradict hypothesis?
        Premise MUST be first; Hypothesis MUST be second.
        """
        results = self.audit_batch([(premise, hypothesis)])
        return results[0]

    def audit_batch(self, pairs: List[Tuple[str, str]], batch_size: int = 16) -> List[NLIScores]:
        """
        Batch evaluate multiple (premise, hypothesis) pairs.
        """
        if not pairs:
            return []

        # Predict raw logits
        logits = self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # Ensure 2D array
        if len(pairs) == 1 and logits.ndim == 1:
            logits = np.expand_dims(logits, axis=0)

        # Apply softmax over logits
        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

        idx_c = self.label_indices["contradiction"]
        idx_e = self.label_indices["entailment"]
        idx_n = self.label_indices["neutral"]

        scores_list: List[NLIScores] = []
        for i, (premise, hyp) in enumerate(pairs):
            c_score = float(probs[i, idx_c])
            e_score = float(probs[i, idx_e])
            n_score = float(probs[i, idx_n])

            dominant = "neutral"
            max_prob = n_score
            if e_score > max_prob and e_score >= c_score:
                dominant = "entailment"
                max_prob = e_score
            elif c_score > max_prob:
                dominant = "contradiction"
                max_prob = c_score

            scores_list.append(
                NLIScores(
                    entailment=round(e_score, 4),
                    contradiction=round(c_score, 4),
                    neutral=round(n_score, 4),
                    dominant_label=dominant,
                    premise_excerpt=premise[:150],
                    hypothesis_text=hyp,
                )
            )

        return scores_list
