from __future__ import annotations

import hashlib
import os

import pandas as pd
import streamlit as st

from services.classifier import (
    RESULT_COLUMNS,
    classify_demo,
    preserve_confirmed_replies,
    process_dataframe,
    result_column_name,
)
from services.excel import (
    MAX_ROWS,
    SpreadsheetError,
    build_demo_dataframe,
    detect_message_column,
    export_sendable_workbook,
    export_result_workbook,
    export_template_xlsx,
    export_xlsx,
    read_table,
)
from services.model_client import ModelClientError, OpenAICompatibleClassifier
from services.policy_defaults import (
    DEFAULT_FORBIDDEN_TERMS,
    DEFAULT_LABELS,
    DEFAULT_POLICY_VERSION,
)
from services.reply_profile import (
    FORBIDDEN_CATEGORY_OPTIONS,
    ReplyProfileError,
    TONE_OPTIONS,
    default_reply_profile,
    normalize_reply_profile,
    profile_signature,
)
from services.results import (
    FUNNEL_FILTERS,
    INTENT_FILTERS,
    SORT_OPTIONS,
    STATUS_FILTERS,
    filter_and_sort_results,
    review_row_mask,
)
from services.workflow import (
    ReplyEditError,
    clear_final_reply,
    restore_draft,
    row_label,
    update_funnel_stage,
    update_final_reply,
)
from services.funnel import FUNNEL_COLUMN, FUNNEL_STAGES
from services.industry_presets import (
    INDUSTRY_PRESET_OPTIONS,
    get_industry_preset,
)
from services.usage import (
    real_ai_upload_error,
    session_usage_message,
    usage_status,
)
from services.version import BUILD_SHA


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _display_value(value: object) -> str:
    """Render a cell safely without exposing pandas NaN/NA text."""

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _render_footer() -> None:
    """Show the process-captured build id on every reachable page."""

    st.divider()
    st.caption(f"版本 {BUILD_SHA} · 运行时版本以本次进程启动时捕获的提交为准")


