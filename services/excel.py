from __future__ import annotations

from io import BytesIO
from numbers import Integral
from pathlib import Path
import re

import pandas as pd

from services.reply_profile import ReplyProfile


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5_000
SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
_PANDAS_DUPLICATE_SUFFIX = re.compile(r"^(.*)\.(\d+)$")

# The template intentionally contains one synthetic row.  ``read_table``
# rejects files without data rows, and an example makes the expected input
# shape clear when a customer opens the downloaded workbook for the first
# time.  The instruction sheet tells users to replace this row before upload.
TEMPLATE_COLUMNS = ["客户留言", "联系方式", "来源", "时间"]
_TEMPLATE_SHEET = "填写模板"
_INSTRUCTION_SHEET = "使用说明"

# Ordered from the most specific/common Chinese names to the English fallbacks.
# Matching is done on a punctuation-insensitive representation, while the
# caller receives the original column label unchanged.
_MESSAGE_COLUMN_ALIASES = (
    "客户留言",
    "客户咨询",
    "留言内容",
    "咨询内容",
    "用户问题",
    "询盘内容",
    "询价内容",
    "留言",
    "咨询",
    "问题",
    "询盘",
    "询价",
    "customer message",
    "customer_message",
    "message content",
    "message",
    "inquiry",
    "question",
    "content",
    "msg",
)
_RESULT_COLUMN_SUFFIX = re.compile(r"（AI(?:\d+)?）$")


class SpreadsheetError(ValueError):
    """A user-facing spreadsheet validation or parsing error."""


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    names: list[str] = []
    used: set[str] = set()
    occurrences: dict[str, int] = {}
    for index, name in enumerate(frame.columns):
        text = "" if name is None else str(name).strip()
        base_name = text or f"列{index + 1}"
        suffix_match = _PANDAS_DUPLICATE_SUFFIX.match(base_name)
        if suffix_match and suffix_match.group(1) in occurrences:
            # pandas disambiguates duplicate CSV headers as ``name.1``/``name.2``.
            # Convert that implementation detail into the same readable suffix
            # used for duplicates found in XLSX or already-normalised frames.
            base_name = suffix_match.group(1)
        occurrences[base_name] = occurrences.get(base_name, 0) + 1
        occurrence = occurrences[base_name]
        candidate = base_name if occurrence == 1 else f"{base_name}（{occurrence}）"
        while candidate in used:
            occurrence += 1
            occurrences[base_name] = occurrence
            candidate = f"{base_name}（{occurrence}）"
        used.add(candidate)
        names.append(candidate)
    frame.columns = names
    return frame


def read_table(
    payload: bytes,
    filename: str,
    *,
    max_bytes: int = MAX_FILE_BYTES,
    max_rows: int = MAX_ROWS,
) -> pd.DataFrame:
    """Read a supported CSV/XLSX payload while keeping user-facing errors clear."""

    if not isinstance(payload, (bytes, bytearray)):
        raise SpreadsheetError("文件内容无效，请重新上传。")
    if len(payload) > max_bytes:
        raise SpreadsheetError("文件超过 10 MB 限制，请拆分后再上传。")

    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise SpreadsheetError("目前只支持 xlsx/csv 文件。")

    try:
        if suffix == ".xlsx":
            frame = pd.read_excel(
                BytesIO(payload),
                sheet_name=0,
                engine="openpyxl",
                nrows=max_rows + 1,
            )
        else:
            frame = None
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
                try:
                    frame = pd.read_csv(
                        BytesIO(payload), encoding=encoding, nrows=max_rows + 1
                    )
                    break
                except (UnicodeDecodeError, LookupError) as error:
                    last_error = error
            if frame is None:
                raise last_error or ValueError("无法识别 CSV 编码")
    except Exception as error:
        if isinstance(error, SpreadsheetError):
            raise
        raise SpreadsheetError("无法读取这个文件，请确认它是有效的 Excel 或 CSV。") from error

    if frame is None or len(frame.columns) == 0:
        raise SpreadsheetError("表格没有可读取的列。")
    if frame.empty:
        raise SpreadsheetError("表格没有数据行，请换一个文件。")
    if len(frame) > max_rows:
        raise SpreadsheetError(f"表格超过 {max_rows:,} 行限制，请拆分后再上传。")
    return _normalise_columns(frame)


