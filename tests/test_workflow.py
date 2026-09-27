import pandas as pd
import pytest

from services.classifier import classify_demo, process_dataframe
from services.workflow import (
    ReplyEditError,
    preserve_confirmed_replies,
    restore_draft,
    row_label,
    update_final_reply,
)


def test_edit_after_filter_writes_to_original_row_not_view_position():
    frame = process_dataframe(
        pd.DataFrame({"客户留言": ["a", "b"]}), "客户留言", classify_demo
    )
    from services.results import filter_and_sort_results

    view = filter_and_sort_results(frame, sort="原始顺序")
    updated = update_final_reply(frame, int(view.index[1]), "人工确认回复")
    assert updated.loc[1, "最终回复"] == "人工确认回复"
    assert updated.loc[0, "最终回复"] != "人工确认回复"
    assert updated.loc[1, "回复状态"] == "已确认"


def test_update_final_reply_rejects_empty_long_and_unsafe_text():
    frame = process_dataframe(pd.DataFrame({"客户留言": ["a"]}), "客户留言", classify_demo)
    with pytest.raises(ReplyEditError, match="不能为空"):
        update_final_reply(frame, 0, " ")
    with pytest.raises(ReplyEditError, match="2000"):
        update_final_reply(frame, 0, "x" * 2001)
    with pytest.raises(ReplyEditError, match="安全"):
        update_final_reply(frame, 0, "保证今天发货")


def test_restore_draft_marks_safe_draft_pending_confirmation_and_unsafe_for_review():
    frame = process_dataframe(pd.DataFrame({"客户留言": ["a", "b"]}), "客户留言", classify_demo)
    frame.loc[0, "客户回复"] = "请确认规格后我们再准备报价。"
    frame.loc[1, "客户回复"] = "保证今天发货"
    restored = restore_draft(frame, 0)
    restored = restore_draft(restored, 1)
    assert restored.loc[0, "最终回复"] == "请确认规格后我们再准备报价。"
    assert restored.loc[0, "回复状态"] == "待确认"
    assert restored.loc[1, "最终回复"] == ""
    assert restored.loc[1, "回复状态"] == "待复核"


def test_preserve_confirmed_replies_requires_unchanged_text_and_safety():
    previous = process_dataframe(
        pd.DataFrame({"客户留言": ["想询价", "随便看看"]}),
        "客户留言",
        classify_demo,
    )
    previous.loc[0, "最终回复"] = "人工确认报价信息"
    previous.loc[0, "回复状态"] = "已确认"
    fresh = process_dataframe(
        pd.DataFrame({"客户留言": ["想询价", "内容已变"]}),
        "客户留言",
        classify_demo,
    )
    preserved = preserve_confirmed_replies(
        fresh, previous, text_column="客户留言", previous_text_column="客户留言"
    )
    assert preserved.loc[0, "最终回复"] == "人工确认报价信息"
    assert preserved.loc[0, "回复状态"] == "已确认"
    assert preserved.loc[1, "回复状态"] != "已确认"


def test_row_label_does_not_expose_profile_or_full_message():
    frame = process_dataframe(
        pd.DataFrame({"客户留言": ["这是一个很长的留言" * 20]}),
        "客户留言",
        classify_demo,
    )
    label = row_label(frame, 0, text_column="客户留言")
    assert "行业背景" not in label
    assert len(label) < 180


def test_row_label_uses_mobile_friendly_separators():
    frame = process_dataframe(
        pd.DataFrame({"客户留言": ["想了解价格"]}), "客户留言", classify_demo
    )
    label = row_label(frame, 0, text_column="客户留言")
    assert "第 1 行 ·" in label
