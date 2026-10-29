from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_starts_in_offline_demo_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("COMMERCE_LEAD_ENABLE_REAL_AI", raising=False)

    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run()

    assert not app.exception
    assert any(button.label == "载入示例数据" for button in app.button)