def build_template_dataframe() -> pd.DataFrame:
    """Return a standard lead-input table with one clearly synthetic row."""

    return pd.DataFrame(
        [
            {
                "客户留言": "示例：想采购100件，想了解报价和交期（请替换）",
                "联系方式": "示例联系方式（请替换）",
                "来源": "示例",
                "时间": "示例日期（请替换）",
            }
        ],
        columns=TEMPLATE_COLUMNS,
    )


def detect_message_column(
    frame_or_columns: pd.DataFrame | object,
) -> str | None:
    """Find the most likely customer-message column by ordered aliases.

    ``frame_or_columns`` may be a DataFrame or any iterable of column labels.
    Alias comparison ignores surrounding whitespace, case, spaces, underscores,
    hyphens and common punctuation; the original label is returned so callers
    can index the source frame without renaming it.  Metadata columns such as
    ``留言时间`` do not match the exact ``留言`` alias.
    """

    if isinstance(frame_or_columns, pd.DataFrame):
        columns = list(frame_or_columns.columns)
    else:
        try:
            columns = list(frame_or_columns)  # type: ignore[arg-type]
        except TypeError:
            return None

    normalised_columns: dict[str, list[object]] = {}
    for column in columns:
        key = _normalise_alias(column)
        normalised_columns.setdefault(key, []).append(column)

    for alias in _MESSAGE_COLUMN_ALIASES:
        key = _normalise_alias(alias)
        matches = normalised_columns.get(key, [])
        if matches:
            # DataFrame headers are normally strings.  Keep the return contract
            # useful for unusual non-string labels while preserving the exact
            # object present in ``columns``.
            match = matches[0]
            return match if isinstance(match, str) else str(match)
    return None


def export_template_xlsx() -> bytes:
    """Build the downloadable input template and its usage instructions."""

    instructions = pd.DataFrame(
        [
            {"项目": "用途", "说明": "把客户留言整理成 E-commerce Lead Automation 可读取的格式。"},
            {
                "项目": "填写列",
                "说明": "客户留言必填；联系方式、来源、时间用于销售后续跟进。",
            },
            {
                "项目": "示例行",
                "说明": "第一行是合成示例，上传前请删除或替换为真实且已脱敏的数据。",
            },
            {
                "项目": "上传",
                "说明": "保存为 xlsx 后上传；系统会自动识别客户留言列并生成结果。",
            },
        ],
        columns=["项目", "说明"],
    )
    return _export_sheets(
        {
            _TEMPLATE_SHEET: build_template_dataframe(),
            _INSTRUCTION_SHEET: instructions,
        }
    )


