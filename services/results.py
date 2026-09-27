from __future__ import annotations

import pandas as pd

from services.classifier import result_column_name
from services.reply_profile import (
    ReplyProfile,
    check_reply_safety,
    default_reply_profile,
)
from services.funnel import FUNNEL_STAGES


INTENT_FILTERS = ("全部", "高", "中", "低")
STATUS_FILTERS = ("全部", "成功", "待复核")
SORT_OPTIONS = ("原始顺序", "高意向优先", "待复核优先")
FUNNEL_FILTERS = ("全部", *FUNNEL_STAGES)


def review_row_mask(
    frame: pd.DataFrame,
    profile: ReplyProfile | None = None,
) -> pd.Series:
    """Return the single canonical mask for rows requiring manual review."""

    status_column = result_column_name(frame, "处理状态")
    if status_column not in frame.columns:
        return pd.Series(True, index=frame.index, dtype=bool)
    mask = frame[status_column].astype("string").fillna("").ne("成功")
    reply_status_column = result_column_name(frame, "回复状态")
    if reply_status_column in frame.columns:
        mask |= frame[reply_status_column].astype("string").fillna("").eq("待复核")
    # A stale or externally edited final reply must not bypass review merely
    # because its status still says ``已确认``.  The final track is the source
    # of truth for sending; drafts are intentionally not checked here.
    mask |= unsafe_final_reply_mask(frame, profile=profile)
    return mask.astype(bool)


def unsafe_final_reply_mask(
    frame: pd.DataFrame,
    profile: ReplyProfile | None = None,
) -> pd.Series:
    """Return rows whose non-empty final reply fails the current safety rules."""

    final_column = result_column_name(frame, "最终回复")
    if final_column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    active = default_reply_profile() if profile is None else profile
    values = frame[final_column].tolist()
    unsafe: list[bool] = []
    for value in values:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            unsafe.append(False)
            continue
        text = str(value).strip()
        unsafe.append(bool(text) and not check_reply_safety(text, active).safe)
    return pd.Series(unsafe, index=frame.index, dtype=bool)


def sendable_row_mask(
    frame: pd.DataFrame,
    profile: ReplyProfile | None = None,
) -> pd.Series:
    """Return rows that are safe and explicitly confirmed for external sending."""

    processing_column = result_column_name(frame, "处理状态")
    final_column = result_column_name(frame, "最终回复")
    reply_status_column = result_column_name(frame, "回复状态")
    required = (processing_column, final_column, reply_status_column)
    if any(column not in frame.columns for column in required):
        return pd.Series(False, index=frame.index, dtype=bool)

    active = default_reply_profile() if profile is None else profile
    mask = (
        frame[processing_column].astype("string").fillna("").eq("成功")
        & frame[reply_status_column].astype("string").fillna("").eq("已确认")
    )
    safe: list[bool] = []
    for value in frame[final_column].tolist():
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            safe.append(False)
            continue
        text = str(value).strip()
        safe.append(bool(text) and check_reply_safety(text, active).safe)
    return (mask & pd.Series(safe, index=frame.index, dtype=bool)).astype(bool)


def filter_and_sort_results(
    frame: pd.DataFrame,
    *,
    intent: str = "全部",
    status: str = "全部",
    sort: str = "原始顺序",
    funnel_stage: str = "全部",
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Filter and stably sort processed rows for the result view."""

    if intent not in INTENT_FILTERS:
        raise ValueError(f"不支持的意向筛选：{intent}")
    if status not in STATUS_FILTERS:
        raise ValueError(f"不支持的状态筛选：{status}")
    if sort not in SORT_OPTIONS:
        raise ValueError(f"不支持的排序方式：{sort}")
    if funnel_stage not in FUNNEL_FILTERS:
        raise ValueError(f"不支持的线索阶段筛选：{funnel_stage}")

    source = frame.copy()
    source.attrs = dict(frame.attrs)
    intent_column = result_column_name(source, "意向等级")
    status_column = result_column_name(source, "处理状态")
    mask = pd.Series(True, index=source.index)
    if funnel_stage != "全部":
        funnel_column = result_column_name(source, "线索阶段")
        if funnel_column not in source.columns:
            mask &= False
        else:
            mask &= source[funnel_column].astype("string").fillna("").eq(funnel_stage)
    if intent != "全部":
        mask &= source[intent_column].eq(intent)
    review = review_row_mask(source, profile=profile)
    if status == "成功":
        mask &= ~review
    elif status == "待复核":
        mask &= review

    result = source.loc[mask].copy()
    result.attrs = dict(source.attrs)

    if sort == "高意向优先":
        rank = result[intent_column].map({"高": 0, "中": 1, "低": 2}).fillna(3)
        result = (
            result.assign(_commerce_lead_sort_rank=rank)
            .sort_values("_commerce_lead_sort_rank", kind="stable")
            .drop(columns="_commerce_lead_sort_rank")
        )
    elif sort == "待复核优先":
        rank = review_row_mask(result, profile=profile).astype(int).rsub(1)
        result = (
            result.assign(_commerce_lead_sort_rank=rank)
            .sort_values("_commerce_lead_sort_rank", kind="stable")
            .drop(columns="_commerce_lead_sort_rank")
        )

    result.attrs = dict(source.attrs)
    return result
