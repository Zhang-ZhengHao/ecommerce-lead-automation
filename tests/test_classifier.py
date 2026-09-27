import pandas as pd

from services.classifier import classify_demo, process_dataframe


def test_demo_classifier_maps_common_sales_intents():
    assert classify_demo("你们这个多少钱？")["意向等级"] == "高"
    assert classify_demo("我想做代理")["客户类型"] == "代理合作"
    assert classify_demo("随便看看")["意向等级"] == "低"


def test_process_dataframe_preserves_order_and_marks_empty_rows():
    source = pd.DataFrame(
        {"客户留言": ["你们这个多少钱？", "", "随便看看"], "来源": ["A", "B", "C"]}
    )

    result = process_dataframe(source, "客户留言", classify_demo)

    assert result["来源"].tolist() == ["A", "B", "C"]
    assert result["意向等级"].tolist() == ["高", "", "低"]
    assert result["处理状态"].tolist() == ["成功", "空内容", "成功"]


def test_process_dataframe_isolates_a_failed_row():
    source = pd.DataFrame({"客户留言": ["正常", "触发失败", "继续"]})

    def classifier(text: str):
        if text == "触发失败":
            raise RuntimeError("temporary model failure")
        return {
            "意向等级": "中",
            "客户类型": "其他",
            "客户回复": "感谢咨询",
            "跟进动作": "中优先级；确认需求。",
            "判断依据": "演示",
        }

    result = process_dataframe(source, "客户留言", classifier)

    assert result["处理状态"].tolist() == ["成功", "模型失败", "成功"]
    assert result.iloc[1]["意向等级"] == ""
    assert result.iloc[2]["客户回复"] == "感谢咨询"
    assert result.iloc[2]["跟进动作"] == "中优先级；确认需求。"


def test_process_dataframe_preserves_colliding_source_columns():
    source = pd.DataFrame(
        {
            "客户留言": ["报价是多少"],
            "意向等级": ["原始值"],
            "处理状态": ["原始状态"],
        }
    )

    result = process_dataframe(source, "客户留言", classify_demo)

    assert result["意向等级"].tolist() == ["原始值"]
    assert result["处理状态"].tolist() == ["原始状态"]
    assert result["意向等级（AI）"].tolist() == ["高"]
    assert result["处理状态（AI）"].tolist() == ["成功"]


def test_result_column_name_falls_back_to_collision_suffix_without_attrs():
    from services.classifier import result_column_name

    frame = pd.DataFrame(
        {
            "客户留言": ["报价是多少"],
            "意向等级": ["原始值"],
            "意向等级（AI）": ["高"],
        }
    )

    assert result_column_name(frame, "意向等级") == "意向等级（AI）"


def test_result_column_name_ignores_stale_mapping_and_uses_existing_column():
    from services.classifier import result_column_name

    frame = pd.DataFrame({"意向等级": ["高"]})
    frame.attrs["commerce_lead_result_columns"] = {"意向等级": "意向等级（AI）"}

    assert result_column_name(frame, "意向等级") == "意向等级"


def test_process_dataframe_handles_duplicate_input_indexes():
    source = pd.DataFrame(
        {"客户留言": ["报价是多少", "随便看看"]}, index=[7, 7]
    )

    result = process_dataframe(source, "客户留言", classify_demo)

    assert result["意向等级"].tolist() == ["高", "低"]


def test_process_initialises_final_reply_and_review_status():
    source = pd.DataFrame({"客户留言": ["想询价", ""]})
    result = process_dataframe(source, "客户留言", classify_demo)

    assert result["最终回复"].notna().all()
    assert result.loc[0, "回复状态"] == "待确认"
    assert result.loc[1, "最终回复"] == ""
    assert result.loc[1, "回复状态"] == "待复核"
