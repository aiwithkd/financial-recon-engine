from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd
import streamlit as st

from src.engine.models import ReconciliationReport, ReconConfig


Stage = Literal["upload", "configure", "results"]


@dataclass
class AppState:
    source_df: Optional[pd.DataFrame] = None
    target_df: Optional[pd.DataFrame] = None
    source_name: str = ""
    target_name: str = ""
    config: Optional[ReconConfig] = None
    report: Optional[ReconciliationReport] = None
    stage: Stage = "upload"
    error: str = ""
    warnings: list[str] = field(default_factory=list)


_KEY = "_recon_app_state"


def get() -> AppState:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = AppState()
    return st.session_state[_KEY]


def update(**kwargs) -> None:
    state = get()
    for k, v in kwargs.items():
        if hasattr(state, k):
            setattr(state, k, v)


def reset() -> None:
    st.session_state[_KEY] = AppState()
