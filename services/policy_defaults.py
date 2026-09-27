"""Customer-facing policy drafts used as safe starting points.

These are deliberately conservative defaults, not a complete platform rule
book. A real delivery must let the customer review and extend them with the
terms used by their platform and business.
"""

from __future__ import annotations


DEFAULT_POLICY_VERSION = "v0.1-2026-09-21"


DEFAULT_LABELS = (
    {
        "name": "询价",
        "description": "价格、规格、数量、采购意向",
    },
    {
        "name": "物流进度",
        "description": "催发货、查物流、到货进度或时效",
    },
    {
        "name": "售后/退换",
        "description": "破损、故障、退款、退货或换货",
    },
    {
        "name": "投诉",
        "description": "不满、纠纷、投诉或平台处罚风险",
    },
    {
        "name": "闲聊/其他",
        "description": "暂时无法归入前四类的留言",
    },
)


# A small, reviewable seed list. It is intentionally not presented as a
# complete Taobao/Pinduoduo prohibited-word database.
DEFAULT_FORBIDDEN_TERMS = (
    "全网最低价",
    "全网第一",
    "最低价",
    "史上最低",
    "绝对保证",
    "100%有效",
    "百分百有效",
    "零风险",
    "保证赚钱",
    "保证盈利",
    "保证发货",
    "一定发货",
    "保证到货",
    "一定退款",
    "保证退款",
    "永久质保",
    "包治",
    "根治",
)
