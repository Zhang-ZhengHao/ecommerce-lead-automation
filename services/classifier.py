from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

import pandas as pd

from services.reply import generate_demo_reply
from services.reply_profile import (
    ReplyProfile,
    check_reply_safety,
    default_reply_profile,
    profile_signature,
)
from services.funnel import (
    DEFAULT_FUNNEL_STAGE,
    FUNNEL_COLUMN,
    funnel_stage_is_invalid,
    normalize_funnel_stage,
)


RESULT_COLUMNS = [
    "意向等级",
    "客户类型",
    FUNNEL_COLUMN,
    "客户回复",
    "跟进动作",
    "处理状态",
    "判断依据",
]
FINAL_COLUMNS = ["最终回复", "回复状态"]
ALL_RESULT_COLUMNS = RESULT_COLUMNS + FINAL_COLUMNS
RESULT_COLUMN_MAP_ATTR = "commerce_lead_result_columns"
PROFILE_SIGNATURE_ATTR = "commerce_lead_profile_signature"
_COLLISION_RESULT_SUFFIX = re.compile(r"（AI(?:\d+)?）$")
Classifier = Callable[[str], dict[str, Any]]


def _result(level: str, category: str, reason: str, reply: dict[str, str]) -> dict[str, str]:
    return {
        "意向等级": level,
        "客户类型": category,
        FUNNEL_COLUMN: DEFAULT_FUNNEL_STAGE,
        "客户回复": reply["客户回复"],
        "跟进动作": reply["跟进动作"],
        "判断依据": reason,
    }


def result_column_map(frame: pd.DataFrame) -> dict[str, str]:
    """Return collision-safe output names without changing source columns."""

    used = {str(column) for column in frame.columns}
    mapping: dict[str, str] = {}
    for base_name in ALL_RESULT_COLUMNS:
        output_name = base_name
        if output_name in used:
            suffix = 2
            output_name = f"{base_name}（AI）"
            while output_name in used:
                output_name = f"{base_name}（AI{suffix}）"
                suffix += 1
        mapping[base_name] = output_name
        used.add(output_name)
    return mapping


def result_column_name(frame: pd.DataFrame, base_name: str) -> str:
    """Resolve a generated result field name, including collision suffixes."""

    mapping = frame.attrs.get(RESULT_COLUMN_MAP_ATTR, {})
    if isinstance(mapping, dict) and base_name in mapping:
        mapped = mapping[base_name]
        if mapped in frame.columns:
            return str(mapped)
    # ``DataFrame.attrs`` is metadata and can be dropped by callers or by
    # third-party transformations.  When that happens, prefer the collision
    # safe generated name over the original source column: a processed frame
    # can contain both ``意向等级`` (source) and ``意向等级（AI）`` (result).
    candidates = [
        column
        for column in frame.columns
        if str(column).startswith(base_name)
        and _COLLISION_RESULT_SUFFIX.search(str(column))
    ]
    if candidates:
        # Generated columns are appended after source columns by
        # ``process_dataframe``.  Choosing the last matching column is a
        # safer metadata-free fallback than lexicographic ordering (where
        # ``（AI10）`` sorts before ``（AI2）``).
        return str(candidates[-1])
    return base_name


def classify_demo(
    text: str, profile: ReplyProfile | None = None
) -> dict[str, str]:
    """Classify a message deterministically for offline demos."""

    content = str(text or "").strip()
    if not content:
        return {
            "意向等级": "",
            "客户类型": "",
            "客户回复": "",
            "跟进动作": "",
            "判断依据": "",
        }

    if any(word in content for word in ("代理", "合作", "加盟")):
        return _result(
            "高",
            "代理合作",
            "包含代理、合作或加盟关键词",
            generate_demo_reply(content, "高", "代理合作", profile),
        )
    if any(word in content for word in ("售后", "退款", "故障", "维修", "坏了", "无法", "不能")):
        return _result(
            "中",
            "售后",
            "包含售后服务关键词",
            generate_demo_reply(content, "中", "售后", profile),
        )
    if any(
        word in content
        for word in (
            "多少钱",
            "价格",
            "报价",
            "采购",
            "预算",
            "规格",
            "型号",
            "交期",
            "发货",
            "到货",
            "想买",
            "购买",
        )
    ):
        return _result(
            "高",
            "询价",
            "包含询价或采购关键词",
            generate_demo_reply(content, "高", "询价", profile),
        )
    if any(word in content for word in ("随便看看", "以后再说", "先了解", "看看")):
        return _result(
            "低",
            "普通咨询",
            "表达了浏览或暂不决策意向",
            generate_demo_reply(content, "低", "普通咨询", profile),
        )
    return _result(
        "中",
        "其他",
        "未命中明确关键词，建议人工复核",
        generate_demo_reply(content, "中", "其他", profile),
    )


