from __future__ import annotations

from pathlib import Path

import yaml

from src.engine.models import FieldConfig, MatchKey, ReconConfig


_USE_CASE_DIR = Path(__file__).parent.parent.parent / "config" / "use_cases"


def load_use_case(name: str) -> ReconConfig:
    """Load a pre-built use case config by filename stem (e.g. 'positions')."""
    path = _USE_CASE_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Use case config not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return _parse(raw)


def list_use_cases() -> list[str]:
    return [p.stem for p in sorted(_USE_CASE_DIR.glob("*.yaml"))]


def from_dict(raw: dict) -> ReconConfig:
    return _parse(raw)


def _parse(raw: dict) -> ReconConfig:
    keys = [
        MatchKey(
            source_col=k["source_col"],
            target_col=k["target_col"],
            normalization=k.get("normalization", "none"),
        )
        for k in raw.get("matching_keys", [])
    ]
    fields = {
        name: FieldConfig(
            tolerance_type=cfg["tolerance_type"],
            tolerance_value=float(cfg["tolerance_value"]),
            weight=float(cfg.get("weight", 1.0)),
            is_regulatory=bool(cfg.get("is_regulatory", False)),
        )
        for name, cfg in raw.get("field_configs", {}).items()
    }
    return ReconConfig(
        matching_keys=keys,
        field_configs=fields,
        classification_mode=raw.get("classification_mode", "worst_field"),
        missing_row_severity=raw.get("missing_row_severity", "HIGH"),
        use_case_name=raw.get("name", "Custom"),
    )
