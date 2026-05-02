from __future__ import annotations

import pandas as pd

from src.data_layer.normalizer import normalize_column
from src.engine.models import MatchKey


def join(
    source: pd.DataFrame,
    target: pd.DataFrame,
    keys: list[MatchKey],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Three-pass matching strategy.
    Returns: (matched_df, source_only_df, target_only_df)
    matched_df has columns suffixed _src and _tgt for compared fields.
    """
    src = source.copy()
    tgt = target.copy()

    src_keys = [k.source_col for k in keys]
    tgt_keys = [k.target_col for k in keys]

    # Deduplicate on keys — keep first
    src = src.drop_duplicates(subset=src_keys)
    tgt = tgt.drop_duplicates(subset=tgt_keys)

    # Pass 1: exact join on raw key values
    matched, src_unmatched, tgt_unmatched = _exact_join(src, tgt, src_keys, tgt_keys)

    # Pass 2: fuzzy normalisation on unmatched residuals
    if not src_unmatched.empty or not tgt_unmatched.empty:
        matched2, src_unmatched, tgt_unmatched = _normalised_join(
            src_unmatched, tgt_unmatched, keys
        )
        matched = pd.concat([matched, matched2], ignore_index=True)

    return matched, src_unmatched, tgt_unmatched


def _exact_join(
    src: pd.DataFrame,
    tgt: pd.DataFrame,
    src_keys: list[str],
    tgt_keys: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Rename target keys to match source keys for the merge
    rename_map = {tk: sk for sk, tk in zip(src_keys, tgt_keys) if sk != tk}
    tgt_renamed = tgt.rename(columns=rename_map)
    tgt_non_key_cols = [c for c in tgt_renamed.columns if c not in src_keys]

    # Suffix non-key cols to avoid collisions
    src_suffixed = src.rename(columns={c: f"{c}_src" for c in src.columns if c not in src_keys})
    tgt_suffixed = tgt_renamed.rename(columns={c: f"{c}_tgt" for c in tgt_non_key_cols})

    merged = pd.merge(
        src_suffixed, tgt_suffixed,
        on=src_keys, how="outer", indicator=True
    )

    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge"]).reset_index(drop=True)
    src_only_keys = merged[merged["_merge"] == "left_only"][src_keys].reset_index(drop=True)
    tgt_only_keys = merged[merged["_merge"] == "right_only"][src_keys].reset_index(drop=True)

    # Recover full rows for unmatched
    src_unmatched = src.merge(src_only_keys, on=src_keys, how="inner").reset_index(drop=True)
    tgt_only_keys_orig = tgt_only_keys.rename(columns={sk: tk for sk, tk in zip(src_keys, tgt_keys)})
    tgt_unmatched = tgt.merge(tgt_only_keys_orig, on=tgt_keys, how="inner").reset_index(drop=True)

    return matched, src_unmatched, tgt_unmatched


def _normalised_join(
    src: pd.DataFrame,
    tgt: pd.DataFrame,
    keys: list[MatchKey],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    src_norm = src.copy()
    tgt_norm = tgt.copy()

    norm_src_keys = []
    norm_tgt_keys = []

    for k in keys:
        ns = f"__norm_{k.source_col}"
        nt = f"__norm_{k.target_col}"
        src_norm[ns] = normalize_column(src[k.source_col], k.normalization)
        tgt_norm[nt] = normalize_column(tgt[k.target_col], k.normalization)
        norm_src_keys.append(ns)
        norm_tgt_keys.append(nt)

    matched, src_unmatched, tgt_unmatched = _exact_join(
        src_norm, tgt_norm, norm_src_keys, norm_tgt_keys
    )

    # Drop normalisation helper columns
    drop_cols = [c for c in matched.columns if c.startswith("__norm_")]
    matched = matched.drop(columns=drop_cols, errors="ignore")

    # Recover original columns for unmatched
    drop_norm = [c for c in src_unmatched.columns if c.startswith("__norm_")]
    src_unmatched = src_unmatched.drop(columns=drop_norm, errors="ignore")
    drop_norm_t = [c for c in tgt_unmatched.columns if c.startswith("__norm_")]
    tgt_unmatched = tgt_unmatched.drop(columns=drop_norm_t, errors="ignore")

    return matched, src_unmatched, tgt_unmatched
