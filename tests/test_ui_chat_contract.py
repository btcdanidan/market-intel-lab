from pathlib import Path


def test_ui_uses_chat_stream_and_local_storage_key() -> None:
    ui_path = Path(__file__).resolve().parent.parent / "src" / "app" / "ui" / "app.js"
    source = ui_path.read_text(encoding="utf-8")

    assert "/chat/stream" in source
    assert "market-intel-lab.chat." in source
    assert "/analysis/runs" in source
