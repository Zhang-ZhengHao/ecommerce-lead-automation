import pandas as pd

from services.results import filter_and_sort_results


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "客户留言": ["a", "b", "c", "d"],
            "意向等级": ["中", "高", "低", "高"],
            "处理状态": ["成功", "模型失败", "成功", "成功"],
            "客户回复": ["r1", "r2", "r3", "r4"],
        }
    )


def test_filter_and_sort_results_filters_high_intent_and_keeps_source_order():
    result = filter_and_sort_results(_frame(), intent="高", status="全部", sort="原始顺序")

    assert result["客户留言"].tolist() == ["b", "d"]


def test_filter_and_sort_results_filters_review_rows():
    result = filter_and_sort_results(_frame(), intent="全部", status="待复核", sort="原始顺序")

    assert result["客户留言"].tolist() == ["b"]


def test_filter_and_sort_results_sorts_high_intent_stably():
    result = filter_and_sort_results(_frame(), intent="全部", status="全部", sort="高意向优先")

    assert result["客户留言"].tolist() == ["b", "d", "a", "c"]


def test_filter_and_sort_results_preserves_collision_mapping_attrs():
    frame = _frame()
    frame.attrs["commerce_lead_result_columns"] = {
        "意向等级": "意向等级（AI）",
        "处理状态": "处理状态（AI）",
    }
    frame = frame.rename(
        columns={"意向等级": "意向等级（AI）", "处理状态": "处理状态（AI）"}
    )

    result = filter_and_sort_results(frame, intent="高", status="全部", sort="原始顺序")

    assert result["客户留言"].tolist() == ["b", "d"]
    assert result.attrs["commerce_lead_result_columns"] == frame.attrs[
        "commerce_lead_result_columns"
    ]


def test_filter_and_sort_results_resolves_collision_columns_when_attrs_are_missing():
    frame = _frame().rename(
        columns={"意向等级": "意向等级（AI）", "处理状态": "处理状态（AI）"}
    )

    result = filter_and_sort_results(frame, intent="高", status="待复核")

    assert result["客户留言"].tolist() == ["b"]


def test_filter_and_sort_keeps_original_row_ids():
    from services.classifier import classify_demo, process_dataframe

    result = process_dataframe(
        pd.DataFrame({"客户留言": ["中", "高", "低"]}),
        "客户留言",
        lambda text: {
            "意向等级": {"高": "高", "低": "低"}.get(text, "中"),
            "客户类型": "其他",
            "客户回复": text,
            "跟进动作": "跟进",
            "判断依据": "测试",
        },
    )
    view = filter_and_sort_results(result, sort="高意向优先")
    assert view.index.tolist() == [1, 0, 2]


def test_review_mask_includes_success_rows_with_review_reply_status():
    from services.results import review_row_mask

    frame = pd.DataFrame(
        {
            "处理状态": ["成功", "成功", "模型失败"],
            "回复状态": ["待确认", "待复核", "待复核"],
        }
    )
    assert review_row_mask(frame).tolist() == [False, True, True]
