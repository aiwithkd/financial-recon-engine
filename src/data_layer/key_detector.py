from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.data_layer.schema_inferrer import infer_schema


_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_NUMERIC_NORM_RE = re.compile(r"[^a-z0-9_]")


@dataclass
class KeyCandidate:
    source_col: str
    target_col: str
    confidence: float          # 0-1
    reasons: list[str]


def detect_keys(
    source: pd.DataFrame,
    target: pd.DataFrame,
    top_n: int = 5,
) -> list[KeyCandidate]:
    """Score all (source_col, target_col) pairs and return top candidates."""
    src_profiles = infer_schema(source)
    tgt_profiles = infer_schema(target)

    src_cols = list(source.columns)
    tgt_cols = list(target.columns)

    # TF-IDF name similarity matrix
    name_sim = _name_similarity_matrix(src_cols, tgt_cols)

    candidates: list[KeyCandidate] = []

    for i, sc in enumerate(src_cols):
        for j, tc in enumerate(tgt_cols):
            score, reasons = _score_pair(
                sc, tc,
                source[sc], target[tc],
                src_profiles[sc], tgt_profiles[tc],
                name_sim[i, j],
            )
            if score > 0.25:
                candidates.append(KeyCandidate(sc, tc, round(score, 3), reasons))

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:top_n]


def _name_similarity_matrix(src_cols: list[str], tgt_cols: list[str]) -> np.ndarray:
    """TF-IDF + cosine similarity on tokenized column names."""
    all_cols = src_cols + tgt_cols
    # Tokenize camelCase / snake_case into words
    tokenized = [" ".join(re.split(r"[_\s]+|(?<=[a-z])(?=[A-Z])", c)).lower() for c in all_cols]
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        mat = vec.fit_transform(tokenized).toarray()
        sim = cosine_similarity(mat[: len(src_cols)], mat[len(src_cols):])
    except Exception:
        sim = np.zeros((len(src_cols), len(tgt_cols)))
    return sim


def _score_pair(
    sc: str, tc: str,
    sv: pd.Series, tv: pd.Series,
    sp, tp,
    name_sim: float,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    # 1. Name similarity (0-0.35)
    score += name_sim * 0.35
    if name_sim > 0.6:
        reasons.append(f"column names are similar ({name_sim:.0%})")

    # 2. Type compatibility (0 or 0.15)
    if sp.inferred_type == tp.inferred_type:
        score += 0.15
        reasons.append(f"same inferred type: {sp.inferred_type}")

    # 3. Uniqueness — both should be near-unique for a good join key
    avg_unique = (sp.uniqueness_ratio + tp.uniqueness_ratio) / 2
    score += avg_unique * 0.25
    if avg_unique > 0.8:
        reasons.append(f"high uniqueness ({avg_unique:.0%})")

    # 4. Value overlap — fraction of source values present in target
    sv_clean = sv.dropna().astype(str).str.strip().str.upper()
    tv_clean = tv.dropna().astype(str).str.strip().str.upper()
    if len(sv_clean) > 0 and len(tv_clean) > 0:
        overlap = len(set(sv_clean) & set(tv_clean)) / max(len(set(sv_clean)), 1)
        score += overlap * 0.20
        if overlap > 0.5:
            reasons.append(f"value overlap {overlap:.0%}")

    # 5. ISIN pattern bonus
    src_isin_rate = sv_clean.str.match(_ISIN_RE).mean()
    tgt_isin_rate = tv_clean.str.match(_ISIN_RE).mean()
    if src_isin_rate > 0.8 and tgt_isin_rate > 0.8:
        score += 0.05
        reasons.append("ISIN pattern detected")

    return min(score, 1.0), reasons