def export_result_workbook(
    frame: pd.DataFrame,
    profile: ReplyProfile | None = None,
) -> bytes:
    """Export results into complete, high-intent, review and instruction sheets.

    Filtering uses the generated ``意向等级`` column and the canonical review
    rule (``处理状态`` is not successful OR ``回复状态`` is ``待复核``).  When a
    result column is absent, the corresponding filtered sheet remains a
    header-only copy (high-intent) or conservatively includes all rows (review),
    so the download is still usable for manual inspection.
    """

    _validate_export_frame(frame)
    intent_column = _resolve_result_column(frame, "意向等级")

    # Keep the workbook and the result page on the same canonical review rule:
    # processing failures, replies still awaiting review, or unsafe final text.
    from services.results import review_row_mask

    review_mask = review_row_mask(frame, profile=profile)
    high_positions = [
        position
        for position, value in enumerate(
            frame[intent_column].astype("string").fillna("").tolist()
        )
        if intent_column is not None and value == "高"
    ] if intent_column is not None else []
    review_positions = [
        position for position, value in enumerate(review_mask.tolist()) if value
    ]
    all_positions = list(range(len(frame)))

    instructions = pd.DataFrame(
        [
            {
                "项目": "全部结果",
                "说明": "包含原始数据和每行的 AI 处理结果；导出用途标记为草稿，仅供复核。",
            },
            {"项目": "高意向", "说明": "仅保留意向等级为“高”的客户，便于优先跟进。"},
            {
                "项目": "待复核",
                "说明": "处理状态非成功，或回复状态为“待复核”的行。",
            },
            {
                "项目": "回复字段",
                "说明": "客户回复是 AI 草稿；最终回复只有人工确认且通过导出安全检查后才可进入可发送文件；回复状态包括待确认、已确认、待复核。",
            },
            {
                "项目": "线索阶段",
                "说明": "线索阶段仅保存在当前浏览器会话，可选：新线索、已联系、待补信息、已转交；导出后由人工继续维护。",
            },
            {
                "项目": "安全提示",
                "说明": "请先脱敏并人工复核客户回复，再对外发送；原始行号用于追溯，不会导出 index、row_id 或 API key。",
            },
        ],
        columns=["项目", "说明"],
    )
    return _export_sheets(
        {
            "全部结果": _with_export_metadata(
                frame, all_positions, purpose="草稿-仅供复核"
            ),
            "高意向": _with_export_metadata(
                frame, high_positions, purpose="草稿-仅供复核"
            ),
            "待复核": _with_export_metadata(
                frame, review_positions, purpose="草稿-仅供复核"
            ),
            _INSTRUCTION_SHEET: instructions,
        }
    )


def export_sendable_workbook(
    frame: pd.DataFrame,
    profile: ReplyProfile | None = None,
) -> bytes:
    """Export only rows explicitly confirmed and safe for external sending."""

    _validate_export_frame(frame)
    from services.results import sendable_row_mask

    mask = sendable_row_mask(frame, profile=profile)
    positions = [position for position, value in enumerate(mask.tolist()) if value]
    return _export_sheets(
        {
            "可发送": _with_export_metadata(
                frame, positions, purpose="可发送-已人工确认"
            )
        }
    )


def export_xlsx(
    frame: pd.DataFrame,
    *,
    purpose: str | None = None,
) -> bytes:
    """Serialize a frame as a downloadable xlsx file.

    The generic helper keeps its historical round-trip behaviour by default.
    Callers that need an auditable export watermark can pass ``purpose``;
    result-page downloads use the richer ``export_result_workbook`` and
    ``export_sendable_workbook`` helpers.
    """

    _validate_export_frame(frame)
    output_frame = (
        frame
        if purpose is None
        else _with_export_metadata(frame, list(range(len(frame))), purpose=purpose)
    )
    return _export_sheets(
        {
            "线索处理结果": output_frame
        }
    )


def _with_export_metadata(
    frame: pd.DataFrame,
    positions: list[int],
    *,
    purpose: str,
) -> pd.DataFrame:
    """Add auditable row numbers and an explicit export-purpose watermark."""

    selected = frame.iloc[positions].copy()
    selected.attrs = dict(frame.attrs)
    used = {str(column) for column in selected.columns}
    row_column = _unique_export_column("原始行号", used)
    used.add(row_column)
    purpose_column = _unique_export_column("导出用途", used)
    selected.insert(
        0,
        row_column,
        [_original_row_number(frame, position) for position in positions],
    )
    selected.insert(1, purpose_column, [purpose] * len(positions))
    return selected


def _original_row_number(frame: pd.DataFrame, position: int) -> int:
    """Return a stable one-based source row number for an export position.

    Processed frames use a zero-based RangeIndex.  Filtered views retain that
    index, so consulting the index avoids renumbering a review subset from
    row 5 back to row 1.  For unusual non-integer indexes, positional
    numbering remains the safest deterministic fallback.
    """

    label = frame.index[position]
    if isinstance(label, Integral) and not isinstance(label, bool):
        return int(label) + 1
    return position + 1


