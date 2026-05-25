from __future__ import annotations

from event_maintainer.gui.encoding_utils import decode_subprocess_bytes


def test_decode_utf8_cli_output():
    raw = "分类审计\n".encode("utf-8")
    assert decode_subprocess_bytes(raw, "cli") == "分类审计\n"


def test_decode_gbk_powershell_fallback():
    raw = "库状态".encode("gbk")
    text = decode_subprocess_bytes(raw, "powershell")
    assert "库" in text
