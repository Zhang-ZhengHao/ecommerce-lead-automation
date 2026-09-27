"""Industry presets for the reply-profile form."""

from __future__ import annotations

from services.reply_profile import ReplyProfile, normalize_reply_profile

INDUSTRY_PRESET_OPTIONS: tuple[str, ...] = ("电商咨询", "售后", "B2B 询价")

INDUSTRY_PRESETS: dict[str, ReplyProfile] = {
    "电商咨询": normalize_reply_profile(
        industry_context="电商零售商品咨询、报价与订单转化",
        tone="亲切",
    ),
    "售后": normalize_reply_profile(
        industry_context="电商售后、退换货与故障信息收集",
        tone="稳重",
    ),
    "B2B 询价": normalize_reply_profile(
        industry_context="企业采购、项目询价与交付需求",
        tone="专业",
    ),
}


def get_industry_preset(name: str) -> ReplyProfile:
    try:
        return INDUSTRY_PRESETS[name]
    except (KeyError, TypeError) as error:
        raise ValueError(f"行业预设不存在：{name}") from error


industry_preset = get_industry_preset
