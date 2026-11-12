"""2026-11-12: 先頭の項目に日本語の行（「何が変わる：…」）があっても原稿を止めず、メモ（notes）として受け取る"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import muse_format  # noqa: E402

TEXT = """---
title: ゆうパックの基本運賃が10月から上がる
genre: 暮らし
sources:
  - url: https://www.post.japanpost.jp/notification/pressrelease/2026/x.html
    name: 日本郵便
    facts: 基本運賃の改定
notes: 題材の理由
- 何が変わる：基本運賃が上がる
何が変わる: 2026年10月1日から
---
本文です。
"""


def test_japanese_head_lines_go_to_notes():
    data = muse_format.parse(TEXT)
    assert data["title"].startswith("ゆうパック")
    assert len(data["sources"]) == 1
    assert "題材の理由" in data["notes"] and "何が変わる" in data["notes"]
    assert data["body"] == "本文です。"