def process_dataframe(
    frame: pd.DataFrame,
    text_column: str,
    classifier: Classifier,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    *,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Process every row while preserving input order and isolating failures."""

    if text_column not in frame.columns:
        raise KeyError(f"找不到列：{text_column}")

    # Excel/CSV inputs normally have a RangeIndex, but normalising here avoids
    # duplicate custom indexes causing ``.at[index, ...]`` to update multiple
    # rows at once. Exported files never include the pandas index.
    source = frame.reset_index(drop=True).copy()
    result = source.copy()
    output_columns = result_column_map(source)
    for column in output_columns.values():
        result[column] = ""
    result.attrs[RESULT_COLUMN_MAP_ATTR] = output_columns
    active_profile = default_reply_profile() if profile is None else profile
    result.attrs[PROFILE_SIGNATURE_ATTR] = profile_signature(active_profile)

    total = len(result)
    source_stage_column = FUNNEL_COLUMN if FUNNEL_COLUMN in source.columns else None
    success = 0
    failed = 0
    for position, value in enumerate(source[text_column].tolist(), start=1):
        index = position - 1
        text = "" if pd.isna(value) else str(value).strip()
        # A stage supplied by an imported sheet is user data, not a model
        # prediction.  Keep it in the generated result column so the original
        # column remains untouched, and route invalid values to review.
        imported_stage = (
            source.at[index, source_stage_column]
            if source_stage_column is not None
            else DEFAULT_FUNNEL_STAGE
        )
        stage_invalid = source_stage_column is not None and funnel_stage_is_invalid(
            imported_stage
        )
        result.at[index, output_columns[FUNNEL_COLUMN]] = normalize_funnel_stage(
            imported_stage
        )
        if not text:
            result.at[index, output_columns["处理状态"]] = "空内容"
            if stage_invalid:
                result.at[index, output_columns["判断依据"]] = (
                    "线索阶段无效，已回退为新线索"
                )
            result.at[index, output_columns["最终回复"]] = ""
            result.at[index, output_columns["回复状态"]] = "待复核"
        else:
            try:
                output = classifier(text)
                for column in RESULT_COLUMNS:
                    if column == "处理状态":
                        continue
                    if column == FUNNEL_COLUMN:
                        continue
                    result.at[index, output_columns[column]] = str(
                        output.get(column, "") or ""
                    )
                # Classifiers that know nothing about funnel metadata get the
                # safe default; imported stages were normalised above.
                if source_stage_column is None:
                    classifier_stage_present = FUNNEL_COLUMN in output
                    classifier_stage = output.get(FUNNEL_COLUMN, DEFAULT_FUNNEL_STAGE)
                    stage_invalid = classifier_stage_present and funnel_stage_is_invalid(
                        classifier_stage
                    )
                    result.at[index, output_columns[FUNNEL_COLUMN]] = normalize_funnel_stage(
                        classifier_stage
                    )
                result.at[index, output_columns["处理状态"]] = "成功"
                draft = str(output.get("客户回复", "") or "").strip()
                safety = check_reply_safety(draft, active_profile)
                if stage_invalid:
                    reason_column = output_columns["判断依据"]
                    reason = str(result.at[index, reason_column] or "").strip()
                    suffix = "线索阶段无效，已回退为新线索"
                    if suffix not in reason:
                        result.at[index, reason_column] = (
                            f"{reason}；{suffix}" if reason else suffix
                        )
                    result.at[index, output_columns["最终回复"]] = ""
                    result.at[index, output_columns["回复状态"]] = "待复核"
                elif draft and safety.safe:
                    # Keep the AI draft and the externally-sendable track
                    # physically separate.  A user must explicitly adopt and
                    # confirm a draft before it can enter ``最终回复``.
                    result.at[index, output_columns["最终回复"]] = ""
                    result.at[index, output_columns["回复状态"]] = "待确认"
                else:
                    result.at[index, output_columns["最终回复"]] = ""
                    result.at[index, output_columns["回复状态"]] = "待复核"
                success += 1
            except Exception:
                result.at[index, output_columns["处理状态"]] = "模型失败"
                result.at[index, output_columns["判断依据"]] = (
                    "处理失败，请稍后重试或人工复核"
                )
                result.at[index, output_columns["最终回复"]] = ""
                result.at[index, output_columns["回复状态"]] = "待复核"
                failed += 1
        if progress_callback:
            progress_callback(position, total, success, failed)
    return result


def preserve_confirmed_replies(
    fresh: pd.DataFrame,
    previous: pd.DataFrame,
    *,
    text_column: str,
    previous_text_column: str | None,
    profile: ReplyProfile | None = None,
) -> pd.DataFrame:
    """Compatibility entry point for the row-preservation workflow helper."""

    # Imported lazily to keep classifier primitives independent from workflow
    # editing helpers while exposing the public interface from this module too.
    from services.workflow import preserve_confirmed_replies as _preserve

    return _preserve(
        fresh,
        previous,
        text_column=text_column,
        previous_text_column=previous_text_column,
        profile=profile,
    )
