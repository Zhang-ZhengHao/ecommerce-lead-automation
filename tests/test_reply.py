import pandas as pd

from services.classifier import classify_demo, process_dataframe
from services.reply import extract_known_info
from services.reply_profile import default_reply_profile, normalize_reply_profile


def test_extract_known_info_reads_quantity_budget_and_order_number():
    info = extract_known_info(
        "想采购100件，预算约2万元，订单号 A1008，人在杭州。"
    )

    assert info["数量"] == "100件"
    assert info["预算"] == "约2万元"
    assert info["订单号"] == "A1008"
    assert info["地区"] == "杭州"


def test_demo_reply_reuses_known_sales_details_and_asks_one_key_question():
    result = classify_demo("想采购100件，预算约2万元，多久能发货？")

    reply = result["客户回复"]
    assert "100件" in reply
    assert "2万元" in reply
    assert "具体规格" in reply or "型号" in reply
    assert reply.count("？") + reply.count("?") <= 1
    assert "请问采购数量" not in reply
    assert result["跟进动作"]


def test_demo_after_sales_reply_does_not_repeat_known_order_number():
    result = classify_demo("订单号 A1008 的机器坏了，开机后无法使用。")

    assert "A1008" in result["客户回复"]
    assert "请提供订单号" not in result["客户回复"]
    assert "请补充故障现象" in result["客户回复"]
    assert "和" not in result["客户回复"]
    assert "故障" in result["跟进动作"] or "现象" in result["跟进动作"]


def test_demo_low_intent_reply_is_low_pressure():
    result = classify_demo("随便看看，先了解一下")

    assert "客户回复" in result
    assert "跟进动作" in result
    assert "？" not in result["客户回复"]
    assert "低优先级" in result["跟进动作"]


def test_processing_appends_new_reply_columns_instead_of_old_name():
    source = pd.DataFrame({"客户留言": ["你们这个多少钱？"]})

    result = process_dataframe(source, "客户留言", classify_demo)

    assert "客户回复" in result.columns
    assert "跟进动作" in result.columns
    assert "建议回复" not in result.columns


def test_demo_after_sales_without_order_number_asks_for_one_key_detail():
    result = classify_demo("机器坏了，开机后无法使用。")

    assert "订单号" in result["客户回复"]
    assert "故障现象" not in result["客户回复"]
    assert "和" not in result["客户回复"]


def test_demo_inquiry_does_not_treat_delivery_question_as_known_time():
    result = classify_demo("规格 X1，想知道多久能发货？")

    assert result["客户类型"] == "询价"
    assert "预计什么时候" in result["客户回复"]
    assert "根据您提供的规格和时间" not in result["客户回复"]


def test_region_extraction_stops_before_follow_up_text():
    result = classify_demo("我在杭州想做代理，怎么合作？")

    assert "杭州" in result["客户回复"]
    assert "杭州想做代理" not in result["客户回复"]


def test_refund_reply_asks_for_reason_instead_of_fault_details():
    result = classify_demo("订单号 A1008，想申请退款。")

    assert "A1008" in result["客户回复"]
    assert "退款原因" in result["客户回复"]
    assert "故障现象" not in result["客户回复"]


def test_region_label_with_colon_is_extracted_cleanly():
    result = classify_demo("地区：北京，想加盟合作。")

    assert result["客户类型"] == "代理合作"
    assert "北京" in result["客户回复"]
    assert "北京想加盟" not in result["客户回复"]


def test_demo_reply_changes_tone_and_mentions_product_context():
    profile = normalize_reply_profile(industry_context="工业阀门", tone="简洁")
    result = classify_demo("想采购100件", profile=profile)
    assert "工业阀门" in result["客户回复"]
    assert len(result["客户回复"]) < len(
        classify_demo("想采购100件", profile=default_reply_profile())["客户回复"]
    )


def test_old_one_argument_demo_call_remains_valid():
    assert classify_demo("随便看看")["意向等级"] == "低"


def test_concise_inquiry_keeps_sentence_boundary():
    profile = normalize_reply_profile(tone="简洁")
    reply = classify_demo("想采购100件", profile=profile)["客户回复"]
    assert "件。请问" in reply


def test_concise_after_sales_keeps_sentence_boundary():
    profile = normalize_reply_profile(tone="简洁")
    reply = classify_demo("订单号 A1008 的机器坏了", profile=profile)["客户回复"]
    assert "A1008。为了" in reply
