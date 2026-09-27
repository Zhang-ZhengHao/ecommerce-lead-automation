import pytest

from services.usage import (
    MAX_REAL_AI_ROWS_PER_SESSION,
    real_ai_upload_error,
    session_usage_message,
    usage_status,
)


def test_session_usage_reports_remaining_rows_before_limit():
    status = usage_status(150)

    assert status.used == 150
    assert status.remaining == 50
    assert status.exhausted is False
    assert "150 / 200" in session_usage_message(150)
    assert "还可处理 50 行" in session_usage_message(150)


def test_session_usage_uses_plain_language_when_limit_is_reached():
    status = usage_status(MAX_REAL_AI_ROWS_PER_SESSION)

    assert status.remaining == 0
    assert status.exhausted is True
    assert "本会话已处理 200 行，已达上限" in session_usage_message(
        MAX_REAL_AI_ROWS_PER_SESSION
    )
    assert "关闭当前页面重新打开" in session_usage_message(
        MAX_REAL_AI_ROWS_PER_SESSION
    )


@pytest.mark.parametrize("used", [-10, 250, 999])
def test_session_usage_clamps_counter_to_a_safe_display_range(used):
    status = usage_status(used)

    assert 0 <= status.used <= MAX_REAL_AI_ROWS_PER_SESSION
    assert 0 <= status.remaining <= MAX_REAL_AI_ROWS_PER_SESSION


def test_real_ai_upload_rejects_a_file_larger_than_the_per_file_limit():
    message = real_ai_upload_error(201, used=0)

    assert message is not None
    assert "单次最多处理 200 行" in message


def test_real_ai_upload_rejects_when_the_session_has_no_rows_left():
    message = real_ai_upload_error(1, used=MAX_REAL_AI_ROWS_PER_SESSION)

    assert message == session_usage_message(MAX_REAL_AI_ROWS_PER_SESSION)


def test_real_ai_upload_rejects_when_file_exceeds_remaining_session_quota():
    message = real_ai_upload_error(52, used=149)

    assert message is not None
    assert "本会话还剩 51 行真实 AI 额度" in message
    assert "至少拆成 2 份" in message
    assert "每份不超过 51 行" in message


def test_real_ai_upload_allows_a_file_within_both_limits():
    assert real_ai_upload_error(50, used=150) is None
