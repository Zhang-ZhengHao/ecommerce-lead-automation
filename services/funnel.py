"""Session-only lead funnel metadata used by the customer-facing workflow."""

from __future__ import annotations

FUNNEL_COLUMN = "线索阶段"
FUNNEL_STAGES: tuple[str, ...] = ("新线索", "已联系", "待补信息", "已转交")
DEFAULT_FUNNEL_STAGE = FUNNEL_STAGES[0]


def is_valid_funnel_stage(value: object) -> bool:
    if value is None:
        return False
    try:
        # Treat pandas' missing values as invalid without importing pandas in
        # this small, reusable module.
        if bool(value != value):
            return False
    except (TypeError, ValueError):
        return False
    return str(value).strip() in FUNNEL_STAGES


def normalize_funnel_stage(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text if text in FUNNEL_STAGES else DEFAULT_FUNNEL_STAGE


normalise_funnel_stage = normalize_funnel_stage


def funnel_stage_is_invalid(value: object) -> bool:
    """Return whether an imported stage needs manual review."""

    return not is_valid_funnel_stage(value)
