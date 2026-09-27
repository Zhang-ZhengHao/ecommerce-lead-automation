from __future__ import annotations

import re

from services.reply_profile import ReplyProfile, default_reply_profile


INFO_KEYS = ("数量", "预算", "地区", "时间", "订单号", "问题描述")


def extract_known_info(text: str) -> dict[str, str]:
    """Extract a small, deterministic set of facts for the demo mode."""

    content = str(text or "").strip()
    info = {key: "" for key in INFO_KEYS}
    if not content:
        return info

    quantity = re.search(
        r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(件|个|台|套|箱|份|人|公斤|千克|吨|平方米|平米|张|条)",
        content,
        flags=re.IGNORECASE,
    )
    if quantity:
        info["数量"] = f"{quantity.group(1)}{quantity.group(2)}"

    budget = re.search(
        r"预算\s*((?:大约|约|是|在)?\s*[¥￥]?\s*\d+(?:[.,]\d+)?\s*(?:万元|万|千|元)?(?:左右|以内|以下)?)",
        content,
        flags=re.IGNORECASE,
    )
    if budget:
        info["预算"] = re.sub(r"\s+", "", budget.group(1))

    order = re.search(
        r"(?:订单号|订单编号|单号)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{2,})",
        content,
        flags=re.IGNORECASE,
    )
    if order:
        info["订单号"] = order.group(1)

    region = re.search(
        r"(?:在|来自|位于|地区\s*[:：]?\s*(?:是|为)?|所在地区\s*[:：]?\s*(?:是|为)?)"
        r"\s*([一-龥]{2,8}?)(?=(?:想|要|准备|希望|咨询|做|申请|了解|的|[，。,.！？!?、\s]|$))",
        content,
    )
    if region:
        info["地区"] = region.group(1)

    time_match = re.search(
        r"(本周|下周|本月底|月底|尽快|\d+\s*(?:天|日|周|个月))", content
    )
    if time_match:
        info["时间"] = re.sub(r"\s+", "", time_match.group(1))

    issue = re.search(
        r"([^。！？!?]*?(?:故障|坏了|无法|不能|维修|问题)[^。！？!?]*)",
        content,
    )
    if issue:
        info["问题描述"] = issue.group(1).strip(" ，,：:")

    return info


def _has_spec_or_model(content: str) -> bool:
    return any(word in content for word in ("规格", "型号", "款式", "尺寸"))


def _known_summary(info: dict[str, str]) -> str:
    details = []
    if info["数量"]:
        details.append(f"采购{info['数量']}")
    if info["预算"]:
        details.append(f"预算{info['预算']}")
    return "、".join(details)


def _style_opening(opening: str, profile: ReplyProfile) -> str:
    """Apply presentation-only tone and optional industry context."""

    if profile.tone == "简洁":
        opening = opening.replace("您好，感谢您的咨询。", "您好，")
        opening = opening.replace("您好，感谢您关注代理合作。", "您好，")
        opening = opening.replace("您好，感谢您的关注。", "您好，")
        opening = opening.replace("您好，已了解您", "已了解您")
        opening = opening.replace("您好，已看到您的", "已看到您的")
        opening = opening.replace("您好，我们来帮您处理售后问题。", "已收到您的售后问题，")
    elif profile.tone == "亲切":
        opening = opening.replace("您好，", "您好呀，", 1)
    elif profile.tone == "稳重":
        opening = opening.replace("您好，", "您好，已确认：", 1)

    if profile.industry_context:
        opening = f"关于您咨询的{profile.industry_context}，" + opening
    return opening


def generate_demo_reply(
    text: str,
    intent_level: str,
    customer_type: str,
    profile: ReplyProfile | None = None,
) -> dict[str, str]:
    """Build a conservative, personalized reply without external API calls."""

    content = str(text or "").strip()
    active_profile = profile or default_reply_profile()
    info = extract_known_info(content)

    if not content:
        return {"客户回复": "", "跟进动作": ""}

    if customer_type == "询价":
        summary = _known_summary(info)
        if summary:
            opening = f"您好，已了解您{summary}。"
        else:
            opening = "您好，感谢您的咨询。"
        opening = _style_opening(opening, active_profile)
        if not _has_spec_or_model(content):
            question = (
                "请问具体规格或型号？"
                if active_profile.tone == "简洁"
                else "为了给您准备合适的报价，请问您关注的具体规格或型号是什么？"
            )
            reply = opening + question
            action = "高优先级；确认规格或型号后，准备对应的报价信息。"
        elif not info["时间"]:
            question = (
                "请问预计什么时候需要？"
                if active_profile.tone == "简洁"
                else "为了安排合适的交付方案，请问您预计什么时候需要？"
            )
            reply = opening + question
            action = "高优先级；确认预计到货时间，准备对应的报价与交付信息。"
        else:
            reply = opening + "我们会根据您提供的规格和时间整理对应方案。"
            action = "高优先级；核对规格与需求时间，准备报价和交付信息。"
        return {"客户回复": reply, "跟进动作": action}

    if customer_type == "代理合作":
        if info["地区"]:
            opening = _style_opening("您好，感谢您关注代理合作。", active_profile)
            reply = f"{opening}了解到您所在地区是{info['地区']}，请问预计的合作规模如何？"
            action = "高优先级；确认合作规模，准备代理政策和区域信息。"
        else:
            opening = _style_opening("您好，感谢您关注代理合作。", active_profile)
            reply = f"{opening}请问您所在的地区是哪里？我们再为您匹配合适的合作政策。"
            action = "高优先级；确认所在地区和合作规模，准备代理政策说明。"
        return {"客户回复": reply, "跟进动作": action}

    if customer_type == "售后":
        if "退款" in content:
            detail_label = "退款原因"
        elif any(word in content for word in ("退货", "换货")):
            detail_label = "退换原因"
        else:
            detail_label = "故障现象"

        if info["订单号"]:
            opening = _style_opening(f"您好，已看到您的订单号 {info['订单号']}。", active_profile)
            reply = (
                opening
                + f"为了尽快帮您处理售后，请补充{detail_label}，方便我们核实。"
            )
            action = f"优先跟进；核对订单并收集{detail_label}，交由售后确认。"
        else:
            opening = _style_opening("您好，我们来帮您处理售后问题。", active_profile)
            reply = opening + "请提供订单号，方便我们先核实记录。"
            action = "优先跟进；先收集订单号，再根据记录确认售后处理方式。"
        return {"客户回复": reply, "跟进动作": action}

    if intent_level == "低":
        reply = _style_opening("您好，感谢您的关注。", active_profile)
        return {
            "客户回复": reply + "您可以先了解产品信息，后续有具体需求时随时联系我们。",
            "跟进动作": "低优先级；记录兴趣，后续有新品或价格信息时再触达。",
        }

    reply = _style_opening("您好，感谢您的咨询。", active_profile)
    return {
        "客户回复": reply + "请告诉我们您的具体使用场景，我们再为您提供合适的建议。",
        "跟进动作": "中优先级；了解使用场景和具体需求，再分配给对应人员。",
    }
