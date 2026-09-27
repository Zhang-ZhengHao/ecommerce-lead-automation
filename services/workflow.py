"""Row-level review workflow operations for processed result frames."""

from __future__ import annotations

from numbers import Integral

import pandas as pd

from services.classifier import (
    FINAL_COLUMNS,
    result_column_name,
)
from services.reply_profile import ReplyProfile, check_reply_safety, default_reply_profile, profile_signature
from services.funnel import (
    DEFAULT_FUNNEL_STAGE,
    FUNNEL_COLUMN,
    FUNNEL_STAGES,
    is_valid_funnel_stage,
    normalize_funnel_stage,
)


class ReplyEditError(ValueError):
    """Raised when a final reply edit cannot be accepted."""


def update_funnel_stage(
    frame: pd.DataFrame,
    row_id: int,
    stage: str,
) -> pd.DataFrame:
    """Update the session-only funnel stage for one result row."""

    result = _copy(frame)
    _row(result, row_id)
    if not is_valid_funnel_stage(stage):
        raise ReplyEditError(
            f"线索阶段只能选择：{'、'.join(FUNNEL_STAGES)}。"
        )
    stage_column = result_column_name(result, FUNNEL_COLUMN)
    if stage_column not in result.columns:
        stage_column = FUNNEL_COLUMN
        result[stage_column] = DEFAULT_FUNNEL_STAGE
        mapping = dict(result.attrs.get("commerce_lead_result_columns", {}))
        mapping[FUNNEL_COLUMN] = stage_column
        result.attrs["commerce_lead_result_columns"] = mapping
    result.at[int(row_id), stage_column] = normalize_funnel_stage(stage)
    return result


def _copy(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.attrs = dict(frame.attrs)
    return result


def _row(frame: pd.DataFrame, row_id: int) -> pd.Series:
    if isinstance(row_id, bool) or not isinstance(row_id, Integral):
        raise ReplyEditError("行号必须是整数。")
    row_id = int(row_id)
    if row_id not in frame.index:
        raise ReplyEditError(f"找不到第 {row_id + 1} 行。")
    matches = frame.loc[[row_id]]
    if len(matches) != 1:
        raise ReplyEditError("行号不唯一，无法编辑。")
    return matches.iloc[0]


def _final_columns(frame: pd.DataFrame) -> tuple[str, str]:
    reply_column = result_column_name(frame, FINAL_COLUMNS[0])
    status_column = result_column_name(frame, FINAL_COLUMNS[1])
    if reply_column not in frame.columns or status_column not in frame.columns:
        raise ReplyEditError("结果中缺少最终回复字段。")
    return reply_column, status_column


def _active_profile(profile: ReplyProfile | None) -> ReplyProfile:
    return default_reply_profile() if profile is None else profile


def _text(value: object) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value)


def update_final_reply(
    frame: pd.DataFrame,
    row_id: int,
    text: str,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Validate and confirm a manually edited final reply."""

    result = _copy(frame)
    _row(result, row_id)
    reply_column, status_column = _final_columns(result)
    if not isinstance(text, str) or not text.strip():
        raise ReplyEditError("最终回复不能为空。")
    cleaned = text.strip()
    if len(cleaned) > 2000:
        raise ReplyEditError("最终回复最多 2000 个字符，请删减后重试。")
    safety = check_reply_safety(cleaned, _active_profile(profile))
    if not safety.safe:
        raise ReplyEditError(f"最终回复未通过安全检查：{safety.reason}。")
    result.at[int(row_id), reply_column] = cleaned
    result.at[int(row_id), status_column] = "已确认"
    return result


def restore_draft(
    frame: pd.DataFrame,
    row_id: int,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Copy an AI draft into an empty final editor without confirming it."""

    result = _copy(frame)
    row = _row(result, row_id)
    reply_column, status_column = _final_columns(result)
    existing_final = _text(row.get(reply_column, "")).strip()
    if existing_final:
        raise ReplyEditError("最终回复已有内容，请先清空后再采用 AI 草稿。")
    draft_column = result_column_name(result, "客户回复")
    draft = "" if draft_column not in result.columns else _text(row.get(draft_column, "")).strip()
    safety = check_reply_safety(draft, _active_profile(profile))
    if draft and safety.safe:
        result.at[int(row_id), reply_column] = draft
        result.at[int(row_id), status_column] = "待确认"
    else:
        result.at[int(row_id), reply_column] = ""
        result.at[int(row_id), status_column] = "待复核"
    return result


def clear_final_reply(
    frame: pd.DataFrame,
    row_id: int,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Explicitly clear the final editor so a draft can be adopted again."""

    result = _copy(frame)
    row = _row(result, row_id)
    reply_column, status_column = _final_columns(result)
    draft_column = result_column_name(result, "客户回复")
    draft = "" if draft_column not in result.columns else _text(row.get(draft_column, "")).strip()
    safety = check_reply_safety(draft, _active_profile(profile))
    result.at[int(row_id), reply_column] = ""
    result.at[int(row_id), status_column] = "待确认" if draft and safety.safe else "待复核"
    return result


def preserve_confirmed_replies(
    fresh: pd.DataFrame,
    previous: pd.DataFrame,
    *,
    text_column: str,
    previous_text_column: str | None,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Carry over only safe, confirmed replies for unchanged source rows."""

    result = _copy(fresh)
    if text_column not in result.columns:
        return result
    old_text_column = previous_text_column or text_column
    if old_text_column not in previous.columns:
        return result
    try:
        final_column, reply_status_column = _final_columns(result)
        old_final_column = result_column_name(previous, FINAL_COLUMNS[0])
        old_reply_status_column = result_column_name(previous, FINAL_COLUMNS[1])
    except ReplyEditError:
        return result
    if old_final_column not in previous.columns or old_reply_status_column not in previous.columns:
        return result

    active_profile = _active_profile(profile)
    stage_column = result_column_name(result, FUNNEL_COLUMN)
    old_stage_column = result_column_name(previous, FUNNEL_COLUMN)
    for row_id in result.index:
        if row_id not in previous.index:
            continue
        old_rows = previous.loc[[row_id]]
        if len(old_rows) != 1:
            continue
        old = old_rows.iloc[0]
        if _text(result.at[row_id, text_column]) != _text(old.get(old_text_column, "")):
            continue
        if stage_column in result.columns and old_stage_column in previous.columns:
            old_stage = old.get(old_stage_column, DEFAULT_FUNNEL_STAGE)
            result.at[row_id, stage_column] = normalize_funnel_stage(old_stage)
        draft = _text(old.get(old_final_column, "")).strip()
        if _text(old.get(old_reply_status_column, "")) != "已确认" or not draft:
            continue
        if not check_reply_safety(draft, active_profile).safe:
            continue
        result.at[row_id, final_column] = draft
        result.at[row_id, reply_status_column] = "已确认"
    return result


def row_label(frame: pd.DataFrame, row_id: int, *, text_column: str) -> str:
    """Build a compact, non-sensitive label for a row in review controls."""

    row = _row(frame, row_id)
    intent_column = result_column_name(frame, "意向等级")
    status_column = result_column_name(frame, "处理状态")
    intent = _text(row.get(intent_column, ""))
    status = _text(row.get(status_column, ""))
    summary = _text(row.get(text_column, "")).strip().replace("\n", " ")
    if len(summary) > 60:
        summary = summary[:60] + "…"
    return f"第 {int(row_id) + 1} 行 · 意向 {intent or '未标注'} · 状态 {status or '未处理'} · 留言：{summary}"
