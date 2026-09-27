"""Small, testable helpers for the real-AI usage guardrails."""

from __future__ import annotations

from dataclasses import dataclass


MAX_REAL_AI_ROWS_PER_FILE = 200
MAX_REAL_AI_ROWS_PER_SESSION = 200


@dataclass(frozen=True)
class UsageStatus:
    """Clamped usage state shown to the user."""

    used: int
    limit: int
    remaining: int
    exhausted: bool


def usage_status(
    used: int | float,
    limit: int = MAX_REAL_AI_ROWS_PER_SESSION,
) -> UsageStatus:
    """Return a safe, integer usage snapshot for UI and guard checks."""

    safe_limit = max(int(limit), 0)
    try:
        safe_used = int(used)
    except (TypeError, ValueError):
        safe_used = 0
    safe_used = min(max(safe_used, 0), safe_limit)
    remaining = max(safe_limit - safe_used, 0)
    return UsageStatus(
        used=safe_used,
        limit=safe_limit,
        remaining=remaining,
        exhausted=safe_used >= safe_limit,
    )


def session_usage_message(
    used: int | float,
    limit: int = MAX_REAL_AI_ROWS_PER_SESSION,
) -> str:
    """Build a non-technical message suitable for the result page."""

    status = usage_status(used, limit)
    if status.exhausted:
        return (
            f"本会话已处理 {status.used} 行，已达上限。"
            "请关闭当前页面重新打开以开始新批次。"
        )
    return (
        f"本会话已处理 {status.used} / {status.limit} 行真实 AI 数据，"
        f"还可处理 {status.remaining} 行。"
    )


def file_usage_message(
    rows: int | float,
    limit: int = MAX_REAL_AI_ROWS_PER_FILE,
) -> str:
    """Build a plain-language message for an overlarge single file."""

    return f"这份文件有 {int(rows):,} 行，真实 AI 单次最多处理 {int(limit):,} 行，请拆分后再试。"


def real_ai_upload_error(
    rows: int | float,
    used: int | float,
    *,
    file_limit: int = MAX_REAL_AI_ROWS_PER_FILE,
    session_limit: int = MAX_REAL_AI_ROWS_PER_SESSION,
) -> str | None:
    """Return a user-facing error before a real-AI file enters the session.

    The same check is used at upload time and immediately before processing so
    a second entry point cannot accidentally bypass either quota.
    """

    try:
        safe_rows = max(int(rows), 0)
    except (TypeError, ValueError):
        safe_rows = 0
    safe_file_limit = max(int(file_limit), 0)
    if safe_rows > safe_file_limit:
        return file_usage_message(safe_rows, safe_file_limit)

    status = usage_status(used, session_limit)
    if status.exhausted:
        return session_usage_message(status.used, status.limit)
    if safe_rows > status.remaining:
        parts = max(
            (safe_rows + status.remaining - 1) // status.remaining,
            2,
        )
        return (
            f"本会话还剩 {status.remaining} 行真实 AI 额度，这份文件有 "
            f"{safe_rows:,} 行。请至少拆成 {parts} 份，每份不超过 "
            f"{status.remaining:,} 行后再试。"
        )
    return None
