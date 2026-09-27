"""Reply configuration and deterministic safety post-checks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from services.policy_defaults import DEFAULT_FORBIDDEN_TERMS

TONE_OPTIONS = ("专业", "亲切", "简洁", "稳重")
FORBIDDEN_CATEGORY_OPTIONS = ("价格", "库存", "折扣", "交期", "售后结论", "效果保证")


@dataclass(frozen=True)
class ReplyProfile:
    industry_context: str = ""
    tone: str = "专业"
    forbidden_categories: tuple[str, ...] = FORBIDDEN_CATEGORY_OPTIONS
    custom_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class SafetyResult:
    safe: bool
    reason: str = ""


class ReplyProfileError(ValueError):
    pass


def default_reply_profile() -> ReplyProfile:
    return ReplyProfile()


def _split_terms(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values: Any = re.split(r"[,，、\n]", value)
    else:
        try:
            values = list(value)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ReplyProfileError(f"{label}必须是文本或可迭代选项") from exc
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            raise ReplyProfileError(f"{label}必须全部是文本")
        item = item.strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def normalize_reply_profile(
    *,
    industry_context: str = "",
    tone: str = "专业",
    forbidden_categories: object = FORBIDDEN_CATEGORY_OPTIONS,
    custom_terms: object = (),
) -> ReplyProfile:
    if not isinstance(industry_context, str):
        raise ReplyProfileError("行业背景必须是文本")
    industry_context = industry_context.strip()
    if len(industry_context) > 800:
        raise ReplyProfileError("行业背景最多 800 个字符，请删减后重试")
    if not isinstance(tone, str) or tone.strip() not in TONE_OPTIONS:
        raise ReplyProfileError(f"语气只能选择：{'、'.join(TONE_OPTIONS)}")
    tone = tone.strip()
    categories = _split_terms(forbidden_categories, "禁止类别")
    invalid = [item for item in categories if item not in FORBIDDEN_CATEGORY_OPTIONS]
    if invalid:
        raise ReplyProfileError(f"禁止类别只能选择六类选项：{'、'.join(FORBIDDEN_CATEGORY_OPTIONS)}")
    terms = _split_terms(custom_terms, "自定义词")
    if len(terms) > 20:
        raise ReplyProfileError("自定义词最多 20 个，请删减后重试")
    if any(len(term) > 40 for term in terms):
        raise ReplyProfileError("每个自定义词最多 40 个字符，请删减后重试")
    if sum(len(term) for term in terms) > 400:
        raise ReplyProfileError("自定义词合计最多 400 个字符，请删减后重试")
    return ReplyProfile(industry_context, tone, tuple(categories), tuple(terms))


def profile_signature(profile: ReplyProfile) -> str:
    normalized = normalize_reply_profile(
        industry_context=profile.industry_context,
        tone=profile.tone,
        forbidden_categories=profile.forbidden_categories,
        custom_terms=profile.custom_terms,
    )
    payload = json.dumps(asdict(normalized), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_BASELINE_RULES = (
    (re.compile(r"保证.{0,12}(发货|交付|完成)|一定.{0,12}(发货|交付|完成)", re.I), "包含结果承诺"),
)
_CATEGORY_RULES = {
    "价格": ((re.compile(r"(?:固定|锁定|最低|最优惠)\s*(?:价|价格)?\s*\d+(?:\.\d+)?\s*元|(?:固定|锁定|最低|最优惠)价|价格保证|保证价格", re.I), "包含价格承诺"),),
    "折扣": ((re.compile(r"(?:固定|保证|确保).{0,8}(折扣|优惠)|\d+\s*折|优惠保证", re.I), "包含折扣承诺"),),
    "库存": ((re.compile(r"现货|保证.{0,8}(有货|库存)|库存充足", re.I), "包含库存承诺"),),
    "交期": ((re.compile(r"(?:保证|一定).{0,12}(?:\d{1,4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d+\s*(?:天|个工作日)|发货)", re.I), "包含交期承诺"),),
    "售后结论": ((re.compile(r"一定(?:退款|退货|换新|赔付)|保证(?:退款|退货|换新|赔付)", re.I), "包含售后结论"),),
    "效果保证": ((re.compile(r"保证效果|一定提升|保证(?:提高|改善).{0,8}(?:效果|性能|效率)", re.I), "包含效果保证"),),
}


def check_reply_safety(text: str, profile: ReplyProfile | None = None) -> SafetyResult:
    if not isinstance(text, str):
        return SafetyResult(False, "回复内容必须是文本")
    active = normalize_reply_profile() if profile is None else normalize_reply_profile(
        industry_context=profile.industry_context,
        tone=profile.tone,
        forbidden_categories=profile.forbidden_categories,
        custom_terms=profile.custom_terms,
    )
    for pattern, reason in _BASELINE_RULES:
        if pattern.search(text):
            return SafetyResult(False, reason)
    for category in active.forbidden_categories:
        for pattern, reason in _CATEGORY_RULES[category]:
            if pattern.search(text):
                return SafetyResult(False, reason)
    lowered = text.casefold()
    for term in DEFAULT_FORBIDDEN_TERMS:
        if term.casefold() in lowered:
            return SafetyResult(False, f"命中内置禁词：{term}")
    for term in active.custom_terms:
        if term.casefold() in lowered:
            return SafetyResult(False, f"包含自定义敏感词：{term}")
    return SafetyResult(True)