st.set_page_config(
    page_title="电商线索与客服表格自动化",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root { --ink: #17212b; --muted: #607080; --accent: #e27645; --soft: #fff7f1; }
    .block-container { max-width: 1120px; padding-top: 2.5rem; padding-bottom: 3rem; }
    .hero { padding: 1.4rem 1.5rem; border: 1px solid #f0ded4; border-radius: 18px;
            background: linear-gradient(135deg, #fffaf7, #fff2e9); margin-bottom: 1.2rem; }
    .hero h1 { color: var(--ink); letter-spacing: -0.04em; margin-bottom: .25rem; }
    .hero p { color: var(--muted); font-size: 1.05rem; margin-bottom: 0; }
    .mode-pill { display: inline-block; border-radius: 999px; padding: .25rem .65rem;
                 background: #fff; color: #9b4e2e; border: 1px solid #edc8b8; font-size: .82rem; }
    [data-testid="stMetricValue"] { color: #9b4e2e; }
    @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        .hero { padding: 1rem; }
        button[data-testid^="stBaseButton-"],
        [data-testid="stDownloadButton"] button {
            min-height: 44px !important;
            height: 44px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _initialise_state() -> None:
    defaults = {
        "source_frame": None,
        "source_name": "",
        "source_signature": "",
        "detected_text_column": None,
        "result_text_column": None,
        "result_frame": None,
        "result_source_signature": "",
        "active_profile": default_reply_profile(),
        "active_profile_signature": profile_signature(default_reply_profile()),
        "industry_preset": "自定义",
        "result_profile_signature": "",
        "selected_row_id": None,
        "profile_form_revision": 0,
        "result_mode": "演示规则",
        "processing_mode": "演示规则",
        "result_revision": 0,
        "upload_widget_version": 0,
        "real_ai_rows_used": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _load_source(payload: bytes, filename: str) -> None:
    signature = hashlib.sha1(payload).hexdigest()
    if signature == st.session_state.get("source_signature"):
        return
    if st.session_state.get("processing_mode") == "真实 AI":
        usage_error = real_ai_upload_error(
            0,
            st.session_state.real_ai_rows_used,
        )
        if usage_error:
            # A zero-row preflight catches an exhausted session before parsing
            # a new upload; the row-aware check runs immediately after read.
            raise SpreadsheetError(usage_error)
    frame = read_table(payload, filename)
    if st.session_state.get("processing_mode") == "真实 AI":
        usage_error = real_ai_upload_error(
            len(frame),
            st.session_state.real_ai_rows_used,
        )
        if usage_error:
            raise SpreadsheetError(usage_error)
    st.session_state.source_frame = frame
    st.session_state.source_name = filename
    st.session_state.source_signature = signature
    st.session_state.detected_text_column = detect_message_column(frame)
    st.session_state.result_text_column = None
    st.session_state.result_frame = None
    st.session_state.result_source_signature = ""
    st.session_state.pop("processing_text_column", None)
    _reset_reply_profile()
    st.session_state.result_revision += 1


def _load_demo() -> None:
    if st.session_state.get("source_signature") == "demo":
        return
    st.session_state.source_frame = build_demo_dataframe()
    st.session_state.source_name = "demo.csv"
    st.session_state.source_signature = "demo"
    st.session_state.detected_text_column = detect_message_column(
        st.session_state.source_frame
    )
    st.session_state.result_text_column = None
    st.session_state.result_frame = None
    st.session_state.result_source_signature = ""
    st.session_state.pop("processing_text_column", None)
    _reset_reply_profile()
    st.session_state.result_revision += 1
    # Give the uploader a fresh key so a previously selected file cannot
    # overwrite the demo data on the rerun triggered by this button.
    st.session_state.upload_widget_version += 1


def _reset_reply_profile() -> None:
    profile = default_reply_profile()
    st.session_state.active_profile = profile
    st.session_state.active_profile_signature = profile_signature(profile)
    st.session_state.result_profile_signature = ""
    st.session_state.industry_preset = "自定义"
    st.session_state.selected_row_id = None
    st.session_state.profile_form_revision += 1


def _render_reply_profile_form() -> None:
    """Render and persist business reply settings only on explicit submit."""

    profile = st.session_state.active_profile
    source_key = st.session_state.source_signature or "none"
    revision = st.session_state.profile_form_revision
    form_key = f"reply_profile_form_{source_key}_{revision}"
    with st.expander("查看默认标签草案（客户校准用）", expanded=False):
        st.table(pd.DataFrame(DEFAULT_LABELS))
        st.caption(
            "这是接单前的标注起点，不代表当前模型已经完成客户行业校准；"
            "不会自动改变当前输出标签。"
        )
    with st.expander("查看内置禁词初稿", expanded=False):
        st.caption(
            f"默认政策 {DEFAULT_POLICY_VERSION}：当前内置 {len(DEFAULT_FORBIDDEN_TERMS)} 项高风险承诺/极限词；"
            "它不是平台完整禁词库，请结合客户词表增补。"
        )
        st.write("、".join(DEFAULT_FORBIDDEN_TERMS))
    with st.form(form_key):
        st.markdown("#### 业务回复设置")
        preset_options = ("自定义", *INDUSTRY_PRESET_OPTIONS)
        current_preset = st.session_state.get("industry_preset", "自定义")
        preset_index = (
            preset_options.index(current_preset)
            if current_preset in preset_options
            else 0
        )
        preset_name = st.selectbox(
            "行业预设",
            preset_options,
            index=preset_index,
            key=f"profile_preset_{source_key}_{revision}",
            help="预设只填充行业说明和语气；你仍可按客户词表调整禁词。",
        )
        industry_context = st.text_area(
            "产品 / 行业说明",
            value=profile.industry_context,
            help="用于帮助模型理解产品，不要填写客户隐私或密钥。",
            key=f"profile_industry_{source_key}_{revision}",
        )
        tone = st.selectbox(
            "回复语气",
            TONE_OPTIONS,
            index=TONE_OPTIONS.index(profile.tone),
            key=f"profile_tone_{source_key}_{revision}",
        )
        st.caption("禁止类别（命中后会标记为待复核；另有内置禁词初稿）")
        category_columns = st.columns(3)
        forbidden_categories = []
        for index, category in enumerate(FORBIDDEN_CATEGORY_OPTIONS):
            checked = category in profile.forbidden_categories
            with category_columns[index % 3]:
                if st.checkbox(
                    category,
                    value=checked,
                    key=f"profile_category_{source_key}_{revision}_{index}",
                ):
                    forbidden_categories.append(category)
        custom_terms = st.text_area(
            "自定义禁词",
            value="\n".join(profile.custom_terms),
            help="多个词可用换行、逗号或顿号分隔。",
            key=f"profile_terms_{source_key}_{revision}",
        )
        submitted = st.form_submit_button("保存回复设置", width="stretch")
    if not submitted:
        return
    try:
        selected_preset = None
        if preset_name != "自定义":
            selected_preset = get_industry_preset(preset_name)
            # Presets provide a safe, repeatable starting point.  The freeform
            # fields stay visible for transparency, while applying a preset on
            # submit intentionally uses its validated context and tone.
            industry_context = selected_preset.industry_context
            tone = selected_preset.tone
        normalized = normalize_reply_profile(
            industry_context=industry_context,
            tone=tone,
            forbidden_categories=forbidden_categories,
            custom_terms=custom_terms,
        )
    except ReplyProfileError as error:
        st.error(f"回复设置有误：{error}")
        return
    st.session_state.active_profile = normalized
    st.session_state.active_profile_signature = profile_signature(normalized)
    st.session_state.industry_preset = preset_name
    st.success("回复设置已保存。点击“开始处理”或按新设置重新生成以应用。")


def _run_processing(*, overwrite_confirmed: bool = False) -> None:
    frame = st.session_state.source_frame
    if frame is None:
        return
    text_column = st.session_state.get("processing_text_column")
    mode = st.session_state.get("processing_mode", "演示规则")
    if text_column not in frame.columns:
        st.error("请选择有效的客户留言列后再处理。")
        return
    if len(frame) > MAX_ROWS:
        st.error(f"当前版本最多处理 {MAX_ROWS:,} 行，请先拆分文件。")
        return
    if mode == "真实 AI":
        usage_error = real_ai_upload_error(
            len(frame),
            st.session_state.real_ai_rows_used,
        )
        if usage_error:
            st.error(usage_error)
            return

    profile = st.session_state.active_profile
    progress = st.progress(0, text="准备处理…")
    status = st.empty()
    if mode == "真实 AI":
        try:
            classifier = OpenAICompatibleClassifier(profile=profile)
        except ModelClientError as error:
            st.error(str(error))
            st.stop()
    else:
        classifier = lambda text: classify_demo(text, profile)

    def update(current: int, total: int, success: int, failed: int) -> None:
        progress.progress(current / max(total, 1), text=f"正在处理 {current}/{total} 行")
        status.caption(f"成功 {success} · 模型失败 {failed}")

    previous = st.session_state.result_frame
    previous_source_signature = st.session_state.get("result_source_signature", "")
    fresh = process_dataframe(
        frame,
        text_column,
        classifier,
        progress_callback=update,
        profile=profile,
    )
    if previous is not None and previous_source_signature == st.session_state.source_signature and not overwrite_confirmed:
        fresh = preserve_confirmed_replies(
            fresh,
            previous,
            text_column=text_column,
            previous_text_column=st.session_state.get("result_text_column"),
            profile=profile,
        )
    st.session_state.result_frame = fresh
    st.session_state.result_text_column = text_column
    st.session_state.result_source_signature = st.session_state.source_signature
    st.session_state.result_profile_signature = profile_signature(profile)
    st.session_state.result_mode = mode
    st.session_state.selected_row_id = None
    st.session_state.result_revision += 1
    if mode == "真实 AI":
        st.session_state.real_ai_rows_used += len(frame)
    progress.progress(1.0, text="处理完成")
    if mode == "真实 AI":
        # The usage banner is rendered before the button handler runs.  Rerun
        # once so the just-consumed quota is visible immediately instead of
        # waiting for an unrelated widget interaction.
        st.rerun()


def _render_results() -> None:
    result = st.session_state.result_frame
    if result is None:
        return
    st.subheader("处理结果")
    if st.session_state.result_mode == "演示规则":
        st.info("当前结果来自本地规则演示，不代表真实模型效果。")
    intent_column = result_column_name(result, "意向等级")
    status_column = result_column_name(result, "处理状态")
    counts = result[intent_column].value_counts()
    high, medium, low = (int(counts.get(level, 0)) for level in ("高", "中", "低"))
    review_mask = review_row_mask(result, profile=st.session_state.active_profile)
    failed = int(review_mask.sum())
    funnel_column = result_column_name(result, FUNNEL_COLUMN)
    metrics = st.columns(4)
    metrics[0].metric("高意向", high)
    metrics[1].metric("中意向", medium)
    metrics[2].metric("低意向", low)
    metrics[3].metric("待复核", failed)
    if funnel_column in result.columns:
        funnel_counts = result[funnel_column].value_counts()
        funnel_summary = " · ".join(
            f"{stage} {int(funnel_counts.get(stage, 0))}" for stage in FUNNEL_STAGES
        )
        st.caption(f"线索漏斗（仅当前会话）：{funnel_summary}")

    filter_columns = st.columns(4)
    intent_filter = filter_columns[0].selectbox(
        "意向筛选", INTENT_FILTERS, key=f"intent_filter_{st.session_state.result_revision}"
    )
    status_filter = filter_columns[1].selectbox(
        "状态筛选", STATUS_FILTERS, key=f"status_filter_{st.session_state.result_revision}"
    )
    sort_choice = filter_columns[2].selectbox(
        "排序方式", SORT_OPTIONS, key=f"sort_results_{st.session_state.result_revision}"
    )
    funnel_filter = filter_columns[3].selectbox(
        "线索阶段", FUNNEL_FILTERS, key=f"funnel_filter_{st.session_state.result_revision}"
    )
    view = filter_and_sort_results(
        result,
        intent=intent_filter,
        status=status_filter,
        sort=sort_choice,
        funnel_stage=funnel_filter,
        profile=st.session_state.active_profile,
    )
    st.caption(f"当前显示 {len(view):,} / {len(result):,} 行")
    message_column = st.session_state.get("result_text_column")
    if message_column not in result.columns:
        message_column = detect_message_column(result)
    if message_column not in result.columns:
        message_column = next(
            (column for column in result.columns if column == "客户留言"), None
        )
    st.caption("客户回复是 AI 草稿；只有已确认的最终回复才建议发送给客户。")

    view_row_ids = [int(row_id) for row_id in view.index]
    selected_row_id = st.session_state.get("selected_row_id")
    if selected_row_id not in view_row_ids:
        selected_row_id = None
        st.session_state.selected_row_id = None
    option_ids: list[int | None] = [None] + view_row_ids

    def _row_option_label(row_id: int | None) -> str:
        if row_id is None:
            return "请选择一行进行编辑"
        return row_label(result, row_id, text_column=message_column or "")

    selected_from_picker = st.selectbox(
        "选择要编辑的行",
        option_ids,
        index=option_ids.index(selected_row_id),
        format_func=_row_option_label,
        key=(
            f"row_picker_{st.session_state.source_signature}_"
            f"{st.session_state.result_revision}_{intent_filter}_{status_filter}_{sort_choice}_{funnel_filter}"
        ),
    )
    if selected_from_picker is not None:
        selected_row_id = int(selected_from_picker)
        st.session_state.selected_row_id = selected_row_id

    if view.empty:
        st.info("当前筛选没有匹配的行，请调整筛选条件。")
        table_event = None
    else:
        table_event = st.dataframe(
            view,
            width="stretch",
            hide_index=True,
            key=(
                f"result_grid_{st.session_state.result_revision}_"
                f"{intent_filter}_{status_filter}_{sort_choice}_{funnel_filter}"
            ),
            on_select="rerun",
            selection_mode="single-row",
        )

    selected_rows = []
    if table_event is not None:
        selection = getattr(table_event, "selection", None)
        selected_rows = list(getattr(selection, "rows", []) or [])
    if selected_rows and 0 <= int(selected_rows[0]) < len(view):
        selected_row_id = int(view.iloc[int(selected_rows[0])].name)
        st.session_state.selected_row_id = selected_row_id

    if selected_row_id is not None and selected_row_id in result.index:
        selected = result.loc[selected_row_id]
        reply_column = result_column_name(result, "客户回复")
        final_column = result_column_name(result, "最终回复")
        reply_status_column = result_column_name(result, "回复状态")
        action_column = result_column_name(result, "跟进动作")
        funnel_column = result_column_name(result, FUNNEL_COLUMN)
        editor_key = (
            f"reply_editor_{st.session_state.source_signature}_"
            f"{selected_row_id}_{st.session_state.result_revision}"
        )
        with st.form(editor_key):
            st.markdown("#### 回复编辑")
            if message_column is not None:
                st.text_area(
                    "客户留言",
                    value=_display_value(selected.get(message_column, "")),
                    disabled=True,
                    key=f"reply_message_{editor_key}",
                )
            st.text_area(
                "AI 草稿",
                value=_display_value(selected.get(reply_column, "")),
                disabled=True,
                key=f"reply_draft_{editor_key}",
            )
            current_stage = _display_value(selected.get(funnel_column, ""))
            if current_stage not in FUNNEL_STAGES:
                current_stage = FUNNEL_STAGES[0]
            selected_stage = st.selectbox(
                "线索阶段（仅当前会话）",
                FUNNEL_STAGES,
                index=FUNNEL_STAGES.index(current_stage),
                key=f"funnel_stage_{editor_key}",
                help="阶段不会写回服务器账号；导出结果会带上当前会话的阶段。",
            )
            final_reply = st.text_area(
                "最终回复",
                value=_display_value(selected.get(final_column, "")),
                key=f"reply_final_{editor_key}",
                help="保存并确认后，才会作为可对外发送的最终回复。",
            )
            st.caption(f"当前回复状态：{_display_value(selected.get(reply_status_column, ''))}")
            action_columns = st.columns(3)
            save_clicked = action_columns[0].form_submit_button("保存并确认")
            adopt_clicked = action_columns[1].form_submit_button("采用 AI 草稿并编辑")
            clear_clicked = action_columns[2].form_submit_button("清空最终回复")
        if save_clicked or adopt_clicked or clear_clicked:
            try:
                updated = update_funnel_stage(result, selected_row_id, selected_stage)
                if adopt_clicked:
                    updated = restore_draft(
                        updated,
                        selected_row_id,
                        profile=st.session_state.active_profile,
                    )
                elif clear_clicked:
                    updated = clear_final_reply(
                        updated,
                        selected_row_id,
                        profile=st.session_state.active_profile,
                    )
                else:
                    updated = update_final_reply(
                        updated,
                        selected_row_id,
                        final_reply,
                        profile=st.session_state.active_profile,
                    )
            except ReplyEditError as error:
                st.error(str(error))
            else:
                st.session_state.result_frame = updated
                st.session_state.result_revision += 1
                st.rerun()

        action = _display_value(selected.get(action_column, ""))
        final_text = _display_value(selected.get(final_column, ""))
        final_status = _display_value(selected.get(reply_status_column, ""))
        if final_text and final_status == "已确认":
            st.download_button(
                "下载这条最终回复",
                data=final_text.encode("utf-8"),
                file_name="customer-final-reply.txt",
                mime="text/plain;charset=utf-8",
                on_click="ignore",
                width="stretch",
                key=f"download_final_{editor_key}",
            )
        else:
            st.info("请先保存并确认最终回复，再下载这条客户回复。")
        if action:
            st.write("跟进动作：", action)

    # Resolve every generated column through the collision map. This keeps the
    # notice correct when an uploaded sheet already contains one of the output
    # fields (for example, ``客户回复（AI）``) and keeps the download aligned
    # with the columns shown in the preview.
    generated_columns = {
        result_column_name(result, name) for name in RESULT_COLUMNS
    }
    if any(column.endswith("（AI）") or "（AI" in column for column in generated_columns):
        st.caption("输入表已有同名字段，AI 结果列已自动加上“（AI）”后缀，原始数据保持不变。")

    try:
        output = export_result_workbook(
            result,
            profile=st.session_state.active_profile,
        )
        sendable_output = export_sendable_workbook(
            result,
            profile=st.session_state.active_profile,
        )
        failed_output = export_xlsx(
            result.loc[review_mask],
            purpose="草稿-仅供复核",
        )
    except SpreadsheetError as error:
        st.error(str(error))
        return
    buttons = st.columns(3)
    buttons[0].download_button(
        "下载全部结果（草稿）",
        data=output,
        file_name="commerce-leads-result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
        width="stretch",
    )
    buttons[1].download_button(
        "下载可发送结果",
        data=sendable_output,
        file_name="commerce-leads-sendable.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
        width="stretch",
    )
    if failed:
        buttons[2].download_button(
            "下载待复核行",
            data=failed_output,
            file_name="commerce-leads-review.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click="ignore",
            width="stretch",
        )


_initialise_state()

api_key_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
real_ai_enabled = api_key_configured and _env_flag("COMMERCE_LEAD_ENABLE_REAL_AI")
session_usage = usage_status(st.session_state.real_ai_rows_used)
if real_ai_enabled and st.session_state.get("processing_mode") == "真实 AI":
    if session_usage.exhausted:
        st.error(session_usage_message(session_usage.used, session_usage.limit))
    elif session_usage.used >= int(session_usage.limit * 0.8):
        st.warning(session_usage_message(session_usage.used, session_usage.limit))
    else:
        st.caption(session_usage_message(session_usage.used, session_usage.limit))
elif real_ai_enabled:
    st.caption("当前为演示规则模式；切换到真实 AI 后会显示本会话处理额度。")
else:
    st.caption(f"当前为演示规则模式，单次最多处理 {MAX_ROWS:,} 行；不会调用外部模型。")

if real_ai_enabled:
    mode_label = "真实 AI 可用"
elif api_key_configured:
    mode_label = "演示模式（真实 AI 未启用）"
else:
    mode_label = "演示模式"
st.markdown(
    f'<div class="hero"><span class="mode-pill">{mode_label}</span>'
    "<h1>电商线索与客服表格自动化</h1>"
    "<p>上传脱敏留言表，自动分类、生成回复草稿和跟进动作，再按线索阶段下载可审核结果。</p></div>",
    unsafe_allow_html=True,
)
st.caption("当前版本无需登录，不会长期保存上传文件；请仅上传已脱敏的数据。启用真实 AI 时，留言会发送到你配置的模型服务并可能产生费用。")
if api_key_configured and not real_ai_enabled:
    st.info("检测到模型密钥，但真实 AI 默认关闭。若这是受控的内部环境，请同时设置 COMMERCE_LEAD_ENABLE_REAL_AI=true 后再开放调用。")

top_actions = st.columns([1, 1, 2])
top_actions[0].download_button(
    "下载 Excel 模板",
    data=export_template_xlsx(),
    file_name="commerce-leads-template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    on_click="ignore",
    width="stretch",
)
if top_actions[1].button("载入示例数据", width="stretch"):
    _load_demo()
    st.rerun()
real_ai_upload_blocked = (
    st.session_state.get("processing_mode") == "真实 AI" and session_usage.exhausted
)
uploaded = top_actions[2].file_uploader(
    "上传 Excel / CSV",
    type=["xlsx", "csv"],
    label_visibility="collapsed",
    key=f"source_upload_{st.session_state.upload_widget_version}",
    disabled=real_ai_upload_blocked,
)
if real_ai_upload_blocked:
    st.caption("真实 AI 会话额度已用完，上传入口已暂停；关闭当前页面重新打开即可开始新批次。")
if uploaded is not None:
    try:
        _load_source(uploaded.getvalue(), uploaded.name)
    except SpreadsheetError as error:
        st.error(str(error))

if st.session_state.source_frame is None:
    st.info("还没有文件。你可以载入示例数据，或上传一份脱敏后的 xlsx/csv。")
    st.caption("文件只在本次处理过程中使用，不会被长期保存。")
    _render_footer()
    st.stop()

frame = st.session_state.source_frame
if st.session_state.get("detected_text_column") is None:
    st.session_state.detected_text_column = detect_message_column(frame)
st.divider()
st.subheader("1. 选择处理方式")
st.caption(f"{st.session_state.source_name} · {len(frame):,} 行 · {len(frame.columns)} 列")
preview_columns = list(frame.columns)
detected_column = st.session_state.get("detected_text_column")
default_column_index = (
    preview_columns.index(detected_column)
    if detected_column in preview_columns
    else 0
)
column_choice = st.selectbox(
    "哪一列是客户留言？",
    preview_columns,
    index=default_column_index,
    key="processing_text_column",
)
if detected_column in preview_columns:
    st.caption(f"已自动识别留言列：{detected_column}；如不准确可手动切换。")
else:
    st.warning("暂未识别出留言列，请手动选择后再处理。")
mode_options = ["演示规则"] + (["真实 AI"] if real_ai_enabled else [])
mode = st.radio("处理模式", mode_options, horizontal=True, key="processing_mode")
if mode == "演示规则":
    st.caption(f"演示模式完全离线，最多处理 {MAX_ROWS:,} 行；结果会标注为规则演示。")
else:
    st.caption("真实 AI 会把留言发送到你配置的模型服务，请先确认数据合规。")

_render_reply_profile_form()

result_exists = st.session_state.result_frame is not None
profile_changed = (
    result_exists
    and st.session_state.result_profile_signature
    != st.session_state.active_profile_signature
)
if profile_changed:
    st.warning("当前结果基于上一版设置。请显式重新生成后再使用新的回复设置。")
    regenerate_columns = st.columns(2)
    if regenerate_columns[0].button(
        "按新设置重新生成",
        key=f"regenerate_profile_{st.session_state.result_revision}",
        width="stretch",
    ):
        _run_processing()
        st.rerun()
    with regenerate_columns[1]:
        overwrite_ack = st.checkbox(
            "我确认覆盖已确认回复",
            key=f"overwrite_ack_{st.session_state.result_revision}",
        )
        if st.button(
            "全部覆盖并重新生成",
            key=f"overwrite_profile_{st.session_state.result_revision}",
            disabled=not overwrite_ack,
            width="stretch",
        ):
            _run_processing(overwrite_confirmed=True)
            st.rerun()

if st.button("开始处理", type="primary", width="stretch"):
    _run_processing()

if st.session_state.result_frame is None:
    st.subheader("2. 先看原始数据")
    st.dataframe(frame.head(8), width="stretch", hide_index=True)
else:
    _render_results()
    _render_footer()
