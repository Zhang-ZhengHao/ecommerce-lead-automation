from pathlib import Path

from services.policy_defaults import (
    DEFAULT_FORBIDDEN_TERMS,
    DEFAULT_LABELS,
    DEFAULT_POLICY_VERSION,
)
from services.reply_profile import check_reply_safety


def test_default_label_draft_is_ready_for_customer_annotation():
    names = [label["name"] for label in DEFAULT_LABELS]

    assert names == ["询价", "物流进度", "售后/退换", "投诉", "闲聊/其他"]
    assert all(label["description"] for label in DEFAULT_LABELS)


def test_builtin_forbidden_terms_are_checked_even_without_custom_terms():
    assert DEFAULT_FORBIDDEN_TERMS
    assert not check_reply_safety("本店全网最低价，保证发货").safe
    assert check_reply_safety("价格和发货时间请以人工核实为准").safe


def test_default_policy_has_a_visible_revision():
    assert DEFAULT_POLICY_VERSION.startswith("v")


def test_policy_document_points_to_the_code_source_instead_of_copying_terms():
    document = (Path(__file__).parents[1] / "POLICY_DEFAULTS.md").read_text(
        encoding="utf-8"
    )

    assert "DEFAULT_FORBIDDEN_TERMS" in document
    assert "全网最低价" not in document