def _unique_export_column(base_name: str, used: set[str]) -> str:
    candidate = base_name
    suffix = 2
    while candidate in used:
        candidate = f"{base_name}（{suffix}）"
        suffix += 1
    return candidate


def _validate_export_frame(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame) or len(frame.columns) == 0:
        raise SpreadsheetError("没有可导出的处理结果。")


def _export_sheets(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Serialize multiple frames while applying formula-injection protection."""

    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet_name, frame in sheets.items():
                _validate_export_frame(frame)
                _safe_frame(frame).to_excel(
                    writer, index=False, sheet_name=sheet_name
                )
    except SpreadsheetError:
        raise
    except Exception as error:
        raise SpreadsheetError("导出 Excel 失败，请稍后重试。") from error
    return output.getvalue()


def _safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    # Excel treats values beginning with =, +, -, or @ as formulas. Prefixing
    # those strings with an apostrophe keeps the visible value while preventing
    # links, commands, or other formulas from executing when a client opens the
    # downloaded workbook. Apply this to source and model-generated cells.
    safe_frame = frame.copy()
    # Internal bookkeeping and credentials must never leak into downloads.
    blocked = {
        "index",
        "rowid",
        "row_id",
        "apikey",
        "api_key",
        "api key",
    }
    drop_columns = [
        column
        for column in safe_frame.columns
        if str(column).strip().casefold() in blocked
    ]
    if drop_columns:
        safe_frame = safe_frame.drop(columns=drop_columns)
    for column in safe_frame.columns:
        safe_frame[column] = safe_frame[column].map(_escape_formula)
    safe_frame.columns = [_escape_formula(column) for column in safe_frame.columns]
    return safe_frame


def _normalise_alias(value: object) -> str:
    text = "" if value is None else str(value).strip().casefold()
    return re.sub(r"[\s_\-—–‐·:：/\\()[\]{}（）【】<>《》]+", "", text)


def _resolve_result_column(frame: pd.DataFrame, base_name: str) -> object | None:
    """Resolve a generated result field, including collision-safe suffixes."""

    mapping = frame.attrs.get("commerce_lead_result_columns", {})
    if isinstance(mapping, dict):
        mapped = mapping.get(base_name)
        if mapped in frame.columns:
            return mapped

    # Prefer collision-safe generated names when attrs were lost by a caller's
    # DataFrame operation.  This is the convention used by classifier.py.
    suffix_candidates: list[object] = []
    for column in frame.columns:
        text = str(column)
        if text.startswith(base_name) and _RESULT_COLUMN_SUFFIX.search(text):
            suffix_candidates.append(column)
    if suffix_candidates:
        # Generated columns are appended after source columns.  Preserve that
        # order when metadata is unavailable; lexicographic ordering would
        # incorrectly put ``（AI10）`` before ``（AI2）``.
        return suffix_candidates[-1]
    if base_name in frame.columns:
        return base_name
    return None


def _escape_formula(value: object) -> object:
    """Keep potentially executable Excel formulas as ordinary text."""

    if not isinstance(value, str):
        return value
    if value.lstrip(" \t\r\n\u0000").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def build_demo_dataframe() -> pd.DataFrame:
    """Return safe, synthetic data for a no-key product demonstration."""

    return pd.DataFrame(
        [
            {
                "客户留言": "想采购100件，预算约2万元，多久能发货？",
                "联系方式": "demo-contact-001",
                "来源": "抖音",
            },
            {
                "客户留言": "我在杭州想做代理，怎么合作？",
                "联系方式": "demo-contact-002",
                "来源": "小红书",
            },
            {
                "客户留言": "随便看看，先了解一下",
                "联系方式": "demo-contact-003",
                "来源": "网站",
            },
            {
                "客户留言": "订单号 A1008 的机器坏了，开机后无法使用。",
                "联系方式": "demo-contact-004",
                "来源": "公众号",
            },
        ]
    )
