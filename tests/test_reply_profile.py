import pytest

from services.reply_profile import (
    FORBIDDEN_CATEGORY_OPTIONS,
    ReplyProfileError,
    check_reply_safety,
    normalize_reply_profile,
    profile_signature,
)


def test_profile_normalises_defaults_and_custom_terms():
    profile = normalize_reply_profile(
        industry_context="  工业阀门  ",
        tone="亲切",
        custom_terms="竞品A, 竞品A\n内部价",
    )
    assert profile.industry_context == "工业阀门"
    assert profile.tone == "亲切"
    assert profile.custom_terms == ("竞品A", "内部价")
    assert profile.forbidden_categories == FORBIDDEN_CATEGORY_OPTIONS


def test_profile_splits_custom_terms_on_dunhao_and_checks_each_term():
    profile = normalize_reply_profile(custom_terms="竞品A、竞品B")
    assert profile.custom_terms == ("竞品A", "竞品B")
    assert not check_reply_safety("请勿透露竞品A信息", profile).safe
    assert not check_reply_safety("请勿透露竞品B信息", profile).safe


def test_profile_rejects_invalid_tone_and_long_context():
    with pytest.raises(ReplyProfileError, match="语气"):
        normalize_reply_profile(tone="夸张")
    with pytest.raises(ReplyProfileError, match="800"):
        normalize_reply_profile(industry_context="x" * 801)


def test_safety_result_distinguishes_guarantee_from_normal_sales_language():
    assert not check_reply_safety("我们保证今天发货").safe
    assert check_reply_safety("我们会准备报价资料供您确认").safe


def test_profile_signature_ignores_normalisation_whitespace():
    a = normalize_reply_profile(industry_context="产品")
    b = normalize_reply_profile(industry_context=" 产品 ")
    c = normalize_reply_profile(industry_context="另一产品")
    assert profile_signature(a) == profile_signature(b)
    assert profile_signature(a) != profile_signature(c)


def test_safety_categories_and_custom_terms_are_checked_without_false_positives():
    assert not check_reply_safety("现在有现货，可以马上发出").safe
    assert check_reply_safety("库存情况需要仓库确认").safe
    assert not check_reply_safety("交期保证 2026-10-01").safe
    assert not check_reply_safety("一定退款").safe
    assert not check_reply_safety("保证效果").safe
    profile = normalize_reply_profile(custom_terms="内部价\n竞品A")
    assert not check_reply_safety("请勿对外透露内部价", profile).safe


def test_profile_limits_custom_terms_and_categories():
    with pytest.raises(ReplyProfileError, match="20"):
        normalize_reply_profile(custom_terms=[str(i) for i in range(21)])
    with pytest.raises(ReplyProfileError, match="40"):
        normalize_reply_profile(custom_terms="x" * 41)
    with pytest.raises(ReplyProfileError, match="类别"):
        normalize_reply_profile(forbidden_categories=("其他",))


def test_safety_does_not_allow_commitment_just_because_confirmation_is_mentioned():
    assert not check_reply_safety("保证价格，需确认").safe
    assert not check_reply_safety("保证库存，供您确认").safe


def test_safety_catches_fixed_amount_and_discount_guarantees():
    assert not check_reply_safety("固定100元").safe
    assert not check_reply_safety("优惠保证").safe
    assert check_reply_safety("报价100元，待确认").safe
    assert not check_reply_safety("现货").safe
